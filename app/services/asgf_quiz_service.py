"""ASGF Quiz Service — generate slide-anchored quiz questions from ASGF slides."""

import json
from typing import Any

import openai

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_QUIZ_SYSTEM_PROMPT = (
    "You are an expert educational quiz generator. Given a set of slides from a "
    "mini-lesson and the learning plan, generate 3-5 multiple-choice quiz questions "
    "that test understanding of the material.\n\n"
    "Each question MUST reference a specific slide number (0-indexed) and be anchored "
    "to that slide's content.\n\n"
    "Questions should progress through Bloom's taxonomy tiers:\n"
    "  1. First question: 'recall' — basic fact retrieval\n"
    "  2. Second question: 'understand' — demonstrate comprehension\n"
    "  3. Third question: 'apply' — use knowledge in a new context\n"
    "  4. Fourth question (optional): 'analyze' — break down relationships\n"
    "  5. Fifth question (optional): 'evaluate' — make judgments\n\n"
    "For each question provide:\n"
    "  - question_text: clear question string\n"
    "  - options: array of exactly 4 answer choices\n"
    "  - correct_index: 0-based index of the correct option\n"
    "  - bloom_tier: one of 'recall', 'understand', 'apply', 'analyze', 'evaluate'\n"
    "  - slide_reference: 0-based slide number the question relates to\n"
    "  - hint_text: a hint that references the specific slide, e.g. "
    "'Look back at Slide 3 — what happens when...'\n"
    "  - explanation: why the correct answer is right (1-2 sentences)\n\n"
    "Return ONLY a JSON array of question objects. No markdown fences."
)


async def generate_asgf_quiz(
    slides: list[dict[str, Any]],
    learning_cycle_plan: dict[str, Any],
    context_package: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate 3-5 quiz questions anchored to specific slides.

    Returns list of dicts with keys:
        question_text, options, correct_index, bloom_tier,
        slide_reference, hint_text, explanation
    """
    # Build slide summaries for the prompt
    slide_summaries: list[str] = []
    for i, slide in enumerate(slides):
        title = slide.get("title", f"Slide {i + 1}")
        body = slide.get("body", slide.get("content", ""))
        bloom = slide.get("bloom_tier", "")
        summary = f"Slide {i} — \"{title}\" (Bloom: {bloom})\n{body[:500]}"
        slide_summaries.append(summary)

    slides_text = "\n\n".join(slide_summaries)

    # Extract topic info from plan
    topic_info = learning_cycle_plan.get("topic_classification", {})
    core_concepts = learning_cycle_plan.get("core_concepts", [])
    question_asked = context_package.get("question", "")

    user_prompt = (
        f"Original student question: {question_asked}\n\n"
        f"Subject: {topic_info.get('subject', '')}\n"
        f"Grade: {topic_info.get('grade_level', '')}\n"
        f"Core concepts: {', '.join(core_concepts) if core_concepts else 'N/A'}\n\n"
        f"Slides:\n{slides_text}\n\n"
        f"Generate 3-5 quiz questions anchored to these slides. "
        f"Each hint MUST reference the specific slide number (1-indexed for the student, "
        f"e.g. 'Look back at Slide 3')."
    )

    if not settings.openai_api_key:
        logger.warning("OpenAI API key not configured — skipping quiz generation")
        return []

    try:
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key, timeout=15.0)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _QUIZ_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content or ""

        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        questions = json.loads(raw)

        if not isinstance(questions, list):
            logger.warning("ASGF quiz: expected array, got %s", type(questions).__name__)
            return []

        # Validate and normalize each question
        validated: list[dict[str, Any]] = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            options = q.get("options", [])
            if not isinstance(options, list) or len(options) != 4:
                continue
            correct_idx = q.get("correct_index", 0)
            if not isinstance(correct_idx, int) or correct_idx < 0 or correct_idx > 3:
                correct_idx = 0

            slide_ref = q.get("slide_reference", 0)
            if not isinstance(slide_ref, int) or slide_ref < 0:
                slide_ref = 0
            # Clamp to valid slide range
            if slide_ref >= len(slides):
                slide_ref = len(slides) - 1

            validated.append({
                "question_text": str(q.get("question_text", "")),
                "options": [str(o) for o in options],
                "correct_index": correct_idx,
                "bloom_tier": str(q.get("bloom_tier", "recall")),
                "slide_reference": slide_ref,
                "hint_text": str(q.get("hint_text", "")),
                "explanation": str(q.get("explanation", "")),
            })

        logger.info("ASGF quiz generated: %d questions from %d slides", len(validated), len(slides))
        return validated

    except (openai.APIError, openai.APITimeoutError) as e:
        logger.warning("ASGF quiz generation API error: %s", e)
        return []
    except json.JSONDecodeError as e:
        logger.warning("ASGF quiz generation JSON parse error: %s", e)
        return []
    except Exception:
        logger.exception("ASGF quiz generation unexpected error")
        return []
