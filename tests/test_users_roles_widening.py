"""CB-CMCP-001 S1 (#4452) — ``users.roles`` String(50) -> String(120).

Verifies that:
- The ``users.roles`` column is wide enough to store the full 6-role
  comma-separated string ``"parent,student,teacher,admin,BOARD_ADMIN,
  CURRICULUM_ADMIN"`` (57 chars) without silent truncation.
- The model column metadata reports the new String(120) length.
- Round-tripping a User with ``set_roles([...all six...])`` re-reads the
  exact same string back, and ``has_role`` / ``get_roles_list`` see all six.

Implementation note: model imports happen *inside* each test function rather
than at module top, matching the existing CMCP test pattern (the
session-scoped ``app`` fixture reloads ``app.models`` so module-top imports
would resolve against a stale class registry).

PG-side correctness is covered by the idempotent ALTER TABLE in ``main.py``
(advisory-lock 4448). SQLite stores VARCHAR as TEXT internally and ignores
length, so a too-short DECLARED length never truncates on SQLite — but the
schema rebuilt by ``Base.metadata.create_all`` already reflects the new
length, so the column metadata assertion still proves the model widened.
"""


def test_users_roles_column_metadata_is_120(app):
    """SQLAlchemy column metadata must report the new 120-char length."""
    from app.models.user import User

    col = User.__table__.c.roles
    assert col.type.length == 120, (
        f"Expected users.roles to be String(120) after #4452 widen, "
        f"got String({col.type.length})"
    )


def test_user_roundtrip_with_all_six_roles(db_session):
    """A User with all 6 roles assigned round-trips without truncation."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    all_six_roles = [
        UserRole.PARENT,
        UserRole.STUDENT,
        UserRole.TEACHER,
        UserRole.ADMIN,
        UserRole.BOARD_ADMIN,
        UserRole.CURRICULUM_ADMIN,
    ]
    expected_roles_str = "parent,student,teacher,admin,BOARD_ADMIN,CURRICULUM_ADMIN"
    # Sanity: this is the full 6-role comma-separated string from the
    # acceptance criteria, exactly 57 chars (over the old 50-char ceiling).
    assert len(expected_roles_str) == 57

    email = "cmcp_widen_all_six@test.com"
    user = User(
        email=email,
        full_name="All Six Roles",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
    )
    user.set_roles(all_six_roles)
    # set_roles writes the exact comma-separated string we expect.
    assert user.roles == expected_roles_str

    db_session.add(user)
    db_session.commit()

    # Re-read from DB (separate query) to prove no truncation occurred.
    db_session.expire_all()
    refetched = db_session.query(User).filter(User.email == email).one()
    assert refetched.roles == expected_roles_str
    assert len(refetched.roles) == 57

    # has_role sees all six.
    for role in all_six_roles:
        assert refetched.has_role(role) is True, (
            f"has_role({role.name}) returned False after round-trip"
        )

    # get_roles_list returns all six in order.
    assert refetched.get_roles_list() == all_six_roles


def test_user_roundtrip_with_new_admin_roles_only(db_session):
    """Round-trip with only BOARD_ADMIN + CURRICULUM_ADMIN (longest names)."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    new_admin_roles = [UserRole.BOARD_ADMIN, UserRole.CURRICULUM_ADMIN]
    expected_roles_str = "BOARD_ADMIN,CURRICULUM_ADMIN"

    email = "cmcp_widen_new_admins@test.com"
    user = User(
        email=email,
        full_name="New Admin Roles",
        role=UserRole.BOARD_ADMIN,
        hashed_password=get_password_hash("Password123!"),
    )
    user.set_roles(new_admin_roles)
    assert user.roles == expected_roles_str

    db_session.add(user)
    db_session.commit()

    db_session.expire_all()
    refetched = db_session.query(User).filter(User.email == email).one()
    assert refetched.roles == expected_roles_str
    assert refetched.has_role(UserRole.BOARD_ADMIN) is True
    assert refetched.has_role(UserRole.CURRICULUM_ADMIN) is True
    assert refetched.has_role(UserRole.PARENT) is False
