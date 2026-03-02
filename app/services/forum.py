import math
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.forum import ForumCategory, ForumThread, ForumPost, ForumLike
from app.schemas.forum import (
    ForumCategoryResponse,
    ForumThreadCreate,
    ForumThreadResponse,
    ForumPostCreate,
    ForumPostResponse,
    ForumListResponse,
)

DEFAULT_CATEGORIES = [
    {"name": "General Discussion", "description": "General conversation for parents and families.", "display_order": 1},
    {"name": "Homework Help", "description": "Ask questions and share tips about homework and assignments.", "display_order": 2},
    {"name": "School News", "description": "Latest updates, events, and news from school.", "display_order": 3},
    {"name": "Tutoring & Resources", "description": "Share tutoring recommendations and learning resources.", "display_order": 4},
    {"name": "Off Topic", "description": "Casual conversation not related to school.", "display_order": 5},
]


def _thread_to_response(thread: ForumThread) -> ForumThreadResponse:
    return ForumThreadResponse(
        id=thread.id,
        category_id=thread.category_id,
        author_id=thread.author_id,
        author_name=thread.author.full_name if thread.author else "Unknown",
        title=thread.title,
        body=thread.body,
        is_pinned=thread.is_pinned,
        is_locked=thread.is_locked,
        view_count=thread.view_count,
        reply_count=thread.reply_count,
        is_moderated=thread.is_moderated,
        approved_at=thread.approved_at,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


def _post_to_response(post: ForumPost, include_replies: bool = True) -> ForumPostResponse:
    replies = []
    if include_replies and post.replies:
        replies = [_post_to_response(r, include_replies=False) for r in post.replies]
    return ForumPostResponse(
        id=post.id,
        thread_id=post.thread_id,
        author_id=post.author_id,
        author_name=post.author.full_name if post.author else "Unknown",
        body=post.body,
        like_count=post.like_count,
        is_moderated=post.is_moderated,
        approved_at=post.approved_at,
        parent_post_id=post.parent_post_id,
        created_at=post.created_at,
        updated_at=post.updated_at,
        replies=replies,
    )


class ForumService:
    def __init__(self, db: Session):
        self.db = db

    def list_categories(self, board_id: Optional[int] = None) -> list[ForumCategoryResponse]:
        query = self.db.query(ForumCategory).filter(ForumCategory.is_active == True)
        if board_id is not None:
            query = query.filter(
                or_(ForumCategory.board_id == board_id, ForumCategory.board_id == None)
            )
        categories = query.order_by(ForumCategory.display_order).all()

        results = []
        for cat in categories:
            thread_count = self.db.query(ForumThread).filter(
                ForumThread.category_id == cat.id
            ).count()
            results.append(ForumCategoryResponse(
                id=cat.id,
                name=cat.name,
                description=cat.description,
                board_id=cat.board_id,
                display_order=cat.display_order,
                is_active=cat.is_active,
                thread_count=thread_count,
                created_at=cat.created_at,
            ))
        return results

    def list_threads(self, category_id: int, page: int = 1, limit: int = 20) -> ForumListResponse:
        query = self.db.query(ForumThread).filter(ForumThread.category_id == category_id)
        total = query.count()
        # Pinned threads first, then by created_at descending
        threads = (
            query
            .order_by(ForumThread.is_pinned.desc(), ForumThread.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        pages = math.ceil(total / limit) if total > 0 else 1
        return ForumListResponse(
            items=[_thread_to_response(t) for t in threads],
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )

    def get_thread(self, thread_id: int) -> Optional[tuple[ForumThreadResponse, list[ForumPostResponse]]]:
        thread = self.db.query(ForumThread).filter(ForumThread.id == thread_id).first()
        if not thread:
            return None
        # Increment view count
        thread.view_count = (thread.view_count or 0) + 1
        self.db.commit()
        self.db.refresh(thread)

        # Get top-level posts (no parent) ordered by created_at
        top_posts = (
            self.db.query(ForumPost)
            .filter(ForumPost.thread_id == thread_id, ForumPost.parent_post_id == None)
            .order_by(ForumPost.created_at)
            .all()
        )
        posts = [_post_to_response(p, include_replies=True) for p in top_posts]
        return _thread_to_response(thread), posts

    def create_thread(self, author_id: int, data: ForumThreadCreate) -> ForumThreadResponse:
        now = datetime.now(timezone.utc)
        thread = ForumThread(
            category_id=data.category_id,
            author_id=author_id,
            title=data.title,
            body=data.body,
            is_pinned=False,
            is_locked=False,
            view_count=0,
            reply_count=0,
            is_moderated=False,
            approved_at=now,
        )
        self.db.add(thread)
        self.db.commit()
        self.db.refresh(thread)
        return _thread_to_response(thread)

    def create_post(self, thread_id: int, author_id: int, data: ForumPostCreate) -> ForumPostResponse:
        now = datetime.now(timezone.utc)
        post = ForumPost(
            thread_id=thread_id,
            author_id=author_id,
            body=data.body,
            like_count=0,
            is_moderated=False,
            approved_at=now,
            parent_post_id=data.parent_post_id,
        )
        self.db.add(post)

        # Increment reply_count on parent thread
        thread = self.db.query(ForumThread).filter(ForumThread.id == thread_id).first()
        if thread:
            thread.reply_count = (thread.reply_count or 0) + 1

        self.db.commit()
        self.db.refresh(post)
        return _post_to_response(post, include_replies=False)

    def like_post(self, post_id: int, user_id: int) -> dict:
        """Toggle like on a post. Returns {"liked": bool, "like_count": int}."""
        existing = (
            self.db.query(ForumLike)
            .filter(ForumLike.post_id == post_id, ForumLike.user_id == user_id)
            .first()
        )
        post = self.db.query(ForumPost).filter(ForumPost.id == post_id).first()
        if not post:
            return {"liked": False, "like_count": 0}

        if existing:
            # Unlike
            self.db.delete(existing)
            post.like_count = max(0, (post.like_count or 0) - 1)
            self.db.commit()
            return {"liked": False, "like_count": post.like_count}
        else:
            # Like
            like = ForumLike(post_id=post_id, user_id=user_id)
            self.db.add(like)
            post.like_count = (post.like_count or 0) + 1
            self.db.commit()
            return {"liked": True, "like_count": post.like_count}

    def pin_thread(self, thread_id: int) -> Optional[ForumThreadResponse]:
        thread = self.db.query(ForumThread).filter(ForumThread.id == thread_id).first()
        if not thread:
            return None
        thread.is_pinned = not thread.is_pinned
        self.db.commit()
        self.db.refresh(thread)
        return _thread_to_response(thread)

    def lock_thread(self, thread_id: int) -> Optional[ForumThreadResponse]:
        thread = self.db.query(ForumThread).filter(ForumThread.id == thread_id).first()
        if not thread:
            return None
        thread.is_locked = not thread.is_locked
        self.db.commit()
        self.db.refresh(thread)
        return _thread_to_response(thread)

    def delete_thread(self, thread_id: int) -> bool:
        thread = self.db.query(ForumThread).filter(ForumThread.id == thread_id).first()
        if not thread:
            return False
        self.db.delete(thread)
        self.db.commit()
        return True

    def search_threads(self, q: str, page: int = 1, limit: int = 20) -> ForumListResponse:
        search = f"%{q}%"
        query = self.db.query(ForumThread).filter(
            or_(ForumThread.title.ilike(search), ForumThread.body.ilike(search))
        )
        total = query.count()
        threads = (
            query
            .order_by(ForumThread.is_pinned.desc(), ForumThread.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        pages = math.ceil(total / limit) if total > 0 else 1
        return ForumListResponse(
            items=[_thread_to_response(t) for t in threads],
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )

    def seed_default_categories(self) -> None:
        existing = self.db.query(ForumCategory).count()
        if existing > 0:
            return
        for cat_data in DEFAULT_CATEGORIES:
            cat = ForumCategory(**cat_data)
            self.db.add(cat)
        self.db.commit()


def seed_default_categories(db: Session) -> None:
    """Standalone seeder callable at startup."""
    service = ForumService(db)
    service.seed_default_categories()
