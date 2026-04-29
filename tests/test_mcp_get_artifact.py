"""CB-CMCP-001 M2-B 2B-2 (#4553) — ``get_artifact`` MCP tool tests.

Covers the role-scoped visibility matrix on the
``POST /mcp/call_tool`` route when ``name="get_artifact"`` and on the
handler directly:

- PARENT linked to a child can fetch the child's artifact.
- PARENT *not* linked → 403.
- TEACHER assigned to the artifact's course can fetch it.
- BOARD_ADMIN with a matching board_id can fetch; cross-board → 403.
- CURRICULUM_ADMIN sees any artifact.
- Unknown ``artifact_id`` → 404.
- M3 dependency invariant: works for non-CMCP artifacts too (legacy
  rows whose CMCP columns are still NULL).

Tests use the shared SQLite test app from ``conftest.py``. JWT signing
is local crypto (jose), DB reads go through the in-process SQLite
session — no external network calls. Per the project conventions, model
imports happen *inside* each test/fixture rather than at module top
because the session-scoped ``app`` fixture reloads ``app.models``.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ---------------------------------------------------------------------------
# Flag fixtures — ``mcp.enabled`` ON for every test in this module
# ---------------------------------------------------------------------------


@pytest.fixture()
def mcp_flag_on(db_session):
    """Force ``mcp.enabled`` ON for the test, OFF after."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "mcp.enabled")
        .first()
    )
    assert flag is not None, "mcp.enabled flag must be seeded"
    flag.enabled = True
    db_session.commit()
    yield flag
    db_session.refresh(flag)
    flag.enabled = False
    db_session.commit()


# ---------------------------------------------------------------------------
# User fixtures — one per role on the matrix
# ---------------------------------------------------------------------------


def _make_user(db_session, role, *, email_prefix=None, board_id=None):
    """Build + persist a User with the given role.

    The optional ``board_id`` kwarg attaches a Python attribute to the
    returned ``User`` instance so :func:`_resolve_caller_board_id` in
    the handler picks it up. We intentionally don't ALTER the users
    table here — board affiliation is M3-E and lives on a future
    column; the handler's ``getattr(user, 'board_id', None)`` lookup
    works either way.
    """
    from app.core.security import get_password_hash
    from app.models.user import User

    prefix = email_prefix or f"mcp_ga_{role.value.lower()}"
    user = User(
        email=f"{prefix}_{uuid4().hex[:8]}@test.com",
        full_name=f"GetArtifact Test {role.value}",
        role=role,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    if board_id is not None:
        # Attach as a transient attribute — see fixture docstring above.
        user.board_id = board_id
    return user


@pytest.fixture()
def parent_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.PARENT)


@pytest.fixture()
def unrelated_parent_user(db_session):
    from app.models.user import UserRole

    return _make_user(
        db_session, UserRole.PARENT, email_prefix="mcp_ga_unrelated_parent"
    )


@pytest.fixture()
def student_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.STUDENT)


@pytest.fixture()
def teacher_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.TEACHER)


@pytest.fixture()
def other_teacher_user(db_session):
    from app.models.user import UserRole

    return _make_user(
        db_session, UserRole.TEACHER, email_prefix="mcp_ga_other_teacher"
    )


@pytest.fixture()
def board_admin_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.BOARD_ADMIN)


@pytest.fixture()
def curriculum_admin_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.CURRICULUM_ADMIN)


# ---------------------------------------------------------------------------
# Student / parent / course / artifact fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def kid_user(db_session):
    """A STUDENT user that the parent fixture is linked to."""
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.STUDENT, email_prefix="mcp_ga_kid")


