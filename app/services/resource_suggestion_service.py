"""AI-powered study resource suggestions (issue #2489, section 6.57.2).

After a study guide is generated, this service calls gpt-4o-mini to suggest
relevant YouTube videos and web resources for the topic.  Results are stored
as ResourceLink rows with source="ai_suggested" and token usage is tracked
in ai_usage_history.

The public entry point is :func:`suggest_resources_background`, which is
designed to be fired-and-forgotten via ``asyncio.create_task`` so it never
blocks the study guide response.
"""

import asyncio
import json
import logging
import re
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.resource_link import ResourceLink
import app.models.teacher  # noqa: F401 — ensure Teacher model loaded for Course relationship
from app.services.ai_service import generate_content, get_last_ai_usage
from app.services.ai_usage import log_ai_usage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trusted educational domains
# ---------------------------------------------------------------------------
TRUSTED_DOMAINS: set[str] = {
    # YouTube channels are validated by youtube.com domain
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    # Educational websites
    "khanacademy.org",
    "www.khanacademy.org",
    "brilliant.org",
    "www.brilliant.org",
    "mathisfun.com",
    "www.mathsisfun.com",
    "mathsisfun.com",
    "www.mathisfun.com",
    "purplemath.com",
    "www.purplemath.com",
    "desmos.com",
    "www.desmos.com",
    "wolframalpha.com",
    "www.wolframalpha.com",
    "bbc.co.uk",
    "www.bbc.co.uk",
    "nationalgeographic.com",
    "www.nationalgeographic.com",
    "sciencebuddies.org",
    "www.sciencebuddies.org",
    "edx.org",
    "www.edx.org",
    "coursera.org",
    "www.coursera.org",
    "openstax.org",
    "www.openstax.org",
    "mathway.com",
    "www.mathway.com",
    "symbolab.com",
    "www.symbolab.com",
    "geogebra.org",
    "www.geogebra.org",
    "phet.colorado.edu",
    "wikipedia.org",
    "en.wikipedia.org",
    "ted.com",
    "www.ted.com",
    "quizlet.com",
    "www.quizlet.com",
}

# Trusted YouTube channel keywords (used in prompt, not for URL filtering)
TRUSTED_YOUTUBE_CHANNELS: list[str] = [
    "Khan Academy",
    "The Organic Chemistry Tutor",
    "3Blue1Brown",
    "CrashCourse",
    "Professor Leonard",
    "PatrickJMT",
    "Mathologer",
    "Numberphile",
    "Veritasium",
    "MinutePhysics",
    "SmarterEveryDay",
    "Kurzgesagt",
    "TED-Ed",
]


def _is_trusted_domain(url: str) -> bool:
    """Check whether a URL belongs to a trusted educational domain."""
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lower()
        # Direct match
        if hostname in TRUSTED_DOMAINS:
            return True
        # Sub-domain match (e.g. en.khanacademy.org)
        for domain in TRUSTED_DOMAINS:
            if hostname.endswith("." + domain):
                return True
        return False
    except Exception:
        return False


def _extract_youtube_video_id(url: str) -> str | None:
    """Extract YouTube video ID from URL."""
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if hostname == "youtu.be":
            return parsed.path.lstrip("/").split("/")[0] or None
        if hostname in ("youtube.com", "www.youtube.com", "m.youtube.com"):
            if parsed.path in ("/watch", "/watch/"):
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                ids = qs.get("v")
                return ids[0] if ids else None
            for prefix in ("/embed/", "/shorts/"):
                if parsed.path.startswith(prefix):
                    return parsed.path[len(prefix):].split("/")[0].split("?")[0] or None
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# AI prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an educational resource curator for a K-12 platform used in Ontario, Canada. "
    "Your job is to suggest high-quality, free, age-appropriate learning resources."
)


def _build_prompt(topic: str, course_name: str, grade_level: str) -> str:
    channels_list = ", ".join(TRUSTED_YOUTUBE_CHANNELS)
    return f"""Suggest study resources for a student studying the following topic.

**Topic:** {topic}
**Course:** {course_name}
**Grade Level:** {grade_level}
**Curriculum:** Ontario, Canada

Please suggest exactly 5 YouTube videos and 3 web resources that would help a student understand this topic.

For YouTube videos, prefer channels like: {channels_list}.
For web resources, prefer educational sites like Khan Academy, Desmos, GeoGebra, PhET, OpenStax, BBC, etc.

Return your response as a JSON object with this exact structure:
```json
{{
  "youtube": [
    {{
      "title": "Video title",
      "url": "https://www.youtube.com/watch?v=...",
      "description": "Brief description of what the video covers",
      "topic_heading": "Relevant sub-topic heading"
    }}
  ],
  "web": [
    {{
      "title": "Resource title",
      "url": "https://...",
      "description": "Brief description of the resource",
      "topic_heading": "Relevant sub-topic heading"
    }}
  ]
}}
```

IMPORTANT:
- Only suggest real, well-known URLs that are very likely to exist
- All YouTube URLs must use the format https://www.youtube.com/watch?v=VIDEO_ID
- Do not invent or guess URLs — only suggest URLs you are confident exist
- Return ONLY the JSON object, no other text"""


# ---------------------------------------------------------------------------
# URL validation (best-effort HEAD request)
# ---------------------------------------------------------------------------

async def _validate_url(client: httpx.AsyncClient, url: str) -> bool:
    """Best-effort HEAD request to check if a URL is reachable."""
    try:
        resp = await client.head(url, follow_redirects=True, timeout=5.0)
        return resp.status_code < 400
    except Exception:
        return False


