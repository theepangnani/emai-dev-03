"""CB-CMCP-001 M3-E 3E-3 (#4660) — Signed CSV export endpoint tests.

Covers ``POST /api/board/{board_id}/catalog/export.csv``:

- BOARD_ADMIN of board X → GCS upload happens + signed URL returned.
- BOARD_ADMIN cross-board → 404 (no existence oracle).
- BOARD_ADMIN with no resolvable board → 404 (fail-closed posture).
- ADMIN → may export any board.
- Non-(BOARD_ADMIN/ADMIN) (PARENT, STUDENT, TEACHER) → 403.
- Unauthenticated → 401.
- ``cmcp.enabled`` flag OFF → 403.
- CSV bytes contain the coverage-map section + the artifact section.
- CSV uploads are namespaced under ``cmcp/board_catalog_exports/{board_id}/``.
- Signed-URL TTL is 1 hour and ``expires_at`` reflects that.

Test conventions
----------------
- All GCS calls are mocked via ``patch("app.api.routes.board_catalog.gcs_service")``
  so no real network calls happen. A tiny in-memory dict captures uploaded
  bytes + records the path argument so tests can assert on the body.
- The ``cmcp_flag_on`` fixture flips ``cmcp.enabled`` ON for the test.
- The route's ``resolve_caller_board_id`` is monkeypatched (same pattern
  used in ``test_board_catalog.py``) to map a User to a board_id without
  requiring the per-user ``User.board_id`` column to land first.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ─────────────────────────────────────────────────────────────────────
# In-memory GCS store + signed-URL stub
# ─────────────────────────────────────────────────────────────────────

_FILE_STORE: dict[str, bytes] = {}
_CONTENT_TYPE_STORE: dict[str, str] = {}


def _fake_upload(gcs_path, data, content_type):
    _FILE_STORE[gcs_path] = data
    _CONTENT_TYPE_STORE[gcs_path] = content_type


def _fake_signed_url(gcs_path, *, ttl_seconds=3600):
    # Return a deterministic stub so tests can assert the path made it
    # into the URL; real V4 signing isn't exercised here (that's GCS's
    # responsibility and it's mocked).
    return f"https://signed.example.test/{gcs_path}?ttl={ttl_seconds}"


@pytest.fixture()
def mock_gcs(monkeypatch):
    """Patch ``gcs_service`` on the route module so no real GCS calls happen."""
    _FILE_STORE.clear()
    _CONTENT_TYPE_STORE.clear()
    with patch("app.api.routes.board_catalog.gcs_service") as mock:
        mock.upload_file.side_effect = _fake_upload
        mock.generate_signed_url.side_effect = _fake_signed_url
        yield mock


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
# User helpers (mirror test_board_catalog.py)
# ─────────────────────────────────────────────────────────────────────


def _make_user(db_session, role, *, email_prefix=None):
    from app.core.security import get_password_hash
    from app.models.user import User

    prefix = email_prefix or f"bdcsv_{role.value.lower()}"
    user = User(
        email=f"{prefix}_{uuid4().hex[:8]}@test.com",
        full_name=f"BoardCSV Test {role.value}",
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
        db_session, UserRole.BOARD_ADMIN, email_prefix="bdcsv_tdsb"
    )


@pytest.fixture()
def board_admin_ocdsb(db_session):
    from app.models.user import UserRole

    return _make_user(
        db_session, UserRole.BOARD_ADMIN, email_prefix="bdcsv_ocdsb"
    )


@pytest.fixture()
def admin_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.ADMIN, email_prefix="bdcsv_admin")


@pytest.fixture()
def parent_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.PARENT, email_prefix="bdcsv_parent")


@pytest.fixture()
def student_user(db_session):
    from app.models.user import UserRole

    return _make_user(
        db_session, UserRole.STUDENT, email_prefix="bdcsv_student"
    )


@pytest.fixture()
def teacher_user(db_session):
    from app.models.user import UserRole

    return _make_user(
        db_session, UserRole.TEACHER, email_prefix="bdcsv_teacher"
    )


@pytest.fixture()
def patch_resolve_board(monkeypatch):
    """Return a setter that monkeypatches ``resolve_caller_board_id``."""

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
    title: str = "Board CSV test artifact",
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
# Happy path — BOARD_ADMIN exports own board → CSV uploaded + signed URL
# ─────────────────────────────────────────────────────────────────────


def test_board_admin_exports_own_board_csv(
    client,
    cmcp_flag_on,
    db_session,
    board_admin_tdsb,
    patch_resolve_board,
    mock_gcs,
):
    """BOARD_ADMIN exports own board → CSV uploaded + signed URL returned.

    Asserts:
    - 200 status.
    - GCS upload called exactly once.
    - GCS path namespaced under ``cmcp/board_catalog_exports/<board_id>/``.
    - GCS content-type is ``text/csv``.
    - Signed-URL function called exactly once with ``ttl_seconds=3600``.
    - Response body has both ``download_url`` and ``expires_at``.
    - ``expires_at`` is roughly 1 hour ahead of the request moment.
    - CSV bytes contain the in-scope artifact AND the coverage map section.
    """
    unique_board = f"TDSB_{uuid4().hex[:6].upper()}"
    patch_resolve_board({board_admin_tdsb.id: unique_board})

    in_scope = _seed_artifact(
        db_session,
        user_id=board_admin_tdsb.id,
        title="In-scope APPROVED",
        state="APPROVED",
        board_id=unique_board,
        se_codes=["MATH.5.A.1"],
        ai_engine="gpt-4o-mini",
        alignment_score=0.875,
    )
    # Cross-board row — must NOT appear in the CSV.
    _seed_artifact(
        db_session,
        user_id=board_admin_tdsb.id,
        title="OUT OF SCOPE",
        state="APPROVED",
        board_id="OCDSB",
        se_codes=["MATH.5.A.1"],
    )
    # DRAFT row — must NOT appear (APPROVED-only export).
    _seed_artifact(
        db_session,
        user_id=board_admin_tdsb.id,
        title="DRAFT row",
        state="DRAFT",
        board_id=unique_board,
        se_codes=["MATH.5.A.1"],
    )

    headers = _auth(client, board_admin_tdsb.email)
    before = datetime.now(tz=timezone.utc)
    resp = client.post(
        f"/api/board/{unique_board}/catalog/export.csv", headers=headers
    )
    after = datetime.now(tz=timezone.utc)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert "download_url" in body
    assert "expires_at" in body
    # Signed-URL stub embeds the GCS path; verify routing landed in URL.
    assert "cmcp/board_catalog_exports/" in body["download_url"]
    assert unique_board in body["download_url"]

    # ── Expires-at sanity ──
    expires_at = datetime.fromisoformat(body["expires_at"])
    delta = (expires_at - before).total_seconds()
    assert 3500 <= delta <= 3700, (
        f"expires_at should be ~1h ahead; got delta={delta}"
    )

    # ── GCS upload contract ──
    assert mock_gcs.upload_file.call_count == 1
    upload_args = mock_gcs.upload_file.call_args
    gcs_path = upload_args.args[0]
    csv_bytes = upload_args.args[1]
    content_type = upload_args.args[2]
    assert gcs_path.startswith(
        f"cmcp/board_catalog_exports/{unique_board}/"
    )
    assert gcs_path.endswith(".csv")
    assert content_type == "text/csv"

    # ── Signed-URL contract ──
    assert mock_gcs.generate_signed_url.call_count == 1
    sig_call = mock_gcs.generate_signed_url.call_args
    assert sig_call.args[0] == gcs_path
    assert sig_call.kwargs.get("ttl_seconds") == 3600

    # ── CSV body contract ──
    csv_text = csv_bytes.decode("utf-8")
    assert f"board_id,{unique_board}" in csv_text
    assert "section,coverage_map" in csv_text
    assert "section,artifacts" in csv_text
    # In-scope artifact ID + title surface in the CSV.
    assert str(in_scope.id) in csv_text
    assert "In-scope APPROVED" in csv_text
    # Cross-board / draft rows must NOT appear.
    assert "OUT OF SCOPE" not in csv_text
    assert "DRAFT row" not in csv_text
    # Coverage map captures the strand A → grade 5 → count 1.
    # csv format: "A,5,1" should be a substring.
    assert "A,5,1" in csv_text


# ─────────────────────────────────────────────────────────────────────
# Cross-board → 404 (no existence oracle)
# ─────────────────────────────────────────────────────────────────────


def test_board_admin_cross_board_export_returns_404(
    client,
    cmcp_flag_on,
    db_session,
    board_admin_ocdsb,
    patch_resolve_board,
    mock_gcs,
):
    """BOARD_ADMIN of OCDSB exporting /board/TDSB/... → 404.

    No existence oracle — same response shape regardless of whether
    TDSB has artifacts or not. Also asserts no GCS call was made.
    """
    patch_resolve_board({board_admin_ocdsb.id: "OCDSB"})

    # Seed a TDSB artifact so the existence-oracle check is meaningful.
    _seed_artifact(
        db_session,
        user_id=board_admin_ocdsb.id,
        title="TDSB approved",
        state="APPROVED",
        board_id="TDSB",
    )

    headers = _auth(client, board_admin_ocdsb.email)
    resp = client.post(
        "/api/board/TDSB/catalog/export.csv", headers=headers
    )
    assert resp.status_code == 404
    # Critical: no GCS call leaked through the 404 path.
    assert mock_gcs.upload_file.call_count == 0
    assert mock_gcs.generate_signed_url.call_count == 0


def test_board_admin_with_no_resolvable_board_returns_404(
    client,
    cmcp_flag_on,
    db_session,
    board_admin_tdsb,
    patch_resolve_board,
    mock_gcs,
):
    """BOARD_ADMIN whose ``resolve_caller_board_id`` returns None → 404."""
    patch_resolve_board({})  # no entries → resolves to None

    headers = _auth(client, board_admin_tdsb.email)
    resp = client.post(
        "/api/board/TDSB/catalog/export.csv", headers=headers
    )
    assert resp.status_code == 404
    assert mock_gcs.upload_file.call_count == 0


# ─────────────────────────────────────────────────────────────────────
# ADMIN bypass — may export any board
# ─────────────────────────────────────────────────────────────────────


def test_admin_can_export_any_board(
    client,
    cmcp_flag_on,
    db_session,
    admin_user,
    patch_resolve_board,
    mock_gcs,
):
    """ADMIN role bypasses the "own board" check (ops / debug)."""
    patch_resolve_board({})  # ADMIN should not need a resolvable board

    _seed_artifact(
        db_session,
        user_id=admin_user.id,
        title="ADMIN-readable",
        state="APPROVED",
        board_id="ADMIN_TARGET",
        se_codes=["SCIE.6.B.1"],
    )

    headers = _auth(client, admin_user.email)
    resp = client.post(
        "/api/board/ADMIN_TARGET/catalog/export.csv", headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert mock_gcs.upload_file.call_count == 1
    csv_bytes = mock_gcs.upload_file.call_args.args[1]
    assert "ADMIN-readable" in csv_bytes.decode("utf-8")


# ─────────────────────────────────────────────────────────────────────
# Role gating — non-(BOARD_ADMIN/ADMIN) → 403
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "role_fixture", ["parent_user", "student_user", "teacher_user"]
)
def test_non_board_admin_returns_403(
    request, client, cmcp_flag_on, mock_gcs, role_fixture
):
    """PARENT / STUDENT / TEACHER → 403 (not in role allowlist)."""
    user = request.getfixturevalue(role_fixture)
    headers = _auth(client, user.email)
    resp = client.post(
        "/api/board/TDSB/catalog/export.csv", headers=headers
    )
    assert resp.status_code == 403
    # Nothing should hit GCS on a 403.
    assert mock_gcs.upload_file.call_count == 0


def test_unauthenticated_returns_401(client, mock_gcs):
    """No Authorization header → 401."""
    resp = client.post("/api/board/TDSB/catalog/export.csv")
    assert resp.status_code == 401
    assert mock_gcs.upload_file.call_count == 0


def test_flag_off_returns_403(client, db_session, board_admin_tdsb, mock_gcs):
    """``cmcp.enabled`` OFF → 403 (matches the rest of CMCP REST surface).

    Deliberately does NOT use ``cmcp_flag_on`` so the flag stays default-OFF.
    """
    headers = _auth(client, board_admin_tdsb.email)
    resp = client.post(
        "/api/board/TDSB/catalog/export.csv", headers=headers
    )
    assert resp.status_code == 403
    assert mock_gcs.upload_file.call_count == 0


# ─────────────────────────────────────────────────────────────────────
# CSV body shape — empty board still emits header + sections
# ─────────────────────────────────────────────────────────────────────


def test_export_with_no_artifacts_still_emits_csv(
    client,
    cmcp_flag_on,
    db_session,
    board_admin_tdsb,
    patch_resolve_board,
    mock_gcs,
):
    """A board with zero APPROVED artifacts still produces a valid CSV.

    The coverage map will be empty (zero strand rows), the artifact
    section will have only the header row. The endpoint must still
    return a 200 + signed URL.
    """
    unique_board = f"EMPTY_{uuid4().hex[:6].upper()}"
    patch_resolve_board({board_admin_tdsb.id: unique_board})

    headers = _auth(client, board_admin_tdsb.email)
    resp = client.post(
        f"/api/board/{unique_board}/catalog/export.csv", headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert mock_gcs.upload_file.call_count == 1

    csv_bytes = mock_gcs.upload_file.call_args.args[1]
    csv_text = csv_bytes.decode("utf-8")
    # Section headers always present even when both sections are empty.
    assert "section,coverage_map" in csv_text
    assert "section,artifacts" in csv_text
    # Artifact column header row present.
    assert "id,title,content_type" in csv_text


# ─────────────────────────────────────────────────────────────────────
# Direct handler test — exercises the cross-board 404 without GCS
# ─────────────────────────────────────────────────────────────────────


def _board_admin_mock(*, board_id="TDSB", user_id=300, is_admin=False):
    """Return a SimpleNamespace that quacks like a User row."""
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


def test_handler_cross_board_raises_404_no_gcs_call(monkeypatch):
    """Direct handler call: cross-board 404 short-circuits before GCS.

    Mirrors ``test_handler_cross_board_raises_404`` from the catalog
    suite — the export path must reach 404 without invoking the GCS
    upload or signed-URL helpers (otherwise a prober could observe
    upload-side latency as an existence oracle).
    """
    from fastapi import HTTPException

    from app.api.routes import board_catalog as bc_module

    fake_gcs = MagicMock()
    monkeypatch.setattr(bc_module, "gcs_service", fake_gcs)

    db = MagicMock()
    user = _board_admin_mock(board_id="TDSB")

    with pytest.raises(HTTPException) as excinfo:
        bc_module.export_board_catalog_csv(
            board_id="OCDSB", current_user=user, db=db
        )
    assert excinfo.value.status_code == 404
    fake_gcs.upload_file.assert_not_called()
    fake_gcs.generate_signed_url.assert_not_called()
