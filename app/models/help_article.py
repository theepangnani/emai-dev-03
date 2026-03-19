from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, DateTime
from app.db.database import Base


class HelpArticle(Base):
    __tablename__ = "help_articles"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(200), unique=True, nullable=False, index=True)
    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True)
    role = Column(String(100), nullable=True, index=True)  # comma-separated roles or NULL for all
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
