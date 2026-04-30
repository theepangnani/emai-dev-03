"""CB-CMCP-001 M3-E 3E-1 (#4653) — Board catalog REST endpoint tests.

Covers ``GET /api/board/{board_id}/catalog``:

- BOARD_ADMIN of board X → returns X's APPROVED artifacts.
- BOARD_ADMIN cross-board → 404 (no existence oracle).
- Non-BOARD_ADMIN (e.g. PARENT, STUDENT, TEACHER) → 403.
- Unauthenticated → 401.
- ``cmcp.enabled`` flag OFF → 403 (matches the rest of the CMCP REST surface).
- Cursor pagination yields stable, disjoint pages across page 1 → page 2.
- ADMIN can read any board's catalog (ops bypass).
- Mock-DB unit-style test: handler builds a query with ``board_id`` +
  ``state == APPROVED`` filters and the cursor predicate.

Per the project test conventions:

- DB writes go through the in-process SQLite session — no external network
  calls (no real Claude/OpenAI).
- Real BOARD_ADMIN users get ``board_id`` attached as a Python attribute
  on the row + via a ``resolve_caller_board_id`` monkeypatch on the route
  module so the integration tests don't depend on M3-E's per-user board
  column landing first.
- Each test that hits the route uses the shared ``cmcp_flag_on`` fixture
  to flip the feature flag ON for the duration of the test.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ─────────────────────────────────────────────────────────────────────
# Flag fixture — ``cmcp.enabled`` ON for every route-level test
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture()
def cmcp_flag_on(db_session):
    """Force ``cmcp.enabled`` ON for the test, OFF after."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "cmcp.enabled")
        .first()
    )
    assert flag is not None, "cmcp.enabled flag must be seeded"
    flag.enabled = True
    db_session.commit()
    yield flag
    db_session.refresh(flag)
    flag.enabled = False
    db_session.commit()


# ─────────────────────────────────────────────────────────────────────
# User helpers
# ─────────────────────────────────────────────────────────────────────


def _make_user(db_session, role, *, email_prefix=None):
    """Build + persist a ``User`` with the given role.

    The optional ``board_id`` is wired via the route module's
    ``resolve_caller_board_id`` helper (monkeypatched per-test) — we
    do NOT touch the users table because the per-user board column is
    M3-E and not yet on this branch.
    """
    from app.core.security import get_password_hash
    from app.models.user import User

    prefix = email_prefix or f"bdcat_{role.value.lower()}"
    user = User(
        email=f"{prefix}_{uuid4().hex[:8]}@test.com",
        full_name=f"BoardCatalog Test {role.value}",
        role=role,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def board_admin_tdsb(db_session):
    from app.models.user import UserRole

    return _make_user(
        db_session, UserRole.BOARD_ADMIN, email_prefix="bdcat_tdsb"
    )


@pytest.fixture()
def board_admin_ocdsb(db_session):
    from app.models.user import UserRole

    return _make_user(
        db_session, UserRole.BOARD_ADMIN, email_prefix="bdcat_ocdsb"
    )


@pytest.fixture()
def admin_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.ADMIN)


@pytest.fixture()
def parent_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.PARENT)


@pytest.fixture()
def student_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.STUDENT)


@pytest.fixture()
def teacher_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.TEACHER)


@pytest.fixture()
def patch_resolve_board(monkeypatch):
    """Return a setter that monkeypatches ``resolve_caller_board_id``.

    The route module imports ``resolve_caller_board_id`` from
    ``app.mcp.tools._visibility``. Until M3-E lands a real
    ``User.board_id`` column, we patch the route's reference to return a
    fixed mapping ``{user_id: board_id}`` so route-level tests can
    exercise the BOARD_ADMIN "own board" path without a schema change.
    """

    def _set(mapping: dict[int, str | None]):
        from app.api.routes import board_catalog as bc_module

        def _fake(user):
            return mapping.get(getattr(user, "id", None), None)

        monkeypatch.setattr(bc_module, "resolve_caller_board_id", _fake)

    return _set


# ─────────────────────────────────────────────────────────────────────
# Seed helper
# ─────────────────────────────────────────────────────────────────────


