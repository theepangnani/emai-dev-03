from sqlalchemy import Column, Integer, String, Date, ForeignKey, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class TeacherThanks(Base):
    __tablename__ = "teacher_thanks"

    id = Column(Integer, primary_key=True, index=True)
    from_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    message = Column(String(100), nullable=True)
    thanks_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    from_user = relationship("User", foreign_keys=[from_user_id])
    teacher = relationship("Teacher", foreign_keys=[teacher_id])
    course = relationship("Course", foreign_keys=[course_id])

    __table_args__ = (
        Index("ix_teacher_thanks_teacher", "teacher_id"),
        Index("ix_teacher_thanks_from_user", "from_user_id"),
        Index("ix_teacher_thanks_daily", "from_user_id", "teacher_id", "created_at"),
        UniqueConstraint("from_user_id", "teacher_id", "thanks_date", name="uq_teacher_thanks_daily"),
    )
