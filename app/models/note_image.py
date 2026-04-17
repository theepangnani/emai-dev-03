from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func

from app.db.database import Base


class NoteImage(Base):
    __tablename__ = "note_images"

    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    gcs_path = Column(String(500), nullable=False)
    media_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
