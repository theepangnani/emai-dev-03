import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Enum,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class MoodLevel(str, enum.Enum):
    GREAT = "great"
    GOOD = "good"
    OKAY = "okay"
    STRUGGLING = "struggling"
    OVERWHELMED = "overwhelmed"


class EnergyLevel(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class WellnessCheckIn(Base):
    __tablename__ = "wellness_check_ins"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mood = Column(Enum(MoodLevel), nullable=False)
    energy = Column(Enum(EnergyLevel), nullable=False)
    stress_level = Column(Integer, nullable=False)  # 1-5
    sleep_hours = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    is_private = Column(Boolean, default=False, nullable=False)
    check_in_date = Column(Date, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    student = relationship("User", foreign_keys=[student_id])

    __table_args__ = (
        UniqueConstraint("student_id", "check_in_date", name="uq_wellness_student_date"),
        Index("ix_wellness_student_date", "student_id", "check_in_date"),
    )


class WellnessAlert(Base):
    __tablename__ = "wellness_alerts"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    triggered_by = Column(String(255), nullable=False)  # e.g., "3+ struggling/overwhelmed days in 7 days"
    alert_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("User", foreign_keys=[student_id])

    __table_args__ = (
        Index("ix_wellness_alerts_student", "student_id"),
    )
