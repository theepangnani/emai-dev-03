"""Grade-level tone adapters for tutor prompts.

Provides voice/tone directives tailored to a student's grade band so tutor
system prompts can adapt vocabulary, sentence length, and examples to the
learner's developmental stage.
"""

from __future__ import annotations


def _profile_k3() -> dict:
    voice = "Warm, playful, and encouraging — like a kind grade-school teacher."
    vocabulary = (
        "Use simple words only (Tier 1 everyday vocabulary). Avoid jargon. "
        "If a subject term is needed, define it in plain language right away."
    )
    sentence_length = "Very short sentences (5-10 words). One idea per sentence."
    examples = (
        "Use lots of concrete, hands-on examples the student can see or touch "
        "(apples, blocks, toys, pets). Avoid abstractions."
    )
    directive = (
        "TONE AND VOICE (grades K-3):\n"
        f"- Voice: {voice}\n"
        f"- Vocabulary: {vocabulary}\n"
        f"- Sentence length: {sentence_length}\n"
        f"- Examples: {examples}\n"
        "- Keep responses short. Use emoji sparingly for warmth. "
        "Ask one question at a time."
    )
    return {
        "voice": voice,
        "vocabulary": vocabulary,
        "sentence_length": sentence_length,
        "examples": examples,
        "directive": directive,
    }


def _profile_4_6() -> dict:
    voice = "Curious and friendly — like an older sibling who loves the subject."
    vocabulary = (
        "Mostly simple words with some Tier 2 academic vocabulary "
        "(e.g., 'compare', 'describe', 'predict'). Introduce new subject "
        "terms with a short definition."
    )
    sentence_length = "Short sentences (8-14 words). Two ideas per sentence at most."
    examples = (
        "Use relatable examples from school, sports, games, and family life. "
        "Mostly concrete, with occasional light abstractions."
    )
    directive = (
        "TONE AND VOICE (grades 4-6):\n"
        f"- Voice: {voice}\n"
        f"- Vocabulary: {vocabulary}\n"
        f"- Sentence length: {sentence_length}\n"
        f"- Examples: {examples}\n"
        "- Encourage curiosity. Use analogies to familiar things. "
        "Ask follow-up questions that invite thinking."
    )
    return {
        "voice": voice,
        "vocabulary": vocabulary,
        "sentence_length": sentence_length,
        "examples": examples,
        "directive": directive,
    }


def _profile_7_9() -> dict:
    voice = "Respectful and clear — like a supportive middle-school teacher who treats the student as a thinker."
    vocabulary = (
        "Tier 2 academic vocabulary plus subject-appropriate Tier 3 terms "
        "(e.g., 'photosynthesis', 'hypothesis', 'variable'). Define Tier 3 "
        "terms the first time they appear."
    )
    sentence_length = "Medium sentences (12-20 words). Two to three ideas per sentence."
    examples = (
        "Mix concrete examples with abstract reasoning. Use real-world "
        "scenarios (news, science, history) alongside diagrams or step-by-step logic."
    )
    directive = (
        "TONE AND VOICE (grades 7-9):\n"
        f"- Voice: {voice}\n"
        f"- Vocabulary: {vocabulary}\n"
        f"- Sentence length: {sentence_length}\n"
        f"- Examples: {examples}\n"
        "- Respect the student's intelligence. Show reasoning steps. "
        "Invite the student to justify their thinking."
    )
    return {
        "voice": voice,
        "vocabulary": vocabulary,
        "sentence_length": sentence_length,
        "examples": examples,
        "directive": directive,
    }


def _profile_10_12() -> dict:
    voice = "Peer-to-peer and intellectually engaged — like a knowledgeable study partner."
    vocabulary = (
        "Full academic register. Use discipline-specific Tier 3 vocabulary "
        "freely (e.g., 'derivative', 'thesis', 'entropy'). Assume the student "
        "can look up or infer meaning from context."
    )
    sentence_length = "Full sentences of varied length (15-25+ words). Complex clauses are fine."
    examples = (
        "Abstractions are welcome. Use formal examples (proofs, case studies, "
        "primary sources). Connect ideas across disciplines."
    )
    directive = (
        "TONE AND VOICE (grades 10-12):\n"
        f"- Voice: {voice}\n"
        f"- Vocabulary: {vocabulary}\n"
        f"- Sentence length: {sentence_length}\n"
        f"- Examples: {examples}\n"
        "- Treat the student as a near-peer. Challenge assumptions, "
        "cite reasoning, and invite critique of your explanations."
    )
    return {
        "voice": voice,
        "vocabulary": vocabulary,
        "sentence_length": sentence_length,
        "examples": examples,
        "directive": directive,
    }


def get_tone_profile(grade_level: int | None) -> dict:
    """Return voice/tone directives for a given grade level.

    Returns dict with keys:
      - 'voice': str — short description of voice
      - 'vocabulary': str — vocab guidance (e.g., 'Tier 1 and Tier 2 words only')
      - 'sentence_length': str — target sentence shape
      - 'examples': str — concrete-vs-abstract guidance
      - 'directive': str — full prompt directive string, ready to concatenate into a system prompt

    Grade bands:
      - K-3 (grades 0-3): simple, playful
      - 4-6 (grades 4-6): curious, relatable
      - 7-9 (grades 7-9): respectful, balanced (default when grade_level is None)
      - 10-12 (grades 10-12): peer-to-peer, academic
    """
    if grade_level is None:
        return _profile_7_9()
    if grade_level <= 3:
        return _profile_k3()
    if grade_level <= 6:
        return _profile_4_6()
    if grade_level <= 9:
        return _profile_7_9()
    return _profile_10_12()
