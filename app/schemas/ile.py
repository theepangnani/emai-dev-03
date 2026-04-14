"""Pydantic schemas for the Interactive Learning Engine (CB-ILE-001)."""
from datetime import datetime

from pydantic import BaseModel, Field


# --- Session ---

class ILESessionCreate(BaseModel):
    mode: str = Field(..., pattern="^(learning|testing|parent_teaching)$")
    subject: str = Field(..., min_length=1, max_length=100)
    topic: str = Field(..., min_length=1, max_length=200)
    grade_level: int | None = None
    question_count: int = Field(default=5, ge=3, le=7)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|challenging)$")
    blooms_tier: str = Field(default="recall", pattern="^(recall|understand|apply)$")
    timer_enabled: bool = False
    timer_seconds: int | None = Field(default=None, ge=30, le=3600)
    is_private_practice: bool = False
    course_id: int | None = None
    course_content_id: int | None = None
    # Parent teaching mode
    child_student_id: int | None = None


class ILESessionResponse(BaseModel):
    id: int
    student_id: int
    parent_id: int | None
    mode: str
    subject: str
    topic: str
    grade_level: int | None
    question_count: int
    difficulty: str
    blooms_tier: str
    timer_enabled: bool
    timer_seconds: int | None
    is_private_practice: bool
    status: str
    current_question_index: int
    score: int | None
    total_correct: int | None
    xp_awarded: int | None
    started_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None
    course_id: int | None
    course_content_id: int | None

    class Config:
        from_attributes = True


class ILESessionSummary(BaseModel):
    id: int
    mode: str
    subject: str
    topic: str
    status: str
    score: int | None
    question_count: int
    total_correct: int | None
    xp_awarded: int | None
    started_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


# --- Question ---

class ILEQuestionOption(BaseModel):
    A: str
    B: str
    C: str
    D: str


class ILEQuestion(BaseModel):
    index: int
    question: str
    options: ILEQuestionOption | None = None  # None for fill_blank
    format: str = "mcq"
    difficulty: str = "medium"
    blooms_tier: str = "recall"


class ILECurrentQuestion(BaseModel):
    session_id: int
    question: ILEQuestion
    question_index: int
    total_questions: int
    mode: str
    attempt_number: int = 1
    disabled_options: list[str] = []  # Previously wrong answers (Learning Mode)
    streak_count: int = 0


# --- Answer ---

class ILEAnswerSubmit(BaseModel):
    answer: str = Field(..., min_length=1, max_length=500)
    time_taken_ms: int | None = Field(default=None, ge=0)
    parent_hint_note: str | None = Field(default=None, max_length=500)


class ILEAnswerFeedback(BaseModel):
    is_correct: bool
    attempt_number: int
    xp_earned: int
    # Learning Mode fields
    hint: str | None = None
    parent_hint_note: str | None = None  # Parent Teaching Mode: parent's personal hint
    explanation: str | None = None
    correct_answer: str | None = None  # Revealed after max attempts or correct
    # Session progress
    question_complete: bool  # True if correct or auto-revealed
    session_complete: bool
    streak_count: int = 0
    streak_broken: bool = False
    difficulty_changed: str | None = None  # New difficulty level if adjusted


# --- Results ---

class ILEQuestionResult(BaseModel):
    index: int
    question: str
    correct_answer: str
    student_answer: str | None
    is_correct: bool
    attempts: int
    xp_earned: int
    difficulty: str
    format: str


class ILEAreaToRevisit(BaseModel):
    index: int
    question: str
    correct_answer: str
    student_answer: str | None
    attempts: int


class ILESessionResults(BaseModel):
    session_id: int
    mode: str
    subject: str
    topic: str
    score: int
    total_questions: int
    percentage: float
    total_xp: int
    questions: list[ILEQuestionResult]
    streak_at_end: int
    time_taken_seconds: int | None
    # Adaptive feedback
    weak_areas: list[str] = []
    suggested_next_topic: str | None = None
    areas_to_revisit: list[ILEAreaToRevisit] = []
    aha_detected: bool = False


# --- Career Connect ---

class ILECareerConnect(BaseModel):
    career: str
    connection: str


# --- Topics ---

class ILETopic(BaseModel):
    subject: str
    topic: str
    course_id: int | None = None
    course_name: str | None = None
    mastery_pct: float | None = None
    is_weak_area: bool = False
    next_review_at: datetime | None = None


class ILETopicList(BaseModel):
    topics: list[ILETopic]


class ILESurpriseMe(BaseModel):
    topic: ILETopic
    reason: str  # e.g. "Weak area — avg 2.3 attempts"


# --- Mastery ---

class ILEMasteryEntry(BaseModel):
    subject: str
    topic: str
    total_sessions: int
    avg_attempts: float
    is_weak_area: bool
    current_difficulty: str
    last_score_pct: float | None
    next_review_at: datetime | None
    glow_intensity: float = 1.0  # 0.0 (faded) to 1.0 (bright)

    class Config:
        from_attributes = True


class ILEMasteryMap(BaseModel):
    student_id: int
    entries: list[ILEMasteryEntry]
    total_topics: int
    mastered_topics: int
    weak_topics: int


# --- Parent Teaching Mode ---

class ILEParentHintSubmit(BaseModel):
    hint_note: str = Field(..., min_length=1, max_length=500)


class ILEParentHintResponse(BaseModel):
    question_index: int
    parent_hint_note: str


# --- Admin Analytics (#3216) ---

class ILEDailySessionCount(BaseModel):
    date: str
    count: int


class ILEModeSplit(BaseModel):
    mode: str
    count: int


class ILETopTopic(BaseModel):
    topic: str
    count: int


class ILEAdminAnalytics(BaseModel):
    sessions_per_day: list[ILEDailySessionCount]
    total_sessions: int
    completed_sessions: int
    completion_rate: float
    average_score: float | None
    average_cost_per_session: float | None
    mode_split: list[ILEModeSplit]
    top_topics: list[ILETopTopic]
    flagged_sessions: int
