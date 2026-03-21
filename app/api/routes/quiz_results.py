import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func as sql_func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.course import student_courses
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
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def save_quiz_result(
    request: Request,
    data: QuizResultCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    guide = db.query(StudyGuide).filter(StudyGuide.id == data.study_guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")
    if guide.guide_type != "quiz":
        raise HTTPException(status_code=400, detail="Study guide is not a quiz")

    # Determine which user_id to attribute the result to
    target_user_id = current_user.id
    if current_user.has_role(UserRole.PARENT):
        # Get parent's linked children
        rows = db.query(parent_students.c.student_id).filter(
            parent_students.c.parent_id == current_user.id
        ).all()
        child_student_ids = [r[0] for r in rows]

        if data.student_user_id and child_student_ids:
            # Explicit child specified — verify it belongs to parent
            child = db.query(Student).filter(
                Student.user_id == data.student_user_id,
                Student.id.in_(child_student_ids),
            ).first()
            if child:
                target_user_id = data.student_user_id
        elif child_student_ids and guide.course_id:
            # Auto-resolve: find which child is enrolled in this quiz's course
            enrolled_child = (
                db.query(Student.user_id)
                .join(student_courses, Student.id == student_courses.c.student_id)
                .filter(
                    student_courses.c.course_id == guide.course_id,
                    Student.id.in_(child_student_ids),
                )
                .first()
            )
            if enrolled_child:
                target_user_id = enrolled_child[0]

    # Auto-compute attempt number
    prev_count = (
        db.query(sql_func.count(QuizResult.id))
        .filter(
            QuizResult.user_id == target_user_id,
            QuizResult.study_guide_id == data.study_guide_id,
        )
        .scalar()
    )

    percentage = round((data.score / data.total_questions) * 100, 1) if data.total_questions > 0 else 0.0

    result = QuizResult(
        user_id=target_user_id,
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

    # Award XP for quiz completion (non-blocking)
    try:
        from app.services.xp_service import XpService
        XpService.award_xp(db, target_user_id, "quiz_complete")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"XP award failed (non-blocking): {e}")

    resp = QuizResultResponse.model_validate(result)
    resp.quiz_title = guide.title
    return resp


@router.get("/", response_model=list[QuizResultSummary])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_quiz_results(
    request: Request,
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
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_quiz_stats(
    request: Request,
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


@router.get("/resolve-student")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def resolve_student_for_quiz(
    request: Request,
    course_id: int | None = Query(None),
    study_guide_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """For parents: resolve which child is enrolled in the given course.

    Non-parents get back their own info. Returns null if no student found.
    """
    if not current_user.has_role(UserRole.PARENT):
        return {"student_user_id": current_user.id, "student_name": current_user.full_name}

    # Resolve course_id from study_guide if not provided directly
    resolved_course_id = course_id
    if not resolved_course_id and study_guide_id:
        guide = db.query(StudyGuide.course_id).filter(StudyGuide.id == study_guide_id).first()
        if guide:
            resolved_course_id = guide[0]

    if not resolved_course_id:
        return None

    rows = db.query(parent_students.c.student_id).filter(
        parent_students.c.parent_id == current_user.id
    ).all()
    child_student_ids = [r[0] for r in rows]
    if not child_student_ids:
        return None

    enrolled = (
        db.query(Student.user_id, User.full_name)
        .join(student_courses, Student.id == student_courses.c.student_id)
        .join(User, Student.user_id == User.id)
        .filter(
            student_courses.c.course_id == resolved_course_id,
            Student.id.in_(child_student_ids),
        )
        .first()
    )
    if enrolled:
        return {"student_user_id": enrolled[0], "student_name": enrolled[1]}
    return None


@router.get("/{result_id}", response_model=QuizResultResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_quiz_result(
    request: Request,
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
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_quiz_result(
    request: Request,
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
