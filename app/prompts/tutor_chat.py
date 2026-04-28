"""Prompt templates for the Arc tutor chat (CB-TUTOR-002 Phase 1).

Exports:
  - build_system_prompt(grade_level, mode='quick') -> str
  - build_user_prompt(message, history, context) -> str
  - SUGGESTION_CHIP_INSTRUCTION

The system prompt instructs Arc to answer directly, use age-appropriate
language, avoid PII leaks, and emit a trailing [[CHIPS: ...]] block of 3-4
suggested follow-up prompts.
"""

from __future__ import annotations

from typing import Any, Literal

from app.prompts.grade_tone import get_tone_profile

SUGGESTION_CHIP_INSTRUCTION = (
    'After your answer, output 3-4 suggestion chips on a new line in this exact format: '
    '[[CHIPS: "chip1", "chip2", "chip3"]]. '
    "Each chip MUST be a complete, self-contained prompt that names the topic the user "
    "is currently learning — never bare verbs like \"Practice problems\", \"Examples\", "
    'or \"More\". Use 4-10 words. Bad: "Practice problems". '
    'Good: "Practice problems on the topic above" or "Show worked examples of this concept".'
)

FULL_MODE_STRUCTURE_INSTRUCTION = (
    "The user asked for a full, detailed response, so produce a structured "
    "Markdown artifact (a cheat-sheet style reference they can keep). "
    "Organize the answer with `##` and `###` headings for clear sections. "
    "When you compare methods, options, or trade-offs, present them in a "
    "Markdown table. Put formulas, equations, code, or syntax inside fenced "
    "code blocks. Walk through 1-2 worked examples for each key concept so "
    "the steps are concrete. End with a short `## Summary` section that "
    "recaps the main takeaways in a few bullets. Keep your warm, "
    "encouraging Arc voice throughout — structure should help the learner, "
    "not feel like a textbook."
)

WORKSHEET_MODE_INSTRUCTION = (
    "The user asked for practice problems, so produce a worksheet on the "
    "most recent topic from the conversation. Output a numbered list of "
    "5-10 practice problems (use exactly the count the user asked for if "
    "they specified one) using Markdown numbering (`1.`, `2.`, `3.`, ...). "
    "Order the problems by difficulty progression — easier first, harder "
    "last — so the learner ramps up. After the problem list, render a "
    "clearly-separated section with the heading `## Answer key` followed "
    "by the worked solutions in matching numbered order (`1.`, `2.`, "
    "`3.`, ...) so the answers line up one-to-one with the problems. Keep "
    "the warm, age-appropriate Arc voice throughout."
)


def build_system_prompt(
    grade_level: int | None,
    mode: Literal["quick", "full", "worksheet"] = "quick",
) -> str:
    """Return the Arc tutor system prompt, shaped by grade level and mode."""
    effective_grade = grade_level if grade_level is not None else 7
    tone = get_tone_profile(effective_grade)

    base = (
        "You are Arc, ClassBridge's AI learning companion for K-12 students, "
        "parents, and teachers in Ontario.\n"
        "Answer the user's question directly and concisely. Do NOT ask for "
        "clarification unless the question is genuinely ambiguous (less than 5% "
        "of the time).\n"
        f"Use age-appropriate language for grade {effective_grade}. "
        f"Vocabulary: {tone['vocabulary']}. Sentence length: {tone['sentence_length']}. "
        f"Examples: {tone['examples']}.\n"
        f"{tone['directive']}\n"
        "Never produce inappropriate, unsafe, or harmful content. Refuse politely "
        "if asked.\n"
        "Do not repeat or leak personally identifiable information (phone numbers, "
        "email addresses, SIN, home addresses) that appears in the conversation "
        "context — treat it as private.\n"
        "Be warm, encouraging, and concise. Avoid corporate hedging like "
        "\"as an AI\" or \"I cannot provide\".\n"
        "When the user's reply is a short follow-up like \"examples\", "
        "\"another\", \"more\", \"practice\", or \"try one\", continue on the "
        "same topic as the prior assistant turn — do NOT switch subjects or "
        "list mixed-subject content.\n"
    )

    if mode == "full":
        return f"{base}{FULL_MODE_STRUCTURE_INSTRUCTION}\n{SUGGESTION_CHIP_INSTRUCTION}"
    if mode == "worksheet":
        return f"{base}{WORKSHEET_MODE_INSTRUCTION}\n{SUGGESTION_CHIP_INSTRUCTION}"
    return f"{base}{SUGGESTION_CHIP_INSTRUCTION}"


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
