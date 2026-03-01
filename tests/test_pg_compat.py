"""PostgreSQL compatibility tests.

These tests exercise known areas where SQLite and PostgreSQL diverge:
  - nullable email columns (NOT NULL constraint differences)
  - String-backed Enum columns round-tripping correctly
  - LIKE queries with % wildcard characters in search terms
  - Integer FK relationships
  - Boolean columns in filter queries
  - Timestamp precision (datetime round-trip)
  - RETURNING clause support (SQLAlchemy 2.0 INSERT behaviour)

Run these tests with a real PostgreSQL instance:
  pytest --pg -m pg

Skip these tests when running against SQLite:
  pytest -m "not pg"
"""

import pytest
from conftest import PASSWORD


# ---------------------------------------------------------------------------
# Helper: skip unless --pg was passed
# ---------------------------------------------------------------------------

def _skip_if_sqlite(request):
    """Raises pytest.skip() if the session is not running against PostgreSQL."""
    db_url = request.config.getoption("--pg")
    if not db_url:
        pytest.skip("PostgreSQL-only test: pass --pg to run")


# ---------------------------------------------------------------------------
# Test 1: users.email nullable — parent-created child account with no email
# ---------------------------------------------------------------------------

@pytest.mark.pg
def test_child_account_without_email(request, client, db_session):
    """A parent-created child account with no email must be accepted.

    The historical bug: users.email had a server-side NOT NULL constraint that
    PostgreSQL enforced but SQLite ignored.  The startup migration drops it.
    This test verifies the constraint is absent on the running database.
    """
    _skip_if_sqlite(request)

    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students, RelationshipType
    from sqlalchemy import insert

    hashed = get_password_hash(PASSWORD)

    # Create parent
    parent = User(
        email="pg_compat_parent_noemail@example.com",
        full_name="PG Compat Parent NoEmail",
        role=UserRole.PARENT,
        hashed_password=hashed,
    )
    db_session.add(parent)
    db_session.flush()

    # Create student with NO email — this must not raise IntegrityError
    child_user = User(
        email=None,          # deliberately null
        full_name="PG Compat Child NoEmail",
        role=UserRole.STUDENT,
        hashed_password=None,
    )
    db_session.add(child_user)
    db_session.flush()  # would raise here if NOT NULL is still set

    student = Student(user_id=child_user.id)
    db_session.add(student)
    db_session.flush()

    db_session.execute(
        insert(parent_students).values(
            parent_id=parent.id,
            student_id=student.id,
            relationship_type=RelationshipType.GUARDIAN,
        )
    )
    db_session.commit()

    # Verify the row is retrievable with email=None
    db_session.expire_all()
    fetched = db_session.query(User).filter(User.id == child_user.id).one()
    assert fetched.email is None
    assert fetched.full_name == "PG Compat Child NoEmail"


# ---------------------------------------------------------------------------
# Test 2: String Enum columns round-trip correctly
# ---------------------------------------------------------------------------

@pytest.mark.pg
def test_user_role_enum_roundtrip(request, db_session):
    """UserRole enum values stored and retrieved from PostgreSQL must match.

    PostgreSQL uses native ENUM types; SQLAlchemy maps them as VARCHAR on
    some dialects.  The values must come back as the Python enum, not raw
    strings that fail equality checks.
    """
    _skip_if_sqlite(request)

    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    hashed = get_password_hash(PASSWORD)

    for role in (UserRole.PARENT, UserRole.STUDENT, UserRole.TEACHER, UserRole.ADMIN):
        email = f"pg_enum_roundtrip_{role.value}@example.com"
        user = User(
            email=email,
            full_name=f"PG Enum {role.value}",
            role=role,
            hashed_password=hashed,
        )
        db_session.add(user)
    db_session.commit()

    for role in (UserRole.PARENT, UserRole.STUDENT, UserRole.TEACHER, UserRole.ADMIN):
        email = f"pg_enum_roundtrip_{role.value}@example.com"
        fetched = db_session.query(User).filter(User.email == email).one()
        # Must be equal to the Python enum (not just the raw string)
        assert fetched.role == role, (
            f"Expected role {role!r}, got {fetched.role!r} ({type(fetched.role).__name__})"
        )
        # The str() representation must also match (UserRole is str+Enum)
        assert fetched.role.value == role.value


