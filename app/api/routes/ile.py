"""Interactive Learning Engine (Flash Tutor) API routes — CB-ILE-001."""
import asyncio
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from starlette.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.logging_config import get_logger
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student, parent_students
from app.schemas.ile import (
    ILEAdminAnalytics,
    ILEAnswerFeedback,
    ILEAnswerSubmit,
    ILECareerConnect,
    ILECurrentQuestion,
    ILEDailySessionCount,
    ILEMasteryEntry,
    ILEMasteryMap,
    ILEParentHintResponse,
    ILEParentHintSubmit,
    ILEModeSplit,
    ILEQuestion,
    ILEQuestionOption,
    ILESessionCreate,
    ILESessionResponse,
    ILESessionResults,
    ILESessionSummary,
    ILESurpriseMe,
    ILETopic,
    ILETopicList,
    ILETopTopic,
)
from app.models.ile_session import ILESession
from app.models.ile_topic_mastery import ILETopicMastery
from app.services import ile_service
from app.services import ile_mastery_service
from app.services import ile_question_service
from app.services.ile_mastery_service import compute_glow_intensity
from app.services import ile_cost_optimizer
from app.services import ile_surprise_service

logger = get_logger(__name__)

router = APIRouter(prefix="/ile", tags=["Interactive Learning Engine"])

# ---------------------------------------------------------------------------
# Simple in-memory TTL cache for mastery/topic data (#3217)
# ---------------------------------------------------------------------------

_CACHE_TTL = 60  # seconds
_cache: dict[str, tuple[float, object]] = {}


def _cache_get(key: str) -> object | None:
    """Return cached value if still fresh, else None."""
    entry = _cache.get(key)
    if entry and time.monotonic() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None


_CACHE_MAX_SIZE = 1000


