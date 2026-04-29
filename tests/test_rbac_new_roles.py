"""CB-CMCP-001 M2-A 2A-3 (#4551) — BOARD_ADMIN + CURRICULUM_ADMIN role wiring.

Wave 2 stripe (M2-A 2A-3) verifies the role *wiring* lands correctly:

- The two new ``UserRole`` values exist (already added in M0-A 0A-3 #4414;
  this stripe re-asserts the surface as a regression net).
- A directly-seeded BOARD_ADMIN / CURRICULUM_ADMIN user can complete the
  end-to-end **JWT login → /api/users/me** auth flow and the resolved role
  matches what was stored.
- Existing PARENT / STUDENT / TEACHER / ADMIN users continue to round-trip
  through the same flow (regression net for the four legacy roles).
- :data:`app.mcp.auth.ROLE_TOOLS` now carries entries for ``BOARD_ADMIN``
  and ``CURRICULUM_ADMIN`` (empty allowlists today; populated by future
  M3-E + curriculum-admin stripes — see module docstring).
- The MCP role dispatcher (:func:`get_tools_for_role`) returns an empty
  *list* (not ``None`` and not "unknown") for the two new roles, so they
  are recognised by the dispatcher but currently denied every tool.

Per-tool RBAC enforcement and registration-flow exposure for
BOARD_ADMIN / CURRICULUM_ADMIN are out of scope (deferred to 2B-* and
M3-* stripes per the locked plan §7).

Implementation note: model imports happen *inside* each test function
because ``conftest.py`` reloads ``app.models`` against the SQLite test
DB; module-top imports would resolve against a stale class registry.
Same pattern as ``tests/test_cmcp_auth_roles.py`` and ``tests/test_auth.py``.
"""
from __future__ import annotations

import pytest

from conftest import PASSWORD


# ── Enum surface (regression net) ─────────────────────────────


def test_userrole_enum_includes_new_admin_roles(app):
    """``UserRole`` must expose ``BOARD_ADMIN`` and ``CURRICULUM_ADMIN``."""
    from app.models.user import UserRole

    assert UserRole.BOARD_ADMIN.value == "BOARD_ADMIN"
    assert UserRole.CURRICULUM_ADMIN.value == "CURRICULUM_ADMIN"


def test_userrole_enum_member_count_is_six(app):
    """Pin the enum size so an accidental rename / removal trips this test."""
    from app.models.user import UserRole

    members = {m.name for m in UserRole}
    assert members == {
        "PARENT",
        "STUDENT",
        "TEACHER",
        "ADMIN",
        "BOARD_ADMIN",
        "CURRICULUM_ADMIN",
    }


# ── ROLE_TOOLS dispatcher coverage ────────────────────────────


def test_role_tools_contains_board_admin_entry(app):
    """``BOARD_ADMIN`` must be a known key in ``ROLE_TOOLS`` (M2-A 2A-3)."""
    from app.mcp.auth import ROLE_TOOLS

    assert "BOARD_ADMIN" in ROLE_TOOLS
    # Empty list today; populated by a later M3-E / curriculum-admin
    # stripe. The presence of the key is what 2A-3 ships.
    assert ROLE_TOOLS["BOARD_ADMIN"] == []


def test_role_tools_contains_curriculum_admin_entry(app):
    """``CURRICULUM_ADMIN`` must be a known key in ``ROLE_TOOLS`` (M2-A 2A-3)."""
    from app.mcp.auth import ROLE_TOOLS

    assert "CURRICULUM_ADMIN" in ROLE_TOOLS
    assert ROLE_TOOLS["CURRICULUM_ADMIN"] == []


def test_role_tools_legacy_roles_unchanged(app):
    """The four phase-2 roles keep their existing entries (regression)."""
    from app.mcp.auth import ROLE_TOOLS

    # Spot-check: ADMIN remains the unrestricted sentinel.
    assert ROLE_TOOLS["ADMIN"] is None
    # PARENT / STUDENT / TEACHER each still hold a non-empty allowlist.
    for role_key in ("PARENT", "STUDENT", "TEACHER"):
        tools = ROLE_TOOLS[role_key]
        assert isinstance(tools, list) and len(tools) > 0, (
            f"ROLE_TOOLS[{role_key!r}] regressed to empty/None"
        )


@pytest.mark.parametrize("role_key", ["BOARD_ADMIN", "CURRICULUM_ADMIN"])
def test_get_tools_for_role_returns_empty_list_for_new_roles(role_key, app):
    """Dispatcher recognises the new roles (returns ``[]``, not unknown)."""
    from app.mcp.auth import get_tools_for_role

    tools = get_tools_for_role(role_key)
    # Distinct from ``None`` (admin sentinel) and distinct from the
    # implicit unknown-role default — the keys exist and map to a real
    # empty list.
    assert tools == []


@pytest.mark.parametrize("role_key", ["BOARD_ADMIN", "CURRICULUM_ADMIN"])
def test_assert_role_can_use_tool_denies_new_roles_today(role_key, app):
    """Empty allowlist → every tool is denied for the new roles today."""
    from app.mcp.auth import assert_role_can_use_tool

    with pytest.raises(PermissionError):
        assert_role_can_use_tool(role_key, "list_courses_api_courses__get")


# ── Auth flow: login → /api/users/me → role round-trip ────────


def _seed_user(db_session, email: str, role):
    """Create a user with the given role directly in the DB.

    Public registration only allows PARENT/STUDENT/TEACHER (see
    ``_ALLOWED_REGISTRATION_ROLES`` in ``app/api/routes/auth.py``), so
    BOARD_ADMIN / CURRICULUM_ADMIN must be seeded directly. The
    ``onboarding_completed`` flag is set so ``ProtectedRoute``-style
    checks don't redirect to onboarding in any future test that exercises
    a frontend dependency.
    """
    from app.core.security import get_password_hash
    from app.models.user import User

    user = User(
        email=email,
        full_name=f"RBAC test {role.name}",
        role=role,
        hashed_password=get_password_hash(PASSWORD),
        onboarding_completed=True,
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.parametrize("role_name", ["BOARD_ADMIN", "CURRICULUM_ADMIN"])
def test_new_role_user_can_authenticate_end_to_end(role_name, client, db_session):
    """Seed → login → /api/users/me; ``role`` round-trips with the new value."""
    from app.models.user import UserRole

    role = UserRole[role_name]
    email = f"rbac_new_{role.name.lower()}@test.com"
    _seed_user(db_session, email, role)

    login = client.post(
        "/api/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    me = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["email"] == email
    # ``UserRole`` is a ``str`` enum — the wire format is the enum *value*
    # (``"BOARD_ADMIN"`` / ``"CURRICULUM_ADMIN"``).
    assert body["role"] == role.value


@pytest.mark.parametrize("role_name", ["PARENT", "STUDENT", "TEACHER", "ADMIN"])
def test_existing_role_user_can_authenticate_end_to_end(role_name, client, db_session):
    """Regression: the four legacy roles still survive the same flow."""
    from app.models.user import UserRole

    role = UserRole[role_name]
    email = f"rbac_legacy_{role.name.lower()}@test.com"
    _seed_user(db_session, email, role)

    login = client.post(
        "/api/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    me = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200, me.text
    assert me.json()["role"] == role.value
