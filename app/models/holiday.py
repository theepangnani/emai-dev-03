from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, Index
from sqlalchemy.sql import func

from app.db.database import Base


class HolidayDate(Base):
    """School holiday dates for streak calendar awareness (#2024)."""
    __tablename__ = "holiday_dates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    date = Column(Date, nullable=False)
    board_code = Column(String(20), nullable=True)  # e.g. "YRDSB", null = all boards
    is_recurring = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_holiday_dates_date", "date"),
        Index("ix_holiday_dates_board_code", "board_code"),
    )
