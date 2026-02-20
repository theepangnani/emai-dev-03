import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func as sql_func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.quiz_result import QuizResult
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.user import User, UserRole
from app.schemas.quiz_result import (
    QuizHistoryStats,
    QuizResultCreate,
    QuizResultResponse,
    QuizResultSummary,
)

router = APIRouter(prefix="/quiz-results", tags=["Quiz Results"])


def _get_target_user_ids(
    db: Session, current_user: User, student_user_id: int | None = None
) -> list[int]:
    """Return the user_id(s) whose quiz results should be visible.

    - Students/teachers/admins see their own results.
    - Parents see their own results + linked children's results.
    """
    if not current_user.has_role(UserRole.PARENT):
        return [current_user.id]

    # Parent: always include own results + children's results
    target_ids = [current_user.id]

    rows = db.query(parent_students.c.student_id).filter(
        parent_students.c.parent_id == current_user.id
    ).all()
    child_student_ids = [r[0] for r in rows]
    if not child_student_ids:
        return target_ids

    if student_user_id:
        # Verify this child belongs to the parent
        child = db.query(Student).filter(
            Student.user_id == student_user_id,
            Student.id.in_(child_student_ids),
        ).first()
        if child:
            target_ids.append(student_user_id)
        return target_ids

    # All children's user_ids
    students = db.query(Student.user_id).filter(
        Student.id.in_(child_student_ids)
    ).all()
    target_ids.extend(s[0] for s in students)
    return target_ids


@router.post("/", response_model=QuizResultResponse, status_code=status.HTTP_201_CREATED)
def save_quiz_result(
    data: QuizResultCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    guide = db.query(StudyGuide).filter(StudyGuide.id == data.study_guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")
    if guide.guide_type != "quiz":
        raise HTTPException(status_code=400, detail="Study guide is not a quiz")

    # Auto-compute attempt number
    prev_count = (
        db.query(sql_func.count(QuizResult.id))
        .filter(
            QuizResult.user_id == current_user.id,
            QuizResult.study_guide_id == data.study_guide_id,
        )
        .scalar()
    )

    percentage = round((data.score / data.total_questions) * 100, 1) if data.total_questions > 0 else 0.0

    result = QuizResult(
        user_id=current_user.id,
        study_guide_id=data.study_guide_id,
        score=data.score,
        total_questions=data.total_questions,
        percentage=percentage,
        answers_json=json.dumps(data.answers, default=str),
        attempt_number=prev_count + 1,
        time_taken_seconds=data.time_taken_seconds,
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    resp = QuizResultResponse.model_validate(result)
    resp.quiz_title = guide.title
    return resp


@router.get("/", response_model=list[QuizResultSummary])
def list_quiz_results(
    study_guide_id: int | None = Query(None),
    student_user_id: int | None = Query(None, description="Filter by child (parent only)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target_ids = _get_target_user_ids(db, current_user, student_user_id)
    if not target_ids:
        return []

    query = (
        db.query(QuizResult, StudyGuide.title)
        .outerjoin(StudyGuide, QuizResult.study_guide_id == StudyGuide.id)
        .filter(QuizResult.user_id.in_(target_ids))
    )
    if study_guide_id is not None:
        query = query.filter(QuizResult.study_guide_id == study_guide_id)
    query = query.order_by(QuizResult.completed_at.desc())
    rows = query.offset(offset).limit(limit).all()

    results = []
    for qr, title in rows:
        summary = QuizResultSummary.model_validate(qr)
        summary.quiz_title = title
        results.append(summary)
    return results


@router.get("/stats", response_model=QuizHistoryStats)
def get_quiz_stats(
    student_user_id: int | None = Query(None, description="Filter by child (parent only)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target_ids = _get_target_user_ids(db, current_user, student_user_id)
    if not target_ids:
        return QuizHistoryStats(
            total_attempts=0,
            unique_quizzes=0,
            average_score=0.0,
            best_score=0.0,
            recent_trend="stable",
        )

    base = db.query(QuizResult).filter(QuizResult.user_id.in_(target_ids))

    total_attempts = base.count()
    if total_attempts == 0:
        return QuizHistoryStats(
            total_attempts=0,
            unique_quizzes=0,
            average_score=0.0,
            best_score=0.0,
            recent_trend="stable",
        )

    unique_quizzes = (
        db.query(sql_func.count(sql_func.distinct(QuizResult.study_guide_id)))
        .filter(QuizResult.user_id.in_(target_ids))
        .scalar()
    )
    average_score = (
        db.query(sql_func.avg(QuizResult.percentage))
        .filter(QuizResult.user_id.in_(target_ids))
        .scalar()
    ) or 0.0
    best_score = (
        db.query(sql_func.max(QuizResult.percentage))
        .filter(QuizResult.user_id.in_(target_ids))
        .scalar()
    ) or 0.0

    # Trend: compare average of last 5 vs previous 5
    recent = (
        base.order_by(QuizResult.completed_at.desc()).limit(5).all()
    )
    recent_avg = sum(r.percentage for r in recent) / len(recent) if recent else 0

    prev = (
        base.order_by(QuizResult.completed_at.desc()).offset(5).limit(5).all()
    )
    prev_avg = sum(r.percentage for r in prev) / len(prev) if prev else recent_avg

    diff = recent_avg - prev_avg
    if diff > 3:
        trend = "improving"
    elif diff < -3:
        trend = "declining"
    else:
        trend = "stable"

    return QuizHistoryStats(
        total_attempts=total_attempts,
        unique_quizzes=unique_quizzes,
        average_score=round(average_score, 1),
        best_score=round(best_score, 1),
        recent_trend=trend,
    )


@router.get("/{result_id}", response_model=QuizResultResponse)
def get_quiz_result(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = db.query(QuizResult).filter(
        QuizResult.id == result_id,
        QuizResult.user_id == current_user.id,
    ).first()
    if not result:
        raise HTTPException(status_code=404, detail="Quiz result not found")

    guide = db.query(StudyGuide).filter(StudyGuide.id == result.study_guide_id).first()
    resp = QuizResultResponse.model_validate(result)
    resp.quiz_title = guide.title if guide else None
    return resp


@router.delete("/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quiz_result(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = db.query(QuizResult).filter(
        QuizResult.id == result_id,
        QuizResult.user_id == current_user.id,
    ).first()
    if not result:
        raise HTTPException(status_code=404, detail="Quiz result not found")
    db.delete(result)
    db.commit()
