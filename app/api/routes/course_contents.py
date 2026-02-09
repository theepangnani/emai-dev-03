from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.course_content import CourseContent
from app.models.course import Course, student_courses
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.api.deps import get_current_user
from app.schemas.course_content import CourseContentCreate, CourseContentUpdate, CourseContentResponse

router = APIRouter(prefix="/course-contents", tags=["Course Contents"])


@router.post("/", response_model=CourseContentResponse, status_code=status.HTTP_201_CREATED)
def create_course_content(
    data: CourseContentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new content item for a course."""
    course = db.query(Course).filter(Course.id == data.course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    content = CourseContent(
        course_id=data.course_id,
        title=data.title,
        description=data.description,
        text_content=data.text_content,
        content_type=data.content_type,
        reference_url=data.reference_url,
        google_classroom_url=data.google_classroom_url,
        created_by_user_id=current_user.id,
    )
    db.add(content)
    db.commit()
    db.refresh(content)
    return content


@router.get("/", response_model=list[CourseContentResponse])
def list_course_contents(
    course_id: Optional[int] = Query(None, description="Filter by course ID"),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    student_user_id: Optional[int] = Query(None, description="Filter by child (parent only)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List content items. If course_id is given, scoped to that course.
    Otherwise returns all course contents visible to the user across courses."""
    if course_id:
        query = db.query(CourseContent).filter(CourseContent.course_id == course_id)
    else:
        # Cross-course: all content visible to the user
        visible_course_ids = _get_visible_course_ids(db, current_user, student_user_id)
        query = db.query(CourseContent).filter(CourseContent.course_id.in_(visible_course_ids))

    if content_type:
        query = query.filter(CourseContent.content_type == content_type.strip().lower())
    return query.order_by(CourseContent.created_at.desc()).all()


def _get_visible_course_ids(db: Session, user: User, student_user_id: int | None = None) -> list[int]:
    """Return course IDs visible to the user for cross-course content listing."""
    # Courses created by the user
    created = db.query(Course.id).filter(Course.created_by_user_id == user.id).all()
    ids = {r[0] for r in created}

    if user.role == UserRole.STUDENT:
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if student:
            ids.update(c.id for c in student.courses)

    elif user.role == UserRole.PARENT:
        # Get children's enrolled course IDs
        child_rows = db.query(parent_students.c.student_id).filter(
            parent_students.c.parent_id == user.id
        ).all()
        child_sids = [r[0] for r in child_rows]

        if student_user_id:
            # Filter to a specific child
            child_student = db.query(Student).filter(
                Student.user_id == student_user_id,
                Student.id.in_(child_sids),
            ).first()
            if child_student:
                ids.update(c.id for c in child_student.courses)
                # Also include contents created by this child
                child_created = db.query(Course.id).filter(Course.created_by_user_id == student_user_id).all()
                ids.update(r[0] for r in child_created)
        elif child_sids:
            enrolled = db.query(student_courses.c.course_id).filter(
                student_courses.c.student_id.in_(child_sids)
            ).all()
            ids.update(r[0] for r in enrolled)
            # Also include contents created by children
            child_user_ids = db.query(Student.user_id).filter(Student.id.in_(child_sids)).all()
            child_uids = [r[0] for r in child_user_ids]
            if child_uids:
                child_created = db.query(Course.id).filter(Course.created_by_user_id.in_(child_uids)).all()
                ids.update(r[0] for r in child_created)

    elif user.role == UserRole.TEACHER:
        from app.models.teacher import Teacher
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if teacher:
            taught = db.query(Course.id).filter(Course.teacher_id == teacher.id).all()
            ids.update(r[0] for r in taught)

    elif user.role == UserRole.ADMIN:
        all_ids = db.query(Course.id).all()
        return [r[0] for r in all_ids]

    return list(ids)


@router.get("/{content_id}", response_model=CourseContentResponse)
def get_course_content(
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single content item."""
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    return content


@router.patch("/{content_id}", response_model=CourseContentResponse)
def update_course_content(
    content_id: int,
    data: CourseContentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a content item. Only the creator can update."""
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    if content.created_by_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creator can edit content")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(content, field, value)

    db.commit()
    db.refresh(content)
    return content


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course_content(
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a content item. Only the creator can delete."""
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    if content.created_by_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creator can delete content")

    db.delete(content)
    db.commit()
