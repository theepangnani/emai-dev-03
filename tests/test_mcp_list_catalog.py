"""CB-CMCP-001 M2-B 2B-3 (#4554) — ``list_catalog`` MCP tool tests.

The tool is registered in :data:`app.mcp.tools.TOOLS` and dispatched via
the ``/mcp/call_tool`` route. These tests cover three layers:

1. The pure handler in :mod:`app.mcp.tools.list_catalog` (cursor encoding
   round-trip, validation, default state, role-scope dispatch). Database
   access is mocked at the SQLAlchemy ``Query`` boundary so the tests
   don't depend on M3 persistence.
2. The registry wiring (``TOOLS["list_catalog"].roles`` includes the new
   admin roles; ``input_schema`` exposes the new parameters).
3. The end-to-end route dispatch via ``TestClient`` for the regression
   net (default state + cursor pagination over real ``study_guides``
   rows seeded in the in-process SQLite DB).

We mock the DB query in (1) so the tests are deterministic regardless of
whether the M3 persistence stripe has landed. The route-level test in (3)
seeds rows directly via the SQLAlchemy session — no real Claude/OpenAI
calls.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _fake_row(
    *,
    row_id: int,
    title: str = "Sample Guide",
    guide_type: str = "study_guide",
    state: str = "APPROVED",
    se_codes: list[str] | None = None,
    course_id: int | None = None,
    user_id: int = 1,
    created_at: datetime | None = None,
):
    """Return an object that quacks like a ``StudyGuide`` row."""
    return SimpleNamespace(
        id=row_id,
        title=title,
        guide_type=guide_type,
        state=state,
        se_codes=se_codes,
        course_id=course_id,
        user_id=user_id,
        archived_at=None,
        created_at=created_at
        or datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        - timedelta(minutes=row_id),
    )


def _admin_user():
    """Return an in-memory ADMIN user — no DB seeding required."""
    role = SimpleNamespace(name="ADMIN", value="admin")
    return SimpleNamespace(id=999, role=role)


def _student_user():
    role = SimpleNamespace(name="STUDENT", value="student")
    return SimpleNamespace(id=42, role=role)


def _parent_user():
    role = SimpleNamespace(name="PARENT", value="parent")
    return SimpleNamespace(id=7, role=role)


def _teacher_user():
    role = SimpleNamespace(name="TEACHER", value="teacher")
    return SimpleNamespace(id=21, role=role)


def _board_admin_user(board_id: str | None = "TDSB"):
    """BOARD_ADMIN with an attached ``board_id`` attribute.

    ``board_id`` is intentionally ``getattr``-able (not a real column)
    because the User model doesn't carry it yet — see
    :func:`app.mcp.tools.list_catalog._resolve_caller_board_id`.
    """
    role = SimpleNamespace(name="BOARD_ADMIN", value="board_admin")
    user = SimpleNamespace(id=300, role=role)
    if board_id is not None:
        user.board_id = board_id
    return user


class _RecordingQuery:
    """A recording stand-in for ``session.query(StudyGuide)``.

    Captures the full call chain (``filter`` / ``order_by`` / ``limit``)
    and returns a configurable row list from ``.all()``. Used to assert
    on the role-scope filter applied to PARENT / STUDENT without
    standing up a real DB.
    """

    def __init__(self, all_result=None, subquery_result=None, first_result=None):
        self.calls: list[tuple[str, tuple]] = []
        self._all_result = all_result or []
        self._subquery_result = subquery_result
        self._first_result = first_result

    def filter(self, *args, **kw):
        self.calls.append(("filter", args))
        return self

    def order_by(self, *args, **kw):
        self.calls.append(("order_by", args))
        return self

    def limit(self, n):
        self.calls.append(("limit", (n,)))
        return self

    def join(self, *args, **kw):
        self.calls.append(("join", args))
        return self

    def subquery(self):
        self.calls.append(("subquery", ()))
        return self._subquery_result

    def all(self):
        return list(self._all_result)

    def first(self):
        # 3B-3 (#4585): SELF_STUDY scoping looks up the caller's
        # ``Student`` row to walk to linked-parent ids. Tests that
        # don't seed a Student return ``None`` (no parent linkage),
        # which the scope handles as "caller-only family list".
        return self._first_result


# ─────────────────────────────────────────────────────────────────────
# Cursor round-trip
# ─────────────────────────────────────────────────────────────────────


def test_cursor_encode_decode_roundtrip():
    from app.mcp.tools.list_catalog import _decode_cursor, _encode_cursor

    when = datetime(2026, 4, 28, 12, 30, 45, tzinfo=timezone.utc)
    cursor = _encode_cursor(when, 17)
    decoded_when, decoded_id = _decode_cursor(cursor)
    assert decoded_when == when
    assert decoded_id == 17


def test_cursor_decode_rejects_garbage():
    from app.mcp.tools._errors import MCPToolValidationError
    from app.mcp.tools.list_catalog import _decode_cursor

    with pytest.raises(MCPToolValidationError) as excinfo:
        _decode_cursor("not-base64!!!")
    assert "Invalid cursor" in str(excinfo.value)


def test_cursor_decode_rejects_missing_id_key():
    """Payload missing ``id`` → MCPToolValidationError (dispatcher 422)."""
    import base64
    import json

    from app.mcp.tools._errors import MCPToolValidationError
    from app.mcp.tools.list_catalog import _decode_cursor

    bad = base64.urlsafe_b64encode(
        json.dumps({"created_at": "2026-04-28T12:00:00+00:00"}).encode()
    ).decode()
    with pytest.raises(MCPToolValidationError):
        _decode_cursor(bad)


# ─────────────────────────────────────────────────────────────────────
# Argument validation
# ─────────────────────────────────────────────────────────────────────


def test_validate_arguments_defaults():
    from app.mcp.tools.list_catalog import (
        DEFAULT_LIMIT,
        DEFAULT_STATE,
        _validate_arguments,
    )

    out = _validate_arguments({})
    assert out["state"] == DEFAULT_STATE
    assert out["limit"] == DEFAULT_LIMIT
    assert out["subject_code"] is None
    assert out["grade"] is None
    assert out["content_type"] is None
    assert out["cursor"] is None


def test_validate_arguments_limit_too_high():
    from app.mcp.tools._errors import MCPToolValidationError
    from app.mcp.tools.list_catalog import _validate_arguments

    with pytest.raises(MCPToolValidationError) as excinfo:
        _validate_arguments({"limit": 101})
    assert "between 1 and 100" in str(excinfo.value)


def test_validate_arguments_limit_zero():
    from app.mcp.tools._errors import MCPToolValidationError
    from app.mcp.tools.list_catalog import _validate_arguments

    with pytest.raises(MCPToolValidationError):
        _validate_arguments({"limit": 0})


def test_validate_arguments_grade_bool_rejected():
    """Booleans are an ``int`` subclass — reject explicitly."""
    from app.mcp.tools._errors import MCPToolValidationError
    from app.mcp.tools.list_catalog import _validate_arguments

    with pytest.raises(MCPToolValidationError):
        _validate_arguments({"grade": True})


def test_validate_arguments_strips_strings():
    from app.mcp.tools.list_catalog import _validate_arguments

    out = _validate_arguments(
        {"subject_code": "  MATH  ", "content_type": "  study_guide  "}
    )
    assert out["subject_code"] == "MATH"
    assert out["content_type"] == "study_guide"


# ─────────────────────────────────────────────────────────────────────
# Handler — default state + empty result
# ─────────────────────────────────────────────────────────────────────


def test_handler_empty_result_returns_empty_list_not_404(monkeypatch, app):
    """Empty selection → ``{"artifacts": [], "next_cursor": None}``."""
    from app.mcp.tools.list_catalog import list_catalog

    db = MagicMock()
    db.query.return_value = _RecordingQuery(all_result=[])

    out = list_catalog({}, _admin_user(), db)
    assert out == {"artifacts": [], "next_cursor": None}


def test_handler_default_state_is_approved(monkeypatch, app):
    """Default state should be APPROVED (not all states).

    SQLAlchemy renders comparisons with bind parameters (``state = :state_1``),
    so we walk the BinaryExpression and inspect the right operand to
    confirm the bound value is ``APPROVED``.
    """
    from sqlalchemy.sql.elements import BinaryExpression

    from app.mcp.tools.list_catalog import list_catalog

    captured: dict = {}

    class _Q(_RecordingQuery):
        def filter(self, *args, **kw):
            captured.setdefault("filters", []).extend(args)
            return self

    db = MagicMock()
    db.query.return_value = _Q(all_result=[])

    list_catalog({}, _admin_user(), db)

    state_eq_approved = False
    for clause in captured["filters"]:
        if isinstance(clause, BinaryExpression) and "state" in str(clause.left):
            value = getattr(clause.right, "value", None)
            if value == "APPROVED":
                state_eq_approved = True
                break
    assert state_eq_approved, (
        f"expected a state == 'APPROVED' filter; got {captured['filters']!r}"
    )


# ─────────────────────────────────────────────────────────────────────
# Handler — pagination + next_cursor
# ─────────────────────────────────────────────────────────────────────


def test_handler_pagination_emits_next_cursor_when_more_rows(monkeypatch, app):
    """``limit + 1`` rows fetched → next_cursor anchors the LAST in-page row."""
    from app.mcp.tools.list_catalog import _decode_cursor, list_catalog

    rows = [_fake_row(row_id=i) for i in range(1, 5)]  # 4 rows back
    db = MagicMock()
    db.query.return_value = _RecordingQuery(all_result=rows)

    out = list_catalog({"limit": 3}, _admin_user(), db)

    assert len(out["artifacts"]) == 3
    assert out["next_cursor"] is not None

    # Decode the cursor and confirm it points at the LAST in-page row
    # (rows[2]) — NOT the over-fetched 4th row.
    when, row_id = _decode_cursor(out["next_cursor"])
    assert row_id == rows[2].id
    assert when == rows[2].created_at


def test_handler_pagination_no_next_cursor_when_under_limit(monkeypatch, app):
    """Fewer rows than ``limit + 1`` → no next_cursor."""
    from app.mcp.tools.list_catalog import list_catalog

    rows = [_fake_row(row_id=i) for i in range(1, 3)]
    db = MagicMock()
    db.query.return_value = _RecordingQuery(all_result=rows)

    out = list_catalog({"limit": 5}, _admin_user(), db)

    assert len(out["artifacts"]) == 2
    assert out["next_cursor"] is None


def test_handler_cursor_decodes_and_filters_query(monkeypatch, app):
    """A valid cursor adds an ``id < cursor_id`` predicate.

    Per the module docstring, the SQL predicate uses ``id`` only (not
    ``created_at``) to sidestep SQLite's microsecond-format quirk. The
    cursor payload still encodes ``(created_at, id)`` for forward
    compatibility, but the SQL only references ``id``.
    """
    from sqlalchemy.sql.elements import BinaryExpression

    from app.mcp.tools.list_catalog import _encode_cursor, list_catalog

    cursor = _encode_cursor(
        datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc), 100
    )
    captured_filters: list = []

    class _Q(_RecordingQuery):
        def filter(self, *args, **kw):
            captured_filters.extend(args)
            return self

    db = MagicMock()
    db.query.return_value = _Q(all_result=[])

    list_catalog({"cursor": cursor, "limit": 5}, _admin_user(), db)

    # Look for an ``id < 100`` clause among the filters.
    cursor_predicate_found = False
    for clause in captured_filters:
        if (
            isinstance(clause, BinaryExpression)
            and "id" in str(clause.left)
            and getattr(clause.right, "value", None) == 100
        ):
            cursor_predicate_found = True
            break
    assert cursor_predicate_found, (
        f"expected an ``id < 100`` predicate; got {captured_filters!r}"
    )


# ─────────────────────────────────────────────────────────────────────
# Handler — role scoping
# ─────────────────────────────────────────────────────────────────────


def test_handler_admin_role_skips_authoring_filter(monkeypatch, app):
    """ADMIN sees every artifact — no ``user_id`` predicate added."""
    from app.mcp.tools.list_catalog import list_catalog

    captured_filters: list = []

    class _Q(_RecordingQuery):
        def filter(self, *args, **kw):
            captured_filters.extend(args)
            return self

    db = MagicMock()
    db.query.return_value = _Q(all_result=[])

    list_catalog({}, _admin_user(), db)
    rendered = " ".join(str(f) for f in captured_filters)
    # No ``user_id`` predicate added for ADMIN. Mask out columns that
    # legitimately contain ``user_id`` as a substring (none today, but
    # keep the assertion narrow).
    assert "user_id" not in rendered


def test_handler_student_role_restricts_to_own_artifacts(monkeypatch, app):
    """STUDENT only sees rows whose ``user_id`` is their own."""
    from app.mcp.tools.list_catalog import list_catalog

    captured_filters: list = []

    class _Q(_RecordingQuery):
        def filter(self, *args, **kw):
            captured_filters.extend(args)
            return self

    db = MagicMock()
    db.query.return_value = _Q(all_result=[])

    list_catalog({}, _student_user(), db)
    rendered = " ".join(str(f) for f in captured_filters)
    assert "study_guides.user_id" in rendered.lower() or "user_id" in rendered


def test_handler_parent_role_triggers_kids_subquery(monkeypatch, app):
    """PARENT scoping must build a subquery from ``parent_students``.

    We don't run this against a real DB (route-level test below covers
    that); we just confirm ``db.query`` is invoked TWICE — once for the
    main StudyGuide query and once for the parent_students/students
    subquery — proving the kid-scope branch was entered.

    Performance contract (3B-3 / #4585): a PARENT calling list_catalog
    on the default ``state="APPROVED"`` filter must NOT incur an extra
    SELF_STUDY family-allowlist DB lookup — the override is short-
    circuited because the upstream state filter excludes SELF_STUDY.
    A regression here would flip ``call_count`` to 3.
    """
    from sqlalchemy import select

    from app.mcp.tools.list_catalog import list_catalog
    from app.models.student import Student, parent_students

    parent = _parent_user()

    main_q = _RecordingQuery(all_result=[])

    # Real (but trivially false) subquery so SQLAlchemy's ``in_()``
    # accepts the result. Avoids re-implementing SQLAlchemy's
    # SubqueryClause type for the mock.
    real_subq = (
        select(Student.user_id)
        .join(
            parent_students,
            parent_students.c.student_id == Student.id,
        )
        .where(parent_students.c.parent_id == parent.id)
        .subquery()
    )

    class _SubQ(_RecordingQuery):
        def __init__(self):
            super().__init__()
            self._called = False

        def filter(self, *args, **kw):
            self.calls.append(("filter", args))
            return self

        def join(self, *args, **kw):
            self.calls.append(("join", args))
            return self

        def subquery(self):
            self.calls.append(("subquery", ()))
            return real_subq

    sub_q = _SubQ()
    db = MagicMock()
    db.query.side_effect = [main_q, sub_q]

    list_catalog({}, parent, db)

    # Both queries fired: the main StudyGuide query and the kid subquery.
    # NOT three — the SELF_STUDY family allowlist short-circuits when
    # the upstream state filter excludes SELF_STUDY (3B-3 / #4585).
    assert db.query.call_count == 2
    # The kid subquery had a join(parent_students, ...) call.
    assert any(c[0] == "join" for c in sub_q.calls)


def test_handler_student_role_self_study_state_triggers_family_lookup(
    monkeypatch, app
):
    """STUDENT calling list_catalog with state=SELF_STUDY incurs the
    family-allowlist DB lookup; default state=APPROVED does NOT.

    Locks the perf contract from PR #4613 review — the SELF_STUDY
    family-allowlist lookup must be skipped when the upstream state
    filter already excludes SELF_STUDY (the dominant default-traffic
    case). Mutation guard: a regression that runs the lookup
    unconditionally would flip ``default_call_count`` from 1 to >=2.
    """
    from app.mcp.tools.list_catalog import list_catalog

    student = _student_user()

    # Default state (APPROVED) — only the main StudyGuide query should
    # fire. No family-allowlist lookup, no Student row lookup.
    default_db = MagicMock()
    default_db.query.return_value = _RecordingQuery(all_result=[])
    list_catalog({}, student, default_db)
    default_call_count = default_db.query.call_count

    # Explicit SELF_STUDY state — main query + Student row first()
    # = 2 calls (the .first() returns ``None`` here so the
    # parent_students walk is skipped). The contract we're locking is
    # ">=2 calls when SELF_STUDY is in scope", not the exact 3 — the
    # third call only fires when a Student row exists, which depends
    # on test seed data.
    self_study_db = MagicMock()
    self_study_db.query.return_value = _RecordingQuery(
        all_result=[], first_result=None
    )
    list_catalog({"state": "SELF_STUDY"}, student, self_study_db)
    self_study_call_count = self_study_db.query.call_count

    assert default_call_count == 1, (
        f"STUDENT default-state list must skip the SELF_STUDY family "
        f"lookup (got {default_call_count} db.query calls, expected 1)"
    )
    assert self_study_call_count >= 2, (
        f"STUDENT SELF_STUDY-state list must run the Student-row "
        f"lookup at minimum (got {self_study_call_count} db.query "
        f"calls, expected >= 2)"
    )


def test_handler_teacher_role_includes_course_subquery(monkeypatch, app):
    """TEACHER scoping must include the ``course_id IN (...)`` predicate.

    ``db.query`` should be called THREE times — main StudyGuide query,
    the teacher-PK subquery (``Teacher.id WHERE user_id == self.id``),
    and the owned-course subquery (``Course.id WHERE teacher_id IN ...``)
    — confirming both legs of the OR are wired.
    """
    from app.mcp.tools.list_catalog import list_catalog
    from app.models.course import Course
    from app.models.teacher import Teacher
    from sqlalchemy import select

    teacher = _teacher_user()

    main_q = _RecordingQuery(all_result=[])
    # Real (but trivially false) subqueries so SQLAlchemy's ``in_()``
    # accepts the result.
    teacher_subq = (
        select(Teacher.id).where(Teacher.user_id == teacher.id).subquery()
    )
    course_subq = (
        select(Course.id).where(Course.teacher_id.in_(teacher_subq)).subquery()
    )

    teacher_pk_q = _RecordingQuery(subquery_result=teacher_subq)
    course_q = _RecordingQuery(subquery_result=course_subq)

    db = MagicMock()
    db.query.side_effect = [main_q, teacher_pk_q, course_q]

    list_catalog({}, teacher, db)

    # All three queries fired — main + teacher-PK + owned-course.
    assert db.query.call_count == 3


def test_handler_board_admin_with_board_id_scopes_to_board(monkeypatch, app):
    """BOARD_ADMIN with a resolvable ``board_id`` filters by board match."""
    from app.mcp.tools.list_catalog import list_catalog

    captured_filters: list = []

    class _Q(_RecordingQuery):
        def filter(self, *args, **kw):
            captured_filters.extend(args)
            return self

    db = MagicMock()
    db.query.return_value = _Q(all_result=[])

    list_catalog({}, _board_admin_user(board_id="TDSB"), db)
    rendered = " ".join(str(f) for f in captured_filters)
    assert "board_id" in rendered.lower()
    # IS NOT NULL guard — distinct from the equality predicate.
    assert "is not null" in rendered.lower() or "is_not" in rendered.lower()


def test_handler_board_admin_without_board_id_sees_nothing(monkeypatch, app):
    """BOARD_ADMIN with no resolvable ``board_id`` → fail-closed empty filter."""
    from app.mcp.tools.list_catalog import list_catalog

    captured_filters: list = []

    class _Q(_RecordingQuery):
        def filter(self, *args, **kw):
            captured_filters.extend(args)
            return self

    db = MagicMock()
    db.query.return_value = _Q(all_result=[])

    out = list_catalog(
        {}, _board_admin_user(board_id=None), db
    )
    # The handler still returns a clean empty result envelope (NOT 404).
    assert out == {"artifacts": [], "next_cursor": None}
    # And the filter chain saw a "False" predicate (deny-all sentinel).
    rendered = " ".join(str(f) for f in captured_filters)
    assert "false" in rendered.lower()


# ─────────────────────────────────────────────────────────────────────
# Registry wiring
# ─────────────────────────────────────────────────────────────────────


def test_registry_list_catalog_handler_is_not_stub(app):
    """The registry's ``handler`` must be the concrete impl, not the stub."""
    from app.mcp.tools import TOOLS

    descriptor = TOOLS["list_catalog"]
    # Calling the handler with a mock DB must NOT raise
    # ``MCPNotImplementedError`` (the stub-handler signature).
    from app.mcp.tools import MCPNotImplementedError

    db = MagicMock()
    db.query.return_value = _RecordingQuery(all_result=[])
    try:
        result = descriptor.handler({}, _admin_user(), db)
    except MCPNotImplementedError:
        pytest.fail("list_catalog handler is still the stub")
    assert "artifacts" in result


def test_registry_list_catalog_roles_include_new_admin_roles(app):
    """``BOARD_ADMIN`` + ``CURRICULUM_ADMIN`` must be in the role allowlist."""
    from app.mcp.tools import TOOLS

    descriptor = TOOLS["list_catalog"]
    assert descriptor.is_role_allowed("BOARD_ADMIN")
    assert descriptor.is_role_allowed("CURRICULUM_ADMIN")
    assert descriptor.is_role_allowed("PARENT")
    assert descriptor.is_role_allowed("STUDENT")
    assert descriptor.is_role_allowed("TEACHER")
    assert descriptor.is_role_allowed("ADMIN")


def test_registry_list_catalog_input_schema_exposes_pagination(app):
    """The ``input_schema`` must publish ``cursor`` + ``state`` + ``content_type``."""
    from app.mcp.tools import TOOLS

    schema = TOOLS["list_catalog"].input_schema
    props = schema["properties"]
    assert "cursor" in props
    assert "state" in props
    assert "content_type" in props
    assert "limit" in props
    assert props["limit"]["maximum"] == 100


# ─────────────────────────────────────────────────────────────────────
# Route-level integration — default state + cursor pagination
# ─────────────────────────────────────────────────────────────────────


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
    assert flag is not None
    flag.enabled = True
    db_session.commit()
    yield flag
    db_session.refresh(flag)
    flag.enabled = False
    db_session.commit()


def _make_user(db_session, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"listcat_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"ListCat {role.value}",
        role=role,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def admin_user_real(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.ADMIN)


@pytest.fixture()
def student_user_real(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.STUDENT)


def _seed_guide(
    db_session,
    *,
    user_id: int,
    title: str = "Test guide",
    guide_type: str = "study_guide",
    state: str = "APPROVED",
    se_codes: list[str] | None = None,
    course_id: int | None = None,
):
    from app.models.study_guide import StudyGuide

    g = StudyGuide(
        user_id=user_id,
        title=title,
        content="body",
        guide_type=guide_type,
        state=state,
        se_codes=se_codes,
        course_id=course_id,
    )
    db_session.add(g)
    db_session.commit()
    db_session.refresh(g)
    return g


def test_route_default_state_returns_only_approved(
    client, admin_user_real, mcp_flag_on, db_session
):
    """Default request returns APPROVED rows; DRAFT is filtered out."""
    _seed_guide(
        db_session,
        user_id=admin_user_real.id,
        title="approved row",
        state="APPROVED",
    )
    _seed_guide(
        db_session,
        user_id=admin_user_real.id,
        title="draft row",
        state="DRAFT",
    )

    headers = _auth(client, admin_user_real.email)
    resp = client.post(
        "/mcp/call_tool",
        json={"name": "list_catalog", "arguments": {}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["content"]
    titles = [a["title"] for a in body["artifacts"]]
    assert "approved row" in titles
    assert "draft row" not in titles


def test_route_pagination_resumes_from_cursor(
    client, admin_user_real, mcp_flag_on, db_session
):
    """Cursor from page 1 yields the next page in stable order."""
    titles = [f"row {i:02d}" for i in range(8)]
    for t in titles:
        _seed_guide(db_session, user_id=admin_user_real.id, title=t)

    headers = _auth(client, admin_user_real.email)

    page1 = client.post(
        "/mcp/call_tool",
        json={"name": "list_catalog", "arguments": {"limit": 3}},
        headers=headers,
    )
    assert page1.status_code == 200, page1.text
    body1 = page1.json()["content"]
    assert len(body1["artifacts"]) == 3
    cursor = body1["next_cursor"]
    assert cursor is not None

    page2 = client.post(
        "/mcp/call_tool",
        json={
            "name": "list_catalog",
            "arguments": {"limit": 3, "cursor": cursor},
        },
        headers=headers,
    )
    assert page2.status_code == 200, page2.text
    body2 = page2.json()["content"]
    assert len(body2["artifacts"]) == 3

    # IDs must be disjoint (no overlap) and stable order across pages.
    ids1 = {a["id"] for a in body1["artifacts"]}
    ids2 = {a["id"] for a in body2["artifacts"]}
    assert ids1.isdisjoint(ids2)


def test_route_cross_role_scoping_student_cannot_see_other_users(
    client, student_user_real, mcp_flag_on, db_session
):
    """STUDENT only sees own artifacts; another user's APPROVED row is hidden."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    other = User(
        email=f"other_{uuid4().hex[:8]}@test.com",
        full_name="Other Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(other)
    db_session.commit()

    _seed_guide(db_session, user_id=other.id, title="other user row")
    _seed_guide(db_session, user_id=student_user_real.id, title="my row")

    headers = _auth(client, student_user_real.email)
    resp = client.post(
        "/mcp/call_tool",
        json={"name": "list_catalog", "arguments": {}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    titles = [a["title"] for a in resp.json()["content"]["artifacts"]]
    assert "my row" in titles
    assert "other user row" not in titles


def test_route_limit_over_100_returns_422(
    client, admin_user_real, mcp_flag_on
):
    """``limit > 100`` is rejected with 422 (matches issue acceptance criteria)."""
    headers = _auth(client, admin_user_real.email)
    resp = client.post(
        "/mcp/call_tool",
        json={"name": "list_catalog", "arguments": {"limit": 101}},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "100" in resp.json()["detail"]


def test_route_filter_by_content_type_narrows_result(
    client, admin_user_real, mcp_flag_on, db_session
):
    """``content_type=worksheet`` returns only worksheet rows."""
    _seed_guide(
        db_session,
        user_id=admin_user_real.id,
        title="study a",
        guide_type="study_guide",
    )
    _seed_guide(
        db_session,
        user_id=admin_user_real.id,
        title="worksheet a",
        guide_type="worksheet",
    )

    headers = _auth(client, admin_user_real.email)
    resp = client.post(
        "/mcp/call_tool",
        json={
            "name": "list_catalog",
            "arguments": {"content_type": "worksheet"},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    titles = [a["title"] for a in resp.json()["content"]["artifacts"]]
    assert "worksheet a" in titles
    assert "study a" not in titles


def test_route_filter_by_subject_code_narrows_result(
    client, admin_user_real, mcp_flag_on, db_session
):
    """``subject_code=MATH`` only returns rows with MATH-prefixed SE codes."""
    _seed_guide(
        db_session,
        user_id=admin_user_real.id,
        title="math row",
        se_codes=["MATH.5.A.1"],
    )
    _seed_guide(
        db_session,
        user_id=admin_user_real.id,
        title="science row",
        se_codes=["SCI.5.B.1"],
    )

    headers = _auth(client, admin_user_real.email)
    resp = client.post(
        "/mcp/call_tool",
        json={
            "name": "list_catalog",
            "arguments": {"subject_code": "MATH"},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    titles = [a["title"] for a in resp.json()["content"]["artifacts"]]
    assert "math row" in titles
    assert "science row" not in titles


def test_route_filter_by_grade_narrows_result(
    client, admin_user_real, mcp_flag_on, db_session
):
    """``grade=5`` only returns rows whose SE code's grade segment is ``5``.

    Today's schema has no ``study_guides.grade`` column — the grade is
    embedded in the SE code (``<SUBJECT>.<GRADE>.<...>``). This test
    locks the post-filter behaviour so a future schema migration that
    adds a real ``grade`` column doesn't silently change the user-
    visible filter semantics.
    """
    _seed_guide(
        db_session,
        user_id=admin_user_real.id,
        title="grade-5 row",
        se_codes=["MATH.5.A.1"],
    )
    _seed_guide(
        db_session,
        user_id=admin_user_real.id,
        title="grade-8 row",
        se_codes=["MATH.8.A.1"],
    )

    headers = _auth(client, admin_user_real.email)
    resp = client.post(
        "/mcp/call_tool",
        json={
            "name": "list_catalog",
            "arguments": {"grade": 5},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    titles = [a["title"] for a in resp.json()["content"]["artifacts"]]
    assert "grade-5 row" in titles
    assert "grade-8 row" not in titles


@pytest.fixture()
def board_admin_user_real(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.BOARD_ADMIN)


def test_route_board_admin_without_board_id_sees_empty_until_m3e(
    client, board_admin_user_real, mcp_flag_on, db_session
):
    """BOARD_ADMIN with no resolvable ``board_id`` → empty result, not error.

    The ``User`` model has no ``board_id`` column today (M3-E concern),
    so ``_resolve_caller_board_id`` returns ``None`` for every real
    BOARD_ADMIN user — collapsing to a fail-closed empty selection.
    The handler must return a clean ``200`` with an empty artifact
    list, NOT a ``404`` or a ``403``. This locks the contract until
    M3-E adds per-row board stamping.
    """
    _seed_guide(
        db_session,
        user_id=board_admin_user_real.id,
        title="legacy unscoped row",
        se_codes=["MATH.5.A.1"],
    )

    headers = _auth(client, board_admin_user_real.email)
    resp = client.post(
        "/mcp/call_tool",
        json={"name": "list_catalog", "arguments": {}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["content"]
    assert body["artifacts"] == []
    assert body["next_cursor"] is None


# ─────────────────────────────────────────────────────────────────────
# #4568 — over-fetch loop fills the page across post-filtered windows
# ─────────────────────────────────────────────────────────────────────


def test_list_catalog_overfetches_to_fill_page(
    client, admin_user_real, mcp_flag_on, db_session
):
    """Sparse-match windows should still emit a full page (#4568).

    Seed 12 rows where every 3rd row has the test's unique subject SE
    code (4 matches out of 12). Request ``limit=3``; the handler's
    first SQL window fetches ``limit + 1 = 4`` rows ordered ``id DESC``,
    which yields only ~1 match. The over-fetch loop must keep
    advancing the cursor through more SQL windows until 3 matches are
    accumulated OR the DB is exhausted.

    Uses a unique subject prefix (``OVRFTCH``) and a unique
    ``content_type`` so the test isolates from other route-level tests
    that share the session-scoped DB fixture (see conftest comment).

    Locks the standard cursor contract for the typical case: a single
    ``call_tool`` with sparse matches returns exactly ``limit`` rows
    (when enough exist) without forcing the caller to chase through
    empty pages.
    """
    unique_subject = "OVRFTCH"
    unique_type = "overfetch_test_type"
    for i in range(12):
        # Every 3rd row gets the unique SE prefix; the rest get a
        # different prefix so the post-filter excludes them.
        if i % 3 == 0:
            se_codes = [f"{unique_subject}.5.A.{i}"]
            title = f"match row {i:02d}"
        else:
            se_codes = [f"NOMATCH.5.B.{i}"]
            title = f"skip row {i:02d}"
        _seed_guide(
            db_session,
            user_id=admin_user_real.id,
            title=title,
            guide_type=unique_type,
            se_codes=se_codes,
        )

    headers = _auth(client, admin_user_real.email)
    resp = client.post(
        "/mcp/call_tool",
        json={
            "name": "list_catalog",
            "arguments": {
                "subject_code": unique_subject,
                "content_type": unique_type,
                "limit": 3,
            },
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["content"]

    # The page must be FULL — exactly 3 matching rows, no noise.
    assert len(body["artifacts"]) == 3
    titles = [a["title"] for a in body["artifacts"]]
    assert all(t.startswith("match row") for t in titles), titles

    # And the cursor must be set so the caller can fetch the 4th match.
    assert body["next_cursor"] is not None

    page2 = client.post(
        "/mcp/call_tool",
        json={
            "name": "list_catalog",
            "arguments": {
                "subject_code": unique_subject,
                "content_type": unique_type,
                "limit": 3,
                "cursor": body["next_cursor"],
            },
        },
        headers=headers,
    )
    assert page2.status_code == 200, page2.text
    body2 = page2.json()["content"]
    # Only the 4th match remains; DB exhausts past it for this filter.
    assert len(body2["artifacts"]) == 1
    assert body2["artifacts"][0]["title"].startswith("match row")
    # Standard cursor contract: empty next_cursor → caller is done.
    assert body2["next_cursor"] is None


def test_list_catalog_overfetch_caps_at_max_passes(monkeypatch, app):
    """A degenerate filter (no matches anywhere) hits the pass cap (#4568).

    Build a fake query that always returns ``limit + 1`` rows (so the
    SQL window never exhausts) but where none of the rows match the
    post-filter. The handler must stop after :data:`MAX_OVERFETCH_PASSES`
    passes and emit a partial page (here: empty) with a non-null cursor
    so the caller advances rather than the server walking the entire
    table.
    """
    from app.mcp.tools.list_catalog import (
        MAX_OVERFETCH_PASSES,
        list_catalog,
    )

    pass_counter = {"n": 0}

    class _Q(_RecordingQuery):
        def all(self):
            pass_counter["n"] += 1
            # Always return ``limit + 1`` SCI rows so the over-fetch
            # loop never sees ``db_exhausted`` and only stops when it
            # hits MAX_OVERFETCH_PASSES.
            return [
                _fake_row(
                    row_id=1000 - pass_counter["n"] * 10 - i,
                    se_codes=[f"SCI.5.B.{pass_counter['n']}.{i}"],
                )
                for i in range(4)  # limit=3 → fetch limit+1=4
            ]

    db = MagicMock()
    db.query.return_value = _Q(all_result=[])

    out = list_catalog(
        {"subject_code": "MATH", "limit": 3}, _admin_user(), db
    )

    # No MATH matches anywhere → empty page.
    assert out["artifacts"] == []
    # But the cursor is non-null so the caller advances on the next
    # request — this is the documented edge case in the tool's
    # description (#4568).
    assert out["next_cursor"] is not None
    # And we capped at MAX_OVERFETCH_PASSES SQL rounds rather than
    # walking the whole table.
    assert pass_counter["n"] == MAX_OVERFETCH_PASSES
