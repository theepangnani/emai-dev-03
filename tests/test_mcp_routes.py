"""CB-CMCP-001 M2-A 2A-2 (#4550) — MCP transport route tests.

Covers the route surface ported to dev-03 (no ``fastapi_mcp`` dep):

- ``POST /mcp/initialize``  — handshake.
- ``GET  /mcp/list_tools``   — role-filtered tool catalog.
- ``POST /mcp/call_tool``   — dispatch by name; 404 unknown / 403 role
  mismatch / 501 stub.

All tests exercise the real router via ``TestClient`` + the session-
scoped ``app`` fixture from ``tests/conftest.py``. JWT signing is local
crypto (jose), DB reads go through the in-process SQLite session — no
external network calls.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── Flag fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def mcp_flag_off(db_session):
    """Force ``mcp.enabled`` OFF for the test (matches default)."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "mcp.enabled")
        .first()
    )
    assert flag is not None, "mcp.enabled flag must be seeded"
    if flag.enabled is True:
        flag.enabled = False
        db_session.commit()
    return flag


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


# ── User fixtures ──────────────────────────────────────────────────────


def _make_user(db_session, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"mcproute_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"MCPRoute {role.value}",
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
def student_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.STUDENT)


@pytest.fixture()
def teacher_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.TEACHER)


@pytest.fixture()
def admin_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.ADMIN)


# ─────────────────────────────────────────────────────────────────────
# Auth — unauthenticated requests are rejected on all three routes
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("post", "/mcp/initialize", None),
        ("get", "/mcp/list_tools", None),
        ("post", "/mcp/call_tool", {"name": "get_expectations", "arguments": {}}),
    ],
)
def test_unauthenticated_returns_401(client, mcp_flag_on, method, path, body):
    """Missing ``Authorization`` header → 401 even when the flag is ON.

    Auth resolution short-circuits via ``OAuth2PasswordBearer`` before
    the flag check runs, so flag state never leaks to anonymous probers.
    """
    func = getattr(client, method)
    resp = func(path) if body is None else func(path, json=body)
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────
# Flag gating — auth + flag OFF → 403
# ─────────────────────────────────────────────────────────────────────


def test_initialize_flag_off_returns_403(client, parent_user, mcp_flag_off):
    """Authed + ``mcp.enabled`` OFF → 403 with a clear detail."""
    headers = _auth(client, parent_user.email)
    resp = client.post("/mcp/initialize", headers=headers)
    assert resp.status_code == 403
    assert "MCP transport" in resp.json()["detail"]


def test_list_tools_flag_off_returns_403(client, parent_user, mcp_flag_off):
    """``GET /mcp/list_tools`` is also gated by the flag."""
    headers = _auth(client, parent_user.email)
    resp = client.get("/mcp/list_tools", headers=headers)
    assert resp.status_code == 403


def test_call_tool_flag_off_returns_403(client, parent_user, mcp_flag_off):
    """``POST /mcp/call_tool`` is also gated by the flag."""
    headers = _auth(client, parent_user.email)
    resp = client.post(
        "/mcp/call_tool",
        json={"name": "get_expectations", "arguments": {}},
        headers=headers,
    )
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# Initialize — auth + flag ON returns server identity + tool count
# ─────────────────────────────────────────────────────────────────────


def test_initialize_returns_identity_and_tool_count(
    client, teacher_user, mcp_flag_on
):
    """Teacher sees all 4 stub tools (registry includes TEACHER for each)."""
    headers = _auth(client, teacher_user.email)
    resp = client.post("/mcp/initialize", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "ClassBridge MCP Server"
    assert body["protocol_version"]
    assert body["available_tools"] == 4  # all 4 stubs include TEACHER


# ─────────────────────────────────────────────────────────────────────
# list_tools — flag ON returns a catalog; role filtering works
# ─────────────────────────────────────────────────────────────────────


def test_list_tools_returns_catalog_for_teacher(
    client, teacher_user, mcp_flag_on
):
    """TEACHER sees all 4 stub tools (the entire current registry)."""
    headers = _auth(client, teacher_user.email)
    resp = client.get("/mcp/list_tools", headers=headers)
    assert resp.status_code == 200, resp.text
    tools = resp.json()["tools"]
    names = [t["name"] for t in tools]
    assert set(names) == {
        "get_expectations",
        "get_artifact",
        "list_catalog",
        "generate_content",
    }
    # Each tool entry exposes the public fields and nothing else.
    for t in tools:
        assert set(t.keys()) == {"name", "description", "input_schema"}


def test_list_tools_filters_by_role_parent_excludes_generate(
    client, parent_user, mcp_flag_on
):
    """PARENT does NOT see ``generate_content`` (TEACHER + ADMIN only)."""
    headers = _auth(client, parent_user.email)
    resp = client.get("/mcp/list_tools", headers=headers)
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()["tools"]}
    assert "generate_content" not in names
    # The read-only tools remain visible to PARENT.
    assert names == {"get_expectations", "get_artifact", "list_catalog"}