@pytest.fixture()
def kid_student_record(db_session, kid_user):
    from app.models.student import Student

    s = Student(
        user_id=kid_user.id,
        grade_level=8,
        school_name="MCP GetArtifact Test School",
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture()
def linked_parent(db_session, parent_user, kid_student_record):
    """Parent linked to ``kid_student_record`` via ``parent_students``."""
    from app.models.student import parent_students

    db_session.execute(
        parent_students.insert().values(
            parent_id=parent_user.id,
            student_id=kid_student_record.id,
        )
    )
    db_session.commit()
    return parent_user


@pytest.fixture()
def teacher_record(db_session, teacher_user):
    from app.models.teacher import Teacher

    t = Teacher(
        user_id=teacher_user.id, school_name="MCP GetArtifact Test School"
    )
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture()
def teacher_course(db_session, teacher_record):
    """Course assigned to ``teacher_record``."""
    from app.models.course import Course

    c = Course(
        name="MCP GetArtifact Test Course",
        subject="Math",
        teacher_id=teacher_record.id,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture()
def kid_artifact(db_session, kid_user):
    """A non-CMCP study guide owned by ``kid_user``.

    Mirrors a legacy CB-ASGF/CB-UTDF artifact — CMCP columns are NULL
    so the test exercises the M3-dependency-safe code path the handler
    must support.
    """
    from app.models.study_guide import StudyGuide

    sg = StudyGuide(
        user_id=kid_user.id,
        title="Kid's Study Guide",
        content="# Kid's notes",
        guide_type="study_guide",
    )
    db_session.add(sg)
    db_session.commit()
    db_session.refresh(sg)
    return sg


@pytest.fixture()
def class_artifact(db_session, teacher_user, teacher_course):
    """A study guide created by the teacher, attached to their course."""
    from app.models.study_guide import StudyGuide

    sg = StudyGuide(
        user_id=teacher_user.id,
        course_id=teacher_course.id,
        title="Class Study Guide",
        content="# Class notes",
        guide_type="study_guide",
        # CMCP columns populated to verify they round-trip in the
        # response shape (covers M3 origin artifacts).
        se_codes=["MTH.A.1", "MTH.A.2"],
        state="APPROVED",
        ai_engine="openai",
    )
    db_session.add(sg)
    db_session.commit()
    db_session.refresh(sg)
    return sg


@pytest.fixture()
def board_artifact(db_session, kid_user):
    """A study guide stamped with ``board_id="TDSB"``.

    Owner is incidental — what matters for BOARD_ADMIN tests is the
    ``board_id`` column. We re-use ``kid_user`` as a simple owner.
    """
    from app.models.study_guide import StudyGuide

    sg = StudyGuide(
        user_id=kid_user.id,
        title="Board-Scoped Artifact",
        content="# Board content",
        guide_type="study_guide",
        board_id="TDSB",
    )
    db_session.add(sg)
    db_session.commit()
    db_session.refresh(sg)
    return sg


# ---------------------------------------------------------------------------
# Direct handler tests — exercise the visibility matrix without the route
# ---------------------------------------------------------------------------


class TestGetArtifactHandler:
    """Direct handler tests — bypass the route to focus on visibility."""

    def test_parent_can_fetch_kids_artifact(
        self, db_session, linked_parent, kid_artifact
    ):
        from app.mcp.tools.get_artifact import get_artifact_handler

        result = get_artifact_handler(
            {"artifact_id": kid_artifact.id}, linked_parent, db_session
        )
        assert result["artifact"]["id"] == kid_artifact.id
        assert result["artifact"]["title"] == "Kid's Study Guide"
        # Legacy artifact — CMCP columns surface as None, not absent.
        assert result["artifact"]["se_codes"] is None
        assert result["artifact"]["board_id"] is None

    def test_parent_cannot_fetch_unrelated_kids_artifact(
        self, db_session, unrelated_parent_user, kid_artifact
    ):
        from app.mcp.tools.get_artifact import (
            MCPArtifactAccessDeniedError,
            get_artifact_handler,
        )

        with pytest.raises(MCPArtifactAccessDeniedError):
            get_artifact_handler(
                {"artifact_id": kid_artifact.id},
                unrelated_parent_user,
                db_session,
            )

    def test_student_can_fetch_own_artifact(
        self, db_session, kid_user, kid_artifact
    ):
        from app.mcp.tools.get_artifact import get_artifact_handler

        result = get_artifact_handler(
            {"artifact_id": kid_artifact.id}, kid_user, db_session
        )
        assert result["artifact"]["id"] == kid_artifact.id

    def test_student_cannot_fetch_others_artifact(
        self, db_session, student_user, kid_artifact
    ):
        from app.mcp.tools.get_artifact import (
            MCPArtifactAccessDeniedError,
            get_artifact_handler,
        )

        with pytest.raises(MCPArtifactAccessDeniedError):
            get_artifact_handler(
                {"artifact_id": kid_artifact.id}, student_user, db_session
            )

    def test_teacher_can_fetch_class_artifact(
        self, db_session, teacher_user, teacher_record, class_artifact
    ):
        from app.mcp.tools.get_artifact import get_artifact_handler

        result = get_artifact_handler(
            {"artifact_id": class_artifact.id}, teacher_user, db_session
        )
        assert result["artifact"]["id"] == class_artifact.id
        # CMCP columns round-trip to the response.
        assert result["artifact"]["se_codes"] == ["MTH.A.1", "MTH.A.2"]
        assert result["artifact"]["state"] == "APPROVED"
        assert result["artifact"]["ai_engine"] == "openai"

    def test_teacher_cannot_fetch_other_class_artifact(
        self, db_session, other_teacher_user, class_artifact
    ):
        from app.mcp.tools.get_artifact import (
            MCPArtifactAccessDeniedError,
            get_artifact_handler,
        )

        # ``other_teacher_user`` has no Teacher row at all — assigned to
        # nothing. Verifies the matrix denies "TEACHER but not on this
        # course" cleanly.
        with pytest.raises(MCPArtifactAccessDeniedError):
            get_artifact_handler(
                {"artifact_id": class_artifact.id},
                other_teacher_user,
                db_session,
            )

    def test_board_admin_can_fetch_board_artifact(
        self, db_session, board_artifact
    ):
        from app.mcp.tools.get_artifact import get_artifact_handler
        from app.models.user import UserRole

        admin = _make_user(
            db_session,
            UserRole.BOARD_ADMIN,
            email_prefix="mcp_ga_ba_match",
            board_id="TDSB",
        )

        result = get_artifact_handler(
            {"artifact_id": board_artifact.id}, admin, db_session
        )
        assert result["artifact"]["id"] == board_artifact.id
        assert result["artifact"]["board_id"] == "TDSB"

    def test_board_admin_cross_board_denied(
        self, db_session, board_artifact
    ):
        from app.mcp.tools.get_artifact import (
            MCPArtifactAccessDeniedError,
            get_artifact_handler,
        )
        from app.models.user import UserRole

        admin = _make_user(
            db_session,
            UserRole.BOARD_ADMIN,
            email_prefix="mcp_ga_ba_other",
            board_id="OCDSB",
        )

        with pytest.raises(MCPArtifactAccessDeniedError):
            get_artifact_handler(
                {"artifact_id": board_artifact.id}, admin, db_session
            )

    def test_board_admin_denied_on_unscoped_artifact(
        self, db_session, kid_artifact
    ):
        """Per the conservative default: BOARD_ADMIN gets no access to
        artifacts whose ``board_id`` is NULL (the M3-E pre-stamping
        state). Without this guard a BOARD_ADMIN with no resolvable
        board would inadvertently see every legacy row.
        """
        from app.mcp.tools.get_artifact import (
            MCPArtifactAccessDeniedError,
            get_artifact_handler,
        )
        from app.models.user import UserRole

        admin = _make_user(
            db_session,
            UserRole.BOARD_ADMIN,
            email_prefix="mcp_ga_ba_unscoped",
            board_id="TDSB",
        )

        with pytest.raises(MCPArtifactAccessDeniedError):
            get_artifact_handler(
                {"artifact_id": kid_artifact.id}, admin, db_session
            )

    def test_curriculum_admin_can_fetch_any_artifact(
        self, db_session, curriculum_admin_user, kid_artifact, board_artifact
    ):
        from app.mcp.tools.get_artifact import get_artifact_handler

        # Across two artifacts owned by an unrelated user with mixed
        # board_id state — CURRICULUM_ADMIN reads both.
        for artifact in (kid_artifact, board_artifact):
            result = get_artifact_handler(
                {"artifact_id": artifact.id},
                curriculum_admin_user,
                db_session,
            )
            assert result["artifact"]["id"] == artifact.id

    def test_unknown_artifact_id_raises_not_found(
        self, db_session, curriculum_admin_user
    ):
        from app.mcp.tools.get_artifact import (
            MCPArtifactNotFoundError,
            get_artifact_handler,
        )

        with pytest.raises(MCPArtifactNotFoundError):
            get_artifact_handler(
                {"artifact_id": 9_999_999},
                curriculum_admin_user,
                db_session,
            )

    def test_invalid_artifact_id_type_raises_not_found(
        self, db_session, curriculum_admin_user
    ):
        """Non-integer ``artifact_id`` is rejected before the DB hit.

        The MCP transport's JSON Schema enforces this for normal HTTP
        callers, but unit tests calling the handler directly can pass
        whatever they want — the handler re-validates so misuse from
        another stripe surfaces as 404 rather than a 500.
        """
        from app.mcp.tools.get_artifact import (
            MCPArtifactNotFoundError,
            get_artifact_handler,
        )

        with pytest.raises(MCPArtifactNotFoundError):
            get_artifact_handler(
                {"artifact_id": "abc"}, curriculum_admin_user, db_session
            )

        # ``True``/``False`` would silently coerce to 1/0 in a DB query
        # because ``bool`` subclasses ``int``; the handler rejects them
        # explicitly to avoid that.
        with pytest.raises(MCPArtifactNotFoundError):
            get_artifact_handler(
                {"artifact_id": True}, curriculum_admin_user, db_session
            )


# ---------------------------------------------------------------------------
# Route-level tests — exercise the full ``POST /mcp/call_tool`` surface
# ---------------------------------------------------------------------------


class TestGetArtifactRoute:
    """End-to-end tests via ``POST /mcp/call_tool`` with auth + flag.

    These verify that the handler's exception types translate to the
    documented HTTP status codes, and that the catalog allowlist
    (extended to BOARD_ADMIN + CURRICULUM_ADMIN) lets those roles
    actually invoke the tool through the route layer.
    """

    def test_parent_route_fetches_kids_artifact(
        self, client, mcp_flag_on, linked_parent, kid_artifact
    ):
        headers = _auth(client, linked_parent.email)
        resp = client.post(
            "/mcp/call_tool",
            json={
                "name": "get_artifact",
                "arguments": {"artifact_id": kid_artifact.id},
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == "get_artifact"
        assert body["content"]["artifact"]["id"] == kid_artifact.id

    def test_parent_route_unrelated_artifact_403(
        self, client, mcp_flag_on, unrelated_parent_user, kid_artifact
    ):
        headers = _auth(client, unrelated_parent_user.email)
        resp = client.post(
            "/mcp/call_tool",
            json={
                "name": "get_artifact",
                "arguments": {"artifact_id": kid_artifact.id},
            },
            headers=headers,
        )
        assert resp.status_code == 403
        assert str(kid_artifact.id) in resp.json()["detail"]

    def test_route_unknown_artifact_404(
        self, client, mcp_flag_on, curriculum_admin_user
    ):
        headers = _auth(client, curriculum_admin_user.email)
        resp = client.post(
            "/mcp/call_tool",
            json={
                "name": "get_artifact",
                "arguments": {"artifact_id": 9_999_999},
            },
            headers=headers,
        )
        assert resp.status_code == 404
        assert "9999999" in resp.json()["detail"]

    def test_route_curriculum_admin_in_allowlist(
        self, client, mcp_flag_on, curriculum_admin_user, kid_artifact
    ):
        """CURRICULUM_ADMIN must reach the handler (catalog allowlist)."""
        headers = _auth(client, curriculum_admin_user.email)
        resp = client.post(
            "/mcp/call_tool",
            json={
                "name": "get_artifact",
                "arguments": {"artifact_id": kid_artifact.id},
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["content"]["artifact"]["id"] == kid_artifact.id

    def test_route_board_admin_in_allowlist(
        self, client, mcp_flag_on, board_admin_user, board_artifact
    ):
        """BOARD_ADMIN passes the catalog filter; per-row scoping then
        denies the artifact (because no User.board_id column exists yet,
        :func:`_resolve_caller_board_id` returns ``None``). The dispatch
        produces a 403 (per-row), not the 403-from-catalog of stripe 2A-3,
        which is exactly the visibility behaviour we want until M3-E.
        """
        headers = _auth(client, board_admin_user.email)
        resp = client.post(
            "/mcp/call_tool",
            json={
                "name": "get_artifact",
                "arguments": {"artifact_id": board_artifact.id},
            },
            headers=headers,
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Catalog tests — verify the role allowlist extension
# ---------------------------------------------------------------------------


class TestGetArtifactRegistry:
    """Lightweight checks on the ``TOOLS`` registry entry itself."""

    def test_registered_with_concrete_handler(self):
        """``TOOLS["get_artifact"].handler`` is no longer the stub."""
        from app.mcp.tools import TOOLS
        from app.mcp.tools.get_artifact import get_artifact_handler

        descriptor = TOOLS["get_artifact"]
        assert descriptor.handler is get_artifact_handler

    @pytest.mark.parametrize(
        "role",
        [
            "PARENT",
            "STUDENT",
            "TEACHER",
            "BOARD_ADMIN",
            "CURRICULUM_ADMIN",
            "ADMIN",
        ],
    )
    def test_role_in_allowlist(self, role):
        from app.mcp.tools import TOOLS

        descriptor = TOOLS["get_artifact"]
        assert descriptor.is_role_allowed(role)
