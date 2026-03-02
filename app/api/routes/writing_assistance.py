"""Writing Assistance API routes.

Routes:
  POST  /api/writing/analyze              — analyze essay, get feedback + score + improved version
  POST  /api/writing/improve              — apply specific improvement instruction
  GET   /api/writing/sessions             — list user's writing sessions
  GET   /api/writing/sessions/{id}        — get full session
  GET   /api/writing/templates            — list writing templates
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_feature, require_role
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.writing_assistance import (
    WritingAnalysisRequest,
    WritingAnalysisResponse,
    WritingImproveRequest,
    WritingImproveResponse,
    WritingSessionDetail,
    WritingSessionSummary,
    WritingTemplateResponse,
)
from app.services import writing_assistance as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/writing", tags=["writing-assistance"])

# Any authenticated user can use the writing assistant
_any_user = get_current_user


@router.post("/analyze", response_model=WritingAnalysisResponse)
async def analyze_writing(
    body: WritingAnalysisRequest,
    _flag=Depends(require_feature("ai_writing_assistant")),
    current_user: User = Depends(_any_user),
    db: Session = Depends(get_db),
) -> WritingAnalysisResponse:
    """Analyze a piece of student writing.

    Returns an overall score, itemized feedback (grammar, clarity, structure,
    argumentation, vocabulary), and an AI-improved version of the text.
    """
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    return await svc.analyze_writing(
        user_id=current_user.id,
        text=body.text,
        title=body.title,
        db=db,
        course_id=body.course_id,
        assignment_type=body.assignment_type or "essay",
    )


@router.post("/improve", response_model=WritingImproveResponse)
async def improve_writing(
    body: WritingImproveRequest,
    _flag=Depends(require_feature("ai_writing_assistant")),
    current_user: User = Depends(_any_user),
    db: Session = Depends(get_db),
) -> WritingImproveResponse:
    """Apply a specific improvement instruction to a previous writing session.

    The result is returned but NOT saved — the user can review and choose to apply it.
    """
    if not body.instruction or not body.instruction.strip():
        raise HTTPException(status_code=400, detail="Instruction cannot be empty")

    return await svc.improve_writing(
        session_id=body.session_id,
        user_id=current_user.id,
        instruction=body.instruction,
        db=db,
    )


@router.get("/sessions", response_model=list[WritingSessionSummary])
def list_sessions(
    _flag=Depends(require_feature("ai_writing_assistant")),
    current_user: User = Depends(_any_user),
    db: Session = Depends(get_db),
) -> list[WritingSessionSummary]:
    """List all writing sessions for the current user (summary only, no full text)."""
    return svc.get_sessions(user_id=current_user.id, db=db)


@router.get("/sessions/{session_id}", response_model=WritingSessionDetail)
def get_session(
    session_id: int,
    _flag=Depends(require_feature("ai_writing_assistant")),
    current_user: User = Depends(_any_user),
    db: Session = Depends(get_db),
) -> WritingSessionDetail:
    """Get the full writing session including original text, improved text, and feedback."""
    return svc.get_session(session_id=session_id, user_id=current_user.id, db=db)


@router.get("/templates", response_model=list[WritingTemplateResponse])
def list_templates(
    _flag=Depends(require_feature("ai_writing_assistant")),
    current_user: User = Depends(_any_user),
    db: Session = Depends(get_db),
) -> list[WritingTemplateResponse]:
    """List all active writing templates."""
    return svc.get_templates(db=db)
