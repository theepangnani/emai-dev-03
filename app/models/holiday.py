from sqlalchemy import Column, Integer, String, Date, DateTime
from sqlalchemy.sql import func

from app.db.database import Base


class HolidayDate(Base):
    """School holiday dates for streak calendar awareness (#2024)."""
    __tablename__ = "holiday_dates"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    board = Column(String(50), default="YRDSB")
    created_at = Column(DateTime, default=func.now())
