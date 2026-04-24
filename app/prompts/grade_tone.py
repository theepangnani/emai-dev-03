"""Grade-appropriate tone profiles for Arc tutor prompts.

Maps a K-12 grade level to a tone profile describing vocabulary, sentence
length, and encouragement style. Used to shape system prompts so Arc's
replies match a student's reading age.
"""

from __future__ import annotations

from typing import Any


def _clamp_grade(grade_level: int | None) -> int:
    """Clamp grade_level to the K-12 range (0-12). None defaults to 6."""
    if grade_level is None:
        return 6
    try:
        g = int(grade_level)
    except (TypeError, ValueError):
        return 6
    if g < 0:
        return 0
    if g > 12:
        return 12
    return g


def get_tone_profile(grade_level: int) -> dict[str, Any]:
    """Return an age-appropriate tone profile for the given grade level.

    Returns a dict with:
      - grade_level: int (clamped 0-12)
      - band: 'primary' | 'junior' | 'intermediate' | 'senior'
      - vocabulary: short description of word difficulty
      - sentence_length: target sentence length
      - directives: list of language rules for the system prompt
    """
    g = _clamp_grade(grade_level)

    if g <= 3:
        return {
            "grade_level": g,
            "band": "primary",
            "vocabulary": "very simple, common words only",
            "sentence_length": "short sentences (under 12 words)",
            "directives": [
                "Use very simple, everyday words a young child knows.",
                "Keep sentences short (under 12 words).",
                "Explain one idea at a time.",
                "Use friendly, warm encouragement like 'Great try!'.",
                "Avoid jargon, abbreviations, and abstract concepts.",
            ],
        }
    if g <= 6:
        return {
            "grade_level": g,
            "band": "junior",
            "vocabulary": "everyday vocabulary with occasional new terms explained",
            "sentence_length": "short to medium sentences (under 18 words)",
            "directives": [
                "Use clear, everyday vocabulary suitable for a junior student.",
                "Keep sentences short to medium (under 18 words).",
                "Introduce new terms with a short plain-language explanation.",
                "Stay warm and encouraging without being childish.",
                "Use concrete examples before abstract ideas.",
            ],
        }
    if g <= 8:
        return {
            "grade_level": g,
            "band": "intermediate",
            "vocabulary": "grade-appropriate subject terms, defined on first use",
            "sentence_length": "medium sentences (under 24 words)",
            "directives": [
                "Use grade-appropriate subject vocabulary and define new terms on first use.",
                "Keep sentences medium in length (under 24 words).",
                "Be concise; respect the student's growing independence.",
                "Encourage critical thinking with a brief follow-up prompt when useful.",
                "Avoid condescension; treat the student as a capable learner.",
            ],
        }
    return {
        "grade_level": g,
        "band": "senior",
        "vocabulary": "precise subject vocabulary appropriate for secondary students",
        "sentence_length": "clear sentences, prioritising precision over length",
        "directives": [
            "Use precise, subject-appropriate vocabulary for a secondary student.",
            "Prioritise clarity and precision over simplification.",
            "Be direct and confident; skip filler and corporate hedging.",
            "Link ideas to real-world or exam-style contexts when relevant.",
            "Respect the student's autonomy; avoid over-explaining basics.",
        ],
    }
