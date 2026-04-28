"""CB-CMCP-001 M0-A 0A-3 (#4414) — UserRole BOARD_ADMIN + CURRICULUM_ADMIN.

Verifies that:
- The two new enum values exist on ``UserRole``.
- A ``User`` row can be persisted with each new role and round-tripped.
- ``require_role(UserRole.BOARD_ADMIN)`` / ``require_role(UserRole.CURRICULUM_ADMIN)``
  accept users with that role and 403 for users without it.
- The existing four roles (PARENT/STUDENT/TEACHER/ADMIN) continue to round-trip
  and gate as before (regression net for the enum extension).

These tests use the shared SQLite test app from ``conftest.py`` and the
``require_role`` dependency from ``app.api.deps`` (the production gate).

No frontend changes; no RBAC matrix logic — those live in M2/M3 stripes per
the implementation plan.

Implementation note: model imports happen *inside* each test function rather
than at module top. The session-scoped ``app`` fixture in ``conftest.py``
reloads ``app.models`` (to pick up the test ``DATABASE_URL``), so module-top
imports would resolve against a stale class registry that no longer matches
the registered SQLAlchemy mappers. This is the same pattern used in
``tests/test_auth.py``.
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient


# ── Enum surface ──────────────────────────────────────────────


def test_userrole_enum_includes_new_admin_roles(app):
    """Both new values must be exposed on the ``UserRole`` enum."""
    from app.models.user import UserRole

    assert UserRole.BOARD_ADMIN.value == "BOARD_ADMIN"
    assert UserRole.CURRICULUM_ADMIN.value == "CURRICULUM_ADMIN"
    # Existing values still present (regression).
    assert UserRole.PARENT.value == "parent"
    assert UserRole.STUDENT.value == "student"
    assert UserRole.TEACHER.value == "teacher"
    assert UserRole.ADMIN.value == "admin"


def test_userrole_enum_member_count_is_six(app):
    """Sanity check that we added exactly two new members, no more."""
    from app.models.user import UserRole

    members = list(UserRole)
    assert len(members) == 6
    names = {m.name for m in members}
    assert names == {
        "PARENT",
        "STUDENT",
        "TEACHER",
        "ADMIN",
        "BOARD_ADMIN",
        "CURRICULUM_ADMIN",
    }


# ── Persistence round-trip ────────────────────────────────────


@pytest.mark.parametrize(
    "role_name",
    [
        "PARENT",
        "STUDENT",
        "TEACHER",
        "ADMIN",
        "BOARD_ADMIN",
        "CURRICULUM_ADMIN",
    ],
)
def test_user_round_trip_for_each_role(role_name, db_session):
    """A User can be persisted with any of the six roles and re-read."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    role = UserRole[role_name]
    email = f"cmcp_roundtrip_{role.name.lower()}@test.com"
    user = User(
        email=email,
        full_name=f"Role Test {role.name}",
        role=role,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(user)
    db_session.commit()

    refetched = db_session.query(User).filter(User.email == email).one()
    assert refetched.role == role
    assert refetched.has_role(role) is True


# ── require_role dependency ───────────────────────────────────


def _build_role_check_app(app, required_role):
    """Mount a tiny isolated route that uses ``require_role`` for one role.

    Returns a fresh ``FastAPI`` instance that copies the test app's
    dependency overrides (so ``get_db`` keeps pointing at the SQLite fixture).
    Using a standalone app avoids mutating the session-scoped router.
    """
    from app.api.deps import require_role

    sub_app = FastAPI()

    @sub_app.get("/probe")
    def probe(user=Depends(require_role(required_role))):
        return {"ok": True, "role": user.role.value if user.role else None}

    sub_app.dependency_overrides = dict(app.dependency_overrides)
    return sub_app


def _make_user(db_session, email, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    user = User(
        email=email,
        full_name=f"Probe {email}",
        role=role,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.parametrize(
    "required_role_name",
    ["BOARD_ADMIN", "CURRICULUM_ADMIN"],
)
def test_require_role_accepts_matching_user(required_role_name, app, db_session):
    """require_role(NEW_ROLE) returns 200 for a user with that role."""
    from app.api.deps import get_current_user
    from app.models.user import UserRole

    required_role = UserRole[required_role_name]
    user = _make_user(
        db_session,
        email=f"cmcp_match_{required_role.name.lower()}@test.com",
        role=required_role,
    )

    sub_app = _build_role_check_app(app, required_role)
    sub_app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(sub_app) as client:
        resp = client.get("/probe")
        assert resp.status_code == 200, resp.text
        assert resp.json()["ok"] is True


@pytest.mark.parametrize(
    "required_role_name",
    ["BOARD_ADMIN", "CURRICULUM_ADMIN"],
)
def test_require_role_rejects_non_matching_user(required_role_name, app, db_session):
    """require_role(NEW_ROLE) returns 403 for a user without that role."""
    from app.api.deps import get_current_user
    from app.models.user import UserRole

    required_role = UserRole[required_role_name]
    user = _make_user(
        db_session,
        email=f"cmcp_reject_{required_role.name.lower()}@test.com",
        role=UserRole.PARENT,  # not the required role
    )

    sub_app = _build_role_check_app(app, required_role)
    sub_app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(sub_app) as client:
        resp = client.get("/probe")
        assert resp.status_code == 403, resp.text


# ── Regression: existing roles still gate correctly ───────────


@pytest.mark.parametrize(
    "required_role_name",
    ["PARENT", "STUDENT", "TEACHER", "ADMIN"],
)
def test_require_role_existing_roles_accept_match(required_role_name, app, db_session):
    """Existing four roles still accept matching users (regression net)."""
    from app.api.deps import get_current_user
    from app.models.user import UserRole

    required_role = UserRole[required_role_name]
    user = _make_user(
        db_session,
        email=f"cmcp_existing_match_{required_role.name.lower()}@test.com",
        role=required_role,
    )

    sub_app = _build_role_check_app(app, required_role)
    sub_app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(sub_app) as client:
        resp = client.get("/probe")
        assert resp.status_code == 200, resp.text


@pytest.mark.parametrize(
    "required_role_name",
    ["PARENT", "STUDENT", "TEACHER", "ADMIN"],
)
def test_require_role_existing_roles_reject_mismatch(required_role_name, app, db_session):
    """Existing four roles still 403 on mismatch (regression net)."""
    from app.api.deps import get_current_user
    from app.models.user import UserRole

    required_role = UserRole[required_role_name]
    # Pick a different role than the required one for the user.
    other_role = (
        UserRole.STUDENT if required_role != UserRole.STUDENT else UserRole.TEACHER
    )
    user = _make_user(
        db_session,
        email=f"cmcp_existing_reject_{required_role.name.lower()}@test.com",
        role=other_role,
    )

    sub_app = _build_role_check_app(app, required_role)
    sub_app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(sub_app) as client:
        resp = client.get("/probe")
        assert resp.status_code == 403, resp.text


# ── has_role helper for the comma-separated multi-role column ─


def test_user_has_role_supports_new_roles_in_multi_role_column(app, db_session):
    """``User.has_role`` works against the multi-role ``roles`` column too."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = User(
        email="cmcp_multi@test.com",
        full_name="Multi Role",
        role=UserRole.PARENT,
        roles="parent,BOARD_ADMIN",
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(user)
    db_session.commit()

    assert user.has_role(UserRole.PARENT) is True
    assert user.has_role(UserRole.BOARD_ADMIN) is True
    assert user.has_role(UserRole.CURRICULUM_ADMIN) is False
