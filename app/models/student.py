import enum

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Table, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class RelationshipType(str, enum.Enum):
    MOTHER = "mother"
    FATHER = "father"
    GUARDIAN = "guardian"
    OTHER = "other"


parent_students = Table(
    "parent_students",
    Base.metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("parent_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("student_id", Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
    Column("relationship_type", Enum(RelationshipType), default=RelationshipType.GUARDIAN),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("parent_id", "student_id", name="uq_parent_students_pair"),
)


student_teachers = Table(
    "student_teachers",
    Base.metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("student_id", Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
    Column("teacher_user_id", Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    Column("teacher_name", String(255), nullable=True),
    Column("teacher_email", String(255), nullable=True),
    Column("added_by_user_id", Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("student_id", "teacher_email", name="uq_student_teachers_pair"),
)


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    grade_level = Column(Integer, nullable=True)  # e.g., 5-12
    school_name = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    parents = relationship("User", secondary=parent_students, backref="linked_students",
                           passive_deletes=True)

    __table_args__ = (
        Index("ix_students_user", "user_id"),
    )
