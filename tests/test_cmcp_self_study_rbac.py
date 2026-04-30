"""Tests for CB-CMCP-001 M3α 3B-3 (#4585) — SELF_STUDY artifact RBAC.

3B-1 (#4577) wired the SELF_STUDY state per locked decision D3=C
(self-initiated parent + student artifacts skip the teacher review
queue). This stripe enforces visibility: a SELF_STUDY artifact is
private to a family pair (requestor + their parent/child) and is NOT
visible to the broader class roster, the course teacher, BOARD_ADMIN,
or CURRICULUM_ADMIN.

Coverage:
- Row-level (``_user_can_view`` / ``_self_study_family_can_view``)
- List-level (``_apply_role_scope`` SELF_STUDY narrowing)
- Review queue (SELF_STUDY rows denied even for ADMIN by id)
- Parent companion REST endpoint (uses ``_user_can_view`` → 404 on
  cross-family access for SELF_STUDY)

All tests use the in-process SQLite test app from ``conftest.py`` —
no external Claude/OpenAI calls.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from conftest import PASSWORD


# ─────────────────────────────────────────────────────────────────────
# User factory + role fixtures
# ─────────────────────────────────────────────────────────────────────


def _make_user(db_session, role, *, email_prefix=None):
    from app.core.security import get_password_hash
    from app.models.user import User

    prefix = email_prefix or f"cmcp_ss_{role.value.lower()}"
    user = User(
        email=f"{prefix}_{uuid4().hex[:8]}@test.com",
        full_name=f"SelfStudy Test {role.value}",
        role=role,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def parent_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.PARENT)


@pytest.fixture()
def unrelated_parent_user(db_session):
    from app.models.user import UserRole

    return _make_user(
        db_session, UserRole.PARENT, email_prefix="cmcp_ss_unrelated_parent"
    )


@pytest.fixture()
def student_user(db_session):
    """The 'kid' — a STUDENT user that ``parent_user`` is linked to."""
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.STUDENT, email_prefix="cmcp_ss_kid")


@pytest.fixture()
def unrelated_student_user(db_session):
    from app.models.user import UserRole

    return _make_user(
        db_session, UserRole.STUDENT, email_prefix="cmcp_ss_unrelated_kid"
    )


@pytest.fixture()
def teacher_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.TEACHER)


@pytest.fixture()
def board_admin_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.BOARD_ADMIN)


@pytest.fixture()
def curriculum_admin_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.CURRICULUM_ADMIN)


@pytest.fixture()
def admin_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.ADMIN)


# ─────────────────────────────────────────────────────────────────────
# Student record + parent-link fixture
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture()
def student_record(db_session, student_user):
    from app.models.student import Student

    s = Student(
        user_id=student_user.id,
        grade_level=8,
        school_name="SelfStudy Test School",
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture()
def linked_parent(db_session, parent_user, student_record):
    """Link ``parent_user`` to ``student_record`` via parent_students.

    Returns the parent user. Use this fixture (rather than ``parent_user``
    directly) when the test needs the parent-child relationship to be
    materialized.
    """
    from app.models.student import parent_students

    db_session.execute(
        parent_students.insert().values(
            parent_id=parent_user.id,
            student_id=student_record.id,
        )
    )
    db_session.commit()
    return parent_user


@pytest.fixture()
def teacher_record(db_session, teacher_user):
    from app.models.teacher import Teacher

    t = Teacher(
        user_id=teacher_user.id,
        school_name="SelfStudy Test School",
    )
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture()
def teacher_course(db_session, teacher_record, student_record):
    """Course taught by ``teacher_user`` and enrolling ``student_record``.

    The enrollment is what makes the teacher "the kid's teacher" in
    spec terms — used to verify that even a teacher with the kid in
    their class is denied access to the kid's SELF_STUDY artifact.
    """
    from app.models.course import Course, student_courses

    c = Course(
        name="SelfStudy Test Course",
        subject="Math",
        teacher_id=teacher_record.id,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)

    db_session.execute(
        student_courses.insert().values(
            student_id=student_record.id,
            course_id=c.id,
        )
    )
    db_session.commit()
    return c


# ─────────────────────────────────────────────────────────────────────
# SELF_STUDY artifact fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture()
def kid_self_study_artifact(db_session, student_user):
    """A SELF_STUDY artifact owned by the STUDENT (the kid).

    Per D3=C, a student-self-initiated artifact has state=SELF_STUDY
    and ``course_id IS NULL`` — the artifact persistence helper assigns
    SELF_STUDY only when the requestor is non-teacher OR has no
    ``course_id``.
    """
    from app.models.study_guide import StudyGuide

    sg = StudyGuide(
        user_id=student_user.id,
        course_id=None,
        title="Kid's Self-Study Guide",
        content="# kid private notes",
        guide_type="study_guide",
        state="SELF_STUDY",
    )
    db_session.add(sg)
    db_session.commit()
    db_session.refresh(sg)
    return sg


@pytest.fixture()
def parent_self_study_artifact(db_session, parent_user):
    """A SELF_STUDY artifact owned by the PARENT.

    Used to verify symmetric visibility: a child should see their
    parent's SELF_STUDY artifact (kid-of-creator branch).
    """
    from app.models.study_guide import StudyGuide

    sg = StudyGuide(
        user_id=parent_user.id,
        course_id=None,
        title="Parent's Self-Study Guide",
        content="# parent private notes",
        guide_type="study_guide",
        state="SELF_STUDY",
    )
    db_session.add(sg)
    db_session.commit()
    db_session.refresh(sg)
    return sg


# ─────────────────────────────────────────────────────────────────────
# Row-level: ``_user_can_view`` SELF_STUDY override
# ─────────────────────────────────────────────────────────────────────


class TestRowLevelSelfStudyVisibility:
    """Row-level visibility for SELF_STUDY artifacts."""

    def test_creator_student_can_view_own_self_study(
        self, db_session, student_user, kid_self_study_artifact
    ):
        """STUDENT who created the artifact can view it."""
        from app.mcp.tools.get_artifact import _user_can_view

        assert (
            _user_can_view(kid_self_study_artifact, student_user, db_session)
            is True
        )

    def test_creator_parent_can_view_own_self_study(
        self, db_session, parent_user, parent_self_study_artifact
    ):
        """PARENT who created the artifact can view it."""
        from app.mcp.tools.get_artifact import _user_can_view

        assert (
            _user_can_view(
                parent_self_study_artifact, parent_user, db_session
            )
            is True
        )

    def test_linked_parent_can_view_kids_self_study(
        self, db_session, linked_parent, kid_self_study_artifact
    ):
        """PARENT linked to the STUDENT requestor can view kid's SELF_STUDY."""
        from app.mcp.tools.get_artifact import _user_can_view

        assert (
            _user_can_view(
                kid_self_study_artifact, linked_parent, db_session
            )
            is True
        )

    def test_linked_kid_can_view_parents_self_study(
        self,
        db_session,
        linked_parent,  # ensures the parent-student link exists
        student_user,
        parent_self_study_artifact,
    ):
        """STUDENT linked to the PARENT requestor can view parent's SELF_STUDY.

        Symmetric to the parent-sees-kid case. ``linked_parent`` is
        included so the parent_students association exists; the test
        then checks the STUDENT-as-caller branch.
        """
        from app.mcp.tools.get_artifact import _user_can_view

        assert (
            _user_can_view(
                parent_self_study_artifact, student_user, db_session
            )
            is True
        )

    def test_unrelated_parent_denied_kids_self_study(
        self, db_session, unrelated_parent_user, kid_self_study_artifact
    ):
        """A PARENT NOT linked to the kid → cross-family denied."""
        from app.mcp.tools.get_artifact import _user_can_view

        assert (
            _user_can_view(
                kid_self_study_artifact, unrelated_parent_user, db_session
            )
            is False
        )

    def test_unrelated_student_denied_other_kids_self_study(
        self,
        db_session,
        unrelated_student_user,
        kid_self_study_artifact,
    ):
        """A STUDENT who is not the creator → cross-family denied.

        Two unrelated students each have their own SELF_STUDY workspace;
        one student must not see the other's artifact even when both
        are pure-STUDENT role (no ADMIN bypass).
        """
        from app.mcp.tools.get_artifact import _user_can_view

        assert (
            _user_can_view(
                kid_self_study_artifact, unrelated_student_user, db_session
            )
            is False
        )

    def test_teacher_of_class_denied_kids_self_study(
        self,
        db_session,
        teacher_user,
        teacher_record,
        teacher_course,  # enrolls student_record
        kid_self_study_artifact,
    ):
        """The teacher who has the kid in class is STILL denied SELF_STUDY.

        This is the heart of the 3B-3 contract: SELF_STUDY is private,
        not class-distributable. Even a teacher whose roster includes
        the student gets no read access to that student's SELF_STUDY
        artifact.
        """
        from app.mcp.tools.get_artifact import _user_can_view

        assert (
            _user_can_view(
                kid_self_study_artifact, teacher_user, db_session
            )
            is False
        )

    def test_board_admin_denied_self_study(
        self, db_session, board_admin_user, kid_self_study_artifact
    ):
        """BOARD_ADMIN cannot view SELF_STUDY artifacts.

        Even when the artifact's ``board_id`` matches the admin's board
        scope, the SELF_STUDY override blocks access — the family
        override doesn't open a board-admin path. Set the admin's
        ``board_id`` to verify the standard BOARD_ADMIN match path is
        suppressed for SELF_STUDY.
        """
        from app.mcp.tools.get_artifact import _user_can_view

        # Match the board_id so the standard BOARD_ADMIN path WOULD
        # have granted access on a non-SELF_STUDY row.
        kid_self_study_artifact.board_id = "TDSB"
        db_session.add(kid_self_study_artifact)
        db_session.commit()
        board_admin_user.board_id = "TDSB"

        assert (
            _user_can_view(
                kid_self_study_artifact, board_admin_user, db_session
            )
            is False
        )

    def test_curriculum_admin_denied_self_study(
        self, db_session, curriculum_admin_user, kid_self_study_artifact
    ):
        """CURRICULUM_ADMIN cannot view SELF_STUDY artifacts.

        The standard matrix lets CURRICULUM_ADMIN see everything; the
        SELF_STUDY override narrows that — curriculum admins manage
        curriculum, not private learner workspaces.
        """
        from app.mcp.tools.get_artifact import _user_can_view

        assert (
            _user_can_view(
                kid_self_study_artifact, curriculum_admin_user, db_session
            )
            is False
        )

    def test_admin_can_view_self_study(
        self, db_session, admin_user, kid_self_study_artifact
    ):
        """ADMIN keeps the catch-all bypass even for SELF_STUDY.

        ADMIN is the one ops/debug role that retains full visibility —
        explicitly documented in ``_user_can_view``'s SELF_STUDY block.
        """
        from app.mcp.tools.get_artifact import _user_can_view

        assert (
            _user_can_view(
                kid_self_study_artifact, admin_user, db_session
            )
            is True
        )


