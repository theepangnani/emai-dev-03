"""Demo generation helpers (CB-DEMO-001 B1, #3603).

Loads demo prompt templates from ``prompts/demo/`` and streams Claude
Haiku completions for the three public demo types.

The helpers intentionally do not touch ``ai_service._last_ai_usage`` or
any user XP/streak/library store — demo generations are transient.
"""
from __future__ import annotations

import math
import re
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Optional

import anthropic

from app.core.logging_config import get_logger
from app.services.ai_service import get_async_anthropic_client

logger = get_logger(__name__)

# Anthropic pricing for claude-haiku-4-5 (USD per 1M tokens):
#   input:  $0.80
#   output: $4.00
# Cents conversion: USD * 100. Divide by 1M to get per-token price.
# Formula: ceil((input * 0.80 + output * 4.00) / 10_000) with a 1-cent
# floor so record_generation never stores 0 for tiny generations.
_INPUT_PRICE_PER_M = 0.80
_OUTPUT_PRICE_PER_M = 4.00

_DEMO_MODEL = "claude-haiku-4-5"

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts" / "demo"

# Demo type → prompt file mapping.
_DEMO_TYPE_FILES: dict[str, str] = {
    "ask": "ask.md",
    "study_guide": "study-guide.md",
    "flash_tutor": "flash-tutor.md",
}

# Token budgets per demo_type (PRD §11.6).
# - ask (300): each turn of the multi-turn chatbox (§6.135.5, #3785) is
#   billed against the rate-limit bucket; tighter per-turn output keeps
#   aggregate cost roughly linear in turns.
# - study_guide (600): dropped from 1200 when the tab switched from
#   "5 key points + 3 Q&A" to a ≤150-word overview paragraph (#3787).
_MAX_TOKENS: dict[str, int] = {
    "ask": 300,
    "study_guide": 600,
    "flash_tutor": 500,
}


def _prompt_path(demo_type: str) -> Path:
    filename = _DEMO_TYPE_FILES.get(demo_type)
    if not filename:
        raise ValueError(f"Unknown demo_type: {demo_type!r}")
    return _PROMPTS_DIR / filename


def load_prompt(demo_type: str) -> tuple[str, str]:
    """Parse ``prompts/demo/{demo_type}.md`` and return ``(system, user_template)``.

    The markdown files have two load-bearing sections:

        ## System prompt
        <plain text up to the next heading>

        ## User prompt template
        ```
        <template with {{placeholders}}>
        ```

    The user template may or may not be fenced; we tolerate either.
    """
    path = _prompt_path(demo_type)
    if not path.exists():
        raise ValueError(f"Demo prompt file not found: {path}")

    content = path.read_text(encoding="utf-8")

    system = _extract_section(content, "System prompt")
    if not system:
        raise ValueError(
            f"Missing 'System prompt' section in {path.name}"
        )

    user_block = _extract_section(content, "User prompt template")
    if not user_block:
        raise ValueError(
            f"Missing 'User prompt template' section in {path.name}"
        )
    user_template = _strip_fences(user_block).strip()

    return system.strip(), user_template


def _extract_section(markdown: str, heading: str) -> str:
    """Extract text between ``## {heading}`` and the next ``## `` heading."""
    # Match the heading at the start of a line, then capture until the next ## heading.
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s+|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(markdown)
    if not match:
        return ""
    return match.group(1)


def _strip_fences(text: str) -> str:
    """Strip a single leading ``` fence + trailing ``` fence if present."""
    stripped = text.strip()
    fence = re.match(r"^```[a-zA-Z0-9_-]*\n(.*?)\n```\s*$", stripped, re.DOTALL)
    if fence:
        return fence.group(1)
    return stripped


