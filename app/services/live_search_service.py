"""YouTube Data API v3 integration for live resource search (§6.57.3).

Provides topic-based YouTube video search with per-user rate limiting
and in-memory result caching (24-hour TTL).
"""

import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class YouTubeSearchResult(BaseModel):
    """A single YouTube search result."""
    title: str
    description: str
    video_id: str
    thumbnail_url: str
    channel_title: str


# ---------------------------------------------------------------------------
# Rate limiting — 10 searches per user per hour (in-memory)
# ---------------------------------------------------------------------------

_rate_limit_store: dict[int, list[float]] = {}
_RATE_LIMIT_MAX = 10
_RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds


def _check_rate_limit(user_id: int) -> bool:
    """Return True if the user is within their rate limit, False otherwise."""
    now = time.time()
    timestamps = _rate_limit_store.get(user_id, [])
    # Remove entries older than the window
    timestamps = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]
    _rate_limit_store[user_id] = timestamps
    return len(timestamps) < _RATE_LIMIT_MAX


def _record_search(user_id: int) -> None:
    """Record a search for the user."""
    _rate_limit_store.setdefault(user_id, []).append(time.time())


# ---------------------------------------------------------------------------
# Result caching — 24 hours per (topic + grade) key
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[list[YouTubeSearchResult], float]] = {}
_CACHE_TTL = 86400  # 24 hours in seconds


def _cache_key(topic: str, grade_level: str) -> str:
    return f"{topic.lower().strip()}|{grade_level.lower().strip()}"


def _get_cached(key: str) -> list[YouTubeSearchResult] | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    results, ts = entry
    if time.time() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return results


def _set_cache(key: str, results: list[YouTubeSearchResult]) -> None:
    _cache[key] = (results, time.time())
    # Prune if cache grows too large
    if len(_cache) > 5000:
        now = time.time()
        expired = [k for k, (_, ts) in _cache.items() if now - ts > _CACHE_TTL]
        for k in expired:
            del _cache[k]


# ---------------------------------------------------------------------------
# YouTube API search
# ---------------------------------------------------------------------------


def _build_query(topic: str, course_name: str, grade_level: str) -> str:
    """Build a search query from topic, course name, and grade level."""
    parts = [topic]
    if course_name:
        parts.append(course_name)
    if grade_level:
        parts.append(grade_level)
    parts.append("Ontario curriculum")
    return " ".join(parts)


def search_youtube(
    query: str,
    max_results: int = 5,
) -> list[YouTubeSearchResult]:
    """Call YouTube Data API v3 search.list and return structured results.

    Args:
        query: The search query string (pre-built).
        max_results: Maximum number of results to return (1-10).

    Returns:
        List of YouTubeSearchResult objects.

    Raises:
        RuntimeError: If the API key is not configured.
        httpx.HTTPStatusError: On API errors.
    """
    api_key = settings.youtube_api_key
    if not api_key:
        raise RuntimeError("YouTube API key is not configured")

    params: dict[str, Any] = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoEmbeddable": "true",
        "relevanceLanguage": "en",
        "maxResults": min(max_results, 10),
        "key": api_key,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(YOUTUBE_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code == 403:
            logger.error("YouTube API quota exhausted or forbidden: %s", exc.response.text)
            raise RuntimeError("YouTube API quota exhausted") from exc
        if status_code == 400:
            logger.error("YouTube API bad request (invalid key?): %s", exc.response.text)
            raise RuntimeError("YouTube API request failed — check API key") from exc
        logger.error("YouTube API error %d: %s", status_code, exc.response.text)
        raise
    except httpx.ConnectError as exc:
        logger.error("YouTube API network failure: %s", exc)
        raise RuntimeError("Unable to reach YouTube API") from exc
    except httpx.TimeoutException as exc:
        logger.error("YouTube API timeout: %s", exc)
        raise RuntimeError("YouTube API request timed out") from exc

    results: list[YouTubeSearchResult] = []
    for item in data.get("items", []):
        snippet = item.get("snippet", {})
        video_id = item.get("id", {}).get("videoId")
        if not video_id:
            continue
        thumbnails = snippet.get("thumbnails", {})
        thumb = thumbnails.get("medium", thumbnails.get("default", {}))
        results.append(
            YouTubeSearchResult(
                title=snippet.get("title", ""),
                description=snippet.get("description", ""),
                video_id=video_id,
                thumbnail_url=thumb.get("url", ""),
                channel_title=snippet.get("channelTitle", ""),
            )
        )

    return results


# ---------------------------------------------------------------------------
# Public API — orchestrates rate limiting, caching, and search
# ---------------------------------------------------------------------------


def search_youtube_for_topic(
    user_id: int,
    topic: str,
    course_name: str,
    grade_level: str,
    max_results: int = 5,
) -> list[YouTubeSearchResult]:
    """Search YouTube for educational resources with rate limiting and caching.

    Args:
        user_id: The authenticated user's ID (for rate limiting).
        topic: The topic to search for.
        course_name: Course name for context.
        grade_level: Grade level for context.
        max_results: Max results to return.

    Returns:
        List of YouTubeSearchResult objects.

    Raises:
        RuntimeError: If rate limited, API key missing, or API error.
    """
    if not settings.youtube_api_key:
        raise RuntimeError("YouTube search is not available")

    if not _check_rate_limit(user_id):
        raise RuntimeError("Rate limit exceeded — max 10 searches per hour")

    # Check cache
    key = _cache_key(topic, grade_level)
    cached = _get_cached(key)
    if cached is not None:
        return cached[:max_results]

    # Build query and search
    query = _build_query(topic, course_name, grade_level)
    results = search_youtube(query, max_results=max_results)

    # Record the search (even if results are empty)
    _record_search(user_id)

    # Cache the results
    _set_cache(key, results)

    return results