def _seed_artifact(
    db_session,
    *,
    user_id: int,
    title: str = "Board test artifact",
    state: str = "APPROVED",
    board_id: str | None = "TDSB",
    se_codes: list[str] | None = None,
    guide_type: str = "study_guide",
    alignment_score=None,
    ai_engine: str | None = None,
):
    from app.models.study_guide import StudyGuide

    g = StudyGuide(
        user_id=user_id,
        title=title,
        content="body",
        guide_type=guide_type,
        state=state,
        board_id=board_id,
        se_codes=se_codes,
        alignment_score=alignment_score,
        ai_engine=ai_engine,
    )
    db_session.add(g)
    db_session.commit()
    db_session.refresh(g)
    return g


# ─────────────────────────────────────────────────────────────────────
# Route-level tests — happy path
# ─────────────────────────────────────────────────────────────────────


def test_board_admin_can_list_own_board_artifacts(
    client,
    cmcp_flag_on,
    db_session,
    board_admin_tdsb,
    patch_resolve_board,
):
    """BOARD_ADMIN of board X sees X's APPROVED artifacts.

    Seeds three rows: one APPROVED with board_id=TDSB (in-scope), one
    APPROVED with board_id=OCDSB (cross-board, must NOT appear), one
    DRAFT with board_id=TDSB (wrong state, must NOT appear).
    """
    patch_resolve_board({board_admin_tdsb.id: "TDSB"})

    in_scope = _seed_artifact(
        db_session,
        user_id=board_admin_tdsb.id,
        title="TDSB approved",
        state="APPROVED",
        board_id="TDSB",
        ai_engine="gpt-4o-mini",
    )
    _seed_artifact(
        db_session,
        user_id=board_admin_tdsb.id,
        title="OCDSB approved",
        state="APPROVED",
        board_id="OCDSB",
    )
    _seed_artifact(
        db_session,
        user_id=board_admin_tdsb.id,
        title="TDSB draft",
        state="DRAFT",
        board_id="TDSB",
    )

    headers = _auth(client, board_admin_tdsb.email)
    resp = client.get("/api/board/TDSB/catalog", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    titles = {a["title"] for a in body["artifacts"]}
    assert "TDSB approved" in titles
    assert "OCDSB approved" not in titles
    assert "TDSB draft" not in titles
    # Verify the metadata fields the issue calls out are present.
    in_scope_row = next(a for a in body["artifacts"] if a["id"] == in_scope.id)
    assert in_scope_row["content_type"] == "study_guide"
    assert in_scope_row["state"] == "APPROVED"
    assert in_scope_row["ai_engine"] == "gpt-4o-mini"
    assert "se_codes" in in_scope_row
    assert "alignment_score" in in_scope_row
    assert in_scope_row["created_at"] is not None
    assert body["next_cursor"] is None  # only 1 in-scope row → no more pages


def test_board_admin_cross_board_returns_404(
    client,
    cmcp_flag_on,
    db_session,
    board_admin_ocdsb,
    patch_resolve_board,
):
    """BOARD_ADMIN of OCDSB hitting /api/board/TDSB/catalog → 404.

    Per D7=B + the issue spec: "no existence oracle" — a BOARD_ADMIN
    must not be able to distinguish "this board exists but you don't
    admin it" from "this board doesn't exist".
    """
    patch_resolve_board({board_admin_ocdsb.id: "OCDSB"})

    # Seed a TDSB artifact so the existence-oracle check is meaningful
    # — the artifact exists but the cross-board read still 404s.
    _seed_artifact(
        db_session,
        user_id=board_admin_ocdsb.id,
        title="TDSB approved",
        state="APPROVED",
        board_id="TDSB",
    )

    headers = _auth(client, board_admin_ocdsb.email)
    resp = client.get("/api/board/TDSB/catalog", headers=headers)
    assert resp.status_code == 404


def test_board_admin_with_no_resolvable_board_returns_404(
    client,
    cmcp_flag_on,
    db_session,
    board_admin_tdsb,
    patch_resolve_board,
):
    """BOARD_ADMIN whose ``resolve_caller_board_id`` returns None → 404.

    Same fail-closed posture as the M2 MCP tools: until per-user board
    stamping lands, an unscoped BOARD_ADMIN gets nothing — and on this
    REST surface, "nothing" reads as 404 (no existence oracle).
    """
    patch_resolve_board({})  # no entries → resolve returns None

    _seed_artifact(
        db_session,
        user_id=board_admin_tdsb.id,
        title="TDSB approved",
        state="APPROVED",
        board_id="TDSB",
    )

    headers = _auth(client, board_admin_tdsb.email)
    resp = client.get("/api/board/TDSB/catalog", headers=headers)
    assert resp.status_code == 404


def test_admin_can_list_any_board(
    client,
    cmcp_flag_on,
    db_session,
    admin_user,
    patch_resolve_board,
):
    """ADMIN role bypasses the "own board" check (ops / debug)."""
    patch_resolve_board({})  # ADMIN should not need a resolvable board

    _seed_artifact(
        db_session,
        user_id=admin_user.id,
        title="TDSB approved",
        state="APPROVED",
        board_id="TDSB",
    )

    headers = _auth(client, admin_user.email)
    resp = client.get("/api/board/TDSB/catalog", headers=headers)
    assert resp.status_code == 200, resp.text
    titles = [a["title"] for a in resp.json()["artifacts"]]
    assert "TDSB approved" in titles


# ─────────────────────────────────────────────────────────────────────
# Route-level tests — auth / role gating
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "role_fixture", ["parent_user", "student_user", "teacher_user"]
)
def test_non_board_admin_returns_403(
    request, client, cmcp_flag_on, role_fixture
):
    """PARENT / STUDENT / TEACHER all → 403 (not in the role allowlist).

    Cross-checks that the role gate is in front of the cross-board
    check — a STUDENT must not get 404 on a probed board_id.
    """
    user = request.getfixturevalue(role_fixture)
    headers = _auth(client, user.email)
    resp = client.get("/api/board/TDSB/catalog", headers=headers)
    assert resp.status_code == 403


