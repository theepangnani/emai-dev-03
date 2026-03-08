"""Conversation Starters — AI-generated dinner table prompts for parents."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student, parent_students
from app.models.course import Course, student_courses
from app.models.assignment import Assignment
from app.models.study_guide import StudyGuide
from app.api.deps import require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.services.ai_service import generate_content
from app.services.ai_usage import check_ai_usage, increment_ai_usage
from app.schemas.conversation_starters import (
    ConversationStarterRequest,
    ConversationStartersResponse,
    ConversationStarter,
)

import json

from app.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/conversation-starters", tags=["Conversation Starters"])

# Simple in-memory cache: (parent_id, date_str) -> response
_daily_cache: dict[tuple[int, str], ConversationStartersResponse] = {}


def _verify_parent_child(db: Session, parent_user_id: int, student_id: int) -> tuple[Student, User]:
    """Verify parent-child link and return (student, child_user)."""
    row = (
        db.query(Student, User)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .join(User, User.id == Student.user_id)
        .filter(
            parent_students.c.parent_id == parent_user_id,
            Student.id == student_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Child not found or not linked to your account.")
    return row


def _gather_context(db: Session, student: Student, course_id: int | None) -> str:
    """Gather recent school context for prompt generation."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    week_ahead = now + timedelta(days=7)

    # Get student's courses
    course_rows = (
        db.query(Course)
        .join(student_courses, student_courses.c.course_id == Course.id)
        .filter(student_courses.c.student_id == student.id)
        .all()
    )
    if course_id:
        course_rows = [c for c in course_rows if c.id == course_id]

    course_ids = [c.id for c in course_rows]
    course_names = {c.id: c.name for c in course_rows}

    parts = []
    parts.append("Courses: " + ", ".join(c.name for c in course_rows) if course_rows else "No courses")

    # Upcoming assignments
    if course_ids:
        assignments = (
            db.query(Assignment)
            .filter(
                Assignment.course_id.in_(course_ids),
                Assignment.due_date.isnot(None),
                Assignment.due_date >= now,
                Assignment.due_date < week_ahead,
            )
            .order_by(Assignment.due_date.asc())
            .limit(10)
            .all()
        )
        if assignments:
            lines = []
            for a in assignments:
                cname = course_names.get(a.course_id, "")
                due = a.due_date.strftime("%b %d") if a.due_date else ""
                lines.append(f"- {a.title} ({cname}, due {due})")
            parts.append("Upcoming assignments:\n" + "\n".join(lines))

    # Recent study guides
    if student.user_id:
        guides = (
            db.query(StudyGuide)
            .filter(
                StudyGuide.user_id == student.user_id,
                StudyGuide.created_at >= week_ago,
                StudyGuide.archived_at.is_(None),
            )
            .order_by(StudyGuide.created_at.desc())
            .limit(5)
            .all()
        )
        if guides:
            parts.append(f"Study guides created this week: {len(guides)} — topics: " +
                         ", ".join(g.title or "Untitled" for g in guides))

    return "\n\n".join(parts)


SYSTEM_PROMPT = """You are a warm, supportive parenting coach helping parents connect with their children about school.
Generate conversation starters that are:
- Casual and natural — things a parent would say at dinner, in the car, or before bed
- Curiosity-driven, NOT interrogative or pressuring (never "Did you do your homework?")
- Age-appropriate and encouraging
- Based on real school context provided
- Short — 1-2 sentences each

Return a JSON array of objects with "prompt" and "context" fields.
"prompt" is what the parent would say. "context" is a brief note about what school data inspired it.
Return ONLY the JSON array, no other text."""


@router.post("/generate", response_model=ConversationStartersResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def generate_conversation_starters(
    body: ConversationStarterRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Generate AI-powered conversation starters for a parent about their child's schoolwork."""
    student, child_user = _verify_parent_child(db, current_user.id, body.student_id)
    check_ai_usage(current_user, db)

    context = _gather_context(db, student, body.course_id)
    child_first = (child_user.full_name or "your child").split()[0]

    prompt = f"""Generate 3-5 casual conversation starters for a parent to discuss school with their child "{child_first}".

Here is the child's current school context:
{context}

Return a JSON array of objects: [{{"prompt": "...", "context": "..."}}]
Return ONLY the JSON array."""

    raw = await generate_content(prompt, SYSTEM_PROMPT, max_tokens=800, temperature=0.8)
    increment_ai_usage(current_user, db, generation_type="conversation_starters")

    # Parse JSON from response
    starters = _parse_starters(raw)

    now_str = datetime.now(timezone.utc).isoformat()
    response = ConversationStartersResponse(
        starters=starters,
        student_name=child_first,
        generated_at=now_str,
    )

    # Cache for daily endpoint
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _daily_cache[(current_user.id, today)] = response

    return response


@router.get("/daily", response_model=ConversationStartersResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def daily_conversation_starters(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Get cached conversation starters for today, or generate new ones for the first linked child."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cached = _daily_cache.get((current_user.id, today))
    if cached:
        return cached

    # Find first linked child
    row = (
        db.query(Student, User)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .join(User, User.id == Student.user_id)
        .filter(parent_students.c.parent_id == current_user.id)
        .first()
    )
    if not row:
        return ConversationStartersResponse(
            starters=[],
            student_name="",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    student, child_user = row
    check_ai_usage(current_user, db)

    context = _gather_context(db, student, course_id=None)
    child_first = (child_user.full_name or "your child").split()[0]

    prompt = f"""Generate 3-5 casual conversation starters for a parent to discuss school with their child "{child_first}".

Here is the child's current school context:
{context}

Return a JSON array of objects: [{{"prompt": "...", "context": "..."}}]
Return ONLY the JSON array."""

    raw = await generate_content(prompt, SYSTEM_PROMPT, max_tokens=800, temperature=0.8)
    increment_ai_usage(current_user, db, generation_type="conversation_starters")

    starters = _parse_starters(raw)
    response = ConversationStartersResponse(
        starters=starters,
        student_name=child_first,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    _daily_cache[(current_user.id, today)] = response
    return response


def _parse_starters(raw: str) -> list[ConversationStarter]:
    """Parse AI response into ConversationStarter objects."""
    try:
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        items = json.loads(text)
        return [
            ConversationStarter(
                prompt=item.get("prompt", ""),
                context=item.get("context"),
            )
            for item in items
            if item.get("prompt")
        ]
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logger.warning("Failed to parse conversation starters JSON: %s", e)
        # Fallback: return the raw text as a single starter
        return [ConversationStarter(prompt=raw.strip()[:500])]
