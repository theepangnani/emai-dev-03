import enum

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Table, Index
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
    Column("parent_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("student_id", Integer, ForeignKey("students.id"), nullable=False),
    Column("relationship_type", Enum(RelationshipType), default=RelationshipType.GUARDIAN),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    grade_level = Column(Integer, nullable=True)  # e.g., 5-12
    school_name = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    parents = relationship("User", secondary=parent_students, backref="linked_students")

    __table_args__ = (
        Index("ix_students_user", "user_id"),
    )