def test_unauthenticated_returns_401(client):
    """No Authorization header → 401."""
    resp = client.get("/api/board/TDSB/catalog")
    assert resp.status_code == 401


def test_flag_off_returns_403(client, db_session, board_admin_tdsb):
    """``cmcp.enabled`` OFF → 403 (matches the rest of CMCP REST surface).

    Deliberately does NOT use the ``cmcp_flag_on`` fixture so the flag
    stays in its default-OFF state.
    """
    headers = _auth(client, board_admin_tdsb.email)
    resp = client.get("/api/board/TDSB/catalog", headers=headers)
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# Route-level tests — cursor pagination (stable + disjoint)
# ─────────────────────────────────────────────────────────────────────


def test_cursor_pagination_yields_disjoint_pages(
    client,
    cmcp_flag_on,
    db_session,
    board_admin_tdsb,
    patch_resolve_board,
):
    """Page 1 (limit=3) + page 2 (with cursor) → 6 distinct rows in stable order.

    Uses a **unique board_id** (``PAGINATE_TEST``) so the seven seeded
    rows are isolated from any other test's TDSB rows in the
    session-scoped SQLite DB. Without this isolation, sibling tests
    that seed under ``TDSB`` would inflate the page count.
    """
    unique_board = f"PAGINATE_{uuid4().hex[:8].upper()}"
    patch_resolve_board({board_admin_tdsb.id: unique_board})

    for i in range(7):
        _seed_artifact(
            db_session,
            user_id=board_admin_tdsb.id,
            title=f"row {i:02d}",
            state="APPROVED",
            board_id=unique_board,
        )

    headers = _auth(client, board_admin_tdsb.email)

    page1 = client.get(
        f"/api/board/{unique_board}/catalog?limit=3", headers=headers
    )
    assert page1.status_code == 200, page1.text
    body1 = page1.json()
    assert len(body1["artifacts"]) == 3
    cursor = body1["next_cursor"]
    assert cursor is not None

    page2 = client.get(
        f"/api/board/{unique_board}/catalog?limit=3&cursor={cursor}",
        headers=headers,
    )
    assert page2.status_code == 200, page2.text
    body2 = page2.json()
    assert len(body2["artifacts"]) == 3
    cursor2 = body2["next_cursor"]

    # IDs must be disjoint and stable order across pages (id DESC).
    ids1 = [a["id"] for a in body1["artifacts"]]
    ids2 = [a["id"] for a in body2["artifacts"]]
    assert set(ids1).isdisjoint(set(ids2))
    assert ids1 == sorted(ids1, reverse=True)
    assert ids2 == sorted(ids2, reverse=True)
    # Page 1's last id is greater than page 2's first id (id DESC).
    assert ids1[-1] > ids2[0]

    # Page 3 should yield the lone remaining row + a ``None`` cursor.
    page3 = client.get(
        f"/api/board/{unique_board}/catalog?limit=3&cursor={cursor2}",
        headers=headers,
    )
    assert page3.status_code == 200, page3.text
    body3 = page3.json()
    assert len(body3["artifacts"]) == 1
    assert body3["next_cursor"] is None


