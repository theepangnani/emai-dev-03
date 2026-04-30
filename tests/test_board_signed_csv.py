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


# ─────────────────────────────────────────────────────────────────────
# CSV-formula-injection neutralization
# ─────────────────────────────────────────────────────────────────────


def test_csv_safe_neutralizes_formula_prefixes():
    """``_csv_safe`` prefixes formula-trigger strings with a literal ``'``."""
    from app.api.routes.board_catalog import _csv_safe

    # Each of the OWASP-listed formula triggers gets neutralized.
    for prefix in ("=", "+", "-", "@", "\t", "\r"):
        assert _csv_safe(f"{prefix}danger") == f"'{prefix}danger"

    # Benign strings + non-strings pass through untouched.
    assert _csv_safe("Plain title") == "Plain title"
    assert _csv_safe("") == ""
    assert _csv_safe(123) == 123
    assert _csv_safe(None) is None


def test_export_csv_neutralizes_formula_in_title(
    client,
    cmcp_flag_on,
    db_session,
    board_admin_tdsb,
    patch_resolve_board,
    mock_gcs,
):
    """Title starting with ``=`` is rendered as ``'=...`` in the CSV.

    Open-in-Sheets would otherwise execute the cell as a formula. The
    leading single-quote forces text rendering. This is the OWASP CSV-
    injection mitigation.
    """
    unique_board = f"INJECT_{uuid4().hex[:6].upper()}"
    patch_resolve_board({board_admin_tdsb.id: unique_board})

    _seed_artifact(
        db_session,
        user_id=board_admin_tdsb.id,
        title='=HYPERLINK("evil.test","steal")',
        state="APPROVED",
        board_id=unique_board,
    )

    headers = _auth(client, board_admin_tdsb.email)
    resp = client.post(
        f"/api/board/{unique_board}/catalog/export.csv", headers=headers
    )
    assert resp.status_code == 200, resp.text
    csv_text = mock_gcs.upload_file.call_args.args[1].decode("utf-8")
    # The rendered cell starts with ``'=`` — formula is neutralized.
    assert "'=HYPERLINK" in csv_text
    # And the un-prefixed form is NOT present (would trip Sheets).
    # Use a regex-style check: bare "=HYPERLINK" never appears without
    # the leading ``'``. csv.writer quotes the cell, so the literal
    # substring ``"=HYPERLINK"`` (with double-quote) would mark
    # injection; the safe form is ``"'=HYPERLINK"``.
    assert '"=HYPERLINK' not in csv_text


# ─────────────────────────────────────────────────────────────────────
# Hard cap — too many artifacts → 413
# ─────────────────────────────────────────────────────────────────────


def test_export_over_cap_returns_413(monkeypatch):
    """If a board has more APPROVED rows than the cap, return 413.

    Exercised at the handler level so we don't have to seed 50k+ rows
    in SQLite — the test patches ``_query_all_approved_artifacts`` to
    return a synthetic over-cap list and verifies the early-exit
    happens before the GCS upload helper fires.
    """
    from fastapi import HTTPException

    from app.api.routes import board_catalog as bc_module

    fake_gcs = MagicMock()
    monkeypatch.setattr(bc_module, "gcs_service", fake_gcs)
    # Avoid the real DB by stubbing the coverage_map + artifact loader.
    monkeypatch.setattr(
        bc_module, "compute_coverage_map", lambda board_id, db: {}
    )
    over_cap = bc_module.MAX_EXPORT_ARTIFACT_ROWS + 1
    fake_artifact = SimpleNamespace(
        id=1,
        title="x",
        content_type="study_guide",
        state="APPROVED",
        subject_code=None,
        grade=None,
        se_codes=[],
        alignment_score=None,
        ai_engine=None,
        course_id=None,
        created_at=None,
    )
    monkeypatch.setattr(
        bc_module,
        "_query_all_approved_artifacts",
        lambda db, *, board_id: [fake_artifact] * over_cap,
    )

    db = MagicMock()
    user = _board_admin_mock(board_id="TDSB")

    with pytest.raises(HTTPException) as excinfo:
        bc_module.export_board_catalog_csv(
            board_id="TDSB", current_user=user, db=db
        )
    assert excinfo.value.status_code == 413
    fake_gcs.upload_file.assert_not_called()
    fake_gcs.generate_signed_url.assert_not_called()


# ─────────────────────────────────────────────────────────────────────
# Expanded CSV-injection coverage (#4700) — content_type / state /
# board_id / SE-codes / subject_code all run through `_csv_safe`.
# ─────────────────────────────────────────────────────────────────────


def test_safe_row_neutralizes_every_string_cell():
    """`_safe_row` runs every string positional through `_csv_safe`."""
    from app.api.routes.board_catalog import _safe_row

    row = _safe_row("=BAD", 42, "+plus", None, "@at", "ok", 3.14)
    assert row == ["'=BAD", 42, "'+plus", None, "'@at", "ok", 3.14]


