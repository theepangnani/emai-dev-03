"""Interactive Learning Engine (Flash Tutor) API routes — CB-ILE-001."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student, parent_students
from app.schemas.ile import (
    ILEAnswerFeedback,
    ILEAnswerSubmit,
    ILECurrentQuestion,
    ILEQuestion,
    ILEQuestionOption,
    ILESessionCreate,
    ILESessionResponse,
    ILESessionResults,
    ILESessionSummary,
    ILESurpriseMe,
    ILETopic,
    ILETopicList,
)
from app.services import ile_service
from app.services import ile_surprise_service

router = APIRouter(prefix="/ile", tags=["Interactive Learning Engine"])


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=ILESessionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def create_session(
    request: Request,
    body: ILESessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new Flash Tutor session."""
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
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return ILEAnswerFeedback(**result)


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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List available topics from student's courses."""
    topics_data = ile_service.get_available_topics(db, current_user.id)
    topics = [ILETopic(**t) for t in topics_data]
    return ILETopicList(topics=topics)


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
# Session History
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=list[ILESessionSummary])
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_session_history(
    request: Request,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get recent session history."""
    sessions = ile_service.get_session_history(db, current_user.id, limit)
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
