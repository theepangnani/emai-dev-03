"""Public survey API endpoints (no auth required)."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.survey import SurveyResponse, SurveyAnswer
from app.models.user import User, UserRole
from app.models.notification import NotificationType
from app.schemas.survey import SurveySubmission, SurveyResponseOut
from app.services.survey_questions import get_questions_for_role, get_question_map_for_role, validate_answer, VALID_SURVEY_ROLES
from app.services.notification_service import send_multi_channel_notification
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/survey", tags=["Survey"])


@router.get("/questions/{role}")
def get_survey_questions(role: str):
    """Return survey question definitions for a given role."""
    if role not in VALID_SURVEY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invalid role '{role}'. Must be one of: {', '.join(sorted(VALID_SURVEY_ROLES))}",
        )
    questions = get_questions_for_role(role)
    return {"role": role, "questions": questions}


@router.post("", response_model=SurveyResponseOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
def submit_survey(
    data: SurveySubmission,
    request: Request,
    db: Session = Depends(get_db),
):
    """Submit a complete survey response. Public endpoint, no auth required."""
    role = data.role

    # Validate role
    if role not in VALID_SURVEY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{role}'. Must be one of: {', '.join(sorted(VALID_SURVEY_ROLES))}",
        )

    # Get question map for this role
    question_map = get_question_map_for_role(role)

    # Check all required questions are answered
    answered_keys = {a.question_key for a in data.answers}
    required_keys = {q["key"] for q in question_map.values() if q.get("required", True)}
    missing = required_keys - answered_keys
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required questions: {', '.join(sorted(missing))}",
        )

    # Validate each answer
    for answer in data.answers:
        # Check question_key belongs to this role's questions
        question = question_map.get(answer.question_key)
        if question is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Question '{answer.question_key}' does not belong to the '{role}' survey.",
            )

        # Validate answer value against question type
        if not validate_answer(question, answer.answer_value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid answer for question '{answer.question_key}'. Check value and type.",
            )

    # Check for duplicate session_id
    existing = db.query(SurveyResponse).filter(SurveyResponse.session_id == data.session_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A survey response with this session_id already exists.",
        )

    # Get client IP
    ip_address = request.client.host if request.client else None

    # Create SurveyResponse
    survey_response = SurveyResponse(
        session_id=data.session_id,
        role=role,
        ip_address=ip_address,
        completed=True,
    )
    db.add(survey_response)
    db.flush()  # Get the id for foreign key

    # Create SurveyAnswer rows
    for answer in data.answers:
        survey_answer = SurveyAnswer(
            response_id=survey_response.id,
            question_key=answer.question_key,
            question_type=answer.question_type,
            answer_value=answer.answer_value,
        )
        db.add(survey_answer)

    db.commit()
    db.refresh(survey_response)

    logger.info("Survey submitted: session_id=%s role=%s", data.session_id, role)

    # Best-effort admin notification
    try:
        admins = db.query(User).filter(User.role == UserRole.ADMIN).all()
        for admin in admins:
            try:
                send_multi_channel_notification(
                    db=db,
                    recipient=admin,
                    sender=None,
                    title="New Survey Response",
                    content=f"A {role} completed the pre-launch survey.",
                    notification_type=NotificationType.SURVEY_COMPLETED,
                    link="/admin/survey",
                    channels=["in_app", "email"],
                )
            except Exception as e:
                logger.warning("Failed to notify admin %s: %s", admin.id, e)
    except Exception as e:
        logger.warning("Failed to send survey admin notifications: %s", e)

    return survey_response
