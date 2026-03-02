from datetime import date, timedelta, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.models.teacher import Teacher
from app.models.course import Course, student_courses
from app.models.assignment import StudentAssignment, Assignment
from app.schemas.student import StudentCreate, StudentResponse
from app.schemas.assignment import SubmissionResponse
from app.api.deps import get_current_user, require_role

# ---------------------------------------------------------------------------
# In-memory AI insights cache — stores (insight_text, expires_at) per student
# ---------------------------------------------------------------------------
_ai_insights_cache: dict[int, tuple[str, datetime]] = {}

router = APIRouter(prefix="/students", tags=["Students"])


# ── Streak Schemas ──────────────────────────────────────────────

class StudyActivityResponse(BaseModel):
    study_streak_days: int
    last_study_date: date | None
    longest_streak: int
    streak_updated: bool  # True if streak actually changed

    class Config:
        from_attributes = True


@router.post("/", response_model=StudentResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def create_student(
    request: Request,
    student_data: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Create a student record. Admin only (parents use /parent/children/create)."""
    student = Student(**student_data.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/", response_model=list[StudentResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_students(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    """List students. Admin sees all; teachers see students in their courses."""
    if current_user.role == UserRole.ADMIN:
        return db.query(Student).all()

    # Teacher: only students enrolled in their courses
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher:
        return []

    course_ids = [
        r[0] for r in db.query(Course.id).filter(Course.teacher_id == teacher.id).all()
    ]
    if not course_ids:
        return []

    student_ids = {
        r[0] for r in db.query(student_courses.c.student_id).filter(
            student_courses.c.course_id.in_(course_ids)
        ).all()
    }
    if not student_ids:
        return []

    return db.query(Student).filter(Student.id.in_(student_ids)).all()


@router.get("/me", response_model=StudentResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_my_student_profile(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's own student profile."""
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No student profile found")
    return student


@router.get("/{student_id}", response_model=StudentResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_student(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a student. Access: admin, teacher (course), parent (linked), student (own)."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    # Admin sees all
    if current_user.role == UserRole.ADMIN:
        return student

    # Student sees own profile
    if current_user.role == UserRole.STUDENT and student.user_id == current_user.id:
        return student

    # Parent sees linked children
    if current_user.role == UserRole.PARENT:
        link = db.query(parent_students).filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        ).first()
        if link:
            return student

    # Teacher sees students in their courses
    if current_user.role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher:
            course_ids = [
                r[0] for r in db.query(Course.id).filter(Course.teacher_id == teacher.id).all()
            ]
            if course_ids:
                enrolled = db.query(student_courses).filter(
                    student_courses.c.student_id == student_id,
                    student_courses.c.course_id.in_(course_ids),
                ).first()
                if enrolled:
                    return student

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.post("/study-activity", response_model=StudyActivityResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def record_study_activity(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Record that the student studied today. Updates streak counters.

    - If last_study_date is today: no change (idempotent)
    - If last_study_date is yesterday: increment streak
    - If last_study_date is older (or null): reset streak to 1
    - Always updates longest_streak if current exceeds it
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No student profile found")

    today = date.today()
    yesterday = today - timedelta(days=1)
    streak_updated = False

    if student.last_study_date == today:
        # Already recorded today — idempotent, return current state
        pass
    elif student.last_study_date == yesterday:
        # Consecutive day — extend streak
        student.study_streak_days = (student.study_streak_days or 0) + 1
        student.last_study_date = today
        streak_updated = True
    else:
        # Gap or first time — reset streak to 1
        student.study_streak_days = 1
        student.last_study_date = today
        streak_updated = True

    # Update longest streak
    if student.study_streak_days > (student.longest_streak or 0):
        student.longest_streak = student.study_streak_days
        streak_updated = True

    if streak_updated:
        db.commit()
        db.refresh(student)

    return StudyActivityResponse(
        study_streak_days=student.study_streak_days or 0,
        last_study_date=student.last_study_date,
        longest_streak=student.longest_streak or 0,
        streak_updated=streak_updated,
    )


@router.get("/streak", response_model=StudyActivityResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_streak(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Get the current student's streak data."""
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No student profile found")

    return StudyActivityResponse(
        study_streak_days=student.study_streak_days or 0,
        last_study_date=student.last_study_date,
        longest_streak=student.longest_streak or 0,
        streak_updated=False,
    )


@router.get("/{student_id}/submissions", response_model=list[SubmissionResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_student_submissions(
    request: Request,
    student_id: int,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all submissions for a student. Accessible by the student themselves, their linked parents, teachers, and admins."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    # Access control
    if current_user.role == UserRole.ADMIN:
        pass  # Admin can see all
    elif current_user.role == UserRole.STUDENT:
        if student.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif current_user.role == UserRole.PARENT:
        link = db.query(parent_students).filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        ).first()
        if not link:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif current_user.role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher:
            course_ids = [
                r[0] for r in db.query(Course.id).filter(Course.teacher_id == teacher.id).all()
            ]
            enrolled = db.query(student_courses).filter(
                student_courses.c.student_id == student_id,
                student_courses.c.course_id.in_(course_ids),
            ).first() if course_ids else None
            if not enrolled:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    query = db.query(StudentAssignment).filter(
        StudentAssignment.student_id == student_id,
    )
    if status_filter:
        query = query.filter(StudentAssignment.status == status_filter)

    submissions = query.order_by(StudentAssignment.submitted_at.desc().nullslast()).offset(offset).limit(limit).all()

    result = []
    for sa in submissions:
        assignment = sa.assignment
        result.append(SubmissionResponse(
            id=sa.id,
            student_id=sa.student_id,
            assignment_id=sa.assignment_id,
            status=sa.status,
            submitted_at=sa.submitted_at,
            grade=sa.grade,
            submission_file_name=sa.submission_file_name,
            submission_notes=sa.submission_notes,
            is_late=sa.is_late or False,
            assignment_title=assignment.title if assignment else None,
            course_name=assignment.course.name if assignment and assignment.course else None,
            student_name=student.user.full_name if student and student.user else None,
            has_file=bool(sa.submission_file_path),
        ))

    return result


# ---------------------------------------------------------------------------
# Progress snapshot endpoint (#960)
# ---------------------------------------------------------------------------

def _check_progress_access(db: Session, student_id: int, current_user: User) -> Student:
    """Load a student and verify the caller has permission to view their progress."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    if current_user.role == UserRole.ADMIN:
        return student
    if current_user.role == UserRole.STUDENT and student.user_id == current_user.id:
        return student
    if current_user.role == UserRole.PARENT:
        link = db.query(parent_students).filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        ).first()
        if link:
            return student
    if current_user.role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher:
            course_ids = [
                r[0] for r in db.query(Course.id).filter(Course.teacher_id == teacher.id).all()
            ]
            if course_ids:
                enrolled = db.query(student_courses).filter(
                    student_courses.c.student_id == student_id,
                    student_courses.c.course_id.in_(course_ids),
                ).first()
                if enrolled:
                    return student
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.get("/{student_id}/progress")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_student_progress(
    request: Request,
    student_id: int,
    refresh_ai: bool = Query(False, description="Force-refresh AI insights even if cached"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Consolidated progress snapshot for a student.

    Returns quiz performance, teacher grades, report cards, assignment completion,
    study streak, and an AI-generated insight (cached 24 h per student).

    Access: student (own), parent (linked child), teacher (enrolled student), admin.
    """
    student = _check_progress_access(db, student_id, current_user)
    user = student.user

    # ── 1. Study streak ────────────────────────────────────────────────────
    study_streak = {
        "current": student.study_streak_days or 0,
        "longest": student.longest_streak or 0,
        "last_study_date": student.last_study_date.isoformat() if student.last_study_date else None,
    }

    # ── 2. Quiz performance (QuizResult rows keyed to user_id) ────────────
    quiz_performance: dict[str, Any] = {
        "total_attempts": 0,
        "average_score": 0.0,
        "by_guide": [],
    }
    try:
        from app.models.quiz_result import QuizResult
        from app.models.study_guide import StudyGuide

        quiz_rows = (
            db.query(QuizResult)
            .filter(QuizResult.user_id == user.id)
            .all()
        )
        if quiz_rows:
            total_attempts = len(quiz_rows)
            avg_score = sum(r.percentage for r in quiz_rows) / total_attempts

            # Group by study guide
            by_guide: dict[int, dict[str, Any]] = {}
            for qr in quiz_rows:
                guide_id = qr.study_guide_id
                if guide_id not in by_guide:
                    guide = db.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
                    by_guide[guide_id] = {
                        "guide_title": guide.title if guide else f"Guide #{guide_id}",
                        "total_score": 0.0,
                        "attempts": 0,
                    }
                by_guide[guide_id]["total_score"] += qr.percentage
                by_guide[guide_id]["attempts"] += 1

            guide_list = [
                {
                    "guide_title": v["guide_title"],
                    "avg_score": round(v["total_score"] / v["attempts"], 1),
                    "attempts": v["attempts"],
                }
                for v in by_guide.values()
            ]
            # Sort ascending by avg_score (weakest first)
            guide_list.sort(key=lambda x: x["avg_score"])

            quiz_performance = {
                "total_attempts": total_attempts,
                "average_score": round(avg_score, 1),
                "by_guide": guide_list,
            }
    except Exception:
        pass  # Table may not exist yet — return empty

    # ── 3. Teacher grades (published GradeEntry rows) ─────────────────────
    teacher_grades: dict[str, Any] = {
        "overall_average": 0.0,
        "by_course": [],
    }
    try:
        from app.models.grade_entry import GradeEntry

        published_entries = (
            db.query(GradeEntry)
            .filter(
                GradeEntry.student_id == student_id,
                GradeEntry.is_published == True,  # noqa: E712
                GradeEntry.grade.isnot(None),
            )
            .all()
        )
        if published_entries:
            all_grades = [e.grade for e in published_entries]
            overall_avg = sum(all_grades) / len(all_grades)

            # Group by course
            by_course: dict[int, dict[str, Any]] = {}
            for entry in published_entries:
                cid = entry.course_id
                if cid not in by_course:
                    course = db.query(Course).filter(Course.id == cid).first()
                    by_course[cid] = {
                        "course_name": course.name if course else f"Course #{cid}",
                        "grades": [],
                    }
                by_course[cid]["grades"].append(entry.grade)

            course_list = []
            for v in by_course.values():
                avg = sum(v["grades"]) / len(v["grades"])
                # Use grade_entry helper for letter grade
                from app.models.grade_entry import _letter_grade
                course_list.append({
                    "course_name": v["course_name"],
                    "average": round(avg, 1),
                    "letter": _letter_grade(avg) or "N/A",
                    "entries": len(v["grades"]),
                })

            teacher_grades = {
                "overall_average": round(overall_avg, 1),
                "by_course": course_list,
            }
    except Exception:
        pass

    # ── 4. Report cards ────────────────────────────────────────────────────
    report_cards: dict[str, Any] = {
        "latest_average": None,
        "by_term": [],
    }
    try:
        from app.models.report_card import ReportCard

        cards = (
            db.query(ReportCard)
            .filter(
                ReportCard.student_id == student_id,
                ReportCard.overall_average.isnot(None),
            )
            .order_by(ReportCard.uploaded_at.asc())
            .all()
        )
        if cards:
            by_term = [
                {"term": c.term, "average": round(c.overall_average, 1)}
                for c in cards
            ]
            report_cards = {
                "latest_average": by_term[-1]["average"],
                "by_term": by_term,
            }
    except Exception:
        pass

    # ── 5. Assignment completion ───────────────────────────────────────────
    assignments: dict[str, Any] = {
        "total": 0,
        "submitted": 0,
        "submission_rate_pct": 0.0,
    }
    try:
        total_sa = (
            db.query(StudentAssignment)
            .filter(StudentAssignment.student_id == student_id)
            .count()
        )
        submitted_sa = (
            db.query(StudentAssignment)
            .filter(
                StudentAssignment.student_id == student_id,
                StudentAssignment.status.in_(["submitted", "graded"]),
            )
            .count()
        )
        rate = (submitted_sa / total_sa * 100) if total_sa else 0.0
        assignments = {
            "total": total_sa,
            "submitted": submitted_sa,
            "submission_rate_pct": round(rate, 1),
        }
    except Exception:
        pass

    # ── 6. AI insights (24h cache) ─────────────────────────────────────────
    ai_insights: str | None = None
    try:
        now = datetime.utcnow()
        cached = _ai_insights_cache.get(student_id)
        if not refresh_ai and cached and cached[1] > now:
            ai_insights = cached[0]
        else:
            from app.services.ai_service import generate_content

            quiz_avg = quiz_performance.get("average_score", 0)
            grade_avg = teacher_grades.get("overall_average", 0)
            streak = study_streak["current"]
            rc_avg = report_cards.get("latest_average")
            sub_rate = assignments.get("submission_rate_pct", 0)

            prompt = (
                f"A student has the following academic performance data:\n"
                f"- Quiz average: {quiz_avg}%\n"
                f"- Teacher grade average: {grade_avg}%\n"
                f"- Report card average: {rc_avg}% (latest term)\n"
                f"- Assignment submission rate: {sub_rate}%\n"
                f"- Study streak: {streak} day(s)\n\n"
                f"In 2-3 sentences, give encouraging but actionable advice to help this student improve."
            )
            system = (
                "You are a supportive educational coach for a K-12 student. "
                "Be positive, specific, and practical. Do not mention names."
            )
            insight_text = await generate_content(prompt, system, max_tokens=200, temperature=0.6)
            # Cache for 24 h
            expires_at = datetime(now.year, now.month, now.day, now.hour, now.minute, now.second) \
                         + timedelta(hours=24)
            _ai_insights_cache[student_id] = (insight_text, expires_at)
            ai_insights = insight_text
    except Exception:
        ai_insights = None

    return {
        "student_id": student_id,
        "student_name": user.full_name if user else "",
        "study_streak": study_streak,
        "quiz_performance": quiz_performance,
        "teacher_grades": teacher_grades,
        "report_cards": report_cards,
        "assignments": assignments,
        "ai_insights": ai_insights,
    }
