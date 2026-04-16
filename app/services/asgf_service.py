"""ASGF (AI Study Guide Factory) service — intent classification & re-explanation."""
import json
from typing import Any

import openai

from app.core.config import settings
from app.core.logging_config import get_logger
from app.schemas.asgf import IntentClassifyResponse
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
