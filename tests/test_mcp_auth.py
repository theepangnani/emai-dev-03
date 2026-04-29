"""CB-CMCP-001 M2-A 2A-1 (#4549) — MCP auth scaffold tests.

Covers the auth surface ported from ``class-bridge-phase-2``:

- :func:`verify_mcp_token` happy path (valid JWT → :class:`MCPSession`).
- 4× failure paths: invalid signature, expired token, missing Bearer
  header, ``sub``-less payload.
- :func:`assert_role_can_use_tool` rejects insufficient role and accepts
  matching role; ``ADMIN`` (unrestricted) bypasses the allowlist.
- :func:`get_tools_for_role` returns the expected shapes for known roles
  (case-insensitive) and unknown roles.

JWT signing is local crypto (``python-jose``), no network calls; DB
access is unnecessary for the decode-only path under test, so no
``db_session`` fixture is used.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from jose import jwt


# ── Helpers ────────────────────────────────────────────────────


def _make_token(
    sub: str = "42",
    *,
    role: str | None = "parent",
    expires_in: timedelta = timedelta(minutes=30),
    secret: str | None = None,
    algorithm: str | None = None,
    extra_claims: dict | None = None,
) -> str:
    """Locally sign a JWT with the runtime ``settings`` secret/algorithm.

    The signing happens entirely in-process via ``jose.jwt.encode`` — no
    external service is contacted. Tests pass overrides (e.g. a different
    ``secret``) to forge invalid tokens.
    """
    from app.core.config import settings

    payload: dict = {
        "sub": sub,
        "exp": datetime.now(timezone.utc) + expires_in,
        "type": "access",
    }
    if role is not None:
        payload["role"] = role
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        secret or settings.secret_key,
        algorithm=algorithm or settings.algorithm,
    )


# ── verify_mcp_token: happy path ───────────────────────────────


def test_verify_mcp_token_valid_returns_session(app):
    """Valid JWT decodes to an ``MCPSession`` carrying user_id + role."""
    from app.mcp.auth import MCPSession, verify_mcp_token

    token = _make_token(sub="42", role="parent")
    session = verify_mcp_token(token)

    assert isinstance(session, MCPSession)
    assert session.user_id == "42"
    assert session.role == "parent"
    assert session.payload["sub"] == "42"
    assert session.payload["type"] == "access"


def test_verify_mcp_token_role_missing_returns_none_role(app):
    """A JWT without a ``role`` claim still decodes; ``role`` is ``None``."""
    from app.mcp.auth import verify_mcp_token

    token = _make_token(sub="7", role=None)
    session = verify_mcp_token(token)

    assert session.user_id == "7"
    assert session.role is None


# ── verify_mcp_token: failure paths ────────────────────────────


def test_verify_mcp_token_invalid_signature_raises_401(app):
    """A token signed with the wrong secret raises 401."""
    from app.mcp.auth import verify_mcp_token

    bad_token = _make_token(sub="42", secret="not-the-real-secret-pad-to-length-okay")

    with pytest.raises(HTTPException) as excinfo:
        verify_mcp_token(bad_token)
    assert excinfo.value.status_code == 401
    assert excinfo.value.headers == {"WWW-Authenticate": "Bearer"}


def test_verify_mcp_token_expired_raises_401(app):
    """A token whose ``exp`` is in the past raises 401."""
    from app.mcp.auth import verify_mcp_token

    expired = _make_token(sub="42", expires_in=timedelta(minutes=-1))

    with pytest.raises(HTTPException) as excinfo:
        verify_mcp_token(expired)
    assert excinfo.value.status_code == 401


def test_verify_mcp_token_missing_sub_raises_401(app):
    """A signed JWT lacking the ``sub`` claim raises 401."""
    from app.core.config import settings
    from app.mcp.auth import verify_mcp_token

    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        "role": "parent",
        "type": "access",
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    with pytest.raises(HTTPException) as excinfo:
        verify_mcp_token(token)
    assert excinfo.value.status_code == 401


def test_verify_mcp_token_empty_token_raises_401(app):
    """An empty / missing token short-circuits to 401."""
    from app.mcp.auth import verify_mcp_token

    with pytest.raises(HTTPException) as excinfo:
        verify_mcp_token("")
    assert excinfo.value.status_code == 401


@pytest.mark.parametrize(
    "wrong_type",
    ["refresh", "password_reset", "email_verify", "unsubscribe", "account_deletion"],
)
def test_verify_mcp_token_rejects_non_access_token_types(wrong_type, app):
    """Tokens minted with another ``type`` claim must be rejected (PR #4557).

    dev-03 mints multiple JWT types with the same secret + algorithm. A
    leaked refresh / password-reset / unsubscribe / email-verify /
    account-deletion token must NOT authenticate an MCP transport
    session — that would be a token-confusion attack. ``verify_mcp_token``
    enforces ``type=access`` strictly.
    """
    from app.mcp.auth import verify_mcp_token

    token = _make_token(
        sub="42",
        extra_claims={"type": wrong_type},  # overrides the default "access"
    )

    with pytest.raises(HTTPException) as excinfo:
        verify_mcp_token(token)
    assert excinfo.value.status_code == 401


def test_verify_mcp_token_rejects_token_without_type_claim(app):
    """A signed JWT lacking ``type`` is rejected (defence-in-depth).

    All dev-03 token mints set ``type=access`` (or another known type).
    A token that signs cleanly but has no ``type`` claim is either an
    external token we don't trust, or a malformed in-house token — either
    way, reject.
    """
    from app.core.config import settings
    from app.mcp.auth import verify_mcp_token

    payload = {
        "sub": "42",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        # no "type" key
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    with pytest.raises(HTTPException) as excinfo:
        verify_mcp_token(token)
    assert excinfo.value.status_code == 401


def test_verify_mcp_token_returns_fresh_exception_per_call(app):
    """Each rejection raises a *new* ``HTTPException`` instance (no shared state).

    A module-level singleton would risk cross-request mutation if any
    handler attaches context to ``.detail`` / ``.headers``. Mirrors the
    per-call pattern in ``app.api.deps.get_current_user``.
    """
    from app.mcp.auth import verify_mcp_token

    excs: list[HTTPException] = []
    for _ in range(2):
        try:
            verify_mcp_token("")
        except HTTPException as e:
            excs.append(e)

    assert len(excs) == 2
    # Distinct instances — verifies the per-call factory contract.
    assert excs[0] is not excs[1]


def test_verify_mcp_token_role_claim_typically_none_in_production(app):
    """Production access tokens carry no ``role`` claim → ``MCPSession.role is None``.

    Documents the dev-03 reality (``create_access_token`` only emits
    ``sub`` + ``onboarding_completed`` + ``type`` + ``exp`` + ``jti``).
    Downstream stripes (2A-2) MUST resolve the role from the ``User`` row
    rather than relying on ``MCPSession.role``. This test pins that
    contract so a future PR that starts emitting ``role`` claims has to
    update this expectation deliberately.
    """
    from app.core.config import settings
    from app.core.security import create_access_token
    from app.mcp.auth import verify_mcp_token

    # Mint a real production-shape token (mirrors auth.py login path).
    token = create_access_token(data={"sub": "42", "onboarding_completed": True})
    session = verify_mcp_token(token)

    assert session.user_id == "42"
    assert session.role is None
    # The payload still carries the prod claims for downstream consumers.
    assert session.payload["onboarding_completed"] is True
    assert session.payload["type"] == "access"
    assert "role" not in session.payload
    # Reference settings to keep the import valid even if future test
    # refactors add an explicit settings assertion.
    assert settings.algorithm


# ── authenticate_mcp_request: dependency wiring ────────────────


def test_authenticate_mcp_request_missing_bearer_header_returns_401(app):
    """Calling a route protected by ``authenticate_mcp_request`` without a
    Bearer header returns 401 from the OAuth2 scheme itself.

    ``OAuth2PasswordBearer(auto_error=True)`` short-circuits before
    ``verify_mcp_token`` runs, so the 401 comes from the dependency
    chain rather than our own ``HTTPException``. Either way, callers
    can rely on a 401 when no token is presented.
    """
    from app.mcp.auth import MCPSession, authenticate_mcp_request

    sub_app = FastAPI()

    @sub_app.get("/probe")
    async def probe(session: MCPSession = Depends(authenticate_mcp_request)):
        return {"user_id": session.user_id}

    with TestClient(sub_app) as client:
        resp = client.get("/probe")
        assert resp.status_code == 401


def test_authenticate_mcp_request_valid_token_returns_session(app):
    """A valid Bearer token resolves to an ``MCPSession`` in the dep chain."""
    from app.mcp.auth import MCPSession, authenticate_mcp_request

    sub_app = FastAPI()

    @sub_app.get("/probe")
    async def probe(session: MCPSession = Depends(authenticate_mcp_request)):
        return {"user_id": session.user_id, "role": session.role}

    token = _make_token(sub="99", role="teacher")
    with TestClient(sub_app) as client:
        resp = client.get("/probe", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"user_id": "99", "role": "teacher"}


# ── Role-based tool authorization ──────────────────────────────


def test_get_tools_for_role_known_roles(app):
    """All four phase-2 roles return a non-empty allowlist (or ``None`` for ADMIN)."""
    from app.mcp.auth import get_tools_for_role

    parent_tools = get_tools_for_role("PARENT")
    student_tools = get_tools_for_role("STUDENT")
    teacher_tools = get_tools_for_role("TEACHER")
    admin_tools = get_tools_for_role("ADMIN")

    assert isinstance(parent_tools, list) and len(parent_tools) > 0
    assert isinstance(student_tools, list) and len(student_tools) > 0
    assert isinstance(teacher_tools, list) and len(teacher_tools) > 0
    assert admin_tools is None  # unrestricted sentinel


def test_get_tools_for_role_is_case_insensitive(app):
    """Lowercase / mixed-case role names map to the same allowlist."""
    from app.mcp.auth import get_tools_for_role

    assert get_tools_for_role("parent") == get_tools_for_role("PARENT")
    assert get_tools_for_role("Teacher") == get_tools_for_role("TEACHER")


def test_get_tools_for_role_unknown_role_returns_empty(app):
    """Unknown / missing roles get the empty allowlist (deny-all)."""
    from app.mcp.auth import get_tools_for_role

    assert get_tools_for_role("HACKER") == []
    assert get_tools_for_role("") == []
    assert get_tools_for_role(None) == []


def test_assert_role_can_use_tool_rejects_insufficient_role(app):
    """A STUDENT cannot invoke a TEACHER-only tool → ``PermissionError``."""
    from app.mcp.auth import assert_role_can_use_tool

    # ``list_teaching_courses_*`` is in the TEACHER allowlist but not STUDENT.
    with pytest.raises(PermissionError):
        assert_role_can_use_tool(
            "STUDENT",
            "list_teaching_courses_api_courses_teaching_get",
        )


def test_assert_role_can_use_tool_accepts_allowed_tool(app):
    """A PARENT *can* invoke a tool in their allowlist (no exception raised)."""
    from app.mcp.auth import assert_role_can_use_tool

    # No raise == pass.
    assert_role_can_use_tool("PARENT", "list_courses_api_courses__get")


def test_assert_role_can_use_tool_admin_unrestricted(app):
    """ADMIN is mapped to ``None`` in ROLE_TOOLS → can invoke any tool."""
    from app.mcp.auth import assert_role_can_use_tool

    # Even a tool no other role allows still passes for admin.
    assert_role_can_use_tool("ADMIN", "some_future_tool_id_we_have_not_added_yet")


def test_assert_role_can_use_tool_unknown_role_rejected(app):
    """An unknown role gets the empty allowlist → all tools rejected."""
    from app.mcp.auth import assert_role_can_use_tool

    with pytest.raises(PermissionError):
        assert_role_can_use_tool("UNKNOWN_ROLE", "list_courses_api_courses__get")


# ── Public surface re-export ───────────────────────────────────


def test_module_reexports_public_api(app):
    """``app.mcp`` re-exports the auth surface for downstream stripes."""
    import app.mcp as mcp

    for name in (
        "MCPSession",
        "ROLE_TOOLS",
        "assert_role_can_use_tool",
        "authenticate_mcp_request",
        "get_tools_for_role",
        "verify_mcp_token",
    ):
        assert hasattr(mcp, name), f"app.mcp missing re-export: {name}"
