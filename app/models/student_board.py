from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class StudentBoard(Base):
    __tablename__ = "student_boards"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, unique=True)
    board_id = Column(Integer, ForeignKey("ontario_boards.id"), nullable=False)
    school_name = Column(String(300), nullable=True)
    linked_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    student = relationship("Student", backref="board_link")
    board = relationship("OntarioBoard", back_populates="student_boards")

    __table_args__ = (
        Index("ix_student_boards_student", "student_id"),
        Index("ix_student_boards_board", "board_id"),
    )
