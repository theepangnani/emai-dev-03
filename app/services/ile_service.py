"""
ILE Session Orchestrator — CB-ILE-001 (#3198).

Manages the lifecycle of Flash Tutor sessions: create, answer, complete, abandon, resume.
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.ile_session import ILESession
from app.models.ile_question_attempt import ILEQuestionAttempt
from app.models.user import User
from app.services import ile_adaptive_service, ile_question_service

logger = get_logger(__name__)

# XP tiers for Learning Mode (by attempt number)
LEARNING_XP_TIERS = {1: 30, 2: 20, 3: 10}  # 4+ = 0
TESTING_XP_PER_CORRECT = 10
SESSION_EXPIRY_HOURS = 24
MAX_LEARNING_ATTEMPTS = 5  # Auto-reveal after this many attempts


def _utc_now_comparable(dt: datetime | None) -> datetime:
    """Return a UTC 'now' that is comparable with *dt*.

    SQLite returns timezone-naive datetimes even for DateTime(timezone=True)
    columns, while PostgreSQL returns timezone-aware ones.  Comparing naive
    and aware datetimes raises TypeError in Python 3.12+, so we match the
    awareness of the stored value.
    """
    if dt is not None and dt.tzinfo is not None:
        return datetime.now(timezone.utc)
    # Naive — return naive UTC
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

async def create_session(
    db: Session,
    student_id: int,
    mode: str,
    subject: str,
    topic: str,
    question_count: int = 5,
    difficulty: str = "medium",
    blooms_tier: str = "recall",
    grade_level: int | None = None,
    timer_enabled: bool = False,
    timer_seconds: int | None = None,
    is_private_practice: bool = False,
    course_id: int | None = None,
    course_content_id: int | None = None,
    parent_id: int | None = None,
) -> ILESession:
    """Create a new Flash Tutor session.

    Enforces max 1 active session per student.
    Generates questions via AI (bank-first).
    """
    # Check for existing active session
    active = (
        db.query(ILESession)
        .filter(
            ILESession.student_id == student_id,
            ILESession.status == "in_progress",
        )
        .first()
    )
    if active:
        # Expire if past expiry
        now = _utc_now_comparable(active.expires_at)
        if active.expires_at and active.expires_at < now:
            active.status = "expired"
            db.commit()
        else:
            raise ValueError(
                f"Active session {active.id} already exists. "
                "Complete or abandon it first."
            )

    # Check format escalation
    question_format = ile_question_service.check_format_escalation(
        db, student_id, subject, topic,
    )

    # Generate questions
    questions = await ile_question_service.get_from_bank_or_generate(
        db=db,
        subject=subject,
        topic=topic,
        grade_level=grade_level or 8,
        difficulty=difficulty,
        blooms_tier=blooms_tier,
        count=question_count,
        question_format=question_format,
    )

    now = datetime.now(timezone.utc)
    session = ILESession(
        student_id=student_id,
        parent_id=parent_id,
        mode=mode,
        subject=subject,
        topic=topic,
        grade_level=grade_level,
        question_count=len(questions),
        difficulty=difficulty,
        blooms_tier=blooms_tier,
        timer_enabled=timer_enabled,
        timer_seconds=timer_seconds,
        is_private_practice=is_private_practice,
        status="in_progress",
        current_question_index=0,
        questions_json=json.dumps([
            {k: v for k, v in q.items() if not k.startswith("_")}
            for q in questions
        ]),
        course_id=course_id,
        course_content_id=course_content_id,
        started_at=now,
        expires_at=now + timedelta(hours=SESSION_EXPIRY_HOURS),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    logger.info(
        "ILE session %d created | student=%d mode=%s subject=%s topic=%s questions=%d",
        session.id, student_id, mode, subject, topic, len(questions),
    )
    return session


def get_active_session(db: Session, student_id: int) -> ILESession | None:
    """Get the current active (in_progress) session for a student."""
    session = (
        db.query(ILESession)
        .filter(
            ILESession.student_id == student_id,
            ILESession.status == "in_progress",
        )
        .first()
    )
    if session and session.expires_at and session.expires_at < _utc_now_comparable(session.expires_at):
        session.status = "expired"
        db.commit()
        return None
    return session


def get_session(db: Session, session_id: int, user_id: int) -> ILESession:
    """Get a session by ID, verifying ownership."""
    session = db.query(ILESession).filter(ILESession.id == session_id).first()
    if not session:
        raise ValueError("Session not found")
    if session.student_id != user_id and session.parent_id != user_id:
        raise PermissionError("Not authorized to access this session")
    return session


def resume_session(
    db: Session, session: ILESession
) -> dict:
    """Validate a session can be resumed and return current state.

    Returns dict with session info, current question index, and previous
    attempts for the current question.
    """
    # Check expiry
    if session.expires_at and session.expires_at < _utc_now_comparable(session.expires_at):
        session.status = "expired"
        db.commit()
        raise ValueError("Session has expired")

    if session.status != "in_progress":
        raise ValueError(f"Session is not in progress (status={session.status})")

    # Get previous attempts for current question
    prev_attempts = get_attempt_history(db, session.id, session.current_question_index)

    logger.info(
        "ILE session %d resumed | student=%d question=%d/%d attempts=%d",
        session.id, session.student_id,
        session.current_question_index, session.question_count,
        len(prev_attempts),
    )

    return {
        "session_id": session.id,
        "current_question_index": session.current_question_index,
        "question_count": session.question_count,
        "previous_attempts": len(prev_attempts),
        "expires_at": session.expires_at.isoformat() if session.expires_at else None,
    }


def get_current_question(session: ILESession) -> dict:
    """Get the current question for a session."""
    questions = json.loads(session.questions_json)
    idx = session.current_question_index
    if idx >= len(questions):
        raise ValueError("No more questions in this session")

    q = questions[idx]
    return {
        "index": idx,
        "question": q["question"],
        "options": q.get("options"),
        "format": q.get("format", "mcq"),
        "difficulty": q.get("difficulty", session.difficulty),
        "blooms_tier": q.get("blooms_tier", session.blooms_tier),
    }


def get_attempt_history(
    db: Session, session_id: int, question_index: int
) -> list[ILEQuestionAttempt]:
    """Get all attempts for a specific question in a session."""
    return (
        db.query(ILEQuestionAttempt)
        .filter(
            ILEQuestionAttempt.session_id == session_id,
            ILEQuestionAttempt.question_index == question_index,
        )
        .order_by(ILEQuestionAttempt.attempt_number)
        .all()
    )


async def submit_answer(
    db: Session,
    session: ILESession,
    answer: str,
    time_taken_ms: int | None = None,
) -> dict:
    """Submit an answer for the current question.

    Returns feedback dict with correctness, XP, hints/explanations.
    """
    if session.status != "in_progress":
        raise ValueError("Session is not in progress")

    questions = json.loads(session.questions_json)
    idx = session.current_question_index
    if idx >= len(questions):
        raise ValueError("No more questions")

    q = questions[idx]
    correct_answer = q["correct_answer"]

    if q.get("format") == "fill_blank":
        is_correct = _check_fill_blank_answer(answer, correct_answer)
    else:
        is_correct = answer.strip().upper() == correct_answer.strip().upper()

    # Get attempt count for this question
    prev_attempts = get_attempt_history(db, session.id, idx)
    attempt_number = len(prev_attempts) + 1

    # Calculate XP
    xp = _calculate_xp(session.mode, is_correct, attempt_number)

    # Generate feedback based on mode
    hint = None
    explanation = None
    question_complete = False
    auto_revealed = False

    if session.mode == "testing":
        # Testing Mode: no feedback, just record and advance
        question_complete = True
    elif session.mode in ("learning", "parent_teaching"):
        if is_correct:
            question_complete = True
            # Generate "Why Correct" explanation
            explanation = q.get("explanation")
            if not explanation:
                try:
                    explanation = await ile_question_service.generate_explanation(
                        question=q["question"],
                        correct_answer=correct_answer,
                        grade_level=session.grade_level,
                    )
                except Exception:
                    logger.warning("Failed to generate explanation for session %d", session.id)
                    explanation = f"The correct answer is {correct_answer}."
        else:
            # Check if we should auto-reveal
            if attempt_number >= MAX_LEARNING_ATTEMPTS:
                question_complete = True
                auto_revealed = True
                explanation = q.get("explanation", f"The correct answer is {correct_answer}.")
            else:
                # Generate hint
                prev_hints = [a.hint_shown for a in prev_attempts if a.hint_shown]
                # Check for pre-computed hint tree
                hint_tree = q.get("_hint_tree")
                if hint_tree and attempt_number <= len(hint_tree):
                    hint = hint_tree[attempt_number - 1]
                else:
                    try:
                        hint = await ile_question_service.generate_hint(
                            question=q["question"],
                            wrong_answer=answer,
                            correct_answer=correct_answer,
                            attempt_number=attempt_number,
                            previous_hints=prev_hints,
                            grade_level=session.grade_level,
                        )
                    except Exception:
                        logger.warning("Failed to generate hint for session %d", session.id)
                        hint = "Think about this concept more carefully and try again."

    # Record attempt
    attempt = ILEQuestionAttempt(
        session_id=session.id,
        question_index=idx,
        question_text=q["question"],
        question_format=q.get("format", "mcq"),
        difficulty_level=q.get("difficulty", session.difficulty),
        selected_answer=answer,
        correct_answer=correct_answer,
        is_correct=is_correct,
        attempt_number=attempt_number,
        hint_shown=hint,
        explanation_shown=explanation,
        time_taken_ms=time_taken_ms,
        xp_earned=xp,
    )
    db.add(attempt)

    # Adaptive difficulty adjustment
    difficulty_changed = None
    if question_complete:
        db.flush()  # Ensure latest attempt is visible (autoflush=False)
        difficulty_changed = ile_adaptive_service.adjust_within_session(
            db, session
        )

    # Advance session if question is complete
    if question_complete:
        session.current_question_index = idx + 1

    # Check if session is complete
    session_complete = question_complete and (idx + 1 >= session.question_count)

    # Track streak
    streak_count = 0
    streak_broken = False
    if session.mode in ("learning", "parent_teaching"):
        if is_correct and attempt_number == 1:
            streak_count = _count_streak(db, session.id, idx)
        elif not is_correct:
            streak_broken = True

    db.commit()

    return {
        "is_correct": is_correct,
        "attempt_number": attempt_number,
        "xp_earned": xp,
        "hint": hint,
        "explanation": explanation,
        "correct_answer": correct_answer if (question_complete or auto_revealed) else None,
        "question_complete": question_complete,
        "session_complete": session_complete,
        "streak_count": streak_count,
        "streak_broken": streak_broken,
        "difficulty_changed": difficulty_changed,
    }


async def complete_session(db: Session, session: ILESession) -> dict:
    """Finalize a session, calculate score, award XP."""
    if session.status != "in_progress":
        raise ValueError("Session is not in progress")

    # Batch-load all attempts in a single query (#3229)
    all_attempts = (
        db.query(ILEQuestionAttempt)
        .filter(ILEQuestionAttempt.session_id == session.id)
        .order_by(ILEQuestionAttempt.question_index, ILEQuestionAttempt.attempt_number)
        .all()
    )
    attempts_by_q: dict[int, list[ILEQuestionAttempt]] = defaultdict(list)
    for a in all_attempts:
        attempts_by_q[a.question_index].append(a)

    # Calculate final score
    questions = json.loads(session.questions_json)
    total_correct = 0
    total_xp = 0
    question_results = []

    for idx in range(len(questions)):
        q = questions[idx]
        attempts = attempts_by_q.get(idx, [])
        final_attempt = attempts[-1] if attempts else None
        is_correct = final_attempt.is_correct if final_attempt else False
        if is_correct:
            total_correct += 1
        q_xp = sum(a.xp_earned for a in attempts)
        total_xp += q_xp

        question_results.append({
            "index": idx,
            "question": q["question"],
            "correct_answer": q["correct_answer"],
            "student_answer": final_attempt.selected_answer if final_attempt else None,
            "is_correct": is_correct,
            "attempts": len(attempts),
            "xp_earned": q_xp,
            "difficulty": q.get("difficulty", session.difficulty),
            "format": q.get("format", "mcq"),
        })

    # Update session
    session.status = "completed"
    session.score = total_correct
    session.total_correct = total_correct
    session.xp_awarded = total_xp
    session.completed_at = datetime.now(timezone.utc)
    db.commit()

    # Award XP once at status transition (#3227)
    try:
        from app.services.xp_service import award_xp
        award_xp(db, session.student_id, "ile_session_complete", context_id=f"ile_session_{session.id}")
    except Exception:
        pass  # XP is never blocking

    percentage = (total_correct / len(questions) * 100) if questions else 0

    logger.info(
        "ILE session %d completed | student=%d score=%d/%d xp=%d",
        session.id, session.student_id, total_correct, len(questions), total_xp,
    )

    return _build_results_dict(session, questions, question_results, total_correct, total_xp, attempts_by_q)


def get_session_results_from_attempts(db: Session, session: ILESession) -> dict:
    """Reconstruct results from stored attempts without mutating session state (#3225)."""
    # Batch-load all attempts
    all_attempts = (
        db.query(ILEQuestionAttempt)
        .filter(ILEQuestionAttempt.session_id == session.id)
        .order_by(ILEQuestionAttempt.question_index, ILEQuestionAttempt.attempt_number)
        .all()
    )
    attempts_by_q: dict[int, list[ILEQuestionAttempt]] = defaultdict(list)
    for a in all_attempts:
        attempts_by_q[a.question_index].append(a)

    questions = json.loads(session.questions_json)
    total_correct = 0
    total_xp = 0
    question_results = []

    for idx in range(len(questions)):
        q = questions[idx]
        attempts = attempts_by_q.get(idx, [])
        final_attempt = attempts[-1] if attempts else None
        is_correct = final_attempt.is_correct if final_attempt else False
        if is_correct:
            total_correct += 1
        q_xp = sum(a.xp_earned for a in attempts)
        total_xp += q_xp

        question_results.append({
            "index": idx,
            "question": q["question"],
            "correct_answer": q["correct_answer"],
            "student_answer": final_attempt.selected_answer if final_attempt else None,
            "is_correct": is_correct,
            "attempts": len(attempts),
            "xp_earned": q_xp,
            "difficulty": q.get("difficulty", session.difficulty),
            "format": q.get("format", "mcq"),
        })

    return _build_results_dict(session, questions, question_results, total_correct, total_xp, attempts_by_q)


def _build_results_dict(
    session: ILESession,
    questions: list[dict],
    question_results: list[dict],
    total_correct: int,
    total_xp: int,
    attempts_by_q: dict[int, list],
) -> dict:
    """Build the session results dictionary."""
    percentage = (total_correct / len(questions) * 100) if questions else 0

    # Compute streak from pre-fetched attempts
    streak = _count_streak_from_attempts(attempts_by_q, len(questions) - 1)

    return {
        "session_id": session.id,
        "mode": session.mode,
        "subject": session.subject,
        "topic": session.topic,
        "score": total_correct,
        "total_questions": len(questions),
        "percentage": round(percentage, 1),
        "total_xp": total_xp,
        "questions": question_results,
        "streak_at_end": streak,
        "time_taken_seconds": _session_duration_seconds(session),
        "weak_areas": [],
        "suggested_next_topic": None,
    }


def abandon_session(db: Session, session: ILESession) -> None:
    """Abandon a session, preserving progress."""
    if session.status != "in_progress":
        raise ValueError("Session is not in progress")
    session.status = "abandoned"
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("ILE session %d abandoned at question %d", session.id, session.current_question_index)


def get_session_history(
    db: Session, student_id: int, limit: int = 20
) -> list[ILESession]:
    """Get recent sessions for a student."""
    return (
        db.query(ILESession)
        .filter(ILESession.student_id == student_id)
        .order_by(ILESession.created_at.desc())
        .limit(limit)
        .all()
    )


def get_available_topics(
    db: Session, student_id: int
) -> list[dict]:
    """Get available topics from student's courses.

    Returns list of {subject, topic, course_id, course_name}.
    Uses a single joined query to avoid N+1 (#3229).
    """
    from app.models.course import Course, student_courses
    from app.models.course_content import CourseContent
    from app.models.student import Student

    # student_courses stores Student.id, not User.id — look up the Student record
    student = db.query(Student).filter(Student.user_id == student_id).first()
    if student:
        course_ids = [
            r[0] for r in
            db.query(student_courses.c.course_id)
            .filter(student_courses.c.student_id == student.id)
            .all()
        ]
    else:
        course_ids = []

    # Single query: join courses with their content
    rows = (
        db.query(Course, CourseContent)
        .outerjoin(CourseContent, CourseContent.course_id == Course.id)
        .filter(
            (Course.id.in_(course_ids)) | (Course.created_by_user_id == student_id)
        )
        .all()
    )

    topics = []
    seen_courses_without_content: set[int] = set()
    for course, cc in rows:
        if cc is not None:
            topics.append({
                "subject": course.name,
                "topic": cc.title or f"Material {cc.id}",
                "course_id": course.id,
                "course_name": course.name,
            })
        elif course.id not in seen_courses_without_content:
            # Course without specific content — use course name as topic
            seen_courses_without_content.add(course.id)
            topics.append({
                "subject": course.name,
                "topic": course.name,
                "course_id": course.id,
                "course_name": course.name,
            })

    return topics


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _calculate_xp(mode: str, is_correct: bool, attempt_number: int) -> int:
    """Calculate XP for an answer based on mode and attempt."""
    if not is_correct:
        return 0
    if mode == "testing":
        return TESTING_XP_PER_CORRECT
    # Learning / parent_teaching: tiered by attempt
    return LEARNING_XP_TIERS.get(attempt_number, 0)


def _count_streak(db: Session, session_id: int, current_index: int) -> int:
    """Count consecutive first-attempt correct answers up to current_index.

    Used during submit_answer where we don't have pre-fetched attempts for
    the full session yet (the current attempt hasn't been committed).
    """
    # Batch-load all attempts for the session (#3229)
    all_attempts = (
        db.query(ILEQuestionAttempt)
        .filter(ILEQuestionAttempt.session_id == session_id)
        .order_by(ILEQuestionAttempt.question_index, ILEQuestionAttempt.attempt_number)
        .all()
    )
    attempts_by_q: dict[int, list[ILEQuestionAttempt]] = defaultdict(list)
    for a in all_attempts:
        attempts_by_q[a.question_index].append(a)

    return _count_streak_from_attempts(attempts_by_q, current_index)


def _count_streak_from_attempts(
    attempts_by_q: dict[int, list], current_index: int
) -> int:
    """Count consecutive first-attempt correct answers from pre-fetched attempts."""
    streak = 0
    for idx in range(current_index, -1, -1):
        attempts = attempts_by_q.get(idx, [])
        if len(attempts) == 1 and attempts[0].is_correct:
            streak += 1
        else:
            break
    return streak


def _check_fill_blank_answer(student_answer: str, correct_answer: str) -> bool:
    """Check fill-in-the-blank answer with forgiving matching.

    - Case-insensitive
    - Trim whitespace
    - Strip trailing punctuation
    - Accept common variants (e.g. "the " prefix)
    - Numeric equivalence (e.g. "2" == "2.0")
    """
    def _normalize(text: str) -> str:
        t = text.strip().lower()
        # Strip trailing punctuation
        t = t.rstrip(".,;:!?")
        # Strip leading articles
        for prefix in ("the ", "a ", "an "):
            if t.startswith(prefix):
                t = t[len(prefix):]
        return t.strip()

    norm_student = _normalize(student_answer)
    norm_correct = _normalize(correct_answer)

    if norm_student == norm_correct:
        return True

    # Numeric equivalence: "2" == "2.0", "0.5" == ".5"
    try:
        if float(norm_student) == float(norm_correct):
            return True
    except (ValueError, OverflowError):
        pass

    return False


def _session_duration_seconds(session: ILESession) -> int | None:
    """Calculate session duration in seconds."""
    if session.started_at and session.completed_at:
        delta = session.completed_at - session.started_at
        return int(delta.total_seconds())
    return None
