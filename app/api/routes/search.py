from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.course import Course, student_courses
from app.models.study_guide import StudyGuide
from app.models.task import Task
from app.models.course_content import CourseContent
from app.models.student import Student, parent_students
from app.models.teacher import Teacher
from app.api.deps import get_current_user
from app.schemas.search import SearchResultItem, SearchResultGroup, SearchResponse

router = APIRouter(prefix="/search", tags=["search"])

ENTITY_LABELS = {
    "course": "Courses",
    "study_guide": "Study Guides",
    "task": "Tasks",
    "course_content": "Course Content",
}


def _get_accessible_user_ids(db: Session, user: User) -> list[int]:
    """Get user IDs whose data the current user can see (self + children for parents)."""
    ids = [user.id]
    if user.role == UserRole.PARENT:
        child_ids = (
            db.query(Student.user_id)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == user.id)
            .all()
        )
        ids.extend(uid for (uid,) in child_ids)
    return ids


def _get_accessible_course_ids(db: Session, user: User, user_ids: list[int]) -> list[int] | None:
    """Get course IDs the user can access. Returns None if unrestricted (admin)."""
    if user.role == UserRole.ADMIN:
        return None  # admin sees all

    course_ids = set()

    # Courses created by accessible users
    created = db.query(Course.id).filter(Course.created_by_user_id.in_(user_ids)).all()
    course_ids.update(cid for (cid,) in created)

    # Courses enrolled via student_courses
    for uid in user_ids:
        student = db.query(Student).filter(Student.user_id == uid).first()
        if student:
            enrolled = (
                db.query(student_courses.c.course_id)
                .filter(student_courses.c.student_id == student.id)
                .all()
            )
            course_ids.update(cid for (cid,) in enrolled)

    # Teacher's courses
    if user.role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if teacher:
            taught = db.query(Course.id).filter(Course.teacher_id == teacher.id).all()
            course_ids.update(cid for (cid,) in taught)

    return list(course_ids)


def _search_courses(db: Session, term: str, limit: int, course_ids: list[int] | None) -> SearchResultGroup:
    query = db.query(Course).filter(
        or_(
            Course.name.ilike(f"%{term}%"),
            Course.description.ilike(f"%{term}%"),
        )
    )
    if course_ids is not None:
        query = query.filter(Course.id.in_(course_ids))

    total = query.count()
    rows = query.order_by(Course.name).limit(limit).all()

    items = [
        SearchResultItem(
            id=c.id,
            title=c.name,
            subtitle=c.subject or c.description[:80] if c.description else None,
            entity_type="course",
            url=f"/courses/{c.id}",
        )
        for c in rows
    ]
    return SearchResultGroup(entity_type="course", label="Courses", items=items, total=total)


def _search_study_guides(db: Session, term: str, limit: int, user_ids: list[int]) -> SearchResultGroup:
    query = db.query(StudyGuide).filter(
        StudyGuide.title.ilike(f"%{term}%"),
        StudyGuide.user_id.in_(user_ids),
    )

    total = query.count()
    rows = query.order_by(StudyGuide.created_at.desc()).limit(limit).all()

    items = []
    for g in rows:
        guide_type = g.guide_type or "study_guide"
        if guide_type == "quiz":
            url = f"/study/quiz/{g.id}"
        elif guide_type == "flashcards":
            url = f"/study/flashcards/{g.id}"
        else:
            url = f"/study/guide/{g.id}"

        type_label = {"quiz": "Quiz", "flashcards": "Flashcards"}.get(guide_type, "Study Guide")
        items.append(SearchResultItem(
            id=g.id,
            title=g.title,
            subtitle=type_label,
            entity_type="study_guide",
            url=url,
        ))

    return SearchResultGroup(entity_type="study_guide", label="Study Guides", items=items, total=total)


def _search_tasks(db: Session, term: str, limit: int, user_ids: list[int]) -> SearchResultGroup:
    query = db.query(Task).filter(
        or_(
            Task.title.ilike(f"%{term}%"),
            Task.description.ilike(f"%{term}%"),
        ),
        Task.archived_at.is_(None),
        or_(
            Task.created_by_user_id.in_(user_ids),
            Task.assigned_to_user_id.in_(user_ids),
        ),
    )

    total = query.count()
    rows = query.order_by(Task.created_at.desc()).limit(limit).all()

    items = [
        SearchResultItem(
            id=t.id,
            title=t.title,
            subtitle=f"{(t.priority or 'medium').capitalize()} priority" + (" - Done" if t.is_completed else ""),
            entity_type="task",
            url=f"/tasks/{t.id}",
        )
        for t in rows
    ]
    return SearchResultGroup(entity_type="task", label="Tasks", items=items, total=total)


