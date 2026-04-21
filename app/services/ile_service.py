"""
ILE Session Orchestrator — CB-ILE-001 (#3198).

Manages the lifecycle of Flash Tutor sessions: create, answer, complete, abandon, resume.
"""
import json
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func as sa_func, or_
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
MAX_SESSIONS_PER_DAY = 10  # Anti-gaming: rate limit
RAPID_COMPLETION_SECONDS = 30  # Anti-gaming: flag suspicious sessions


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
    # Validate enum-like parameters before any DB work
    VALID_DIFFICULTIES = {"easy", "medium", "challenging"}
    VALID_BLOOMS = {"recall", "understand", "apply"}

    if difficulty not in VALID_DIFFICULTIES:
        raise ValueError(f"Invalid difficulty: {difficulty}. Must be one of {VALID_DIFFICULTIES}")
    if blooms_tier not in VALID_BLOOMS:
        raise ValueError(f"Invalid blooms_tier: {blooms_tier}. Must be one of {VALID_BLOOMS}")

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

    # Anti-gaming: max 10 sessions per student per day (#3216)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    sessions_today = (
        db.query(sa_func.count(ILESession.id))
        .filter(
            ILESession.student_id == student_id,
            ILESession.created_at >= today_start,
        )
        .scalar()
    )
    if sessions_today >= MAX_SESSIONS_PER_DAY:
        raise ValueError(
            f"Daily session limit reached ({MAX_SESSIONS_PER_DAY} sessions per day). "
            "Please try again tomorrow."
        )

    # Use calibration-recommended difficulty if caller used default (#3211)
    if difficulty == "medium":
        try:
            recommended = get_recommended_difficulty(db, student_id, subject, topic)
            if recommended:
                difficulty = recommended
                logger.info(
                    "Using calibrated difficulty=%s for student=%d topic=%s",
                    difficulty, student_id, topic,
                )
        except Exception:
            pass  # Calibration is never blocking

    # Check format escalation
    question_format = ile_question_service.check_format_escalation(
        db, student_id, subject, topic,
    )

    # Fetch study guide / course content text for context-grounded generation
    context_text = None
    if course_content_id:
        context_text = _fetch_context_text(db, course_content_id)

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
        context_text=context_text,
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
    parent_hint_note: str | None = None,
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

    # Apply any pending parent hint stored before the first attempt (#3280)
    pending_key = (session.id, idx)
    if not parent_hint_note and pending_key in _pending_parent_hints:
        parent_hint_note = _pending_parent_hints.pop(pending_key)

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
        # COMMENTED OUT: parent_hint_note column not yet in production DB (#3300)
        # parent_hint_note=parent_hint_note if session.mode == "parent_teaching" else None,
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

    # Track streak — only in learning/parent_teaching modes.
    # Streak increments only on first-attempt correct (attempt_number == 1).
    # Multi-attempt correct answers do not increment the streak.
    # Any wrong answer sets streak_broken=True so the frontend can show feedback.
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
        "parent_hint_note": parent_hint_note if session.mode == "parent_teaching" else None,
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
    session.completed_at = datetime.now(timezone.utc)

    # Rapid completion detection — flag sessions under 30 seconds (#3216)
    # COMMENTED OUT: flagged_reason column not yet in production DB (#3300)
    flagged = False
    duration = _session_duration_seconds(session)
    if duration is not None and duration < RAPID_COMPLETION_SECONDS:
        # session.flagged_reason = f"Rapid completion ({duration}s < {RAPID_COMPLETION_SECONDS}s)"
        flagged = True
        total_xp = 0  # Don't award XP for suspicious sessions
        logger.warning(
            "ILE session %d flagged: rapid completion (%ds) | student=%d",
            session.id, duration, session.student_id,
        )

    session.xp_awarded = total_xp

    # COMMENTED OUT: ai_cost_estimate column not yet in production DB (#3300)
    # try:
    #     session.ai_cost_estimate = _estimate_session_cost(all_attempts, questions)
    # except Exception:
    #     logger.debug("Failed to estimate cost for session %d", session.id)

    db.commit()

    # Award XP once at status transition (#3227) — skip for flagged sessions
    if not flagged:
        try:
            from app.services.xp_service import award_xp
            award_xp(db, session.student_id, "ile_session_complete", context_id=f"ile_session_{session.id}")
        except Exception:
            pass  # XP is never blocking

    # Update topic mastery after session completion (#3206)
    aha_detected = False
    try:
        from app.services.ile_mastery_service import (
            update_mastery_after_session, get_mastery_snapshot, check_aha_moment,
        )
        mastery_before = get_mastery_snapshot(db, session.student_id, session.subject, session.topic)
        mastery_after = update_mastery_after_session(db, session, question_results)
        aha_detected = check_aha_moment(mastery_before, mastery_after)

        if aha_detected:
            try:
                from app.models.notification import NotificationType
                from app.services.notification_service import notify_parents_of_student
                student_user = db.query(User).filter(User.id == session.student_id).first()
                if student_user:
                    student_first_name = (student_user.full_name.split()[0] if student_user.full_name else None) or "Your child"
                    notify_parents_of_student(
                        db=db,
                        student_user=student_user,
                        title=f"{student_first_name} had a breakthrough in {session.topic} today!",
                        content=(
                            f"{student_first_name} was struggling with "
                            f"{session.topic} ({session.subject}) but just had a breakthrough moment. "
                            f"Their accuracy improved significantly!"
                        ),
                        notification_type=NotificationType.ILE_AHA_MOMENT,
                        link="/flash-tutor",
                    )
                    db.commit()
            except Exception:
                logger.warning("Failed to send aha moment notification for session %d", session.id)
    except Exception:
        # Don't rollback — mastery already committed internally, aha detection is read-only
        logger.warning("Failed to update mastery for session %d", session.id, exc_info=True)

    percentage = (total_correct / len(questions) * 100) if questions else 0

    # Update student calibration (non-blocking) (#3211)
    try:
        update_student_calibration(
            db, session.student_id, session.subject, session.topic, percentage,
        )
    except Exception:
        logger.warning("Calibration update failed for session %d", session.id)

    logger.info(
        "ILE session %d completed | student=%d score=%d/%d xp=%d",
        session.id, session.student_id, total_correct, len(questions), total_xp,
    )

    return _build_results_dict(session, questions, question_results, total_correct, total_xp, attempts_by_q, aha_detected)


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
    aha_detected: bool = False,
) -> dict:
    """Build the session results dictionary."""
    percentage = (total_correct / len(questions) * 100) if questions else 0

    # Compute streak from pre-fetched attempts
    streak = _count_streak_from_attempts(attempts_by_q, len(questions) - 1)

    # Areas to revisit — questions answered incorrectly (for parent_teaching summary)
    areas_to_revisit = [
        {
            "index": qr["index"],
            "question": qr["question"],
            "correct_answer": qr["correct_answer"],
            "student_answer": qr["student_answer"],
            "attempts": qr["attempts"],
        }
        for qr in question_results
        if not qr["is_correct"]
    ]

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
        "areas_to_revisit": areas_to_revisit,
        "aha_detected": aha_detected,
    }


