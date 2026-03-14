import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.utils import escape_like
from app.models.course import Course, student_courses
from app.models.course_content import CourseContent
from app.models.faq import FAQQuestion
from app.models.note import Note
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.task import Task


@dataclass
class SearchResult:
    entity_type: str  # "course" | "study_guide" | "task" | "course_content" | "faq" | "note" | "action"
    id: int | None
    title: str
    description: str | None
    actions: list[dict] = field(default_factory=list)


def _strip_html(text: str) -> str:
    """Strip basic HTML tags using regex."""
    return re.sub(r"<[^>]+>", "", text or "")


class SearchService:
    def detect_preset(self, message: str) -> str | None:
        """Returns 'due' | 'overdue' | 'upload' | 'create' | None"""
        msg = message.lower().strip()
        if any(w in msg for w in ["due soon", "overdue", "past due", "what's due", "whats due"]):
            return "overdue"
        if "due" in msg and any(w in msg for w in ["this week", "today", "tomorrow", "upcoming"]):
            return "due"
        if "upload" in msg or "add file" in msg or "add material" in msg:
            return "upload"
        if msg.startswith("create") or msg.startswith("new ") or "add a course" in msg or "add a task" in msg:
            return "create"
        return None

    def get_due_tasks(self, user_id: int, user_role: str, db: Session) -> list[SearchResult]:
        """Return tasks due soon for the user."""
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        soon = now + timedelta(days=7)

        query = db.query(Task).filter(
            Task.archived_at.is_(None),
            Task.is_completed == False,
            Task.due_date.isnot(None),
            Task.due_date <= soon,
        )

        if user_role == "student":
            query = query.filter(
                (Task.assigned_to_user_id == user_id) | (Task.created_by_user_id == user_id)
            )
        elif user_role == "parent":
            student_ids = [
                row[0] for row in db.query(parent_students.c.student_id).filter(
                    parent_students.c.parent_id == user_id
                ).all()
            ]
            child_user_ids = [
                row[0] for row in db.query(Student.user_id).filter(
                    Student.id.in_(student_ids)
                ).all()
            ]
            query = query.filter(Task.assigned_to_user_id.in_(child_user_ids))
        else:
            query = query.filter(Task.created_by_user_id == user_id)

        tasks = query.order_by(Task.due_date).limit(10).all()
        results = []
        for t in tasks:
            due_str = t.due_date.strftime("%b %d") if t.due_date else None
            results.append(SearchResult(
                entity_type="task",
                id=t.id,
                title=t.title,
                description=f"Due: {due_str}" if due_str else None,
                actions=[{"label": "View", "route": f"/tasks/{t.id}"}],
            ))
        return results

    def search(self, query: str, user_id: int, user_role: str, db: Session) -> list[SearchResult]:
        """Search across platform entities and return up to 10 results total."""
        preset = self.detect_preset(query)

        if preset == "upload":
            return [SearchResult(
                entity_type="action",
                id=None,
                title="Upload Material",
                description="Upload course materials or study resources",
                actions=[{"label": "Go to Study Tools", "route": "/study-tools"}],
            )]

        if preset == "create":
            return [
                SearchResult(
                    entity_type="action",
                    id=None,
                    title="New Course",
                    description="Create a new course",
                    actions=[{"label": "Create", "route": "/classes/new"}],
                ),
                SearchResult(
                    entity_type="action",
                    id=None,
                    title="New Task",
                    description="Create a new task",
                    actions=[{"label": "Create", "route": "/tasks/new"}],
                ),
                SearchResult(
                    entity_type="action",
                    id=None,
                    title="Generate Study Guide",
                    description="Generate an AI study guide",
                    actions=[{"label": "Go to Study Tools", "route": "/study-tools"}],
                ),
            ]

        if preset in ("due", "overdue"):
            return self.get_due_tasks(user_id, user_role, db)

        raw = query.strip()
        term = f"%{escape_like(raw)}%"
        results: list[SearchResult] = []
        remaining = 10

        # Children (parent-only — search by full name)
        if user_role == "parent":
            from app.models.user import User as _User
            child_q = (
                db.query(Student, _User)
                .join(parent_students, parent_students.c.student_id == Student.id)
                .join(_User, Student.user_id == _User.id)
                .filter(
                    parent_students.c.parent_id == user_id,
                    _User.full_name.ilike(term),
                )
            )
            for student, user in child_q.limit(remaining).all():
                results.append(SearchResult(
                    entity_type="child",
                    id=student.id,
                    title=user.full_name,
                    description="Child",
                    actions=[{"label": "View Profile", "route": f"/my-kids/{student.id}"}],
                ))
            remaining = 10 - len(results)
            if remaining <= 0:
                return results

        # Courses
        course_q = db.query(Course).filter(
            (Course.name.ilike(term)) | (Course.description.ilike(term))
        )
        if user_role == "student":
            student_row = db.query(Student).filter(Student.user_id == user_id).first()
            if student_row:
                course_q = course_q.filter(
                    Course.students.any(Student.id == student_row.id)
                )
            else:
                course_q = course_q.filter(False)
        elif user_role == "parent":
            student_ids = [
                row[0] for row in db.query(parent_students.c.student_id).filter(
                    parent_students.c.parent_id == user_id
                ).all()
            ]
            if student_ids:
                course_q = course_q.filter(
                    Course.students.any(Student.id.in_(student_ids))
                )
            else:
                course_q = course_q.filter(False)
        elif user_role == "teacher":
            from app.models.teacher import Teacher
            teacher_row = db.query(Teacher).filter(Teacher.user_id == user_id).first()
            if teacher_row:
                course_q = course_q.filter(Course.teacher_id == teacher_row.id)
            else:
                course_q = course_q.filter(False)
        # ADMIN: no extra filter

        for c in course_q.limit(remaining).all():
            results.append(SearchResult(
                entity_type="course",
                id=c.id,
                title=c.name,
                description=c.description,
                actions=[{"label": "View", "route": f"/classes/{c.id}"}],
            ))
        remaining = 10 - len(results)
        if remaining <= 0:
            return results

        # Assignments (scoped to accessible courses)
        from app.models.assignment import Assignment
        asgn_q = db.query(Assignment).filter(Assignment.title.ilike(term))
        if user_role == "student":
            student_row = db.query(Student).filter(Student.user_id == user_id).first()
            if student_row:
                enrolled_course_ids = [
                    row[0] for row in db.query(student_courses.c.course_id).filter(
                        student_courses.c.student_id == student_row.id
                    ).all()
                ]
                asgn_q = asgn_q.filter(Assignment.course_id.in_(enrolled_course_ids))
            else:
                asgn_q = asgn_q.filter(False)
        elif user_role == "parent":
            student_ids = [
                row[0] for row in db.query(parent_students.c.student_id).filter(
                    parent_students.c.parent_id == user_id
                ).all()
            ]
            if student_ids:
                enrolled_course_ids = [
                    row[0] for row in db.query(student_courses.c.course_id).filter(
                        student_courses.c.student_id.in_(student_ids)
                    ).all()
                ]
                asgn_q = asgn_q.filter(Assignment.course_id.in_(enrolled_course_ids))
            else:
                asgn_q = asgn_q.filter(False)
        elif user_role == "teacher":
            from app.models.teacher import Teacher
            teacher_row = db.query(Teacher).filter(Teacher.user_id == user_id).first()
            if teacher_row:
                teacher_course_ids = [
                    row[0] for row in db.query(Course.id).filter(
                        Course.teacher_id == teacher_row.id
                    ).all()
                ]
                asgn_q = asgn_q.filter(Assignment.course_id.in_(teacher_course_ids))
            else:
                asgn_q = asgn_q.filter(False)
        # ADMIN: no extra filter

        for a in asgn_q.order_by(Assignment.due_date.desc().nullslast()).limit(remaining).all():
            results.append(SearchResult(
                entity_type="assignment",
                id=a.id,
                title=a.title,
                description=None,
                actions=[{"label": "View", "route": f"/courses/{a.course_id}/assignments/{a.id}"}],
            ))
        remaining = 10 - len(results)
        if remaining <= 0:
            return results

        # Study Guides (filter by owner)
        guide_q = db.query(StudyGuide).filter(
            StudyGuide.title.ilike(term),
            StudyGuide.user_id == user_id,
            StudyGuide.archived_at.is_(None),
        )
        for g in guide_q.limit(remaining).all():
            guide_type = g.guide_type or "study_guide"
            if guide_type == "quiz":
                route = f"/study/quiz/{g.id}"
            elif guide_type == "flashcards":
                route = f"/study/flashcards/{g.id}"
            else:
                route = f"/study/guide/{g.id}"
            results.append(SearchResult(
                entity_type="study_guide",
                id=g.id,
                title=g.title,
                description=None,
                actions=[{"label": "View", "route": route}],
            ))
        remaining = 10 - len(results)
        if remaining <= 0:
            return results

        # Tasks
        task_q = db.query(Task).filter(
            (Task.title.ilike(term)) | (Task.description.ilike(term)),
            Task.archived_at.is_(None),
        )
        if user_role == "student":
            task_q = task_q.filter(
                (Task.assigned_to_user_id == user_id) | (Task.created_by_user_id == user_id)
            )
        elif user_role == "parent":
            student_ids = [
                row[0] for row in db.query(parent_students.c.student_id).filter(
                    parent_students.c.parent_id == user_id
                ).all()
            ]
            child_user_ids = [
                row[0] for row in db.query(Student.user_id).filter(
                    Student.id.in_(student_ids)
                ).all()
            ]
            task_q = task_q.filter(Task.assigned_to_user_id.in_(child_user_ids))
        else:
            task_q = task_q.filter(Task.created_by_user_id == user_id)

        for t in task_q.limit(remaining).all():
            results.append(SearchResult(
                entity_type="task",
                id=t.id,
                title=t.title,
                description=t.description,
                actions=[{"label": "View", "route": f"/tasks/{t.id}"}],
            ))
        remaining = 10 - len(results)
        if remaining <= 0:
            return results

        # CourseContent
        content_q = db.query(CourseContent).filter(
            (CourseContent.title.ilike(term)) | (CourseContent.description.ilike(term)),
            CourseContent.archived_at.is_(None),
        )
        # Filter by course access (same logic as courses)
        if user_role == "student":
            student_row = db.query(Student).filter(Student.user_id == user_id).first()
            if student_row:
                enrolled_course_ids = [
                    row[0] for row in db.query(student_courses.c.course_id).filter(
                        student_courses.c.student_id == student_row.id
                    ).all()
                ]
                content_q = content_q.filter(CourseContent.course_id.in_(enrolled_course_ids))
            else:
                content_q = content_q.filter(False)
        elif user_role == "parent":
            student_ids = [
                row[0] for row in db.query(parent_students.c.student_id).filter(
                    parent_students.c.parent_id == user_id
                ).all()
            ]
            if student_ids:
                enrolled_course_ids = [
                    row[0] for row in db.query(student_courses.c.course_id).filter(
                        student_courses.c.student_id.in_(student_ids)
                    ).all()
                ]
                content_q = content_q.filter(CourseContent.course_id.in_(enrolled_course_ids))
            else:
                content_q = content_q.filter(False)
        elif user_role == "teacher":
            from app.models.teacher import Teacher
            teacher_row = db.query(Teacher).filter(Teacher.user_id == user_id).first()
            if teacher_row:
                teacher_course_ids = [
                    row[0] for row in db.query(Course.id).filter(
                        Course.teacher_id == teacher_row.id
                    ).all()
                ]
                content_q = content_q.filter(CourseContent.course_id.in_(teacher_course_ids))
            else:
                content_q = content_q.filter(False)
        # ADMIN: no extra filter

        for cc in content_q.limit(remaining).all():
            results.append(SearchResult(
                entity_type="course_content",
                id=cc.id,
                title=cc.title,
                description=cc.description,
                actions=[{"label": "View", "route": f"/classes/{cc.course_id}/content/{cc.id}"}],
            ))
        remaining = 10 - len(results)
        if remaining <= 0:
            return results

        # FAQ (FAQQuestion — database FAQ, same model as main search)
        from sqlalchemy import or_ as _or
        faq_q = db.query(FAQQuestion).filter(
            (_or(
                FAQQuestion.title.ilike(term),
                FAQQuestion.description.ilike(term),
            )),
            FAQQuestion.archived_at.is_(None),
        )
        for fa in faq_q.order_by(FAQQuestion.is_pinned.desc(), FAQQuestion.view_count.desc()).limit(remaining).all():
            results.append(SearchResult(
                entity_type="faq",
                id=fa.id,
                title=fa.title,
                description=None,
                actions=[{"label": "View", "route": f"/faq/{fa.id}"}],
            ))
        remaining = 10 - len(results)
        if remaining <= 0:
            return results

        # Notes (search plain_text or content, filter by user)
        note_q = db.query(Note).filter(
            Note.user_id == user_id,
        )
        # Use plain_text if available, fall back to content
        note_q = note_q.filter(
            (Note.plain_text.ilike(term)) | (Note.content.ilike(term))
        )
        from app.models.course_content import CourseContent as _CC
        for n in note_q.limit(remaining).all():
            raw = n.plain_text or _strip_html(n.content or "")
            snippet = raw[:100].strip() if raw else None
            cc = db.query(_CC).filter(_CC.id == n.course_content_id).first()
            cc_title = cc.title if cc else f"material {n.course_content_id}"
            results.append(SearchResult(
                entity_type="note",
                id=n.id,
                title=f"Note on {cc_title}",
                description=snippet,
                actions=[{"label": "View Material", "route": f"/course-materials/{n.course_content_id}?notes=1"}],
            ))

        return results


# Singleton instance
search_service = SearchService()