def estimate_cost_cents(input_tokens: int, output_tokens: int) -> int:
    """Estimate cost (cents) for a Haiku generation.

    Rounded up via ``ceil`` so we never under-bill the cost cap. Floored
    at 1 cent so tiny generations still register non-zero spend.
    """
    input_tokens = max(0, int(input_tokens))
    output_tokens = max(0, int(output_tokens))
    usd_cents = (
        input_tokens * _INPUT_PRICE_PER_M
        + output_tokens * _OUTPUT_PRICE_PER_M
    ) / 10_000
    return max(1, int(math.ceil(usd_cents)))


def _build_user_prompt(
    demo_type: str,
    user_template: str,
    *,
    source_text: Optional[str],
    question: Optional[str],
) -> str:
    """Substitute user input into the template based on ``demo_type``."""
    if demo_type == "ask":
        value = (question or source_text or "").strip()
        return user_template.replace("{{question}}", value)
    # study_guide, flash_tutor both use {{topic}}
    value = (source_text or question or "").strip()
    return user_template.replace("{{topic}}", value)


async def stream_demo_completion(
    demo_type: str,
    *,
    source_text: Optional[str],
    question: Optional[str],
    history: Optional[list[dict]] = None,
) -> AsyncGenerator[dict, None]:
    """Stream a demo completion from Claude Haiku.

    Yields event dicts:
        {"event": "chunk", "data": "<text>"}
        {"event": "done",  "data": {"input_tokens": int, "output_tokens": int, "latency_ms": int}}
        {"event": "error", "data": "<message>"}

    The caller is responsible for wrapping these into SSE frames and for
    recording the generation (cost, counts) on success.

    For the Ask multi-turn chatbox (§6.135.5, #3785) the caller may pass a
    short ``history`` list (≤2 prior turns, each {role, content}). History
    is prepended to the message array before the current user turn.
    """
    if demo_type not in _DEMO_TYPE_FILES:
        yield {"event": "error", "data": f"Unknown demo_type: {demo_type}"}
        return

    try:
        system_prompt, user_template = load_prompt(demo_type)
    except ValueError as e:
        logger.error("demo_generation: prompt load failed | %s", e)
        yield {"event": "error", "data": "Demo prompt unavailable."}
        return

    user_prompt = _build_user_prompt(
        demo_type, user_template,
        source_text=source_text, question=question,
    )
    max_tokens = _MAX_TOKENS.get(demo_type, 600)

    # Assemble the messages array. Only the Ask tab currently passes
    # history; other demo types ignore it.
    messages: list[dict] = []
    if demo_type == "ask" and history:
        for turn in history:
            role = turn.get("role")
            content = turn.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_prompt})

    start_time = time.time()
    try:
        client = get_async_anthropic_client()
    except ValueError as e:
        logger.error("demo_generation: anthropic client unavailable | %s", e)
        yield {"event": "error", "data": "AI service is temporarily unavailable."}
        return

    try:
        async with client.messages.stream(
            model=_DEMO_MODEL,
            system=system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        ) as stream:
            async for text in stream.text_stream:
                yield {"event": "chunk", "data": text}

            final = await stream.get_final_message()
            input_tok = int(final.usage.input_tokens)
            output_tok = int(final.usage.output_tokens)

        latency_ms = int((time.time() - start_time) * 1000)
        yield {
            "event": "done",
            "data": {
                "input_tokens": input_tok,
                "output_tokens": output_tok,
                "latency_ms": latency_ms,
            },
        }
    except (
        anthropic.APITimeoutError,
        anthropic.APIConnectionError,
        anthropic.APIStatusError,
    ) as e:
        logger.error(
            "demo_generation: Anthropic stream failed | %s: %s",
            type(e).__name__, e,
        )
        yield {"event": "error", "data": "AI generation failed. Please try again."}
    except Exception as e:  # pragma: no cover - defensive
        logger.error(
            "demo_generation: unexpected stream failure | %s: %s",
            type(e).__name__, e,
        )
        yield {"event": "error", "data": "AI generation failed. Please try again."}