def add_parent_hint(
    db: Session, session: ILESession, hint_note: str
) -> dict:
    """Add a parent hint note for the current question (parent_teaching mode only)."""
    if session.mode != "parent_teaching":
        raise ValueError("Parent hints are only available in Parent Teaching Mode")
    if session.status != "in_progress":
        raise ValueError("Session is not in progress")

    idx = session.current_question_index
    # Store as the most recent attempt's parent_hint_note, or create a placeholder
    latest_attempt = (
        db.query(ILEQuestionAttempt)
        .filter(
            ILEQuestionAttempt.session_id == session.id,
            ILEQuestionAttempt.question_index == idx,
        )
        .order_by(ILEQuestionAttempt.attempt_number.desc())
        .first()
    )

    if latest_attempt:
        # COMMENTED OUT: parent_hint_note column not yet in production DB (#3300)
        # latest_attempt.parent_hint_note = hint_note
        pass
    else:
        # No attempt yet — store hint in pending dict; submit_answer will apply it
        _pending_parent_hints[(session.id, idx)] = hint_note

    db.commit()
    return {"question_index": idx, "parent_hint_note": hint_note}


def abandon_session(db: Session, session: ILESession) -> None:
    """Abandon a session, preserving progress."""
    if session.status != "in_progress":
        raise ValueError("Session is not in progress")
    session.status = "abandoned"
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("ILE session %d abandoned at question %d", session.id, session.current_question_index)


