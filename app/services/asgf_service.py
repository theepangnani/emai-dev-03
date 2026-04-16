"""ASGF (AI Study Guide Factory) service — intent classification, plan generation & re-explanation."""
import json
from typing import Any

import openai

from app.core.config import settings
from app.core.logging_config import get_logger
from app.schemas.asgf import (
    ContextPackage,
    IntentClassifyResponse,
    LearningCyclePlan,
    QuizPlanItem,
    SlidePlanItem,
)
from app.services.ai_service import get_async_anthropic_client

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are an educational intent classifier. Given a student or parent question, "
    "identify the most likely subject, grade level, and specific topic. "
    "Return JSON with keys: subject, grade_level, topic, confidence, bloom_tier. "
    "subject: the academic subject (e.g. Math, Science, English, History). "
    "grade_level: estimated grade as a string (e.g. 'Grade 9', 'Grade 12'). "
    "topic: the specific sub-topic (e.g. 'Quadratic Equations', 'Photosynthesis'). "
    "confidence: float 0.0-1.0 indicating how confident you are. "
    "bloom_tier: one of 'remember', 'understand', 'apply', 'analyze', 'evaluate', 'create'. "
    "Return ONLY valid JSON, no markdown."
)


async def classify_intent(question: str) -> IntentClassifyResponse:
    """Classify a student/parent question into subject, grade, and topic."""
    if len(question.strip()) < 15:
        return IntentClassifyResponse()

    try:
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key, timeout=5.0)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            temperature=0.1,
            max_tokens=200,
        )
        content = response.choices[0].message.content or ""
        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        data = json.loads(content)
        return IntentClassifyResponse(
            subject=data.get("subject", ""),
            grade_level=data.get("grade_level", ""),
            topic=data.get("topic", ""),
            confidence=float(data.get("confidence", 0.0)),
            bloom_tier=data.get("bloom_tier", ""),
        )
    except (openai.APIError, openai.APITimeoutError) as e:
        logger.warning("ASGF intent classification API error: %s", e)
        return IntentClassifyResponse()
    except json.JSONDecodeError as e:
        logger.warning("ASGF intent classification JSON parse error: %s", e)
        return IntentClassifyResponse()
    except Exception:
        logger.exception("ASGF intent classification unexpected error")
        return IntentClassifyResponse()


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

_PLAN_SYSTEM_PROMPT = (
    "You are an expert educational curriculum designer. "
    "Given a student's question, extracted document concepts, and context, "
    "generate a Short Learning Cycle Plan — a structured plan for a 10-15 minute "
    "interactive study session.\n\n"
    "Return ONLY valid JSON with these exact keys:\n"
    "- topic_classification: {subject, grade_level, bloom_entry_point}\n"
    "- core_concepts: list of 3-5 key concept strings\n"
    "- prerequisite_check: {known: [...], needs_establishing: [...]}\n"
    "- slide_plan: list of 5-7 objects with {title, brief (2-sentence description), bloom_tier}\n"
    "- direct_answer_outline: {opening, key_points: [...], conclusion}\n"
    "- sample_plan: list of 2-3 objects with {problem, approach, key_insight}\n"
    "- quiz_plan: list of 3-5 objects with {bloom_tier, format, topic, difficulty}\n"
    "- estimated_session_time_min: integer (target 10-15)\n\n"
    "bloom_tier values: remember, understand, apply, analyze, evaluate, create\n"
    "quiz format values: multiple_choice, short_answer, true_false\n"
    "difficulty values: easy, medium, hard\n\n"
    "Return ONLY the JSON object. No markdown fences."
)


async def assemble_context_package(
    question: str,
    ingestion_result: dict,
    student_profile: dict | None = None,
    classroom_context: dict | None = None,
    session_metadata: dict | None = None,
) -> ContextPackage:
    """Assemble the full context package for Claude API.

    Combines the user's question, ingestion pipeline output, student profile,
    classroom context, and session metadata into a single ContextPackage.
    """
    # Run intent classification to get subject/grade/topic/bloom
    intent = await classify_intent(question)

    return ContextPackage(
        question=question,
        subject=intent.subject,
        grade_level=intent.grade_level,
        topic=intent.topic,
        bloom_entry_point=intent.bloom_tier,
        concepts=ingestion_result.get("concepts", []),
        gap_data=ingestion_result.get("gap_data", {}),
        document_metadata=ingestion_result.get("document_metadata", []),
        student_profile=student_profile or {},
        classroom_context=classroom_context or {},
        session_metadata=session_metadata or {},
    )


