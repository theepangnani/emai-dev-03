from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Index
from sqlalchemy.sql import func

from app.db.database import Base


class InspirationMessage(Base):
    __tablename__ = "inspiration_messages"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(20), nullable=False)  # parent, teacher, student
    text = Column(Text, nullable=False)
    author = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("ix_inspiration_role_active", "role", "is_active"),
    )