def test_invalid_cursor_returns_422(
    client,
    cmcp_flag_on,
    board_admin_tdsb,
    patch_resolve_board,
):
    """Garbage cursor → 422 (matches the MCP list_catalog contract)."""
    patch_resolve_board({board_admin_tdsb.id: "TDSB"})
    headers = _auth(client, board_admin_tdsb.email)
    resp = client.get(
        "/api/board/TDSB/catalog?cursor=not-base64!!!", headers=headers
    )
    assert resp.status_code == 422


def test_limit_over_100_returns_422(
    client,
    cmcp_flag_on,
    board_admin_tdsb,
    patch_resolve_board,
):
    """``limit > 100`` rejected by FastAPI's Query validator (422)."""
    patch_resolve_board({board_admin_tdsb.id: "TDSB"})
    headers = _auth(client, board_admin_tdsb.email)
    resp = client.get(
        "/api/board/TDSB/catalog?limit=101", headers=headers
    )
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────
# Mock-DB unit test — verifies SQL filters are wired correctly
# ─────────────────────────────────────────────────────────────────────


class _RecordingQuery:
    """Lightweight stand-in for ``db.query(StudyGuide)`` (mirrors the
    pattern in ``tests/test_mcp_list_catalog.py``).

    Captures the full ``filter`` / ``order_by`` / ``limit`` chain and
    returns a configurable row list from ``.all()``.
    """

    def __init__(self, all_result=None):
        self.calls: list[tuple[str, tuple]] = []
        self._all_result = list(all_result or [])

    def filter(self, *args, **kw):
        self.calls.append(("filter", args))
        return self

    def order_by(self, *args, **kw):
        self.calls.append(("order_by", args))
        return self

    def limit(self, n):
        self.calls.append(("limit", (n,)))
        return self

    def all(self):
        return list(self._all_result)


def _board_admin_mock(*, board_id="TDSB", user_id=300, is_admin=False):
    """Return a SimpleNamespace that quacks like a ``User`` for the route handler.

    ``has_role(role)`` matches the real ``User.has_role`` semantics —
    ``True`` only for the role the mock claims to hold.
    """
    from app.models.user import UserRole

    role = UserRole.ADMIN if is_admin else UserRole.BOARD_ADMIN
    user = SimpleNamespace(
        id=user_id,
        role=role,
        board_id=board_id,
        full_name="Mock",
    )
    user.has_role = lambda r, _self=user: r == role
    return user