def test_list_tools_filters_by_role_student_excludes_generate(
    client, student_user, mcp_flag_on
):
    """STUDENT does NOT see ``generate_content`` either."""
    headers = _auth(client, student_user.email)
    resp = client.get("/mcp/list_tools", headers=headers)
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()["tools"]}
    assert "generate_content" not in names


def test_list_tools_admin_sees_all(client, admin_user, mcp_flag_on):
    """ADMIN is in every tool's allowlist → sees all 4."""
    headers = _auth(client, admin_user.email)
    resp = client.get("/mcp/list_tools", headers=headers)
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()["tools"]}
    assert names == {
        "get_expectations",
        "get_artifact",
        "list_catalog",
        "generate_content",
    }


# ─────────────────────────────────────────────────────────────────────
# call_tool — failure modes
# ─────────────────────────────────────────────────────────────────────


def test_call_tool_unknown_name_returns_404(
    client, teacher_user, mcp_flag_on
):
    """A name not in the registry → 404 with the offending name in detail."""
    headers = _auth(client, teacher_user.email)
    resp = client.post(
        "/mcp/call_tool",
        json={"name": "no_such_tool", "arguments": {}},
        headers=headers,
    )
    assert resp.status_code == 404
    assert "no_such_tool" in resp.json()["detail"]


def test_call_tool_role_not_allowed_returns_403(
    client, parent_user, mcp_flag_on
):
    """PARENT calling ``generate_content`` (TEACHER+ADMIN only) → 403.

    Re-checked at dispatch time even though ``list_tools`` already
    filters by role — the registry is the single source of truth.
    """
    headers = _auth(client, parent_user.email)
    resp = client.post(
        "/mcp/call_tool",
        json={"name": "generate_content", "arguments": {}},
        headers=headers,
    )
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert "generate_content" in detail


@pytest.fixture()
def synthetic_stub_tool(monkeypatch):
    """Inject a temporary stub tool into ``TOOLS`` for dispatch-stub tests.

    All 4 of the M2-B tools (get_expectations, get_artifact, list_catalog,
    generate_content) are now concrete handlers, so to exercise the
    dispatcher's 501 path we register a one-off stub.
    """
    from app.mcp.tools import TOOLS, ToolDescriptor, _stub_handler

    name = "_stub_for_test"
    desc = ToolDescriptor(
        name=name,
        description="Synthetic stub used only by dispatcher 501 tests.",
        input_schema={"type": "object", "additionalProperties": False},
        roles=("PARENT", "STUDENT", "TEACHER", "ADMIN"),
        handler=_stub_handler(name),
    )
    monkeypatch.setitem(TOOLS, name, desc)
    return name


def test_call_tool_stub_returns_501(client, teacher_user, mcp_flag_on, synthetic_stub_tool):
    """A stub tool raises :class:`MCPNotImplementedError` → 501.

    The detail must name the tool so MCP clients can tell which stub
    blocked them. Uses an injected synthetic stub since all 4 production
    M2-B tools are now concrete handlers.
    """
    headers = _auth(client, teacher_user.email)
    resp = client.post(
        "/mcp/call_tool",
        json={"name": synthetic_stub_tool, "arguments": {}},
        headers=headers,
    )
    assert resp.status_code == 501
    detail = resp.json()["detail"]
    assert synthetic_stub_tool in detail
    assert "not yet implemented" in detail


# ─────────────────────────────────────────────────────────────────────
# Validation — empty / malformed body
# ─────────────────────────────────────────────────────────────────────


def test_call_tool_missing_name_returns_422(
    client, teacher_user, mcp_flag_on
):
    """Pydantic rejects an empty ``name`` field with 422."""
    headers = _auth(client, teacher_user.email)
    resp = client.post(
        "/mcp/call_tool",
        json={"name": "", "arguments": {}},
        headers=headers,
    )
    assert resp.status_code == 422


def test_call_tool_default_arguments(client, teacher_user, mcp_flag_on, synthetic_stub_tool):
    """Omitting ``arguments`` falls back to ``{}`` (and still hits 501).

    Verifies the schema's ``default_factory=dict`` so MCP clients don't
    have to send an empty dict explicitly. Uses the injected stub since
    all production tools are now concrete.
    """
    headers = _auth(client, teacher_user.email)
    resp = client.post(
        "/mcp/call_tool",
        json={"name": synthetic_stub_tool},
        headers=headers,
    )
    # Stub raises 501 — confirms the dispatcher reached the handler.
    assert resp.status_code == 501


# ─────────────────────────────────────────────────────────────────────
# Token-type hardening — non-access tokens rejected
# ─────────────────────────────────────────────────────────────────────


def test_call_tool_rejects_non_access_token(client, mcp_flag_on, parent_user):
    """A ``type=refresh`` token signed with the same secret is rejected (401).

    Inherits 2A-1's strict ``type=access`` enforcement via
    :func:`verify_mcp_token`. Without this guard a leaked refresh /
    unsubscribe / password-reset token could authenticate the MCP
    transport.
    """
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    from app.core.config import settings

    refresh_token = jwt.encode(
        {
            "sub": str(parent_user.id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
            "type": "refresh",
        },
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    resp = client.post(
        "/mcp/call_tool",
        json={"name": "get_expectations", "arguments": {}},
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert resp.status_code == 401
