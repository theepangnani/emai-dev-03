import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, can_access_course
from app.core.config import settings
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.course_content import CourseContent
from app.models.resource_link import ResourceLink
from app.models.user import User, UserRole
from app.schemas.resource_link import (
    ResourceLinkCreate,
    ResourceLinkUpdate,
    ResourceLinkResponse,
    ResourceLinkGroupResponse,
)
from app.services.link_extraction_service import (
    extract_and_enrich_links,
    extract_youtube_video_id,
    enrich_youtube_metadata,
)
from app.services.live_search_service import (
    search_youtube_for_topic,
    YouTubeSearchResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Resource Links"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_content_or_404(db: Session, content_id: int) -> CourseContent:
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    return content


def _check_course_access(db: Session, user: User, content: CourseContent) -> None:
    if not can_access_course(db, user, content.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")


def _can_modify_link(user: User, content: CourseContent) -> bool:
    """Only the content creator or an admin can modify resource links."""
    if user.has_role(UserRole.ADMIN):
        return True
    if content.created_by_user_id == user.id:
        return True
    return False


def _get_link_or_404(db: Session, link_id: int) -> ResourceLink:
    link = db.query(ResourceLink).filter(ResourceLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource link not found")
    return link


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/course-contents/{content_id}/links",
    response_model=list[ResourceLinkGroupResponse],
)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_resource_links(
    request: Request,
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all resource links for a course content item, grouped by topic heading."""
    content = _get_content_or_404(db, content_id)
    _check_course_access(db, current_user, content)

    links = (
        db.query(ResourceLink)
        .filter(ResourceLink.course_content_id == content_id)
        .order_by(ResourceLink.display_order)
        .all()
    )

    # Group by topic_heading
    groups: dict[str | None, list[ResourceLink]] = {}
    for link in links:
        groups.setdefault(link.topic_heading, []).append(link)

    result: list[ResourceLinkGroupResponse] = []
    for heading, group_links in groups.items():
        result.append(
            ResourceLinkGroupResponse(
                topic_heading=heading if heading is not None else "Other Resources",
                links=group_links,
            )
        )

    return result


@router.post(
    "/course-contents/{content_id}/links",
    response_model=ResourceLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def create_resource_link(
    request: Request,
    content_id: int,
    data: ResourceLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually add a resource link to a course content item."""
    content = _get_content_or_404(db, content_id)
    _check_course_access(db, current_user, content)

    if not _can_modify_link(current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the content owner or admin can add links")

    # Auto-detect YouTube
    video_id = extract_youtube_video_id(data.url)
    resource_type = "youtube" if video_id else "external_link"
    thumbnail_url = data.thumbnail_url
    title = data.title

    if video_id:
        meta = enrich_youtube_metadata(video_id)
        if not title and meta.get("title"):
            title = meta["title"]
        if not thumbnail_url:
            thumbnail_url = meta.get("thumbnail_url")

    link = ResourceLink(
        course_content_id=content_id,
        url=data.url,
        resource_type=resource_type,
        title=title,
        topic_heading=data.topic_heading,
        description=data.description,
        thumbnail_url=thumbnail_url,
        youtube_video_id=video_id,
        display_order=data.display_order,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.patch(
    "/resource-links/{link_id}",
    response_model=ResourceLinkResponse,
)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_resource_link(
    request: Request,
    link_id: int,
    data: ResourceLinkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit resource link metadata."""
    link = _get_link_or_404(db, link_id)
    content = _get_content_or_404(db, link.course_content_id)
    _check_course_access(db, current_user, content)

    if not _can_modify_link(current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the content owner or admin can edit links")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(link, field, value)

    db.commit()
    db.refresh(link)
    return link


@router.delete(
    "/resource-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_resource_link(
    request: Request,
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a resource link."""
    link = _get_link_or_404(db, link_id)
    content = _get_content_or_404(db, link.course_content_id)
    _check_course_access(db, current_user, content)

    if not _can_modify_link(current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the content owner or admin can delete links")

    db.delete(link)
    db.commit()


@router.patch(
    "/resource-links/{link_id}/pin",
    response_model=ResourceLinkResponse,
)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def pin_resource_link(
    request: Request,
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pin an AI-suggested or API-searched link as a permanent teacher-shared resource."""
    link = _get_link_or_404(db, link_id)
    content = _get_content_or_404(db, link.course_content_id)
    _check_course_access(db, current_user, content)

    link.source = "teacher_shared"
    db.commit()
    db.refresh(link)
    return link


@router.delete(
    "/resource-links/{link_id}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def dismiss_resource_link(
    request: Request,
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dismiss (delete) an AI-suggested or API-searched link."""
    link = _get_link_or_404(db, link_id)
    content = _get_content_or_404(db, link.course_content_id)
    _check_course_access(db, current_user, content)

    db.delete(link)
    db.commit()


@router.post(
    "/course-contents/{content_id}/extract-links",
    response_model=list[ResourceLinkResponse],
)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def extract_resource_links(
    request: Request,
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run link extraction on a course content item's text, replacing existing links."""
    content = _get_content_or_404(db, content_id)
    _check_course_access(db, current_user, content)

    if not _can_modify_link(current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the content owner or admin can extract links")

    text = content.text_content or ""
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course content has no text to extract links from",
        )

    extracted = extract_and_enrich_links(text)

    # Delete existing links for this content
    db.query(ResourceLink).filter(ResourceLink.course_content_id == content_id).delete()

    # Create new links
    new_links: list[ResourceLink] = []
    for item in extracted:
        link = ResourceLink(
            course_content_id=content_id,
            url=item.url,
            resource_type=item.resource_type,
            title=item.title,
            topic_heading=item.topic_heading,
            description=item.description,
            thumbnail_url=item.thumbnail_url,
            youtube_video_id=item.youtube_video_id,
            display_order=item.display_order,
        )
        db.add(link)
        new_links.append(link)

    db.commit()
    for link in new_links:
        db.refresh(link)

    return new_links


# ---------------------------------------------------------------------------
# YouTube live search (§6.57.3)
# ---------------------------------------------------------------------------


class SearchResourcesRequest(BaseModel):
    topic: str
    grade_level: str
    course_name: str
    save: bool = False


class SearchResourcesResponse(BaseModel):
    title: str
    description: str
    video_id: str
    thumbnail_url: str
    channel_title: str


@router.get("/features/youtube-search")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def youtube_search_feature_flag(
    request: Request,
    _current_user: User = Depends(get_current_user),
):
    """Check whether YouTube search is available (API key configured)."""
    return {"available": bool(settings.youtube_api_key)}


@router.post(
    "/course-contents/{content_id}/search-resources",
    response_model=list[SearchResourcesResponse],
)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def search_resources(
    request: Request,
    content_id: int,
    data: SearchResourcesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search YouTube for educational resources related to a course content topic."""
    content = _get_content_or_404(db, content_id)
    _check_course_access(db, current_user, content)

    try:
        results = search_youtube_for_topic(
            user_id=current_user.id,
            topic=data.topic,
            course_name=data.course_name,
            grade_level=data.grade_level,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
            if "Rate limit" in str(exc)
            else status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    # Optionally save results as resource_links
    if data.save:
        for r in results:
            link = ResourceLink(
                course_content_id=content_id,
                url=f"https://www.youtube.com/watch?v={r.video_id}",
                resource_type="youtube",
                title=r.title,
                description=r.description,
                thumbnail_url=r.thumbnail_url,
                youtube_video_id=r.video_id,
                source="api_search",
            )
            db.add(link)
        db.commit()

    return [
        SearchResourcesResponse(
            title=r.title,
            description=r.description,
            video_id=r.video_id,
            thumbnail_url=r.thumbnail_url,
            channel_title=r.channel_title,
        )
        for r in results
    ]