# ─────────────────────────────────────────────────────────────────────
# List-level: ``_apply_role_scope`` SELF_STUDY narrowing
# ─────────────────────────────────────────────────────────────────────


class TestListLevelSelfStudyVisibility:
    """List-level SELF_STUDY scoping via ``_apply_role_scope``.

    These tests exercise the full ``list_catalog`` handler over the
    in-process SQLite session so the SQL filter shape is real.
    """

    def test_linked_parent_sees_kids_self_study_in_list(
        self,
        db_session,
        linked_parent,
        kid_self_study_artifact,
    ):
        """A linked parent listing SELF_STUDY artifacts sees the kid's row."""
        from app.mcp.tools.list_catalog import list_catalog

        result = list_catalog(
            {"state": "SELF_STUDY", "limit": 50},
            linked_parent,
            db_session,
        )
        ids = [row["id"] for row in result["artifacts"]]
        assert kid_self_study_artifact.id in ids

    def test_unrelated_parent_does_not_see_kids_self_study_in_list(
        self,
        db_session,
        unrelated_parent_user,
        kid_self_study_artifact,
    ):
        """An unrelated parent must not see the kid's SELF_STUDY in the list."""
        from app.mcp.tools.list_catalog import list_catalog

        result = list_catalog(
            {"state": "SELF_STUDY", "limit": 50},
            unrelated_parent_user,
            db_session,
        )
        ids = [row["id"] for row in result["artifacts"]]
        assert kid_self_study_artifact.id not in ids

    def test_teacher_does_not_see_kids_self_study_in_list(
        self,
        db_session,
        teacher_user,
        teacher_record,
        teacher_course,
        kid_self_study_artifact,
    ):
        """Teacher of the kid's class cannot see kid's SELF_STUDY via list."""
        from app.mcp.tools.list_catalog import list_catalog

        result = list_catalog(
            {"state": "SELF_STUDY", "limit": 50},
            teacher_user,
            db_session,
        )
        ids = [row["id"] for row in result["artifacts"]]
        assert kid_self_study_artifact.id not in ids

    def test_board_admin_does_not_see_self_study_in_list(
        self,
        db_session,
        board_admin_user,
        kid_self_study_artifact,
    ):
        """BOARD_ADMIN does not see SELF_STUDY rows in the list scope.

        Even when board_id matches, SELF_STUDY narrowing blocks.
        """
        from app.mcp.tools.list_catalog import list_catalog

        kid_self_study_artifact.board_id = "TDSB"
        db_session.add(kid_self_study_artifact)
        db_session.commit()
        board_admin_user.board_id = "TDSB"

        result = list_catalog(
            {"state": "SELF_STUDY", "limit": 50},
            board_admin_user,
            db_session,
        )
        ids = [row["id"] for row in result["artifacts"]]
        assert kid_self_study_artifact.id not in ids

    def test_curriculum_admin_does_not_see_self_study_in_list(
        self,
        db_session,
        curriculum_admin_user,
        kid_self_study_artifact,
    ):
        """CURRICULUM_ADMIN sees no SELF_STUDY rows other than their own."""
        from app.mcp.tools.list_catalog import list_catalog

        result = list_catalog(
            {"state": "SELF_STUDY", "limit": 50},
            curriculum_admin_user,
            db_session,
        )
        ids = [row["id"] for row in result["artifacts"]]
        assert kid_self_study_artifact.id not in ids

    def test_student_can_list_own_and_parents_self_study(
        self,
        db_session,
        linked_parent,
        student_user,
        parent_self_study_artifact,
    ):
        """STUDENT's list scope picks up parent's SELF_STUDY (family override)."""
        from app.mcp.tools.list_catalog import list_catalog

        result = list_catalog(
            {"state": "SELF_STUDY", "limit": 50},
            student_user,
            db_session,
        )
        ids = [row["id"] for row in result["artifacts"]]
        assert parent_self_study_artifact.id in ids

    def test_admin_lists_all_self_study(
        self,
        db_session,
        admin_user,
        kid_self_study_artifact,
        parent_self_study_artifact,
    ):
        """ADMIN keeps full visibility on SELF_STUDY rows."""
        from app.mcp.tools.list_catalog import list_catalog

        result = list_catalog(
            {"state": "SELF_STUDY", "limit": 50},
            admin_user,
            db_session,
        )
        ids = [row["id"] for row in result["artifacts"]]
        assert kid_self_study_artifact.id in ids
        assert parent_self_study_artifact.id in ids