async def _validate_urls(urls: list[str]) -> dict[str, bool]:
    """Validate a batch of URLs concurrently. Returns {url: is_valid}."""
    results: dict[str, bool] = {}
    async with httpx.AsyncClient(
        headers={"User-Agent": "ClassBridge/1.0 (Educational Platform)"},
    ) as client:
        tasks = {url: asyncio.create_task(_validate_url(client, url)) for url in urls}
        for url, task in tasks.items():
            try:
                results[url] = await asyncio.wait_for(task, timeout=8.0)
            except (asyncio.TimeoutError, Exception):
                # Best effort — assume valid if we can't check
                results[url] = True
    return results


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _parse_ai_response(raw: str) -> dict:
    """Extract and parse JSON from AI response, handling markdown code fences."""
    # Strip markdown code fences if present
    cleaned = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if match:
        cleaned = match.group(1).strip()
    return json.loads(cleaned)


async def suggest_resources(
    topic: str,
    course_name: str,
    grade_level: str,
    course_content_id: int,
    user_id: int,
    db: Session,
) -> list[ResourceLink]:
    """Generate AI-powered resource suggestions and store them as ResourceLink rows.

    Returns the list of created ResourceLink objects (may be empty on failure).
    """
    if not settings.anthropic_api_key:
        logger.warning("Anthropic API key not configured — skipping resource suggestions")
        return []

    prompt = _build_prompt(topic, course_name, grade_level)

    # Call AI via existing patterns (Anthropic Claude)
    try:
        raw_content, _stop_reason = await generate_content(
            prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            max_tokens=1500,
            temperature=0.3,
        )
    except Exception as e:
        logger.error("Resource suggestion AI call failed: %s: %s", type(e).__name__, e)
        return []

    # Track token usage
    try:
        usage = get_last_ai_usage() or {}
        log_ai_usage(
            user=type("_U", (), {"id": user_id})(),  # lightweight user-like object
            db=db,
            generation_type="resource_suggestion",
            course_material_id=course_content_id,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            estimated_cost_usd=usage.get("estimated_cost_usd"),
            model_name=usage.get("model_name"),
        )
        db.commit()
    except Exception as e:
        logger.warning("Failed to log AI usage for resource suggestions: %s", e)
        try:
            db.rollback()
        except Exception:
            pass

    # Parse response
    try:
        data = _parse_ai_response(raw_content)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Failed to parse resource suggestion JSON: %s", e)
        return []

    youtube_items = data.get("youtube", [])
    web_items = data.get("web", [])
    all_items = []

    for item in youtube_items:
        item["resource_type"] = "youtube"
        item["youtube_video_id"] = _extract_youtube_video_id(item.get("url", ""))
        all_items.append(item)

    for item in web_items:
        item["resource_type"] = "external_link"
        item["youtube_video_id"] = None
        all_items.append(item)

    # Filter through trusted domain whitelist
    filtered = [item for item in all_items if _is_trusted_domain(item.get("url", ""))]
    if not filtered:
        logger.warning("No resource suggestions passed trusted domain filter")
        return []

    # Validate URLs (best effort)
    urls = [item["url"] for item in filtered]
    validity = await _validate_urls(urls)

    # Remove existing AI-suggested links for this content to avoid duplicates (#2667)
    try:
        db.query(ResourceLink).filter(
            ResourceLink.course_content_id == course_content_id,
            ResourceLink.source == "ai_suggested",
        ).delete()
        db.commit()
    except Exception as e:
        logger.warning("Failed to clean old AI suggestions: %s", e)
        try:
            db.rollback()
        except Exception:
            pass

    # Store valid resources
    created: list[ResourceLink] = []
    order = 0
    for item in filtered:
        url = item.get("url", "")
        if not validity.get(url, False):
            logger.debug("Skipping invalid URL: %s", url)
            continue

        resource = ResourceLink(
            course_content_id=course_content_id,
            url=url,
            resource_type=item.get("resource_type", "external_link"),
            title=item.get("title"),
            topic_heading=item.get("topic_heading"),
            description=item.get("description"),
            youtube_video_id=item.get("youtube_video_id"),
            thumbnail_url=(
                f"https://img.youtube.com/vi/{item['youtube_video_id']}/mqdefault.jpg"
                if item.get("youtube_video_id")
                else None
            ),
            display_order=order,
            source="ai_suggested",
        )
        db.add(resource)
        created.append(resource)
        order += 1

    if created:
        try:
            db.commit()
            logger.info(
                "Stored %d AI-suggested resources for course_content_id=%d",
                len(created), course_content_id,
            )
        except Exception as e:
            logger.error("Failed to commit resource suggestions: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
            return []

    return created


async def suggest_resources_background(
    topic: str,
    course_name: str,
    grade_level: str,
    course_content_id: int,
    user_id: int,
    db_factory,
) -> None:
    """Fire-and-forget wrapper that opens its own DB session.

    Use with ``asyncio.create_task(suggest_resources_background(...))``.
    The ``db_factory`` should be a callable that returns a new Session
    (typically ``app.db.database.SessionLocal``).
    """
    db = db_factory()
    try:
        await suggest_resources(
            topic=topic,
            course_name=course_name,
            grade_level=grade_level,
            course_content_id=course_content_id,
            user_id=user_id,
            db=db,
        )
    except Exception as e:
        logger.error("Background resource suggestion failed: %s: %s", type(e).__name__, e)
    finally:
        db.close()
