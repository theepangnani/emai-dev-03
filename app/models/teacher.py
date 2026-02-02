import enum

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class TeacherType(str, enum.Enum):
    SCHOOL_TEACHER = "school_teacher"
    PRIVATE_TUTOR = "private_tutor"


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for shadow teachers
    school_name = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True)
    teacher_type = Column(Enum(TeacherType), nullable=True)

    # Shadow teacher support
    is_shadow = Column(Boolean, default=False)
    google_email = Column(String(255), nullable=True, unique=True)
    full_name = Column(String(255), nullable=True)  # For shadow teachers without a User

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