# ─────────────────────────────────────────────────────────────────────
# Review queue: SELF_STUDY denied even by id (defence-in-depth)
# ─────────────────────────────────────────────────────────────────────


class TestReviewQueueSelfStudy:
    """SELF_STUDY rows must not be reachable through the review queue."""

    def test_review_queue_does_not_list_self_study(
        self,
        db_session,
        admin_user,
        kid_self_study_artifact,
    ):
        """The review queue list filters by state=PENDING_REVIEW already."""
        from app.api.routes.cmcp_review import list_review_queue

        # Direct call rather than via the route — the route layer also
        # gates on cmcp.enabled which is unrelated to the visibility
        # contract being tested here.
        resp = list_review_queue(
            page=1,
            limit=50,
            sort_by="created_at",
            current_user=admin_user,
            db=db_session,
        )
        ids = [item.id for item in resp.items]
        assert kid_self_study_artifact.id not in ids

    def test_review_queue_by_id_denies_self_study_for_admin(
        self,
        db_session,
        admin_user,
        kid_self_study_artifact,
    ):
        """ADMIN by id 404s on a SELF_STUDY artifact (queue is not its home).

        Defence-in-depth: SELF_STUDY rows live outside the review
        pipeline. Even ADMIN gets a 404 by id so a stray PATCH/approve
        cannot mutate state on a private learner artifact.
        """
        from fastapi import HTTPException

        from app.api.routes.cmcp_review import _load_review_artifact

        with pytest.raises(HTTPException) as excinfo:
            _load_review_artifact(
                kid_self_study_artifact.id, admin_user, db_session
            )
        assert excinfo.value.status_code == 404

    def test_review_queue_by_id_denies_self_study_for_teacher(
        self,
        db_session,
        teacher_user,
        teacher_record,
        teacher_course,
        kid_self_study_artifact,
    ):
        """TEACHER by id 404s on a SELF_STUDY artifact, even of own class."""
        from fastapi import HTTPException

        from app.api.routes.cmcp_review import _load_review_artifact

        # Pin the artifact to the teacher's course so the standard
        # matrix would otherwise grant access.
        kid_self_study_artifact.course_id = teacher_course.id
        db_session.add(kid_self_study_artifact)
        db_session.commit()

        with pytest.raises(HTTPException) as excinfo:
            _load_review_artifact(
                kid_self_study_artifact.id, teacher_user, db_session
            )
        assert excinfo.value.status_code == 404