def test_handler_builds_board_id_and_state_filters(monkeypatch):
    """Direct handler call: SQL window includes ``board_id == X`` + state filter.

    Mocks the DB at the SQLAlchemy ``Query`` boundary so we can assert
    the route built the expected predicate chain without seeding rows.
    """
    from sqlalchemy.sql.elements import BinaryExpression

    from app.api.routes import board_catalog as bc_module

    captured_filters: list = []

    class _Q(_RecordingQuery):
        def filter(self, *args, **kw):
            captured_filters.extend(args)
            return self

    db = MagicMock()
    db.query.return_value = _Q(all_result=[])

    user = _board_admin_mock(board_id="TDSB")
    out = bc_module.get_board_catalog(
        board_id="TDSB",
        cursor=None,
        limit=20,
        subject_code=None,
        grade=None,
        content_type=None,
        current_user=user,
        db=db,
    )

    # Empty result → empty artifacts list + no cursor.
    assert out.artifacts == []
    assert out.next_cursor is None

    # Column-name presence (the rendered SQL uses bind parameter names
    # like ``state_1`` / ``board_id_1``, so we walk the BinaryExpression
    # tree to verify the bound values rather than substring-matching).
    rendered = " ".join(str(f) for f in captured_filters).lower()
    assert "board_id" in rendered
    assert "archived_at" in rendered
    assert "state" in rendered

    # Confirm the BOUND values: state == "APPROVED" and board_id == "TDSB".
    state_eq_approved = False
    board_eq_tdsb = False
    for clause in captured_filters:
        if not isinstance(clause, BinaryExpression):
            continue
        bound = getattr(clause.right, "value", None)
        left_str = str(clause.left).lower()
        if "state" in left_str and bound == "APPROVED":
            state_eq_approved = True
        if "board_id" in left_str and bound == "TDSB":
            board_eq_tdsb = True
    assert state_eq_approved, (
        f"expected a state == 'APPROVED' bound predicate; got {captured_filters!r}"
    )
    assert board_eq_tdsb, (
        f"expected a board_id == 'TDSB' bound predicate; got {captured_filters!r}"
    )


def test_handler_cross_board_raises_404(monkeypatch):
    """Direct handler call: BOARD_ADMIN of TDSB hitting /board/OCDSB → 404."""
    from fastapi import HTTPException

    from app.api.routes import board_catalog as bc_module

    db = MagicMock()
    db.query.return_value = _RecordingQuery(all_result=[])
    user = _board_admin_mock(board_id="TDSB")

    with pytest.raises(HTTPException) as excinfo:
        bc_module.get_board_catalog(
            board_id="OCDSB",
            cursor=None,
            limit=20,
            subject_code=None,
            grade=None,
            content_type=None,
            current_user=user,
            db=db,
        )
    assert excinfo.value.status_code == 404


def test_handler_admin_bypass_for_any_board(monkeypatch):
    """ADMIN reading /board/ANY/catalog does not trip the cross-board 404."""
    from app.api.routes import board_catalog as bc_module

    db = MagicMock()
    db.query.return_value = _RecordingQuery(all_result=[])
    admin = _board_admin_mock(is_admin=True, board_id=None)

    out = bc_module.get_board_catalog(
        board_id="OCDSB",
        cursor=None,
        limit=20,
        subject_code=None,
        grade=None,
        content_type=None,
        current_user=admin,
        db=db,
    )
    assert out.artifacts == []


def test_handler_uses_overfetch_loop_max_passes(monkeypatch):
    """A degenerate post-filter (no matches) hits MAX_OVERFETCH_PASSES.

    Mirrors the M2-followup #4568 contract test from
    ``tests/test_mcp_list_catalog.py`` — the route reuses the same
    over-fetch loop helper so this is a regression net for
    cross-stripe consistency.
    """
    from app.api.routes import board_catalog as bc_module
    from app.mcp.tools.list_catalog import MAX_OVERFETCH_PASSES

    pass_counter = {"n": 0}

    class _Q(_RecordingQuery):
        def all(self):
            pass_counter["n"] += 1
            # Always return ``limit + 1 = 4`` rows with a non-matching
            # subject prefix so the post-filter drops them all and the
            # over-fetch loop keeps advancing the cursor.
            return [
                SimpleNamespace(
                    id=1000 - pass_counter["n"] * 10 - i,
                    title=f"skip {i}",
                    guide_type="study_guide",
                    state="APPROVED",
                    se_codes=[f"NOMATCH.5.B.{pass_counter['n']}.{i}"],
                    course_id=None,
                    archived_at=None,
                    alignment_score=None,
                    ai_engine=None,
                    board_id="TDSB",
                    user_id=1,
                    created_at=None,
                )
                for i in range(4)
            ]

    db = MagicMock()
    db.query.return_value = _Q(all_result=[])
    user = _board_admin_mock(board_id="TDSB")

    out = bc_module.get_board_catalog(
        board_id="TDSB",
        cursor=None,
        limit=3,
        subject_code="MATH",
        grade=None,
        content_type=None,
        current_user=user,
        db=db,
    )

    # No matches → empty list, but cursor is non-null so the caller
    # advances on the next call (#4568 contract).
    assert out.artifacts == []
    assert out.next_cursor is not None
    # And we capped at MAX_OVERFETCH_PASSES (didn't walk the table).
    assert pass_counter["n"] == MAX_OVERFETCH_PASSES


