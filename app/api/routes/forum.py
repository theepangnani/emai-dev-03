from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role, require_feature, get_db
from app.models.user import User, UserRole
from app.schemas.forum import (
    ForumCategoryResponse,
    ForumThreadCreate,
    ForumThreadResponse,
    ForumPostCreate,
    ForumPostResponse,
    ForumListResponse,
)
from app.services.forum import ForumService

router = APIRouter(tags=["forum"])


def _get_service(db: Session = Depends(get_db)) -> ForumService:
    return ForumService(db)


@router.get("/forum/categories", response_model=list[ForumCategoryResponse])
def list_categories(
    _flag=Depends(require_feature("parent_forum")),
    board_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    service: ForumService = Depends(_get_service),
):
    """List all active forum categories, optionally filtered by school board."""
    return service.list_categories(board_id=board_id)


@router.get("/forum/categories/{category_id}/threads", response_model=ForumListResponse)
def list_threads(
    category_id: int,
    _flag=Depends(require_feature("parent_forum")),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: ForumService = Depends(_get_service),
):
    """List threads in a category (pinned first), paginated."""
    return service.list_threads(category_id=category_id, page=page, limit=limit)


@router.post("/forum/threads", response_model=ForumThreadResponse, status_code=status.HTTP_201_CREATED)
def create_thread(
    data: ForumThreadCreate,
    _flag=Depends(require_feature("parent_forum")),
    current_user: User = Depends(require_role(
        UserRole.PARENT, UserRole.TEACHER, UserRole.STUDENT
    )),
    service: ForumService = Depends(_get_service),
):
    """Create a new forum thread. Accessible to parents, teachers, and students."""
    return service.create_thread(author_id=current_user.id, data=data)


@router.get("/forum/threads/{thread_id}")
def get_thread(
    thread_id: int,
    _flag=Depends(require_feature("parent_forum")),
    current_user: User = Depends(get_current_user),
    service: ForumService = Depends(_get_service),
):
    """Get thread detail with all posts (nested replies, view count incremented)."""
    result = service.get_thread(thread_id=thread_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread, posts = result
    return {"thread": thread, "posts": posts}


@router.post("/forum/threads/{thread_id}/posts", response_model=ForumPostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    thread_id: int,
    data: ForumPostCreate,
    _flag=Depends(require_feature("parent_forum")),
    current_user: User = Depends(require_role(
        UserRole.PARENT, UserRole.TEACHER, UserRole.STUDENT
    )),
    service: ForumService = Depends(_get_service),
    db: Session = Depends(get_db),
):
    """Add a reply to a thread. Thread must not be locked."""
    from app.models.forum import ForumThread
    thread = db.query(ForumThread).filter(ForumThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread.is_locked:
        raise HTTPException(status_code=403, detail="Thread is locked")
    return service.create_post(thread_id=thread_id, author_id=current_user.id, data=data)


@router.post("/forum/posts/{post_id}/like")
def like_post(
    post_id: int,
    _flag=Depends(require_feature("parent_forum")),
    current_user: User = Depends(get_current_user),
    service: ForumService = Depends(_get_service),
):
    """Toggle like on a forum post."""
    return service.like_post(post_id=post_id, user_id=current_user.id)


@router.delete("/forum/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(
    thread_id: int,
    _flag=Depends(require_feature("parent_forum")),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    service: ForumService = Depends(_get_service),
):
    """Admin: delete a thread and all its posts."""
    ok = service.delete_thread(thread_id=thread_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found")


@router.patch("/forum/threads/{thread_id}/pin", response_model=ForumThreadResponse)
def pin_thread(
    thread_id: int,
    _flag=Depends(require_feature("parent_forum")),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    service: ForumService = Depends(_get_service),
):
    """Admin: toggle pin/unpin on a thread."""
    result = service.pin_thread(thread_id=thread_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return result


@router.patch("/forum/threads/{thread_id}/lock", response_model=ForumThreadResponse)
def lock_thread(
    thread_id: int,
    _flag=Depends(require_feature("parent_forum")),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    service: ForumService = Depends(_get_service),
):
    """Admin: toggle lock/unlock on a thread."""
    result = service.lock_thread(thread_id=thread_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return result


@router.get("/forum/search", response_model=ForumListResponse)
def search_threads(
    _flag=Depends(require_feature("parent_forum")),
    q: str = Query(..., min_length=1),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: ForumService = Depends(_get_service),
):
    """Full-text search across thread titles and bodies."""
    return service.search_threads(q=q, page=page, limit=limit)
