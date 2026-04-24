"""Prompt templates for the Arc tutor chat (CB-TUTOR-002 Phase 1).

Exports:
  - build_system_prompt(grade_level) -> str
  - build_user_prompt(message, history, context) -> str
  - SUGGESTION_CHIP_INSTRUCTION

The system prompt instructs Arc to answer directly, use age-appropriate
language, avoid PII leaks, and emit a trailing [[CHIPS: ...]] block of 3-4
suggested follow-up prompts.
"""

from __future__ import annotations

from typing import Any

from app.prompts.grade_tone import get_tone_profile

SUGGESTION_CHIP_INSTRUCTION = (
    'After your answer, output 3-4 suggestion chips on a new line in this exact format: '
    '[[CHIPS: "chip1", "chip2", "chip3"]]. '
    "Chips should be short (under 8 words) follow-up prompts the user could tap next."
)


def build_system_prompt(grade_level: int | None) -> str:
    """Return the Arc tutor system prompt, shaped by grade level."""
    tone = get_tone_profile(grade_level if grade_level is not None else 6)
    g = tone["grade_level"]
    directives = "\n".join(f"- {d}" for d in tone["directives"])

    return (
        "You are Arc, ClassBridge's AI learning companion for K-12 students, "
        "parents, and teachers in Ontario.\n"
        "Answer the user's question directly and concisely. Do NOT ask for "
        "clarification unless the question is genuinely ambiguous (less than 5% "
        "of the time).\n"
        f"Use age-appropriate language for grade {g}. "
        f"Vocabulary: {tone['vocabulary']}. Sentence length: {tone['sentence_length']}.\n"
        f"{directives}\n"
        "Never produce inappropriate, unsafe, or harmful content. Refuse politely "
        "if asked.\n"
        "Do not repeat or leak personally identifiable information (phone numbers, "
        "email addresses, SIN, home addresses) that appears in the conversation "
        "context — treat it as private.\n"
        "Be warm, encouraging, and concise. Avoid corporate hedging like "
        "\"as an AI\" or \"I cannot provide\".\n"
        f"{SUGGESTION_CHIP_INSTRUCTION}"
    )


def _format_history(history: list[dict[str, Any]] | None) -> str:
    if not history:
        return ""
    lines: list[str] = []
    for turn in history:
        role = str(turn.get("role", "")).strip().lower()
        content = str(turn.get("content", "")).strip()
        if not role or not content:
            continue
        label = "User" if role in {"user", "human"} else "Arc"
        lines.append(f"{label}: {content}")
    if not lines:
        return ""
    return "Recent conversation:\n" + "\n".join(lines)


def _format_context(context: dict[str, Any] | None) -> str:
    if not context:
        return ""
    parts: list[str] = []
    for key, value in context.items():
        if value is None or value == "":
            continue
        parts.append(f"- {key}: {value}")
    if not parts:
        return ""
    return "Context:\n" + "\n".join(parts)


def build_user_prompt(
    message: str,
    history: list[dict[str, Any]] | None,
    context: dict[str, Any] | None,
) -> str:
    """Compose the user-turn prompt from message, prior history, and context."""
    sections: list[str] = []
    ctx_block = _format_context(context)
    if ctx_block:
        sections.append(ctx_block)
    hist_block = _format_history(history)
    if hist_block:
        sections.append(hist_block)
    sections.append(f"User's question: {message.strip()}")
    return "\n\n".join(sections)