def _search_course_content(db: Session, term: str, limit: int, course_ids: list[int] | None) -> SearchResultGroup:
    query = db.query(CourseContent).filter(
        or_(
            CourseContent.title.ilike(f"%{term}%"),
            CourseContent.description.ilike(f"%{term}%"),
        )
    )
    if course_ids is not None:
        query = query.filter(CourseContent.course_id.in_(course_ids))

    total = query.count()
    rows = query.order_by(CourseContent.created_at.desc()).limit(limit).all()

    items = [
        SearchResultItem(
            id=cc.id,
            title=cc.title,
            subtitle=cc.content_type or "Content",
            entity_type="course_content",
            url=f"/study-guides/{cc.id}",
        )
        for cc in rows
    ]
    return SearchResultGroup(entity_type="course_content", label="Course Content", items=items, total=total)


@router.get("", response_model=SearchResponse)
def global_search(
    q: str = Query(..., min_length=2, max_length=200),
    types: str | None = Query(None, description="Comma-separated entity types to search"),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search across courses, study guides, tasks, and course content."""
    term = q.strip()

    # Determine which types to search
    all_types = {"course", "study_guide", "task", "course_content"}
    if types:
        requested = {t.strip() for t in types.split(",")} & all_types
    else:
        requested = all_types

    # Compute access scopes once
    user_ids = _get_accessible_user_ids(db, current_user)
    course_ids = _get_accessible_course_ids(db, current_user, user_ids)

    # Admin sees all study guides and tasks too
    if current_user.role == UserRole.ADMIN:
        admin_user_ids = None  # signal to skip user filtering
    else:
        admin_user_ids = user_ids

    groups: list[SearchResultGroup] = []

    if "course" in requested:
        groups.append(_search_courses(db, term, limit, course_ids))

    if "study_guide" in requested:
        if admin_user_ids is None:
            # Admin: search all
            sg_query = db.query(StudyGuide).filter(StudyGuide.title.ilike(f"%{term}%"))
            sg_total = sg_query.count()
            sg_rows = sg_query.order_by(StudyGuide.created_at.desc()).limit(limit).all()
            items = []
            for g in sg_rows:
                guide_type = g.guide_type or "study_guide"
                url = f"/study/quiz/{g.id}" if guide_type == "quiz" else f"/study/flashcards/{g.id}" if guide_type == "flashcards" else f"/study/guide/{g.id}"
                type_label = {"quiz": "Quiz", "flashcards": "Flashcards"}.get(guide_type, "Study Guide")
                items.append(SearchResultItem(id=g.id, title=g.title, subtitle=type_label, entity_type="study_guide", url=url))
            groups.append(SearchResultGroup(entity_type="study_guide", label="Study Guides", items=items, total=sg_total))
        else:
            groups.append(_search_study_guides(db, term, limit, admin_user_ids))

    if "task" in requested:
        if admin_user_ids is None:
            # Admin: search all non-archived tasks
            t_query = db.query(Task).filter(
                or_(Task.title.ilike(f"%{term}%"), Task.description.ilike(f"%{term}%")),
                Task.archived_at.is_(None),
            )
            t_total = t_query.count()
            t_rows = t_query.order_by(Task.created_at.desc()).limit(limit).all()
            items = [
                SearchResultItem(
                    id=t.id, title=t.title,
                    subtitle=f"{(t.priority or 'medium').capitalize()} priority" + (" - Done" if t.is_completed else ""),
                    entity_type="task", url=f"/tasks/{t.id}",
                )
                for t in t_rows
            ]
            groups.append(SearchResultGroup(entity_type="task", label="Tasks", items=items, total=t_total))
        else:
            groups.append(_search_tasks(db, term, limit, admin_user_ids))

    if "course_content" in requested:
        groups.append(_search_course_content(db, term, limit, course_ids))

    total = sum(g.total for g in groups)

    return SearchResponse(query=term, groups=groups, total=total)
