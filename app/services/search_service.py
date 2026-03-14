import re
import re as _re
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


_ENTITY_LIST_TRIGGERS = {"my", "show", "list", "all", "view", "see", "get"}

_ENTITY_LIST_PATTERNS = [
    ("list_tasks",        _re.compile(r'\btasks?\b', _re.IGNORECASE)),
    ("list_courses",      _re.compile(r'\bcourses?\b', _re.IGNORECASE)),
    ("list_assignments",  _re.compile(r'\bassignments?\b', _re.IGNORECASE)),
    ("list_study_guides", _re.compile(r'\bstudy[\s\-]guides?\b', _re.IGNORECASE)),
    ("list_notes",        _re.compile(r'\bnotes?\b', _re.IGNORECASE)),
    ("list_materials",    _re.compile(r'\bmaterials?\b|\bcontent\b', _re.IGNORECASE)),
]


@dataclass
class SearchResult:
    entity_type: str  # "course" | "study_guide" | "task" | "course_content" | "faq" | "note" | "action" | "summary"
    id: int | None
    title: str
    description: str | None
    actions: list[dict] = field(default_factory=list)
    total: int | None = None  # total available (for pagination hint)


_ACTION_PREFIX_RE = _re.compile(
    r'^(find|search\s+for|show\s+me|show|list|where\s+is|where\s+are|'
    r'look\s+up|get\s+me|get|what\s+are\s+my|what\s+are\s+the)\s+',
    _re.IGNORECASE,
)
_POSSESSIVE_RE = _re.compile(r'\bmy\s+|\bthe\s+', _re.IGNORECASE)


def _extract_search_term(query: str) -> str:
    """Strip leading action verbs and possessives to get the core search term.

    Examples:
        "Find my course"   -> "course"
        "Show me my tasks" -> "tasks"
        "list my notes"    -> "notes"
        "math"             -> "math"  (unchanged)
    """
    q = _ACTION_PREFIX_RE.sub("", query.strip())
    q = _POSSESSIVE_RE.sub("", q)
    return q.strip() or query.strip()  # fallback to original if stripping empties it


def _strip_html(text: str) -> str:
    """Strip basic HTML tags using regex."""
    return re.sub(r"<[^>]+>", "", text or "")