def get_session_history(
    db: Session, student_id: int, limit: int = 20,
    exclude_private: bool = False,
) -> list[ILESession]:
    """Get recent sessions for a student.

    When *exclude_private* is True, sessions with is_private_practice=True
    are filtered out (used for parent/teacher views).
    """
    query = (
        db.query(ILESession)
        .filter(ILESession.student_id == student_id)
    )
    if exclude_private:
        query = query.filter(ILESession.is_private_practice == False)  # noqa: E712
    return (
        query
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
        .filter(or_(CourseContent.archived_at.is_(None), CourseContent.id.is_(None)))
        .all()
    )

    topics = []
    seen_topics: set[str] = set()
    seen_courses_without_content: set[int] = set()
    for course, cc in rows:
        if cc is not None:
            topic_title = cc.title or f"Material {cc.id}"
            if topic_title in seen_topics:
                continue
            seen_topics.add(topic_title)
            topics.append({
                "subject": course.name,
                "topic": topic_title,
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

    # Enrich topics with mastery data (#3206)
    if topics:
        from app.models.ile_topic_mastery import ILETopicMastery
        mastery_rows = (
            db.query(ILETopicMastery)
            .filter(ILETopicMastery.student_id == student_id)
            .all()
        )
        mastery_map = {
            (m.subject, m.topic): m for m in mastery_rows
        }
        for t in topics:
            m = mastery_map.get((t["subject"], t["topic"]))
            if m:
                t["mastery_pct"] = m.last_score_pct
                t["is_weak_area"] = m.is_weak_area
                t["next_review_at"] = m.next_review_at

    return topics


# ---------------------------------------------------------------------------
# Student Calibration
# ---------------------------------------------------------------------------

def update_student_calibration(
    db: Session, student_id: int, subject: str, topic: str, score_pct: float
) -> None:
    """Update calibration after session completion.

    - Get or create calibration record
    - Increment sessions_completed
    - After 3 sessions: calculate baseline_accuracy (running average)
    - Set recommended_difficulty based on accuracy
    """
    from app.models.ile_student_calibration import ILEStudentCalibration

    cal = (
        db.query(ILEStudentCalibration)
        .filter(
            ILEStudentCalibration.student_id == student_id,
            ILEStudentCalibration.subject == subject,
            ILEStudentCalibration.topic == topic,
        )
        .first()
    )

    if not cal:
        cal = ILEStudentCalibration(
            student_id=student_id,
            subject=subject,
            topic=topic,
            sessions_completed=0,
        )
        db.add(cal)
        db.flush()

    old_count = cal.sessions_completed or 0
    cal.sessions_completed = old_count + 1

    # Track running average from session 1 so baseline is accurate at threshold
    if cal.baseline_accuracy is not None:
        # Running average: blend old baseline with new score
        cal.baseline_accuracy = round(
            (cal.baseline_accuracy * old_count + score_pct) / cal.sessions_completed,
            1,
        )
    else:
        # First session — initialise baseline to this score
        cal.baseline_accuracy = round(score_pct, 1)

    # Only set recommended difficulty after 3+ sessions
    if cal.sessions_completed >= 3:
        # Set recommended difficulty based on accuracy
        if cal.baseline_accuracy < 50:
            cal.recommended_difficulty = "easy"
        elif cal.baseline_accuracy <= 80:
            cal.recommended_difficulty = "medium"
        else:
            cal.recommended_difficulty = "challenging"

    db.commit()


def get_recommended_difficulty(
    db: Session, student_id: int, subject: str, topic: str
) -> str | None:
    """Get recommended difficulty from calibration, if available."""
    from app.models.ile_student_calibration import ILEStudentCalibration

    cal = (
        db.query(ILEStudentCalibration)
        .filter(
            ILEStudentCalibration.student_id == student_id,
            ILEStudentCalibration.subject == subject,
            ILEStudentCalibration.topic == topic,
        )
        .first()
    )
    if cal and cal.recommended_difficulty:
        return cal.recommended_difficulty
    return None


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

    Streak rules:
    - A streak is a run of consecutive questions answered correctly on the
      first attempt (attempt_number == 1 and is_correct == True).
    - A question answered correctly on a later attempt (multi-attempt correct)
      does NOT count toward the streak and breaks it.
    - A wrong answer on any attempt resets the streak to 0.
    - Counting walks backward from current_index toward question 0; the
      streak ends at the first question that doesn't meet the criteria.

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
    """Count consecutive first-attempt correct answers from pre-fetched attempts.

    Walks backward from *current_index* to 0.  A question contributes to the
    streak only if it has exactly one attempt and that attempt is correct
    (i.e., first-attempt correct).  Any other outcome (wrong, or correct on a
    retry) breaks the streak immediately.
    """
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
        started = session.started_at
        completed = session.completed_at
        # Normalize timezone awareness (SQLite returns naive, PG returns aware)
        if started.tzinfo is None and completed.tzinfo is not None:
            started = started.replace(tzinfo=timezone.utc)
        elif started.tzinfo is not None and completed.tzinfo is None:
            completed = completed.replace(tzinfo=timezone.utc)
        delta = completed - started
        return int(delta.total_seconds())
    return None


# ---------------------------------------------------------------------------
# Career Connect
# ---------------------------------------------------------------------------

# Pending parent hints: keyed by (session_id, question_index) → hint_note
# Applied and removed when submit_answer creates the attempt record.
_pending_parent_hints: dict[tuple[int, int], str] = {}

# In-memory cache keyed by session ID to avoid re-generating (bounded LRU)
_CAREER_CACHE_MAX = 500
_career_connect_cache: OrderedDict[int, dict] = OrderedDict()


async def get_career_connect(db: Session, session_id: int, user_id: int) -> dict:
    """Generate a career connection for a completed session.

    Returns { career: str, connection: str }.
    Caches results in memory to avoid re-generation.
    """
    # Check cache first (move to end on access for LRU ordering)
    if session_id in _career_connect_cache:
        _career_connect_cache.move_to_end(session_id)
        return _career_connect_cache[session_id]

    session = get_session(db, session_id, user_id)
    if session.status not in ("completed", "abandoned"):
        raise ValueError("Session is not completed")

    topic = session.topic
    subject = session.subject
    grade = session.grade_level or 8

    from app.services.ai_service import generate_content

    prompt = (
        f"Connect the topic '{topic}' (subject: {subject}) to a real career. "
        f"The student is in grade {grade}. "
        "Respond in exactly this JSON format: "
        '{"career": "<career name>", "connection": "<1-2 sentence explanation>"}\n'
        "Example: "
        '{"career": "Data Scientist", "connection": "Data scientists use statistics '
        'every day to find patterns in large datasets and make predictions."}\n'
        "Keep it grade-appropriate, inspiring, and concise."
    )

    try:
        content, _model = await generate_content(
            prompt=prompt,
            system_prompt="You are a career counselor for students. Respond only with valid JSON.",
            max_tokens=200,
            temperature=0.8,
        )
        # Parse JSON from response
        import re as _re
        # Extract JSON object from response (may be wrapped in markdown)
        match = _re.search(r'\{[^}]*"career"[^}]*\}', content)
        if match:
            result = json.loads(match.group())
            career = result.get("career", "")
            connection = result.get("connection", "")
        else:
            raise ValueError("No JSON found in AI response")
    except Exception:
        logger.warning("Career connect generation failed for session %d", session_id)
        # Fallback
        career = "Professional"
        connection = f"Many careers use {topic} skills from {subject} in their daily work."

    data = {"career": career, "connection": connection}
    # LRU eviction: move accessed/new entries to end, evict from front
    _career_connect_cache[session_id] = data
    _career_connect_cache.move_to_end(session_id)
    if len(_career_connect_cache) > _CAREER_CACHE_MAX:
        _career_connect_cache.popitem(last=False)
    return data


def _fetch_context_text(db: Session, course_content_id: int) -> str | None:
    """Fetch text content from a course content or its study guide.

    Tries course_content.text_content first, falls back to the latest
    study guide for that content. Truncates to 2000 chars.
    """
    from app.models.course_content import CourseContent
    from app.models.study_guide import StudyGuide

    cc = db.query(CourseContent).filter(CourseContent.id == course_content_id).first()
    if cc and cc.text_content:
        return cc.text_content[:2000]

    # Fallback: latest study guide linked to this content
    sg = (
        db.query(StudyGuide)
        .filter(StudyGuide.course_content_id == course_content_id)
        .order_by(StudyGuide.created_at.desc())
        .first()
    )
    if sg and sg.content:
        return sg.content[:2000]

    return None


def _estimate_session_cost(
    all_attempts: list,
    questions: list[dict],
) -> float:
    """Estimate AI cost in USD for a session.

    Heuristic based on typical token usage per AI call:
    - Question generation: ~2000 tokens out
    - Hint generation: ~200 tokens out
    - Explanation generation: ~300 tokens out

    Uses the model pricing from ai_service.
    """
    from app.services.ai_service import _calc_cost
    from app.core.config import settings

    model = settings.claude_model
    cost = 0.0

    # Question generation cost (one call per session)
    cost += float(_calc_cost(model, 500, 2000))

    # Hint costs (one per wrong attempt in learning/parent_teaching mode)
    hints_generated = sum(1 for a in all_attempts if a.hint_shown)
    cost += hints_generated * float(_calc_cost(model, 300, 200))

    # Explanation costs (one per correct answer or auto-reveal)
    explanations_generated = sum(1 for a in all_attempts if a.explanation_shown)
    cost += explanations_generated * float(_calc_cost(model, 200, 300))

    return round(cost, 6)
