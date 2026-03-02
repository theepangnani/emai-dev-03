"""Pydantic schemas for AI Grade Prediction."""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel


class PredictionFactorResponse(BaseModel):
    """A single factor that influenced the grade prediction."""
    factor: str
    impact: str  # "positive" | "negative" | "neutral"
    weight: float


class GradePredictionResponse(BaseModel):
    """Response schema for a single grade prediction record."""
    id: int
    student_id: int
    course_id: Optional[int] = None
    course_name: Optional[str] = None
    predicted_grade: float
    confidence: float
    trend: str  # "improving" | "stable" | "declining"
    factors: List[str] = []
    prediction_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class GradePredictionListResponse(BaseModel):
    """Response schema for listing multiple grade predictions."""
    predictions: List[GradePredictionResponse]
    overall_gpa_prediction: Optional[float] = None
    strongest_course: Optional[str] = None
    at_risk_course: Optional[str] = None
