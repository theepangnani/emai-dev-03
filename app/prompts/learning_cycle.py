"""Prompt builders for the CB-TUTOR-002 short learning-cycle loop.

These builders return prompt STRINGS only. They do not call the LLM — that
is the caller's responsibility. Every prompt uses Arc's voice
(warm, grade-appropriate, no corporate hedging) and, where the response
must be machine-parsed, enforces strict JSON output.
"""

from __future__ import annotations

from typing import List, Optional

ARC_SYSTEM_VOICE = (
    "You are Arc, ClassBridge's AI tutor. "
    "Warm, grade-appropriate, no corporate hedging."
)

JSON_ONLY_SUFFIX = "Respond ONLY with valid JSON, no prose."


def _grade_label(grade: Optional[int | str]) -> str:
    """Return a safe grade label. Defaults to Grade 7 voice when grade is None."""
    if grade is None or grade == "":
        return "Grade 7"
    return f"Grade {grade}"


def build_topic_outline_prompt(
    topic: str,
    subject: str,
    grade: Optional[int | str],
    num_chunks: int = 5,
) -> str:
    """Ask the LLM for an ordered outline of sub-concepts (easier -> harder)."""
    grade_label = _grade_label(grade)
    return (
        f"{ARC_SYSTEM_VOICE}\n\n"
        f"Break down the topic \"{topic}\" from {subject} for a {grade_label} "
        f"student into exactly {num_chunks} ordered sub-concepts. "
        "Order them from easiest to hardest so each chunk builds on the one "
        "before it. Each chunk must be teachable in about 2 minutes.\n\n"
        "Return a JSON array of objects with these fields:\n"
        "- chunk_idx (integer, starting at 1)\n"
        "- title (short, student-friendly)\n"
        "- learning_objective (one sentence starting with a verb)\n\n"
        f"{JSON_ONLY_SUFFIX}"
    )


def build_chunk_teach_prompt(
    topic: str,
    subject: str,
    grade: Optional[int | str],
    chunk_title: str,
    objective: str,
    prior_chunks_titles: List[str],
) -> str:
    """Ask the LLM for a ~150-word teach block in markdown that introduces the chunk."""
    grade_label = _grade_label(grade)
    if prior_chunks_titles:
        continuity = (
            "Prior chunks the student has already seen (reference them briefly "
            "for continuity): "
            + ", ".join(f'"{t}"' for t in prior_chunks_titles)
            + "."
        )
    else:
        continuity = "This is the first chunk — no prior chunks to reference."
    return (
        f"{ARC_SYSTEM_VOICE}\n\n"
        f"Teach the concept \"{chunk_title}\" as part of the topic \"{topic}\" "
        f"in {subject} to a {grade_label} student. "
        f"Learning objective: {objective}.\n\n"
        f"{continuity}\n\n"
        "Write a teach block of approximately 150 words in markdown. "
        "Use short paragraphs, one concrete example, and end with a single "
        "sentence that sets up a quick check for understanding. "
        "Do not include headings above H2. Do not add a quiz — questions "
        "come in a separate step.\n\n"
        "Respond with the markdown teach block only."
    )


def build_chunk_questions_prompt(
    topic: str,
    chunk_title: str,
    teach_content: str,
    grade: Optional[int | str],
) -> str:
    """Ask the LLM for exactly 3 questions: 1 MCQ, 1 true_false, 1 fill_blank."""
    grade_label = _grade_label(grade)
    return (
        f"{ARC_SYSTEM_VOICE}\n\n"
        f"Write a short check-for-understanding for a {grade_label} student on "
        f"the chunk \"{chunk_title}\" of the topic \"{topic}\".\n\n"
        "Teach content the student just saw:\n"
        "---\n"
        f"{teach_content}\n"
        "---\n\n"
        "Return a JSON array with EXACTLY 3 questions in this order:\n"
        "1. One multiple-choice question (format=\"mcq\") with exactly 4 options.\n"
        "2. One true/false question (format=\"true_false\").\n"
        "3. One fill-in-the-blank question (format=\"fill_blank\").\n\n"
        "Each question object must contain:\n"
        "- prompt (string)\n"
        "- format (one of: \"mcq\", \"true_false\", \"fill_blank\")\n"
        "- options (array of 4 strings, ONLY for mcq — omit for other formats)\n"
        "- correct_answer (string; for mcq the exact matching option text; "
        "for true_false \"True\" or \"False\"; for fill_blank the missing word/phrase)\n"
        "- explanation (one-sentence reason the answer is correct)\n\n"
        f"{JSON_ONLY_SUFFIX}"
    )


def build_retry_hint_prompt(
    question: str,
    wrong_answer: str,
    attempt_number: int,
) -> str:
    """Ask for a coaching hint after a wrong answer. MUST NOT reveal the correct answer."""
    return (
        f"{ARC_SYSTEM_VOICE}\n\n"
        f"The student answered a question incorrectly. This is attempt "
        f"#{attempt_number}.\n\n"
        f"Question: {question}\n"
        f"Their answer: {wrong_answer}\n\n"
        "Write a short coaching hint (1-2 sentences) that nudges them toward "
        "the right reasoning. Do NOT state or reveal the correct answer. "
        "Do NOT give away key terms that would be equivalent to revealing it. "
        "Ask one guiding question or point at the concept they should reconsider. "
        "Keep your voice warm and encouraging.\n\n"
        "Respond with the hint text only."
    )


def build_answer_reveal_prompt(
    question: str,
    correct_answer: str,
    user_attempts: List[str],
) -> str:
    """After 3 wrong tries, explain the correct answer and what went wrong."""
    if user_attempts:
        attempts_block = "\n".join(
            f"- Attempt {i + 1}: {ans}" for i, ans in enumerate(user_attempts)
        )
    else:
        attempts_block = "- (no recorded attempts)"
    return (
        f"{ARC_SYSTEM_VOICE}\n\n"
        "The student has used all 3 attempts on this question. "
        "Now reveal the correct answer and walk them through it kindly.\n\n"
        f"Question: {question}\n"
        f"Correct answer: {correct_answer}\n\n"
        "The student's attempts:\n"
        f"{attempts_block}\n\n"
        "Write a short explanation (3-5 sentences) that:\n"
        "1. States the correct answer clearly.\n"
        "2. Explains WHY it is correct in plain language.\n"
        "3. Addresses what each of the student's attempts got wrong (what "
        "they probably mixed up or missed).\n"
        "4. Ends on one encouraging sentence.\n\n"
        "Respond with the explanation text only."
    )