def _cache_set(key: str, value: object) -> None:
    # Lazy eviction: purge expired entries when cache grows too large
    if len(_cache) >= _CACHE_MAX_SIZE:
        now = time.monotonic()
        expired = [k for k, (t, _) in _cache.items() if now - t >= _CACHE_TTL]
        for k in expired:
            del _cache[k]
        # If still too large, drop oldest entries
        if len(_cache) >= _CACHE_MAX_SIZE:
            oldest = sorted(_cache, key=lambda k: _cache[k][0])[:len(_cache) // 2]
            for k in oldest:
                del _cache[k]
    _cache[key] = (time.monotonic(), value)


def _cache_invalidate_user(user_id: int) -> None:
    """Invalidate all cache entries for a specific user."""
    prefix = f"mastery:{user_id}:"
    keys = [k for k in _cache if k.startswith(prefix) or k == f"topics:{user_id}"]
    for k in keys:
        _cache.pop(k, None)


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=ILESessionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def create_session(
    request: Request,
    body: ILESessionCreate,
    stream: bool = Query(False, description="Return SSE stream with progress events"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new Flash Tutor session.

    When ``stream=true``, returns an SSE ``text/event-stream`` with events:

    * ``start`` — ``{session_id, question_count}``
    * ``question`` — ``{index, total}`` (emitted per question)
    * ``done`` — ``{session_id}``
    * ``error`` — ``{message}`` (on failure)
    """
    student_id = current_user.id
    parent_id = None

    # Parent Teaching Mode: parent creates session for child
    if body.mode == "parent_teaching":
        if not current_user.has_role(UserRole.PARENT):
            raise HTTPException(403, "Only parents can use Parent Teaching Mode")
        if not body.child_student_id:
            raise HTTPException(400, "child_student_id required for Parent Teaching Mode")
        # Verify parent-child relationship
        child_student_ids = [
            r[0] for r in
            db.query(parent_students.c.student_id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        ]
        child = (
            db.query(Student)
            .filter(
                Student.user_id == body.child_student_id,
                Student.id.in_(child_student_ids),
            )
            .first()
        )
        if not child:
            raise HTTPException(403, "Child not linked to this parent")
        student_id = body.child_student_id
        parent_id = current_user.id

    # --- Non-streaming path (default) — unchanged behaviour ----------------
    if not stream:
        try:
            session = await ile_service.create_session(
                db=db,
                student_id=student_id,
                mode=body.mode,
                subject=body.subject,
                topic=body.topic,
                question_count=body.question_count,
                difficulty=body.difficulty,
                blooms_tier=body.blooms_tier,
                grade_level=body.grade_level,
                timer_enabled=body.timer_enabled,
                timer_seconds=body.timer_seconds,
                is_private_practice=body.is_private_practice,
                course_id=body.course_id,
                course_content_id=body.course_content_id,
                parent_id=parent_id,
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

        return session

    # --- Streaming path (stream=true) — SSE progress events ----------------
    from datetime import datetime, timedelta, timezone
    from app.services.ile_service import (
        MAX_SESSIONS_PER_DAY, SESSION_EXPIRY_HOURS,
        _utc_now_comparable,
    )
    from app.services.ile_service import get_recommended_difficulty
    from app.services.ile_service import _fetch_context_text
    from sqlalchemy import func as sa_func

    # --- Inline validation (mirrors ile_service.create_session) ---

    VALID_DIFFICULTIES = {"easy", "medium", "challenging"}
    VALID_BLOOMS = {"recall", "understand", "apply"}

    difficulty = body.difficulty or "medium"
    blooms_tier = body.blooms_tier or "recall"

    if difficulty not in VALID_DIFFICULTIES:
        raise HTTPException(400, f"Invalid difficulty: {difficulty}. Must be one of {VALID_DIFFICULTIES}")
    if blooms_tier not in VALID_BLOOMS:
        raise HTTPException(400, f"Invalid blooms_tier: {blooms_tier}. Must be one of {VALID_BLOOMS}")

    # Check for existing active session
    active = (
        db.query(ILESession)
        .filter(ILESession.student_id == student_id, ILESession.status == "in_progress")
        .first()
    )
    if active:
        now_cmp = _utc_now_comparable(active.expires_at)
        if active.expires_at and active.expires_at < now_cmp:
            active.status = "expired"
            db.commit()
        else:
            raise HTTPException(
                400,
                f"Active session {active.id} already exists. Complete or abandon it first.",
            )

    # Daily limit
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    sessions_today = (
        db.query(sa_func.count(ILESession.id))
        .filter(ILESession.student_id == student_id, ILESession.created_at >= today_start)
        .scalar()
    )
    if sessions_today >= MAX_SESSIONS_PER_DAY:
        raise HTTPException(
            400,
            f"Daily session limit reached ({MAX_SESSIONS_PER_DAY} sessions per day). Please try again tomorrow.",
        )

    # Calibrated difficulty
    effective_difficulty = difficulty
    if effective_difficulty == "medium":
        try:
            recommended = get_recommended_difficulty(db, student_id, body.subject, body.topic)
            if recommended:
                effective_difficulty = recommended
        except Exception:
            pass

    # Format escalation
    question_format = ile_question_service.check_format_escalation(
        db, student_id, body.subject, body.topic,
    )

    # Context text
    context_text = None
    if body.course_content_id:
        context_text = _fetch_context_text(db, body.course_content_id)

    question_count = body.question_count or 5
    grade_level = body.grade_level or 8

    # Create session record with empty questions (in_progress)
    now = datetime.now(timezone.utc)
    session = ILESession(
        student_id=student_id,
        parent_id=parent_id,
        mode=body.mode,
        subject=body.subject,
        topic=body.topic,
        grade_level=body.grade_level,
        question_count=question_count,
        difficulty=effective_difficulty,
        blooms_tier=blooms_tier,
        timer_enabled=body.timer_enabled,
        timer_seconds=body.timer_seconds,
        is_private_practice=body.is_private_practice,
        status="in_progress",
        current_question_index=0,
        questions_json="[]",
        course_id=body.course_id,
        course_content_id=body.course_content_id,
        started_at=now,
        expires_at=now + timedelta(hours=SESSION_EXPIRY_HOURS),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    session_id = session.id

    # Capture generation params before closing DB
    gen_params = {
        "subject": body.subject,
        "topic": body.topic,
        "difficulty": effective_difficulty,
        "question_count": question_count,
        "grade_level": grade_level,
        "format_type": question_format,
        "blooms_tier": blooms_tier,
        "context_text": context_text,
    }

    db.close()

    async def event_stream():
        yield f"event: start\ndata: {json.dumps({'session_id': session_id, 'question_count': gen_params['question_count']})}\n\n"

        try:
            from app.db.database import SessionLocal
            gen_db = SessionLocal()
            try:
                questions = await ile_question_service.get_from_bank_or_generate(
                    db=gen_db,
                    subject=gen_params["subject"],
                    topic=gen_params["topic"],
                    grade_level=gen_params["grade_level"],
                    difficulty=gen_params["difficulty"],
                    blooms_tier=gen_params["blooms_tier"],
                    count=gen_params["question_count"],
                    question_format=gen_params["format_type"],
                    context_text=gen_params.get("context_text"),
                )

                for i, _q in enumerate(questions):
                    yield f"event: question\ndata: {json.dumps({'index': i, 'total': len(questions)})}\n\n"

                # Save questions to session
                sess = gen_db.query(ILESession).get(session_id)
                if sess:
                    sess.questions_json = json.dumps([
                        {k: v for k, v in q.items() if not k.startswith("_")}
                        for q in questions
                    ])
                    sess.question_count = len(questions)
                    gen_db.commit()

                yield f"event: done\ndata: {json.dumps({'session_id': session_id})}\n\n"
            finally:
                gen_db.close()
        except Exception as e:
            logger.error("Streaming question generation failed: %s: %s", type(e).__name__, e)
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/sessions/from-study-guide", response_model=ILESessionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def create_session_from_study_guide(
    request: Request,
    study_guide_id: int | None = None,
    course_content_id: int | None = None,
    mode: str = "learning",
    question_count: int = 5,
    difficulty: str = "medium",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a Flash Tutor session grounded in a study guide or course content."""
    from app.models.study_guide import StudyGuide as StudyGuideModel
    from app.models.course_content import CourseContent

    if not study_guide_id and not course_content_id:
        raise HTTPException(400, "Provide study_guide_id or course_content_id")

    subject = ""
    topic = ""

    if study_guide_id:
        sg = db.query(StudyGuideModel).filter(StudyGuideModel.id == study_guide_id).first()
        if not sg:
            raise HTTPException(404, "Study guide not found")
        # Verify ownership: user must own the guide or have it shared with them
        if sg.user_id != current_user.id and sg.shared_with_user_id != current_user.id:
            raise HTTPException(403, "Not authorized to use this study guide")
        course_content_id = sg.course_content_id or course_content_id
        # Derive subject/topic from the study guide
        if sg.course_id:
            from app.models.course import Course
            course = db.query(Course).filter(Course.id == sg.course_id).first()
            subject = course.name if course else sg.title
        else:
            subject = sg.title
        topic = sg.title

    if course_content_id and not subject:
        cc = db.query(CourseContent).filter(CourseContent.id == course_content_id).first()
        if not cc:
            raise HTTPException(404, "Course content not found")
        subject = cc.course_name or cc.title
        topic = cc.title

    try:
        session = await ile_service.create_session(
            db=db,
            student_id=current_user.id,
            mode=mode,
            subject=subject,
            topic=topic,
            question_count=question_count,
            difficulty=difficulty,
            course_content_id=course_content_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return session


@router.get("/sessions/active", response_model=ILESessionResponse | None)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_active_session(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current active (in_progress) session, if any."""
    session = ile_service.get_active_session(db, current_user.id)
    return session


@router.get("/sessions/{session_id}", response_model=ILESessionResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_session(
    request: Request,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get session details by ID."""
    try:
        session = ile_service.get_session(db, session_id, current_user.id)
    except ValueError:
        raise HTTPException(404, "Session not found")
    except PermissionError:
        raise HTTPException(403, "Not authorized")
    return session


# ---------------------------------------------------------------------------
# Question & Answer
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/question", response_model=ILECurrentQuestion)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
async def get_current_question(
    request: Request,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current question for a session."""
    try:
        session = ile_service.get_session(db, session_id, current_user.id)
    except ValueError:
        raise HTTPException(404, "Session not found")
    except PermissionError:
        raise HTTPException(403, "Not authorized")

    if session.status != "in_progress":
        raise HTTPException(400, "Session is not in progress")

    try:
        q = ile_service.get_current_question(session)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Get attempt history for this question (Learning Mode: disabled options)
    prev_attempts = ile_service.get_attempt_history(db, session.id, q["index"])
    disabled_options = [
        a.selected_answer for a in prev_attempts if not a.is_correct
    ]

    options = None
    if q.get("options"):
        opts = q["options"]
        if isinstance(opts, dict):
            options = ILEQuestionOption(**opts)

    return ILECurrentQuestion(
        session_id=session.id,
        question=ILEQuestion(
            index=q["index"],
            question=q["question"],
            options=options,
            format=q.get("format", "mcq"),
            difficulty=q.get("difficulty", session.difficulty),
            blooms_tier=q.get("blooms_tier", session.blooms_tier),
        ),
        question_index=q["index"],
        total_questions=session.question_count,
        mode=session.mode,
        attempt_number=len(prev_attempts) + 1,
        disabled_options=disabled_options,
        streak_count=0,
    )


@router.post("/sessions/{session_id}/answer", response_model=ILEAnswerFeedback)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def submit_answer(
    request: Request,
    session_id: int,
    body: ILEAnswerSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit an answer for the current question."""
    try:
        session = ile_service.get_session(db, session_id, current_user.id)
    except ValueError:
        raise HTTPException(404, "Session not found")
    except PermissionError:
        raise HTTPException(403, "Not authorized")

    try:
        result = await ile_service.submit_answer(
            db=db,
            session=session,
            answer=body.answer,
            time_taken_ms=body.time_taken_ms,
            parent_hint_note=body.parent_hint_note,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return ILEAnswerFeedback(**result)


# ---------------------------------------------------------------------------
# Parent Teaching Mode
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/parent-hint", response_model=ILEParentHintResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def add_parent_hint(
    request: Request,
    session_id: int,
    body: ILEParentHintSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a parent hint note for the current question (parent_teaching mode only)."""
    try:
        session = ile_service.get_session(db, session_id, current_user.id)
    except ValueError:
        raise HTTPException(404, "Session not found")
    except PermissionError:
        raise HTTPException(403, "Not authorized")

    try:
        result = ile_service.add_parent_hint(db, session, body.hint_note)
    except ValueError as e:
        if "Parent Teaching Mode" in str(e) or "parent_teaching" in str(e):
            raise HTTPException(403, str(e))
        raise HTTPException(400, str(e))

    return ILEParentHintResponse(**result)


# ---------------------------------------------------------------------------
# Session completion
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/complete", response_model=ILESessionResults)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def complete_session(
    request: Request,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Complete a session and get results."""
    try:
        session = ile_service.get_session(db, session_id, current_user.id)
    except ValueError:
        raise HTTPException(404, "Session not found")
    except PermissionError:
        raise HTTPException(403, "Not authorized")

    try:
        results = await ile_service.complete_session(db, session)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Invalidate mastery/topic cache after session completion (#3217)
    _cache_invalidate_user(current_user.id)

    return ILESessionResults(**results)


@router.post("/sessions/{session_id}/abandon", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def abandon_session(
    request: Request,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Abandon a session, preserving progress."""
    try:
        session = ile_service.get_session(db, session_id, current_user.id)
    except ValueError:
        raise HTTPException(404, "Session not found")
    except PermissionError:
        raise HTTPException(403, "Not authorized")

    try:
        ile_service.abandon_session(db, session)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/sessions/{session_id}/results", response_model=ILESessionResults)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_session_results(
    request: Request,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get results for a completed session."""
    try:
        session = ile_service.get_session(db, session_id, current_user.id)
    except ValueError:
        raise HTTPException(404, "Session not found")
    except PermissionError:
        raise HTTPException(403, "Not authorized")

    if session.status not in ("completed", "abandoned"):
        raise HTTPException(400, "Session is not completed")

    # Reconstruct results from stored attempts without mutating state (#3225)
    results = ile_service.get_session_results_from_attempts(db, session)
    if not results:
        raise HTTPException(400, "No results available")
    return ILESessionResults(**results)


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

@router.get("/topics", response_model=ILETopicList)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_topics(
    request: Request,
    student_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List available topics from student's courses.

    Parents can pass ``student_id`` to view a child's topics.
    """
    target_id = current_user.id

    if student_id and student_id != current_user.id:
        # Parent viewing child's topics — verify relationship
        if not current_user.has_role(UserRole.PARENT):
            raise HTTPException(403, "Only parents can view another student's topics")
        child_student_ids = [
            r[0] for r in
            db.query(parent_students.c.student_id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        ]
        child = (
            db.query(Student)
            .filter(
                Student.user_id == student_id,
                Student.id.in_(child_student_ids),
            )
            .first()
        )
        if not child:
            raise HTTPException(403, "Child not linked to this parent")
        target_id = student_id

    cache_key = f"topics:{target_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    topics_data = ile_service.get_available_topics(db, target_id)
    topics = [ILETopic(**t) for t in topics_data]
    result = ILETopicList(topics=topics)
    _cache_set(cache_key, result)
    return result


@router.get("/topics/surprise-me", response_model=ILESurpriseMe)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def surprise_me(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pick a topic for Surprise Me, weighted by weak areas."""
    try:
        result = ile_surprise_service.get_surprise_topic(db, current_user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ILESurpriseMe(
        topic=ILETopic(**result["topic"]),
        reason=result["reason"],
    )


# ---------------------------------------------------------------------------
# Mastery
# ---------------------------------------------------------------------------

@router.get("/mastery", response_model=ILEMasteryMap)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_mastery_map(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the student's mastery map with glow intensities."""
    cache_key = f"mastery:{current_user.id}:map"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    entries = (
        db.query(ILETopicMastery)
        .filter(ILETopicMastery.student_id == current_user.id)
        .order_by(ILETopicMastery.last_session_at.desc())
        .all()
    )

    mastery_entries = []
    mastered_count = 0
    weak_count = 0

    for e in entries:
        glow = compute_glow_intensity(e.next_review_at)
        mastery_entries.append(ILEMasteryEntry(
            subject=e.subject,
            topic=e.topic,
            total_sessions=e.total_sessions,
            avg_attempts=e.avg_attempts_per_question or 0.0,
            is_weak_area=e.is_weak_area,
            current_difficulty=e.current_difficulty,
            last_score_pct=e.last_score_pct,
            next_review_at=e.next_review_at,
            glow_intensity=glow,
        ))
        if e.is_weak_area:
            weak_count += 1
        elif (e.last_score_pct or 0) >= 80:
            mastered_count += 1

    result = ILEMasteryMap(
        student_id=current_user.id,
        entries=mastery_entries,
        total_topics=len(entries),
        mastered_topics=mastered_count,
        weak_topics=weak_count,
    )
    _cache_set(cache_key, result)
    return result


@router.get("/mastery/weak-areas", response_model=list[ILEMasteryEntry])
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_weak_areas(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get topics flagged as weak areas."""
    entries = ile_mastery_service.get_weak_areas(db, current_user.id)
    return [
        ILEMasteryEntry(
            subject=m.subject,
            topic=m.topic,
            total_sessions=m.total_sessions,
            avg_attempts=m.avg_attempts_per_question,
            is_weak_area=m.is_weak_area,
            current_difficulty=m.current_difficulty,
            last_score_pct=m.last_score_pct,
            next_review_at=m.next_review_at,
        )
        for m in entries
    ]


# ---------------------------------------------------------------------------
# Session History
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=list[ILESessionSummary])
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_session_history(
    request: Request,
    limit: int = 20,
    student_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get recent session history.

    Parents can pass ``student_id`` to view a child's sessions; private
    practice sessions are automatically excluded from parent views.
    """
    target_id = current_user.id
    exclude_private = False

    if student_id and student_id != current_user.id:
        # Parent viewing child's sessions — verify relationship
        if not current_user.has_role(UserRole.PARENT):
            raise HTTPException(403, "Only parents can view another student's sessions")
        child_student_ids = [
            r[0] for r in
            db.query(parent_students.c.student_id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        ]
        child = (
            db.query(Student)
            .filter(
                Student.user_id == student_id,
                Student.id.in_(child_student_ids),
            )
            .first()
        )
        if not child:
            raise HTTPException(403, "Child not linked to this parent")
        target_id = student_id
        exclude_private = True

    sessions = ile_service.get_session_history(
        db, target_id, limit, exclude_private=exclude_private,
    )
    return [
        ILESessionSummary(
            id=s.id,
            mode=s.mode,
            subject=s.subject,
            topic=s.topic,
            status=s.status,
            score=s.score,
            question_count=s.question_count,
            total_correct=s.total_correct,
            xp_awarded=s.xp_awarded,
            started_at=s.started_at,
            completed_at=s.completed_at,
        )
        for s in sessions
    ]


# ---------------------------------------------------------------------------
# Career Connect
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/career-connect", response_model=ILECareerConnect)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def get_career_connect(
    request: Request,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a career connection for a completed session."""
    try:
        result = await ile_service.get_career_connect(db, session_id, current_user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except PermissionError:
        raise HTTPException(403, "Not authorized")
    return ILECareerConnect(**result)


# ---------------------------------------------------------------------------
# Knowledge Decay
# ---------------------------------------------------------------------------

@router.get("/mastery/decaying")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_decaying_topics(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get topics past their review date for the current student."""
    from app.services.ile_mastery_service import get_decaying_topics as _get_decaying
    return _get_decaying(db, current_user.id)


# ---------------------------------------------------------------------------
# Admin — Question Bank Management
# ---------------------------------------------------------------------------

@router.post("/admin/prefill-bank")
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def admin_prefill_bank(
    request: Request,
    subject: str,
    topic: str,
    grade_level: int,
    difficulty: str = "medium",
    count: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Trigger bank prefill for a specific topic (admin only)."""
    added = await ile_cost_optimizer.prefill_question_bank(
        db, subject, topic, grade_level, difficulty, count,
    )
    return {"added": added, "subject": subject, "topic": topic, "grade_level": grade_level}


@router.post("/admin/cleanup-bank")
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def admin_cleanup_bank(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Trigger cleanup of expired and flagged questions (admin only)."""
    removed = ile_cost_optimizer.cleanup_expired_bank(db)
    return {"removed": removed}


@router.get("/admin/bank-stats")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def admin_bank_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Return question bank statistics (admin only)."""
    return ile_cost_optimizer.get_bank_stats(db)


@router.post("/admin/decay-notifications")
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def admin_send_decay_notifications(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Trigger knowledge decay notifications for all students (admin only)."""
    from app.services.ile_mastery_service import send_decay_notifications
    sent = send_decay_notifications(db)
    return {"notifications_sent": sent}


@router.get("/admin/analytics", response_model=ILEAdminAnalytics)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def admin_analytics(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Return ILE analytics dashboard data (admin only) (#3216)."""
    from sqlalchemy import func as sa_func, cast, Date
    from app.models.ile_session import ILESession
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Sessions per day (last 30 days)
    is_sqlite = "sqlite" in str(db.bind.url) if db.bind else False
    if is_sqlite:
        date_expr = sa_func.date(ILESession.created_at)
    else:
        date_expr = cast(ILESession.created_at, Date)

    daily_rows = (
        db.query(date_expr.label("day"), sa_func.count(ILESession.id))
        .filter(ILESession.created_at >= thirty_days_ago)
        .group_by("day")
        .order_by(date_expr)
        .all()
    )
    sessions_per_day = [
        ILEDailySessionCount(date=str(row[0]), count=row[1])
        for row in daily_rows
    ]

    # Total and completed sessions
    total_sessions = (
        db.query(sa_func.count(ILESession.id))
        .filter(ILESession.created_at >= thirty_days_ago)
        .scalar() or 0
    )
    completed_sessions = (
        db.query(sa_func.count(ILESession.id))
        .filter(
            ILESession.created_at >= thirty_days_ago,
            ILESession.status == "completed",
        )
        .scalar() or 0
    )
    completion_rate = round(
        (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0, 1
    )

    # Average score (completed sessions only)
    avg_score_row = (
        db.query(sa_func.avg(ILESession.score))
        .filter(
            ILESession.created_at >= thirty_days_ago,
            ILESession.status == "completed",
            ILESession.score.isnot(None),
        )
        .scalar()
    )
    average_score = round(float(avg_score_row), 2) if avg_score_row is not None else None

    # COMMENTED OUT: ai_cost_estimate column not yet in production DB (#3300)
    # avg_cost_row = (
    #     db.query(sa_func.avg(ILESession.ai_cost_estimate))
    #     .filter(
    #         ILESession.created_at >= thirty_days_ago,
    #         ILESession.ai_cost_estimate.isnot(None),
    #     )
    #     .scalar()
    # )
    # average_cost = round(float(avg_cost_row), 6) if avg_cost_row is not None else None
    average_cost = None

    # Mode split
    mode_rows = (
        db.query(ILESession.mode, sa_func.count(ILESession.id))
        .filter(ILESession.created_at >= thirty_days_ago)
        .group_by(ILESession.mode)
        .all()
    )
    mode_split = [ILEModeSplit(mode=row[0], count=row[1]) for row in mode_rows]

    # Top topics by session count
    topic_rows = (
        db.query(ILESession.topic, sa_func.count(ILESession.id))
        .filter(ILESession.created_at >= thirty_days_ago)
        .group_by(ILESession.topic)
        .order_by(sa_func.count(ILESession.id).desc())
        .limit(10)
        .all()
    )
    top_topics = [ILETopTopic(topic=row[0], count=row[1]) for row in topic_rows]

    # COMMENTED OUT: flagged_reason column not yet in production DB (#3300)
    # flagged_sessions = (
    #     db.query(sa_func.count(ILESession.id))
    #     .filter(
    #         ILESession.created_at >= thirty_days_ago,
    #         ILESession.flagged_reason.isnot(None),
    #     )
    #     .scalar() or 0
    # )
    flagged_sessions = 0

    return ILEAdminAnalytics(
        sessions_per_day=sessions_per_day,
        total_sessions=total_sessions,
        completed_sessions=completed_sessions,
        completion_rate=completion_rate,
        average_score=average_score,
        average_cost_per_session=average_cost,
        mode_split=mode_split,
        top_topics=top_topics,
        flagged_sessions=flagged_sessions,
    )