# ─────────────────────────────────────────────────────────────────────
# Audit log (#4698) — Bill 194: catalog GET writes a `cmcp.board.catalog_listed`
# row with the board_id + page_size + filter shape in the JSON details.
# ─────────────────────────────────────────────────────────────────────


def test_catalog_get_writes_audit_row(
    client,
    cmcp_flag_on,
    db_session,
    board_admin_tdsb,
    patch_resolve_board,
):
    """A successful catalog GET writes a `cmcp.board.catalog_listed` audit row.

    Verifies the Bill-194 audit trail: the audited row must contain
    the board_id + the caller's user_id + the page_size + the filter
    shape so a regulator can later trace who looked at what.
    """
    import json

    from app.models.audit_log import AuditLog

    unique_board = f"AUDIT_{uuid4().hex[:6].upper()}"
    patch_resolve_board({board_admin_tdsb.id: unique_board})

    _seed_artifact(
        db_session,
        user_id=board_admin_tdsb.id,
        title="Auditable row",
        state="APPROVED",
        board_id=unique_board,
        # SE code prefix MATH so the subject_code filter doesn't drop it.
        se_codes=["MATH.5.A.1"],
    )

    headers = _auth(client, board_admin_tdsb.email)
    resp = client.get(
        f"/api/board/{unique_board}/catalog?subject_code=MATH&content_type=study_guide",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # Read from a fresh ``SessionLocal()`` rather than the test
    # fixture ``db_session`` — defensive read across session
    # boundaries. NOTE: SQLAlchemy's connection pool means even a
    # fresh session can see SAVEPOINT-flushed rows, so this is not by
    # itself a guarantee that ``db.commit()`` ran in the handler;
    # the explicit commit is required for production durability and
    # matches the convention in ``cmcp_review.py``.
    from app.db.database import SessionLocal

    fresh = SessionLocal()
    try:
        rows = (
            fresh.query(AuditLog)
            .filter(AuditLog.action == "cmcp.board.catalog_listed")
            .filter(AuditLog.user_id == board_admin_tdsb.id)
            .all()
        )
        assert len(rows) >= 1, (
            "expected one cmcp.board.catalog_listed audit row "
            "(visible from a fresh session — this verifies db.commit() ran)"
        )
        latest = rows[-1]
        assert latest.resource_type == "board_catalog"
        details = json.loads(latest.details)
        assert details["board_id"] == unique_board
        assert details["page_size"] == 1
        assert details["role"] == "BOARD_ADMIN"
        assert details["filters"]["subject_code"] == "MATH"
        assert details["filters"]["content_type"] == "study_guide"
        assert details["filters"]["state"] == "APPROVED"
    finally:
        fresh.close()


def test_catalog_get_403_writes_no_audit_row(
    client,
    cmcp_flag_on,
    db_session,
    parent_user,
):
    """A 403'd request must NOT leak an audit row (handler never runs).

    The audit row is written inside the handler, after the role gate
    + cross-board check pass. A non-allowlisted role hits the role gate
    before the handler — no audit row should be written for the
    rejected request (otherwise an attacker could pollute the log).
    """
    from app.models.audit_log import AuditLog

    pre_count = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "cmcp.board.catalog_listed")
        .count()
    )
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/board/TDSB/catalog", headers=headers)
    assert resp.status_code == 403
    post_count = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "cmcp.board.catalog_listed")
        .count()
    )
    assert post_count == pre_count, (
        "403 path must not emit cmcp.board.catalog_listed"
    )