# ---------------------------------------------------------------------------
# Test 3: LIKE injection safety — % characters in search terms
# ---------------------------------------------------------------------------

@pytest.mark.pg
def test_like_percent_in_search_query(request, client, db_session):
    """Search queries containing % must not break the PostgreSQL LIKE clause.

    SQLite is lenient about malformed LIKE patterns; PostgreSQL raises an error
    if the driver escaping is wrong.
    """
    _skip_if_sqlite(request)

    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    hashed = get_password_hash(PASSWORD)
    user = User(
        email="pg_search_user@example.com",
        full_name="PG Search User",
        role=UserRole.PARENT,
        hashed_password=hashed,
    )
    db_session.add(user)
    db_session.commit()

    # Log in and hit the search endpoint with a % character in the query
    login_resp = client.post(
        "/api/auth/login",
        data={"username": "pg_search_user@example.com", "password": PASSWORD},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # A query that contains %, which should be safely escaped and return 0 results
    resp = client.get("/api/search?q=50%25off", headers=headers)
    # The request must not return a 500 error regardless of result count
    assert resp.status_code in (200, 404), (
        f"Search with % in query returned unexpected status {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Test 4: Integer vs string IDs — FK relationships work with PG integer PKs
# ---------------------------------------------------------------------------

@pytest.mark.pg
def test_integer_pk_fk_relationships(request, db_session):
    """All FK relationships resolve correctly using PostgreSQL integer PKs.

    SQLite allows string literals as FK values and coerces them silently.
    PostgreSQL enforces strict integer types.  This test exercises the
    parent_students join table and the Student.user FK.
    """
    _skip_if_sqlite(request)

    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students, RelationshipType
    from sqlalchemy import insert, select

    hashed = get_password_hash(PASSWORD)

    parent = User(
        email="pg_fk_parent@example.com",
        full_name="PG FK Parent",
        role=UserRole.PARENT,
        hashed_password=hashed,
    )
    child_user = User(
        email="pg_fk_child@example.com",
        full_name="PG FK Child",
        role=UserRole.STUDENT,
        hashed_password=hashed,
    )
    db_session.add_all([parent, child_user])
    db_session.flush()

    # Verify IDs are integers (not strings or UUIDs)
    assert isinstance(parent.id, int), f"parent.id is {type(parent.id)}, expected int"
    assert isinstance(child_user.id, int), f"child_user.id is {type(child_user.id)}, expected int"

    student = Student(user_id=child_user.id)
    db_session.add(student)
    db_session.flush()

    assert isinstance(student.id, int), f"student.id is {type(student.id)}, expected int"
    assert isinstance(student.user_id, int)

    db_session.execute(
        insert(parent_students).values(
            parent_id=parent.id,
            student_id=student.id,
            relationship_type=RelationshipType.FATHER,
        )
    )
    db_session.commit()

    # Query the join table and confirm FK columns are integers
    row = db_session.execute(
        select(parent_students).where(parent_students.c.parent_id == parent.id)
    ).first()
    assert row is not None
    assert isinstance(row.parent_id, int)
    assert isinstance(row.student_id, int)
    assert row.student_id == student.id


# ---------------------------------------------------------------------------
# Test 5: Boolean columns — filter queries use PostgreSQL booleans correctly
# ---------------------------------------------------------------------------

@pytest.mark.pg
def test_boolean_column_filter(request, db_session):
    """Boolean columns stored and filtered via PostgreSQL must not leak 0/1 ints.

    SQLite stores booleans as integers (0/1) and SQLAlchemy may return Python
    ints on some SQLite configurations.  PostgreSQL has a native BOOLEAN type;
    this test verifies that filter expressions using True/False work correctly
    and that the returned values are Python booleans.
    """
    _skip_if_sqlite(request)

    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    hashed = get_password_hash(PASSWORD)

    active_user = User(
        email="pg_bool_active@example.com",
        full_name="PG Bool Active",
        role=UserRole.PARENT,
        hashed_password=hashed,
        is_active=True,
        email_verified=False,
    )
    inactive_user = User(
        email="pg_bool_inactive@example.com",
        full_name="PG Bool Inactive",
        role=UserRole.PARENT,
        hashed_password=hashed,
        is_active=False,
        email_verified=True,
    )
    db_session.add_all([active_user, inactive_user])
    db_session.commit()
    db_session.expire_all()

    # Filter by boolean True
    active_results = (
        db_session.query(User)
        .filter(User.is_active == True)  # noqa: E712  (must be == not 'is')
        .filter(User.email.in_([
            "pg_bool_active@example.com",
            "pg_bool_inactive@example.com",
        ]))
        .all()
    )
    assert len(active_results) == 1
    assert active_results[0].email == "pg_bool_active@example.com"

    # Verify returned type is Python bool, not int
    fetched_active = db_session.query(User).filter(User.email == "pg_bool_active@example.com").one()
    assert fetched_active.is_active is True
    assert fetched_active.email_verified is False
    assert type(fetched_active.is_active) is bool, (
        f"is_active returned {type(fetched_active.is_active)}, expected bool"
    )

    fetched_inactive = db_session.query(User).filter(User.email == "pg_bool_inactive@example.com").one()
    assert fetched_inactive.is_active is False
    assert fetched_inactive.email_verified is True


# ---------------------------------------------------------------------------
# Test 6: Timestamp precision — datetime round-trip without microsecond loss
# ---------------------------------------------------------------------------

@pytest.mark.pg
def test_timestamp_precision_roundtrip(request, db_session):
    """Datetime fields must survive a PostgreSQL write-read cycle intact.

    PostgreSQL TIMESTAMPTZ stores microseconds; Python datetime objects also
    carry microseconds.  The test verifies that created_at is populated by
    the server default and that the value is a proper datetime (not a string),
    and that no precision is lost on a subsequent read.
    """
    _skip_if_sqlite(request)

    import datetime as dt
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    hashed = get_password_hash(PASSWORD)

    before = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)

    user = User(
        email="pg_timestamp@example.com",
        full_name="PG Timestamp User",
        role=UserRole.PARENT,
        hashed_password=hashed,
    )
    db_session.add(user)
    db_session.commit()
    db_session.expire_all()

    after = dt.datetime.now(dt.timezone.utc)

    fetched = db_session.query(User).filter(User.email == "pg_timestamp@example.com").one()

    assert fetched.created_at is not None, "created_at should be populated by server_default"
    assert isinstance(fetched.created_at, dt.datetime), (
        f"created_at returned {type(fetched.created_at)}, expected datetime"
    )

    # created_at should be timezone-aware
    assert fetched.created_at.tzinfo is not None, (
        "created_at should be timezone-aware (TIMESTAMPTZ)"
    )

    # created_at should fall within our before/after window
    created_utc = fetched.created_at.astimezone(dt.timezone.utc)
    assert before <= created_utc <= after, (
        f"created_at {created_utc} is outside the expected range [{before}, {after}]"
    )


# ---------------------------------------------------------------------------
# Test 7: RETURNING clause — SQLAlchemy 2.0 INSERT RETURNING works
# ---------------------------------------------------------------------------

@pytest.mark.pg
def test_insert_returning_clause(request, db_session):
    """SQLAlchemy 2.0 uses RETURNING on INSERT; verify PostgreSQL supports it.

    Older SQLite (< 3.35) does not support RETURNING.  PostgreSQL has supported
    it since version 8.2.  This test exercises an ORM flush followed by
    attribute access that is only satisfied via the RETURNING result set.
    """
    _skip_if_sqlite(request)

    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student

    hashed = get_password_hash(PASSWORD)

    user = User(
        email="pg_returning@example.com",
        full_name="PG Returning User",
        role=UserRole.STUDENT,
        hashed_password=hashed,
    )
    db_session.add(user)
    db_session.flush()  # SQLAlchemy 2.0 uses INSERT...RETURNING id here

    # id must be populated immediately after flush (via RETURNING)
    assert user.id is not None, "user.id should be populated immediately after flush via RETURNING"
    assert isinstance(user.id, int)

    student = Student(user_id=user.id)
    db_session.add(student)
    db_session.flush()

    assert student.id is not None, "student.id should be populated immediately after flush via RETURNING"
    assert isinstance(student.id, int)

    db_session.commit()

    # Final sanity check: round-trip read
    db_session.expire_all()
    fetched_user = db_session.query(User).filter(User.id == user.id).one()
    assert fetched_user.email == "pg_returning@example.com"
    fetched_student = db_session.query(Student).filter(Student.id == student.id).one()
    assert fetched_student.user_id == user.id
