"""Lesson Summary Service — AI-powered class notes analysis.

Generates structured summaries, key concepts, study questions, action items,
and important dates from student-provided class notes or transcripts.
"""
import json
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.lesson_summary import InputType, LessonSummary
from app.models.study_guide import StudyGuide
from app.schemas.lesson_summary import (
    FlashcardsFromSummaryResponse,
    LessonSummaryListItem,
    LessonSummaryResponse,
)
from app.services.ai_service import generate_content

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an expert educational assistant specializing in organizing and summarizing "
    "class notes for students. You extract key information and structure it to maximize "
    "learning retention and exam preparation."
)

_SUMMARY_PROMPT_TEMPLATE = """\
Analyze the following class notes and return a JSON object with this exact structure:
{{
  "summary": "<3-5 sentence summary of the main lesson content>",
  "key_concepts": [
    {{"concept": "<term or concept name>", "definition": "<clear explanation>"}},
    ...
  ],
  "important_dates": [
    {{"date": "<date or time reference>", "event": "<what happens on that date>"}},
    ...
  ],
  "study_questions": [
    "<question to test understanding of the lesson>",
    ...
  ],
  "action_items": [
    "<homework, readings, upcoming tests or tasks mentioned>",
    ...
  ]
}}

Rules:
- Provide 5–10 key_concepts (only the most important terms)
- Provide 5 study_questions that test deep understanding
- Only include important_dates if dates/deadlines are actually mentioned in the notes
- Only include action_items that are explicitly mentioned (homework, readings, tests)
- Return ONLY the JSON object, no other text

Input type: {input_type}
Title: {title}

CLASS NOTES:
{raw_input}
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _count_words(text: str) -> int:
    return len(text.split()) if text else 0


def _parse_ai_json(raw: str) -> dict:
    """Extract JSON from AI response, handling markdown code blocks."""
    raw = raw.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.splitlines()
        # Remove first and last fence lines
        inner = lines[1:] if lines[0].startswith("```") else lines
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        raw = "\n".join(inner).strip()
    return json.loads(raw)


def _build_list_item(summary: LessonSummary, db: Session) -> LessonSummaryListItem:
    course_name: Optional[str] = None
    if summary.course_id:
        from app.models.course import Course
        course = db.query(Course).filter(Course.id == summary.course_id).first()
        course_name = course.name if course else None

    return LessonSummaryListItem(
        id=summary.id,
        title=summary.title,
        course_id=summary.course_id,
        course_name=course_name,
        input_type=summary.input_type,
        word_count=summary.word_count,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
    )


def _build_response(summary: LessonSummary, db: Session) -> LessonSummaryResponse:
    course_name: Optional[str] = None
    if summary.course_id:
        from app.models.course import Course
        course = db.query(Course).filter(Course.id == summary.course_id).first()
        course_name = course.name if course else None

    return LessonSummaryResponse(
        id=summary.id,
        student_id=summary.student_id,
        course_id=summary.course_id,
        course_name=course_name,
        title=summary.title,
        input_type=summary.input_type,
        raw_input=summary.raw_input,
        summary=summary.summary,
        key_concepts=summary.key_concepts,
        important_dates=summary.important_dates,
        study_questions=summary.study_questions,
        action_items=summary.action_items,
        word_count=summary.word_count,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
    )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

async def generate_summary(
    student_id: int,
    title: str,
    raw_input: str,
    input_type: InputType,
    course_id: Optional[int],
    db: Session,
) -> LessonSummaryResponse:
    """Call GPT-4o-mini (via Claude) to structure class notes, then persist the result."""
    logger.info("Generating lesson summary | student_id=%s | title=%s", student_id, title)

    prompt = _SUMMARY_PROMPT_TEMPLATE.format(
        input_type=input_type.value,
        title=title,
        raw_input=raw_input[:8000],  # Limit to ~8 000 chars to stay within token budget
    )

    # Attempt generation with one retry on JSON parse failure
    parsed: Optional[dict] = None
    for attempt in range(2):
        try:
            raw_response = await generate_content(
                prompt=prompt,
                system_prompt=_SYSTEM_PROMPT,
                max_tokens=2500,
                temperature=0.4,
            )
            parsed = _parse_ai_json(raw_response)
            break
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("JSON parse error on attempt %d: %s", attempt + 1, exc)
            if attempt == 1:
                raise ValueError("AI returned invalid JSON after two attempts") from exc

    if parsed is None:
        raise ValueError("Failed to generate lesson summary")

    summary_record = LessonSummary(
        student_id=student_id,
        course_id=course_id,
        title=title,
        input_type=input_type,
        raw_input=raw_input,
        summary=parsed.get("summary"),
        key_concepts=parsed.get("key_concepts") or [],
        important_dates=parsed.get("important_dates") or [],
        study_questions=parsed.get("study_questions") or [],
        action_items=parsed.get("action_items") or [],
        word_count=_count_words(raw_input),
    )
    db.add(summary_record)
    db.commit()
    db.refresh(summary_record)

    logger.info("Lesson summary created | id=%s", summary_record.id)
    return _build_response(summary_record, db)


def get_summaries(
    student_id: int,
    course_id: Optional[int],
    db: Session,
) -> List[LessonSummaryListItem]:
    """Return all summaries for the student, most recent first."""
    query = db.query(LessonSummary).filter(LessonSummary.student_id == student_id)
    if course_id is not None:
        query = query.filter(LessonSummary.course_id == course_id)
    summaries = query.order_by(LessonSummary.created_at.desc()).all()
    return [_build_list_item(s, db) for s in summaries]


def get_summary(summary_id: int, student_id: int, db: Session) -> LessonSummaryResponse:
    """Return a single summary owned by the student, or raise 404."""
    from fastapi import HTTPException

    record = (
        db.query(LessonSummary)
        .filter(LessonSummary.id == summary_id, LessonSummary.student_id == student_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Lesson summary not found")
    return _build_response(record, db)


def update_summary(
    summary_id: int,
    student_id: int,
    title: Optional[str],
    raw_input: Optional[str],
    db: Session,
) -> LessonSummaryResponse:
    """Update the title and/or raw_input of an existing summary."""
    from fastapi import HTTPException

    record = (
        db.query(LessonSummary)
        .filter(LessonSummary.id == summary_id, LessonSummary.student_id == student_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Lesson summary not found")

    if title is not None:
        record.title = title
    if raw_input is not None:
        record.raw_input = raw_input
        record.word_count = _count_words(raw_input)

    db.commit()
    db.refresh(record)
    return _build_response(record, db)


def delete_summary(summary_id: int, student_id: int, db: Session) -> None:
    """Delete a lesson summary owned by the student."""
    from fastapi import HTTPException

    record = (
        db.query(LessonSummary)
        .filter(LessonSummary.id == summary_id, LessonSummary.student_id == student_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Lesson summary not found")

    db.delete(record)
    db.commit()


def generate_flashcards_from_summary(
    summary_id: int,
    student_id: int,
    db: Session,
) -> FlashcardsFromSummaryResponse:
    """Convert key_concepts into a StudyGuide (flashcard set) for the student."""
    from fastapi import HTTPException

    record = (
        db.query(LessonSummary)
        .filter(LessonSummary.id == summary_id, LessonSummary.student_id == student_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Lesson summary not found")

    concepts = record.key_concepts or []
    if not concepts:
        raise HTTPException(status_code=422, detail="No key concepts found in this summary")

    # Build flashcard JSON in the same format as existing StudyGuide content
    cards = [
        {"front": c.get("concept", ""), "back": c.get("definition", "")}
        for c in concepts
        if c.get("concept")
    ]
    content = json.dumps({"cards": cards})
    flashcard_title = f"Flashcards: {record.title}"

    guide = StudyGuide(
        user_id=student_id,
        course_id=record.course_id,
        title=flashcard_title,
        content=content,
        guide_type="flashcards",
    )
    db.add(guide)
    db.commit()
    db.refresh(guide)

    logger.info(
        "Flashcard set created from lesson summary | summary_id=%s | guide_id=%s | cards=%d",
        summary_id,
        guide.id,
        len(cards),
    )

    return FlashcardsFromSummaryResponse(
        study_guide_id=guide.id,
        title=flashcard_title,
        card_count=len(cards),
        message=f"Created {len(cards)} flashcards from key concepts.",
    )
