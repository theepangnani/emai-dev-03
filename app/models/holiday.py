from sqlalchemy import Column, Integer, String, Date, DateTime
from sqlalchemy.sql import func

from app.db.database import Base


class HolidayDate(Base):
    """School holiday dates for streak calendar awareness (#2024)."""
    __tablename__ = "holiday_dates"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    board_name = Column(String(100), nullable=False, default="YRDSB")
    description = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=func.now())
