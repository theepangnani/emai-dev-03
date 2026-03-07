"""Service for extracting URLs from text and enriching YouTube metadata.

Parses teacher course materials to identify YouTube videos and external links,
extracting topic headings, titles, and descriptions from surrounding text context.
No database dependencies — returns plain Pydantic data objects.
"""

import logging
import re
from urllib.parse import parse_qs, urlparse

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

URL_PATTERN = re.compile(
    r"https?://[^\s<>\"')\]},;]+"
)

YOUTUBE_DOMAINS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


class ExtractedLink(BaseModel):
    """A single link extracted from text with contextual metadata."""

    url: str
    resource_type: str  # "youtube" or "external_link"
    title: str | None = None
    topic_heading: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    youtube_video_id: str | None = None
    display_order: int = 0


# ---------------------------------------------------------------------------
# YouTube helpers
# ---------------------------------------------------------------------------


def extract_youtube_video_id(url: str) -> str | None:
    """Extract video ID from various YouTube URL formats.

    Supported formats:
    - youtube.com/watch?v=VIDEO_ID
    - youtu.be/VIDEO_ID
    - youtube.com/embed/VIDEO_ID
    - youtube.com/shorts/VIDEO_ID

    Returns None if the URL is not a recognised YouTube link.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return None

    hostname = (parsed.hostname or "").lower()
    if hostname not in YOUTUBE_DOMAINS:
        return None

    # youtu.be/VIDEO_ID
    if hostname == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
        return video_id if video_id else None

    # youtube.com/watch?v=VIDEO_ID
    if parsed.path in ("/watch", "/watch/"):
        qs = parse_qs(parsed.query)
        ids = qs.get("v")
        return ids[0] if ids else None

    # youtube.com/embed/VIDEO_ID or youtube.com/shorts/VIDEO_ID
    for prefix in ("/embed/", "/shorts/"):
        if parsed.path.startswith(prefix):
            video_id = parsed.path[len(prefix):].split("/")[0].split("?")[0]
            return video_id if video_id else None

    return None


def enrich_youtube_metadata(video_id: str) -> dict:
    """Fetch title and thumbnail for a YouTube video via oEmbed (no API key).

    Returns dict with keys ``title`` and ``thumbnail_url``.
    On failure returns fallback values (None title, deterministic thumbnail).
    """
    oembed_url = (
        f"https://www.youtube.com/oembed"
        f"?url=https://www.youtube.com/watch?v={video_id}&format=json"
    )
    fallback = {
        "title": None,
        "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
    }
    try:
        resp = httpx.get(oembed_url, timeout=5.0, follow_redirects=True)
        if resp.status_code != 200:
            logger.warning(
                "YouTube oEmbed returned %s for video %s", resp.status_code, video_id
            )
            return fallback
        data = resp.json()
        return {
            "title": data.get("title"),
            "thumbnail_url": data.get("thumbnail_url") or fallback["thumbnail_url"],
        }
    except Exception:
        logger.warning("Failed to fetch YouTube oEmbed for video %s", video_id, exc_info=True)
        return fallback


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(.+):\s*$")
_TITLE_STRIP_CHARS = ":- \t"


def _is_topic_heading(line: str) -> bool:
    """Return True if the line looks like a topic heading (ends with colon, no URL)."""
    return bool(_HEADING_RE.match(line)) and not URL_PATTERN.search(line)


def extract_links(text: str) -> list[ExtractedLink]:
    """Extract all links from *text* with topic headings, titles, and descriptions.

    Processing rules
    ----------------
    * A line ending with ``:`` that contains **no URL** is treated as a topic heading.
    * Text before a URL on the same line becomes the link's ``title``.
    * Non-URL, non-heading lines after a URL line accumulate as ``description``
      for the preceding link.
    * ``display_order`` resets to 0 for each new topic heading.
    """
    lines = text.splitlines()
    links: list[ExtractedLink] = []
    current_heading: str | None = None
    order_in_topic: int = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # --- topic heading ---
        if _is_topic_heading(stripped):
            current_heading = _HEADING_RE.match(stripped).group(1).strip()  # type: ignore[union-attr]
            order_in_topic = 0
            continue

        # --- line with URL(s) ---
        urls_found = URL_PATTERN.findall(stripped)
        if urls_found:
            for url in urls_found:
                video_id = extract_youtube_video_id(url)
                resource_type = "youtube" if video_id else "external_link"

                # Title = text before the first URL on the line
                title: str | None = None
                first_url_idx = stripped.find(url)
                if first_url_idx > 0:
                    raw_title = stripped[:first_url_idx].strip().rstrip(_TITLE_STRIP_CHARS).strip()
                    title = raw_title if raw_title else None

                links.append(
                    ExtractedLink(
                        url=url,
                        resource_type=resource_type,
                        title=title,
                        topic_heading=current_heading,
                        youtube_video_id=video_id,
                        display_order=order_in_topic,
                    )
                )
                order_in_topic += 1
            continue

        # --- description line (no URL, not heading) ---
        if links:
            prev = links[-1]
            existing = prev.description or ""
            prev.description = (existing + "\n" + stripped).strip() if existing else stripped

    return links


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------


def extract_and_enrich_links(text: str) -> list[ExtractedLink]:
    """Extract links and enrich YouTube entries with oEmbed metadata."""
    links = extract_links(text)
    for link in links:
        if link.resource_type == "youtube" and link.youtube_video_id:
            meta = enrich_youtube_metadata(link.youtube_video_id)
            if not link.title and meta.get("title"):
                link.title = meta["title"]
            link.thumbnail_url = meta.get("thumbnail_url")
    return links