class SearchService:
    def _get_accessible_user_ids(self, user_id: int, user_role: str, db: Session) -> list[int]:
        """Get user IDs whose data the current user can see (self + children for parents)."""
        ids = [user_id]
        if user_role == "parent":
            child_ids = [
                row[0] for row in db.query(Student.user_id)
                .join(parent_students, parent_students.c.student_id == Student.id)
                .filter(parent_students.c.parent_id == user_id)
                .all()
            ]
            ids.extend(child_ids)
        return ids

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
        # "show my tasks", "list my courses", "my assignments" → list all entities of that type
        words = set(msg.split())
        has_trigger = bool(words & _ENTITY_LIST_TRIGGERS) or msg.startswith("my ")
        if has_trigger:
            for preset_name, pattern in _ENTITY_LIST_PATTERNS:
                if pattern.search(msg):
                    return preset_name
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

    def _extract_person_filter(self, message: str) -> str | None:
        """Detect 'for [name]' / 'for [name]'s' patterns and return the name, or None."""
        msg = message.strip()
        # Match "for <Name>" or "for <Name>'s"
        m = re.search(r"\bfor\s+([A-Za-z]+)(?:'s)?\b", msg, re.IGNORECASE)
        if m:
            return m.group(1)
        # Match "<Name>'s tasks" / "<Name>s tasks"
        m2 = re.search(r"\b([A-Za-z]+)'?s\s+(?:tasks?|assignments?)\b", msg, re.IGNORECASE)
        if m2:
            return m2.group(1)
        return None

    def _list_tasks_for_person(
        self, user_id: int, user_role: str, db: Session, person_name: str | None = None
    ) -> list[SearchResult]:
        """Return up to 8 tasks, optionally filtered to a named child (parent role only)."""
        from app.models.user import User as _User

        task_q = db.query(Task).filter(Task.archived_at.is_(None))

        if user_role == "parent":
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
            if person_name:
                matched_user_ids = [
                    row[0] for row in db.query(_User.id).filter(
                        _User.id.in_(child_user_ids),
                        _User.full_name.ilike(f"%{person_name}%"),
                    ).all()
                ]
                if matched_user_ids:
                    task_q = task_q.filter(
                        (Task.created_by_user_id.in_(matched_user_ids)) |
                        (Task.assigned_to_user_id.in_(matched_user_ids))
                    )
                else:
                    return []
            else:
                accessible_ids = self._get_accessible_user_ids(user_id, user_role, db)
                task_q = task_q.filter(
                    (Task.created_by_user_id.in_(accessible_ids)) |
                    (Task.assigned_to_user_id.in_(accessible_ids))
                )
        elif user_role == "student":
            task_q = task_q.filter(
                (Task.assigned_to_user_id == user_id) | (Task.created_by_user_id == user_id)
            )
        else:
            task_q = task_q.filter(Task.created_by_user_id == user_id)

        tasks = task_q.order_by(Task.due_date.asc().nullslast()).limit(20).all()
        results = []
        for t in tasks:
            due_str = t.due_date.strftime("%b %d") if t.due_date else None
            results.append(SearchResult(
                entity_type="task",
                id=t.id,
                title=t.title,
                description=f"Due: {due_str}" if due_str else t.description,
                actions=[{"label": "View", "route": f"/tasks/{t.id}"}],
            ))
        return results

    def _list_tasks(self, user_id: int, user_role: str, db: Session) -> list[SearchResult]:
        """Return up to 20 most recent non-archived tasks for the user."""
        q = db.query(Task).filter(Task.archived_at.is_(None))
        if user_role == "student":
            q = q.filter(
                (Task.assigned_to_user_id == user_id) | (Task.created_by_user_id == user_id)
            )
        elif user_role == "parent":
            accessible_ids = self._get_accessible_user_ids(user_id, user_role, db)
            q = q.filter(
                (Task.created_by_user_id.in_(accessible_ids)) |
                (Task.assigned_to_user_id.in_(accessible_ids))
            )
        else:
            q = q.filter(Task.created_by_user_id == user_id)
        total_count = q.count()
        tasks = q.order_by(Task.created_at.desc()).limit(20).all()
        results = [
            SearchResult(
                entity_type="task",
                id=t.id,
                title=t.title,
                description=t.description,
                actions=[{"label": "View", "route": f"/tasks/{t.id}"}],
            )
            for t in tasks
        ]
        if total_count > 20:
            results.append(SearchResult(
                entity_type="summary",
                id=None,
                title=f"Showing 20 of {total_count} tasks",
                description=None,
                actions=[{"label": "See all tasks", "route": "/tasks"}],
            ))
        return results

    def _list_courses(self, user_id: int, user_role: str, db: Session) -> list[SearchResult]:
        """Return up to 8 courses accessible to the user."""
        q = db.query(Course)
        if user_role == "student":
            student_row = db.query(Student).filter(Student.user_id == user_id).first()
            if student_row:
                q = q.filter(Course.students.any(Student.id == student_row.id))
            else:
                return []
        elif user_role == "parent":
            student_ids = [
                row[0] for row in db.query(parent_students.c.student_id).filter(
                    parent_students.c.parent_id == user_id
                ).all()
            ]
            if student_ids:
                q = q.filter(Course.students.any(Student.id.in_(student_ids)))
            else:
                return []
        elif user_role == "teacher":
            from app.models.teacher import Teacher
            teacher_row = db.query(Teacher).filter(Teacher.user_id == user_id).first()
            if teacher_row:
                q = q.filter(Course.teacher_id == teacher_row.id)
            else:
                return []
        courses = q.order_by(Course.name).limit(20).all()
        return [
            SearchResult(
                entity_type="course",
                id=c.id,
                title=c.name,
                description=c.description,
                actions=[{"label": "View", "route": f"/courses/{c.id}"}],
            )
            for c in courses
        ]

    def _list_assignments(self, user_id: int, user_role: str, db: Session) -> list[SearchResult]:
        """Return up to 8 recent assignments accessible to the user."""
        from app.models.assignment import Assignment
        q = db.query(Assignment, Course).join(Course, Assignment.course_id == Course.id)
        if user_role == "student":
            student_row = db.query(Student).filter(Student.user_id == user_id).first()
            if student_row:
                enrolled_ids = [
                    row[0] for row in db.query(student_courses.c.course_id).filter(
                        student_courses.c.student_id == student_row.id
                    ).all()
                ]
                q = q.filter(Assignment.course_id.in_(enrolled_ids))
            else:
                return []
        elif user_role == "parent":
            student_ids = [
                row[0] for row in db.query(parent_students.c.student_id).filter(
                    parent_students.c.parent_id == user_id
                ).all()
            ]
            if student_ids:
                enrolled_ids = [
                    row[0] for row in db.query(student_courses.c.course_id).filter(
                        student_courses.c.student_id.in_(student_ids)
                    ).all()
                ]
                q = q.filter(Assignment.course_id.in_(enrolled_ids))
            else:
                return []
        elif user_role == "teacher":
            from app.models.teacher import Teacher
            teacher_row = db.query(Teacher).filter(Teacher.user_id == user_id).first()
            if teacher_row:
                course_ids = [
                    row[0] for row in db.query(Course.id).filter(
                        Course.teacher_id == teacher_row.id
                    ).all()
                ]
                q = q.filter(Assignment.course_id.in_(course_ids))
            else:
                return []
        rows = q.order_by(Assignment.due_date.desc().nullslast()).limit(20).all()
        return [
            SearchResult(
                entity_type="assignment",
                id=a.id,
                title=a.title,
                description=c.name,
                actions=[{"label": "View", "route": f"/courses/{c.id}"}],
            )
            for a, c in rows
        ]

    def _list_study_guides(self, user_id: int, db: Session, user_role: str = "") -> list[SearchResult]:
        """Return up to 20 most recent study guides for the user (and children for parents)."""
        if user_role == "parent":
            accessible_ids = self._get_accessible_user_ids(user_id, user_role, db)
            guide_q = db.query(StudyGuide).filter(
                StudyGuide.user_id.in_(accessible_ids),
                StudyGuide.archived_at.is_(None),
            )
        else:
            guide_q = db.query(StudyGuide).filter(
                StudyGuide.user_id == user_id,
                StudyGuide.archived_at.is_(None),
            )
        total_count = guide_q.count()
        guides = guide_q.order_by(StudyGuide.created_at.desc()).limit(20).all()
        results = []
        tab_map = {"quiz": "quiz", "flashcards": "flashcards"}
        for g in guides:
            guide_type = g.guide_type or "study_guide"
            if g.course_content_id:
                tab = tab_map.get(guide_type, "guide")
                route = f"/course-materials/{g.course_content_id}?tab={tab}"
            else:
                route = f"/study/quiz/{g.id}" if guide_type == "quiz" else f"/study/flashcards/{g.id}" if guide_type == "flashcards" else f"/study/guide/{g.id}"
            results.append(SearchResult(
                entity_type="study_guide",
                id=g.id,
                title=g.title,
                description=None,
                actions=[{"label": "View", "route": route}],
            ))
        if total_count > 20:
            results.append(SearchResult(
                entity_type="summary",
                id=None,
                title=f"Showing 20 of {total_count} study guides",
                description=None,
                actions=[{"label": "See all study guides", "route": "/study-tools"}],
            ))
        return results

    def _list_notes(self, user_id: int, db: Session) -> list[SearchResult]:
        """Return up to 8 most recent notes for the user."""
        from app.models.course_content import CourseContent as _CC
        notes = db.query(Note).filter(Note.user_id == user_id).order_by(Note.updated_at.desc()).limit(20).all()
        results = []
        for n in notes:
            cc = db.query(_CC).filter(_CC.id == n.course_content_id).first()
            cc_title = cc.title if cc else f"material {n.course_content_id}"
            raw = n.plain_text or _strip_html(n.content or "")
            snippet = raw[:80].strip() if raw else None
            results.append(SearchResult(
                entity_type="note",
                id=n.id,
                title=f"Note on {cc_title}",
                description=snippet,
                actions=[{"label": "View", "route": f"/course-materials/{n.course_content_id}?notes=1"}],
            ))
        return results

    def _list_materials(self, user_id: int, user_role: str, db: Session) -> list[SearchResult]:
        """Return up to 8 course materials accessible to the user."""
        q = db.query(CourseContent).filter(CourseContent.archived_at.is_(None))
        if user_role == "student":
            student_row = db.query(Student).filter(Student.user_id == user_id).first()
            if student_row:
                enrolled_ids = [
                    row[0] for row in db.query(student_courses.c.course_id).filter(
                        student_courses.c.student_id == student_row.id
                    ).all()
                ]
                q = q.filter(CourseContent.course_id.in_(enrolled_ids))
            else:
                return []
        elif user_role == "parent":
            student_ids = [
                row[0] for row in db.query(parent_students.c.student_id).filter(
                    parent_students.c.parent_id == user_id
                ).all()
            ]
            if student_ids:
                enrolled_ids = [
                    row[0] for row in db.query(student_courses.c.course_id).filter(
                        student_courses.c.student_id.in_(student_ids)
                    ).all()
                ]
                q = q.filter(CourseContent.course_id.in_(enrolled_ids))
            else:
                return []
        elif user_role == "teacher":
            from app.models.teacher import Teacher
            teacher_row = db.query(Teacher).filter(Teacher.user_id == user_id).first()
            if teacher_row:
                course_ids = [
                    row[0] for row in db.query(Course.id).filter(
                        Course.teacher_id == teacher_row.id
                    ).all()
                ]
                q = q.filter(CourseContent.course_id.in_(course_ids))
            else:
                return []
        items = q.order_by(CourseContent.created_at.desc()).limit(20).all()
        return [
            SearchResult(
                entity_type="course_content",
                id=cc.id,
                title=cc.title,
                description=cc.description,
                actions=[{"label": "View", "route": f"/course-materials/{cc.id}"}],
            )
            for cc in items
        ]

    def search(self, query: str, user_id: int, user_role: str, db: Session) -> list[SearchResult]:
        """Search across platform entities and return up to 10 results total."""
        # Person-scoped queries take priority over list presets
        msg = query.lower().strip()
        person_name = self._extract_person_filter(query)
        if person_name and any(w in msg for w in ["task", "assignment"]):
            return self._list_tasks_for_person(user_id, user_role, db, person_name=person_name)

        preset = self.detect_preset(query)

        if preset == "upload":
            return [SearchResult(
                entity_type="action",
                id=None,
                title="Upload Material",
                description="Upload course materials or study resources",
                actions=[{"label": "Go to Study Tools", "route": "/study"}],
            )]

        if preset == "create":
            return [
                SearchResult(
                    entity_type="action",
                    id=None,
                    title="New Course",
                    description="Create a new course",
                    actions=[{"label": "Create", "route": "/courses"}],
                ),
                SearchResult(
                    entity_type="action",
                    id=None,
                    title="New Task",
                    description="Create a new task",
                    actions=[{"label": "Create", "route": "/tasks"}],
                ),
                SearchResult(
                    entity_type="action",
                    id=None,
                    title="Generate Study Guide",
                    description="Generate an AI study guide",
                    actions=[{"label": "Go to Study Tools", "route": "/study"}],
                ),
            ]

        if preset in ("due", "overdue"):
            return self.get_due_tasks(user_id, user_role, db)

        if preset == "list_tasks":
            return self._list_tasks(user_id, user_role, db)

        if preset == "list_courses":
            return self._list_courses(user_id, user_role, db)

        if preset == "list_assignments":
            return self._list_assignments(user_id, user_role, db)

        if preset == "list_study_guides":
            return self._list_study_guides(user_id, db, user_role=user_role)

        if preset == "list_notes":
            return self._list_notes(user_id, db)

        if preset == "list_materials":
            return self._list_materials(user_id, user_role, db)

        raw = _extract_search_term(query)
        term = f"%{escape_like(raw)}%"
        results: list[SearchResult] = []
        remaining = 25

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
                    actions=[{"label": "View Profile", "route": "/my-kids"}],
                ))
            remaining = 25 - len(results)
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
                actions=[{"label": "View", "route": f"/courses/{c.id}"}],
            ))
        remaining = 25 - len(results)
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
                actions=[{"label": "View", "route": f"/courses/{a.course_id}"}],
            ))
        remaining = 25 - len(results)
        if remaining <= 0:
            return results

        # Study Guides (filter by owner; parents also see children's guides)
        if user_role == "parent":
            accessible_ids = self._get_accessible_user_ids(user_id, user_role, db)
            guide_q = db.query(StudyGuide).filter(
                StudyGuide.title.ilike(term),
                StudyGuide.user_id.in_(accessible_ids),
                StudyGuide.archived_at.is_(None),
            )
        else:
            guide_q = db.query(StudyGuide).filter(
                StudyGuide.title.ilike(term),
                StudyGuide.user_id == user_id,
                StudyGuide.archived_at.is_(None),
            )
        tab_map = {"quiz": "quiz", "flashcards": "flashcards"}
        for g in guide_q.limit(remaining).all():
            guide_type = g.guide_type or "study_guide"
            if g.course_content_id:
                tab = tab_map.get(guide_type, "guide")
                route = f"/course-materials/{g.course_content_id}?tab={tab}"
            else:
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
        remaining = 25 - len(results)
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
            accessible_ids = self._get_accessible_user_ids(user_id, user_role, db)
            task_q = task_q.filter(
                (Task.created_by_user_id.in_(accessible_ids)) |
                (Task.assigned_to_user_id.in_(accessible_ids))
            )
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
        remaining = 25 - len(results)
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
                actions=[{"label": "View", "route": f"/course-materials/{cc.id}"}],
            ))
        remaining = 25 - len(results)
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
        remaining = 25 - len(results)
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
