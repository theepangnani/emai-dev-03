"""Quiz of the Day API routes (#2225)."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User
from app.schemas.daily_quiz import DailyQuizResponse, DailyQuizQuestion, DailyQuizSubmit, DailyQuizSubmitResponse
from app.services.daily_quiz_service import get_or_create_daily_quiz, submit_daily_quiz

router = APIRouter(prefix="/quiz-of-the-day", tags=["Quiz of the Day"])


def _to_response(quiz) -> DailyQuizResponse:
    """Convert DailyQuiz model to response schema."""
    questions = [DailyQuizQuestion(**q) for q in json.loads(quiz.quiz_data)]
    return DailyQuizResponse(
        id=quiz.id,
        user_id=quiz.user_id,
        quiz_date=quiz.quiz_date,
        questions=questions,
        total_questions=quiz.total_questions,
        score=quiz.score,
        percentage=quiz.percentage,
        completed_at=quiz.completed_at,
    )


@router.get("/", response_model=DailyQuizResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def get_quiz_of_the_day(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get today's Quiz of the Day. Auto-generates if not yet created."""
    try:
        quiz = await get_or_create_daily_quiz(db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate daily quiz: {e}")
    return _to_response(quiz)


@router.post("/submit", response_model=DailyQuizSubmitResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def submit_quiz_of_the_day(
    request: Request,
    data: DailyQuizSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit answers for today's Quiz of the Day."""
    try:
        result = submit_daily_quiz(db, current_user, data.answers)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return DailyQuizSubmitResponse(**result)
