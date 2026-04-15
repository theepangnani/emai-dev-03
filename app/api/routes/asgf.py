"""ASGF (AI Study Guide Factory) API routes."""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.logging_config import get_logger
from app.models.user import User
from app.schemas.asgf import IntentClassifyRequest, IntentClassifyResponse
from app.services import asgf_service

logger = get_logger(__name__)

router = APIRouter(prefix="/asgf", tags=["ASGF"])


@router.post("/classify-intent", response_model=IntentClassifyResponse)
async def classify_intent(
    body: IntentClassifyRequest,
    current_user: User = Depends(get_current_user),
):
    """Classify a question into subject, grade level, topic, and Bloom's tier."""
    return await asgf_service.classify_intent(body.question)
