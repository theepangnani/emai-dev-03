"""ASGF (AI Study Guide Factory) service — intent classification."""
import json

import openai

from app.core.config import settings
from app.core.logging_config import get_logger
from app.schemas.asgf import IntentClassifyResponse

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