def test_export_csv_neutralizes_formula_in_content_type_and_state(
    monkeypatch,
):
    """A malicious payload in `content_type` / `state` / `subject_code`
    / `ai_engine` / `se_codes` is neutralized in the rendered CSV.

    Before #4700 the CSV writer passed `art.content_type` and
    `art.state` raw — a future model tweak that lets either become
    user-controlled (or a leak through an attacker-controlled value)
    would have been exploitable. This test injects a malicious payload
    into each previously-unsanitized non-title field and asserts the
    leading single-quote is present in the rendered cell.
    """
    from app.api.routes import board_catalog as bc_module

    fake_gcs = MagicMock()
    captured: dict = {}

    def _capture_upload(path, data, content_type):
        captured["path"] = path
        captured["data"] = data
        captured["content_type"] = content_type

    fake_gcs.upload_file.side_effect = _capture_upload
    fake_gcs.generate_signed_url.return_value = "https://stub.test/x"
    monkeypatch.setattr(bc_module, "gcs_service", fake_gcs)
    monkeypatch.setattr(
        bc_module, "compute_coverage_map", lambda board_id, db: {}
    )
    # Skip audit — irrelevant to this assertion + avoids needing a real DB.
    monkeypatch.setattr(
        bc_module, "log_action", lambda *a, **kw: None
    )

    malicious = SimpleNamespace(
        id=42,
        title="Plain title",
        # `=cmd|...!A1` is the canonical OWASP CSV-injection payload
        # (Excel will execute it on open).
        content_type='=cmd|"/c calc"!A1',
        state="+evil_state",
        subject_code="-malicious_subject",
        grade=None,
        se_codes=["@evil_code"],
        alignment_score=None,
        ai_engine="=HYPERLINK(\"x\",\"y\")",
        course_id=None,
        created_at=None,
    )
    monkeypatch.setattr(
        bc_module,
        "_query_all_approved_artifacts",
        lambda db, *, board_id: [malicious],
    )

    db = MagicMock()
    user = _board_admin_mock(board_id="TDSB")

    bc_module.export_board_catalog_csv(
        board_id="TDSB", current_user=user, db=db
    )

    csv_text = captured["data"].decode("utf-8")
    # Each previously-raw cell now starts with `'` so Excel/Sheets
    # render as literal text instead of executing the formula.
    assert "'=cmd" in csv_text  # content_type neutralized
    assert "'+evil_state" in csv_text  # state neutralized
    assert "'-malicious_subject" in csv_text  # subject_code
    assert "'@evil_code" in csv_text  # se_codes pipe-string
    assert "'=HYPERLINK" in csv_text  # ai_engine neutralized
    # Critical: the un-prefixed (raw) form must NOT appear in any cell.
    # csv.writer wraps formula-trigger cells in quotes, so a raw form
    # would show as `"=cmd|...` (no leading `'`). The neutralized form
    # is `"'=cmd|...`. Ensure the unsafe cell shape never leaks.
    assert '"=cmd' not in csv_text
    assert '"+evil_state' not in csv_text
    assert '"-malicious_subject' not in csv_text
    assert '"@evil_code' not in csv_text


def test_export_csv_neutralizes_formula_in_board_id_header(monkeypatch):
    """A malicious payload in `board_id` (path param) is neutralized
    in the header row.

    `board_id` flows from the URL path into the header row "as-is" —
    `["board_id", board_id]`. Before #4700 this was raw. Even though
    a path param is normally controlled, defense-in-depth says any
    string cell that could ever come from a request must run through
    `_csv_safe`.
    """
    from app.api.routes import board_catalog as bc_module

    fake_gcs = MagicMock()
    captured: dict = {}

    def _capture_upload(path, data, content_type):
        captured["data"] = data

    fake_gcs.upload_file.side_effect = _capture_upload
    fake_gcs.generate_signed_url.return_value = "https://stub.test/x"
    monkeypatch.setattr(bc_module, "gcs_service", fake_gcs)
    monkeypatch.setattr(
        bc_module, "compute_coverage_map", lambda board_id, db: {}
    )
    monkeypatch.setattr(
        bc_module, "_query_all_approved_artifacts", lambda db, *, board_id: []
    )
    monkeypatch.setattr(bc_module, "log_action", lambda *a, **kw: None)

    db = MagicMock()
    # ADMIN bypasses cross-board check so we can pass an arbitrary path value.
    admin = _board_admin_mock(is_admin=True, board_id=None)

    bc_module.export_board_catalog_csv(
        board_id="=DANGER", current_user=admin, db=db
    )

    csv_text = captured["data"].decode("utf-8")
    # Header row starts with the literal `'=DANGER` (single-quote prefix).
    assert "'=DANGER" in csv_text
    # The unsanitized form (`"=DANGER` with double-quote wrapping, which
    # csv.writer applies to formula cells) must NOT appear.
    assert '"=DANGER' not in csv_text


