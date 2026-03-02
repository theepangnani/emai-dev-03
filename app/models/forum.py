from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ForumCategory(Base):
    __tablename__ = "forum_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    board_id = Column(Integer, nullable=True)  # nullable = all boards
    display_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    threads = relationship("ForumThread", back_populates="category", cascade="all, delete-orphan")


class ForumThread(Base):
    __tablename__ = "forum_threads"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("forum_categories.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    is_locked = Column(Boolean, default=False, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)
    reply_count = Column(Integer, default=0, nullable=False)
    is_moderated = Column(Boolean, default=False, nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    category = relationship("ForumCategory", back_populates="threads")
    author = relationship("User", foreign_keys=[author_id])
    # All posts in this thread (service filters by parent_post_id separately)
    all_posts = relationship(
        "ForumPost",
        foreign_keys="ForumPost.thread_id",
        primaryjoin="ForumPost.thread_id == ForumThread.id",
        cascade="all, delete-orphan",
    )


class ForumPost(Base):
    __tablename__ = "forum_posts"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("forum_threads.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    like_count = Column(Integer, default=0, nullable=False)
    is_moderated = Column(Boolean, default=False, nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    parent_post_id = Column(Integer, ForeignKey("forum_posts.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    author = relationship("User", foreign_keys=[author_id])
    # Nested replies (1 level)
    replies = relationship(
        "ForumPost",
        foreign_keys="ForumPost.parent_post_id",
        primaryjoin="ForumPost.parent_post_id == ForumPost.id",
    )
    likes = relationship("ForumLike", back_populates="post", cascade="all, delete-orphan")


class ForumLike(Base):
    __tablename__ = "forum_likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("forum_posts.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    post = relationship("ForumPost", back_populates="likes")
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_forum_like_user_post"),
    )