async def generate_learning_cycle_plan(
    context_package: ContextPackage,
) -> LearningCyclePlan:
    """Generate a Short Learning Cycle Plan using Claude API.

    Returns a structured plan with topic classification, core concepts,
    prerequisite check, slide plan (5-7), direct answer outline,
    sample plan (2-3 worked examples), quiz plan (3-5), and estimated time.
    """
    # Build the user prompt from the context package
    parts: list[str] = [f"Student question: {context_package.question}"]

    if context_package.subject:
        parts.append(f"Subject: {context_package.subject}")
    if context_package.grade_level:
        parts.append(f"Grade level: {context_package.grade_level}")
    if context_package.topic:
        parts.append(f"Topic: {context_package.topic}")
    if context_package.bloom_entry_point:
        parts.append(f"Bloom's entry point: {context_package.bloom_entry_point}")

    # Include student profile if available
    sp = context_package.student_profile
    if sp:
        profile_parts = []
        if sp.get("grade"):
            profile_parts.append(f"Grade: {sp['grade']}")
        if sp.get("board"):
            profile_parts.append(f"Board: {sp['board']}")
        if sp.get("school"):
            profile_parts.append(f"School: {sp['school']}")
        if profile_parts:
            parts.append(f"Student profile: {', '.join(profile_parts)}")

    # Include classroom context if available
    cc = context_package.classroom_context
    if cc:
        cc_parts = []
        if cc.get("course_name"):
            cc_parts.append(f"Course: {cc['course_name']}")
        if cc.get("teacher"):
            cc_parts.append(f"Teacher: {cc['teacher']}")
        if cc_parts:
            parts.append(f"Classroom context: {', '.join(cc_parts)}")

    # Include session metadata
    sm = context_package.session_metadata
    if sm:
        if sm.get("days_to_test"):
            parts.append(f"Days until test: {sm['days_to_test']}")
        if sm.get("role"):
            parts.append(f"Requester role: {sm['role']}")

    # Include extracted concepts (summarised to keep within token budget)
    concepts = context_package.concepts
    if concepts:
        concept_summary = []
        for c in concepts[:10]:  # Limit to top 10 concepts
            name = c.get("concept_name", "")
            relevance = c.get("relevance_score", "")
            difficulty = c.get("difficulty_signal", "")
            if name:
                concept_summary.append(
                    f"- {name} (relevance: {relevance}, difficulty: {difficulty})"
                )
        if concept_summary:
            parts.append(
                "Extracted document concepts:\n" + "\n".join(concept_summary)
            )

    # Include gap data
    gap = context_package.gap_data
    if gap:
        if gap.get("weak_topics"):
            parts.append(f"Weak topics: {', '.join(gap['weak_topics'])}")
        if gap.get("previously_studied"):
            parts.append(
                f"Previously studied: {', '.join(gap['previously_studied'])}"
            )

    user_prompt = "\n\n".join(parts)

    try:
        client = get_async_anthropic_client()
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=_PLAN_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.3,
        )
        raw = response.content[0].text.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]
            raw = raw.strip()

        data = json.loads(raw)

        # Parse slide plan
        slide_plan = []
        for s in data.get("slide_plan", []):
            slide_plan.append(
                SlidePlanItem(
                    title=s.get("title", ""),
                    brief=s.get("brief", ""),
                    bloom_tier=s.get("bloom_tier", ""),
                )
            )

        # Parse quiz plan
        quiz_plan = []
        for q in data.get("quiz_plan", []):
            quiz_plan.append(
                QuizPlanItem(
                    bloom_tier=q.get("bloom_tier", ""),
                    format=q.get("format", "multiple_choice"),
                    topic=q.get("topic", ""),
                    difficulty=q.get("difficulty", "medium"),
                )
            )

        plan = LearningCyclePlan(
            topic_classification=data.get("topic_classification", {}),
            core_concepts=data.get("core_concepts", []),
            prerequisite_check=data.get("prerequisite_check", {}),
            slide_plan=slide_plan,
            direct_answer_outline=data.get("direct_answer_outline", {}),
            sample_plan=data.get("sample_plan", []),
            quiz_plan=quiz_plan,
            estimated_session_time_min=int(
                data.get("estimated_session_time_min", 12)
            ),
        )

        logger.info(
            "ASGF plan generated: topic=%s, slides=%d, quizzes=%d, est_time=%d min",
            plan.topic_classification.get("subject", "unknown"),
            len(plan.slide_plan),
            len(plan.quiz_plan),
            plan.estimated_session_time_min,
        )
        return plan

    except json.JSONDecodeError as e:
        logger.warning("ASGF plan generation JSON parse error: %s", e)
        return LearningCyclePlan()
    except Exception:
        logger.exception("ASGF plan generation unexpected error")
        return LearningCyclePlan()


# --- Re-explanation generation (#3399) ---

_RE_EXPLANATION_SYSTEM = (
    "You are a patient, encouraging tutor. A student just indicated they are "
    "confused about a slide in their study guide. Your job is to re-explain "
    "the SAME concept using:\n"
    "- Simpler vocabulary (aim for 2 grade levels below the original)\n"
    "- A completely different analogy or real-world example\n"
    "- Shorter sentences\n"
    "- One core idea only — do NOT add extra content\n\n"
    "Return ONLY valid JSON with these keys:\n"
    "  title (string): a friendlier, simpler title for the concept\n"
    "  content (string): the re-explanation in Markdown (max ~200 words)\n"
    "  analogy (string): the new analogy you used\n"
    "  key_takeaway (string): one sentence summary\n"
    "No markdown fences around the JSON."
)


async def generate_re_explanation(
    slide_content: dict[str, Any],
    context_package: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Generate a simplified re-explanation slide using Claude API.

    Uses simpler language, different analogy, shorter sentences.
    Returns a slide dict in the same format as regular slides, or None on failure.
    """
    slide_title = slide_content.get("title", "")
    slide_body = slide_content.get("content", "")

    user_prompt = (
        f"The student was confused by this slide:\n\n"
        f"**Title:** {slide_title}\n\n"
        f"**Content:**\n{slide_body}\n\n"
    )
    if context_package:
        question = context_package.get("question", "")
        if question:
            user_prompt += f"**Original question:** {question}\n\n"

    user_prompt += "Please re-explain this concept in a simpler way."

    try:
        client = get_async_anthropic_client()
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=_RE_EXPLANATION_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.7,
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]
            raw = raw.strip()

        data: dict[str, Any] = json.loads(raw)

        return {
            "title": data.get("title", f"Let's try again: {slide_title}"),
            "content": data.get("content", ""),
            "analogy": data.get("analogy", ""),
            "key_takeaway": data.get("key_takeaway", ""),
            "is_re_explanation": True,
            "original_slide_title": slide_title,
        }
    except json.JSONDecodeError as e:
        logger.warning("ASGF re-explanation JSON parse error: %s", e)
        return None
    except Exception:
        logger.exception("ASGF re-explanation generation failed")
        return None