# ─────────────────────────────────────────────────────────────────────
# Audit log (#4698) — Bill 194: CSV export writes a
# `cmcp.board.catalog_exported` row with the board_id, artifact_count,
# csv_bytes, and gcs_path captured in details.
# ─────────────────────────────────────────────────────────────────────


def test_export_writes_audit_row(
    client,
    cmcp_flag_on,
    db_session,
    board_admin_tdsb,
    patch_resolve_board,
    mock_gcs,
):
    """A successful CSV export writes a `cmcp.board.catalog_exported`
    audit row with the board_id + artifact_count + csv_bytes + gcs_path.
    """
    import json

    from app.models.audit_log import AuditLog

    unique_board = f"AUDIT_{uuid4().hex[:6].upper()}"
    patch_resolve_board({board_admin_tdsb.id: unique_board})

    _seed_artifact(
        db_session,
        user_id=board_admin_tdsb.id,
        title="Auditable export row",
        state="APPROVED",
        board_id=unique_board,
    )

    headers = _auth(client, board_admin_tdsb.email)
    resp = client.post(
        f"/api/board/{unique_board}/catalog/export.csv", headers=headers
    )
    assert resp.status_code == 200, resp.text

    # Read from a fresh ``SessionLocal()`` for cross-session sanity.
    # The pool-sharing semantics in SQLAlchemy mean this isn't a
    # mutation-test against a missing ``db.commit()`` (a fresh session
    # backed by the same engine pool can still see SAVEPOINT-flushed
    # rows). The explicit commit in the handler is convention-aligned
    # with ``cmcp_review.py`` and required for production durability.
    from app.db.database import SessionLocal

    fresh = SessionLocal()
    try:
        rows = (
            fresh.query(AuditLog)
            .filter(AuditLog.action == "cmcp.board.catalog_exported")
            .filter(AuditLog.user_id == board_admin_tdsb.id)
            .all()
        )
        assert len(rows) >= 1, (
            "expected cmcp.board.catalog_exported audit row "
            "(visible from a fresh session — verifies db.commit() ran)"
        )
        latest = rows[-1]
        assert latest.resource_type == "board_catalog"
        details = json.loads(latest.details)
        assert details["board_id"] == unique_board
        assert details["artifact_count"] == 1
        assert details["csv_bytes"] > 0
        assert details["gcs_path"].startswith(
            f"cmcp/board_catalog_exports/{unique_board}/"
        )
        assert details["role"] == "BOARD_ADMIN"
    finally:
        fresh.close()


def test_export_403_writes_no_audit_row(
    client,
    cmcp_flag_on,
    db_session,
    parent_user,
    mock_gcs,
):
    """A 403'd export must NOT emit `cmcp.board.catalog_exported`."""
    from app.models.audit_log import AuditLog

    pre_count = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "cmcp.board.catalog_exported")
        .count()
    )
    headers = _auth(client, parent_user.email)
    resp = client.post(
        "/api/board/TDSB/catalog/export.csv", headers=headers
    )
    assert resp.status_code == 403
    post_count = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "cmcp.board.catalog_exported")
        .count()
    )
    assert post_count == pre_count


def test_export_413_writes_no_audit_row(monkeypatch):
    """An over-cap export hits 413 BEFORE the audit / GCS calls.

    The audit row + GCS upload + signed URL all live below the 413 check
    — exercising the cap path must not produce an audit entry (otherwise
    a probe could spam the table).
    """
    from fastapi import HTTPException

    from app.api.routes import board_catalog as bc_module

    fake_gcs = MagicMock()
    monkeypatch.setattr(bc_module, "gcs_service", fake_gcs)
    audit_calls: list = []
    monkeypatch.setattr(
        bc_module, "log_action", lambda *a, **kw: audit_calls.append(kw)
    )
    monkeypatch.setattr(
        bc_module, "compute_coverage_map", lambda board_id, db: {}
    )
    over_cap = bc_module.MAX_EXPORT_ARTIFACT_ROWS + 1
    fake_artifact = SimpleNamespace(
        id=1,
        title="x",
        content_type="study_guide",
        state="APPROVED",
        subject_code=None,
        grade=None,
        se_codes=[],
        alignment_score=None,
        ai_engine=None,
        course_id=None,
        created_at=None,
    )
    monkeypatch.setattr(
        bc_module,
        "_query_all_approved_artifacts",
        lambda db, *, board_id: [fake_artifact] * over_cap,
    )

    db = MagicMock()
    user = _board_admin_mock(board_id="TDSB")

    with pytest.raises(HTTPException) as excinfo:
        bc_module.export_board_catalog_csv(
            board_id="TDSB", current_user=user, db=db
        )
    assert excinfo.value.status_code == 413
    assert audit_calls == [], (
        "413 path must not emit an audit log entry"
    )
