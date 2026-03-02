from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey, JSON, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class CourseCatalogItem(Base):
    __tablename__ = "course_catalog"

    id = Column(Integer, primary_key=True, index=True)
    board_id = Column(Integer, ForeignKey("ontario_boards.id"), nullable=True)   # NULL = universal (all boards)
    course_code = Column(String(20), nullable=False)     # "MCR3U", "ENG4U", "SCI1D"
    course_name = Column(String(300), nullable=False)    # "Functions, Grade 11, University"
    subject_area = Column(String(100), nullable=False)   # "Mathematics", "English", "Science"
    grade_level = Column(Integer, nullable=False)         # 9, 10, 11, or 12
    pathway = Column(String(10), nullable=False)          # "U", "C", "M", "E", "O"
    credit_value = Column(Float, default=1.0, nullable=False)
    is_compulsory = Column(Boolean, default=False, nullable=False)  # Part of OSSD compulsory requirements
    compulsory_category = Column(String(100), nullable=True)        # "English", "Math", "Science", etc.
    prerequisite_codes = Column(JSON, nullable=True)                # ["MCR3U"] — list of course codes
    description = Column(Text, nullable=True)

    # Specialized programs
    is_ib = Column(Boolean, default=False, nullable=False)    # International Baccalaureate
    is_ap = Column(Boolean, default=False, nullable=False)    # Advanced Placement
    is_shsm = Column(Boolean, default=False, nullable=False)  # Specialist High Skills Major

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    board = relationship("OntarioBoard", back_populates="courses")

    __table_args__ = (
        Index("ix_catalog_grade_subject", "grade_level", "subject_area"),
        UniqueConstraint("course_code", "board_id", name="uq_course_code_board"),
    )
