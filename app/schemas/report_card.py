"""Pydantic schemas for the Report Card feature (#2018)."""
from typing import Optional

from pydantic import BaseModel, Field


class SubjectSummary(BaseModel):
    name: str
    guides: int = 0
    quizzes: int = 0


class LevelReached(BaseModel):
    level: int = 1
    title: str = "Curious Learner"


class BadgeEarned(BaseModel):
    name: str
    date: str = ""


class ReportCardResponse(BaseModel):
    student_name: str
    term: str
    subjects_studied: list[SubjectSummary] = Field(default_factory=list)
    total_uploads: int = 0
    total_guides: int = 0
    total_quizzes: int = 0
    total_xp: int = 0
    level_reached: LevelReached = Field(default_factory=LevelReached)
    badges_earned: list[BadgeEarned] = Field(default_factory=list)
    longest_streak: int = 0
    most_reviewed_topics: list[str] = Field(default_factory=list)
    study_sessions: int = 0
    total_study_minutes: int = 0
