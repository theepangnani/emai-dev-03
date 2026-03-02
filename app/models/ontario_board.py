from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class OntarioBoard(Base):
    __tablename__ = "ontario_boards"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False)       # "TDSB", "PDSB", etc.
    name = Column(String(200), nullable=False)                    # "Toronto District School Board"
    region = Column(String(100), nullable=True)                   # "Toronto", "Peel Region", etc.
    website_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    courses = relationship("CourseCatalogItem", back_populates="board", lazy="dynamic")
    student_boards = relationship("StudentBoard", back_populates="board")
