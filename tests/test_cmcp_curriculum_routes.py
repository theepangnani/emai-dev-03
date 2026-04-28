"""Tests for the CB-CMCP-001 M0-B 0B-1 curriculum REST API (#4415).

Covers
------
- ``cmcp.enabled`` flag is seeded as default-OFF.
- Endpoints return 401 when called without a token.
- Endpoints return 403 when the flag is OFF (and short-circuit before any
  DB / model work — verified by leaving the live model unset).
- When the flag is ON and a stub ``CurriculumExpectation`` model is
  monkey-patched into the routes module, the three endpoints serve the
  expected payloads:
    * ``GET /api/curriculum/courses`` — list shape with course code,
      grade level, and expectation count.
    * ``GET /api/curriculum/{course_code}`` — strands grouping.
    * ``GET /api/curriculum/{course_code}/search?q=...`` — keyword
      filter; empty-match returns the course shell with empty strands
      (NOT 404).
- ``GET /api/curriculum/{course_code}`` returns 404 for an unknown
  course code (when the stub model is in place but no rows match).
- When the model is absent (the natural state before stripe 0A-1
  lands) the routes return 503 — the contract that lets this PR be
  independently testable.

The tests inject a tiny in-memory stub model rather than relying on
0A-1's full schema. See ``_StubExpectation`` below — it captures only
the columns the routes touch (``course_code``, ``grade_level``,
``strand``, ``expectation_code``, ``description``, ``expectation_type``)
plus a ``description.ilike`` / ``expectation_code.ilike`` shape that
SQLAlchemy can compile.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, String, Text

from conftest import PASSWORD, _auth


# ── Stub model (mimics 0A-1 columns the routes actually use) ───────────


def _build_stub_model(metadata):
    """Build a tiny ``CurriculumExpectation`` stand-in bound to test metadata.

    Defined as a factory so each test session creates the table fresh
    against its own SQLite file. The columns mirror the names the route
    handlers query (``course_code``, ``grade_level``, ``strand``,
    ``expectation_code``, ``description``, ``expectation_type``).
    """
    from app.db.database import Base

    class StubExpectation(Base):  # type: ignore[misc, valid-type]
        __tablename__ = "cmcp_test_curriculum_expectations"
        __table_args__ = {"extend_existing": True}

        id = Column(Integer, primary_key=True)
        course_code = Column(String(20), index=True, nullable=False)
        grade_level = Column(Integer, nullable=False)
        strand = Column(String(100), nullable=False)
        expectation_code = Column(String(20), nullable=False)
        description = Column(Text, nullable=False)
        expectation_type = Column(String(20), nullable=False)

    return StubExpectation


@pytest.fixture(scope="module")
def stub_expectation_model(app):
    """Create the stub table once per test module and return the class."""
    from app.db.database import Base, engine

    model = _build_stub_model(Base.metadata)
    # Create just this table — calling create_all on the full metadata
    # is harmless because every other table already exists from the
    # session-scoped `app` fixture.
    model.__table__.create(bind=engine, checkfirst=True)
    return model


# ── Flag toggle helpers ────────────────────────────────────────────────


@pytest.fixture()
def cmcp_flag_off(db_session):
    """Ensure ``cmcp.enabled`` exists and is OFF."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "cmcp.enabled")
        .first()
    )
    if flag is not None and flag.enabled is True:
        flag.enabled = False
        db_session.commit()
    return flag


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
    # Reset between tests so the autouse fixture in conftest doesn't see
    # leaks (we don't add cmcp.enabled to the autouse reset list — keep
    # the leak-prevention scoped to this fixture).
    db_session.refresh(flag)
    flag.enabled = False
    db_session.commit()


@pytest.fixture()
def patch_live_model(stub_expectation_model, monkeypatch):
    """Wire the stub model into the curriculum route module.

    The route module captures ``CurriculumExpectation`` at import time
    (or sets it to ``None`` if the import fails). Tests need to swap in
    the stub for the duration of the test; we restore the original
    binding via ``monkeypatch`` to keep tests independent.
    """
    from app.api.routes import curriculum as curriculum_routes

    monkeypatch.setattr(
        curriculum_routes,
        "_EXPECTATION_MODEL",
        stub_expectation_model,
        raising=False,
    )
    return stub_expectation_model


# ── User fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def parent_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = f"cmcp_parent_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name="CMCP Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def student_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = f"cmcp_student_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name="CMCP Student",
        role=UserRole.STUDENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def teacher_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = f"cmcp_teacher_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name="CMCP Teacher",
        role=UserRole.TEACHER,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def seeded_curriculum(db_session, stub_expectation_model):
    """Insert two courses (MTH1W with 3 expectations across 2 strands,
    SNC1D with 1 expectation) and clean up after the test.
    """
    rows = [
        stub_expectation_model(
            course_code="MTH1W",
            grade_level=9,
            strand="Number",
            expectation_code="B1.1",
            description="Demonstrate understanding of fractions",
            expectation_type="overall",
        ),
        stub_expectation_model(
            course_code="MTH1W",
            grade_level=9,
            strand="Number",
            expectation_code="B1.2",
            description="Apply integer operations",
            expectation_type="specific",
        ),
        stub_expectation_model(
            course_code="MTH1W",
            grade_level=9,
            strand="Algebra",
            expectation_code="C1.1",
            description="Solve linear equations using fractions",
            expectation_type="overall",
        ),
        stub_expectation_model(
            course_code="SNC1D",
            grade_level=9,
            strand="Biology",
            expectation_code="B1.1",
            description="Cellular processes and energy transfer",
            expectation_type="overall",
        ),
    ]
    for r in rows:
        db_session.add(r)
    db_session.commit()
    inserted_ids = [r.id for r in rows]
    yield rows
    # Best-effort cleanup so re-runs / sibling tests get a clean slate.
    db_session.query(stub_expectation_model).filter(
        stub_expectation_model.id.in_(inserted_ids)
    ).delete(synchronize_session=False)
    db_session.commit()


# ── Feature-flag seeding ───────────────────────────────────────────────


def test_cmcp_enabled_flag_seeded_default_off(cmcp_flag_off):
    """``seed_features()`` adds ``cmcp.enabled`` with enabled=False."""
    flag = cmcp_flag_off
    assert flag is not None, "cmcp.enabled must be seeded"
    assert flag.enabled is False
    assert flag.variant == "off"
    assert "CB-CMCP-001" in (flag.description or "")


def test_cmcp_constant_matches_seed_key():
    """The ``CMCP_ENABLED`` constant must equal the literal seeded key."""
    from app.services.feature_flag_service import CMCP_ENABLED

    assert CMCP_ENABLED == "cmcp.enabled"


# ── Auth ───────────────────────────────────────────────────────────────


def test_courses_without_auth_returns_401(client):
    resp = client.get("/api/curriculum/courses")
    assert resp.status_code == 401


def test_course_detail_without_auth_returns_401(client):
    resp = client.get("/api/curriculum/MTH1W")
    assert resp.status_code == 401


def test_search_without_auth_returns_401(client):
    resp = client.get("/api/curriculum/MTH1W/search?q=fraction")
    assert resp.status_code == 401


# ── Feature-flag gating (flag OFF) ─────────────────────────────────────


def test_courses_flag_off_returns_403(client, parent_user, cmcp_flag_off):
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/courses", headers=headers)
    assert resp.status_code == 403
    assert "CB-CMCP-001" in resp.json()["detail"]


def test_course_detail_flag_off_returns_403(client, parent_user, cmcp_flag_off):
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/MTH1W", headers=headers)
    assert resp.status_code == 403


def test_search_flag_off_returns_403(client, parent_user, cmcp_flag_off):
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/MTH1W/search?q=fraction", headers=headers)
    assert resp.status_code == 403


# ── 503 when the live model is absent (pre-0A-1 contract) ──────────────


def test_courses_returns_503_when_model_absent(
    client, parent_user, cmcp_flag_on, monkeypatch
):
    """When stripe 0A-1 hasn't merged, the import-guard sets
    ``_EXPECTATION_MODEL`` to ``None`` and every endpoint must return 503
    rather than 500. We simulate the un-merged state by patching it back
    to None for this test.
    """
    from app.api.routes import curriculum as curriculum_routes

    monkeypatch.setattr(
        curriculum_routes, "_EXPECTATION_MODEL", None, raising=False
    )
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/courses", headers=headers)
    assert resp.status_code == 503
    assert "0A-1" in resp.json()["detail"]


def test_course_detail_returns_503_when_model_absent(
    client, parent_user, cmcp_flag_on, monkeypatch
):
    from app.api.routes import curriculum as curriculum_routes

    monkeypatch.setattr(
        curriculum_routes, "_EXPECTATION_MODEL", None, raising=False
    )
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/MTH1W", headers=headers)
    assert resp.status_code == 503


def test_search_returns_503_when_model_absent(
    client, parent_user, cmcp_flag_on, monkeypatch
):
    from app.api.routes import curriculum as curriculum_routes

    monkeypatch.setattr(
        curriculum_routes, "_EXPECTATION_MODEL", None, raising=False
    )
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/MTH1W/search?q=x", headers=headers)
    assert resp.status_code == 503


# ── Happy paths (flag ON + stub model) ─────────────────────────────────


def test_list_courses_returns_seeded_codes(
    client, parent_user, cmcp_flag_on, patch_live_model, seeded_curriculum
):
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/courses", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    codes = {item["course_code"]: item for item in body}
    assert "MTH1W" in codes
    assert "SNC1D" in codes
    assert codes["MTH1W"]["grade_level"] == 9
    assert codes["MTH1W"]["expectation_count"] == 3
    assert codes["SNC1D"]["expectation_count"] == 1


def test_get_course_groups_by_strand(
    client, parent_user, cmcp_flag_on, patch_live_model, seeded_curriculum
):
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/MTH1W", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["course_code"] == "MTH1W"
    assert body["grade_level"] == 9
    strands = {s["name"]: s for s in body["strands"]}
    assert set(strands) == {"Number", "Algebra"}
    number_codes = {e["code"] for e in strands["Number"]["expectations"]}
    assert number_codes == {"B1.1", "B1.2"}
    # ``type`` must be projected from the model's ``expectation_type``.
    types = {e["type"] for e in strands["Number"]["expectations"]}
    assert types == {"overall", "specific"}


def test_get_course_lowercases_input_and_uppercases_output(
    client, parent_user, cmcp_flag_on, patch_live_model, seeded_curriculum
):
    """Course-code casing is normalized (``mth1w`` → ``MTH1W``)."""
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/mth1w", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["course_code"] == "MTH1W"


def test_get_course_returns_404_for_unknown(
    client, parent_user, cmcp_flag_on, patch_live_model, seeded_curriculum
):
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/UNKNOWN1", headers=headers)
    assert resp.status_code == 404
    assert "UNKNOWN1" in resp.json()["detail"]


# ── Search ─────────────────────────────────────────────────────────────


def test_search_filters_by_description(
    client, parent_user, cmcp_flag_on, patch_live_model, seeded_curriculum
):
    headers = _auth(client, parent_user.email)
    resp = client.get(
        "/api/curriculum/MTH1W/search?q=fraction", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["course_code"] == "MTH1W"
    # Two MTH1W rows mention "fraction": B1.1 (Number) and C1.1 (Algebra)
    flat = [
        (s["name"], e["code"])
        for s in body["strands"]
        for e in s["expectations"]
    ]
    assert ("Number", "B1.1") in flat
    assert ("Algebra", "C1.1") in flat
    assert ("Number", "B1.2") not in flat


def test_search_filters_by_expectation_code(
    client, parent_user, cmcp_flag_on, patch_live_model, seeded_curriculum
):
    headers = _auth(client, parent_user.email)
    resp = client.get(
        "/api/curriculum/MTH1W/search?q=B1.2", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    flat = [
        e["code"] for s in body["strands"] for e in s["expectations"]
    ]
    assert flat == ["B1.2"]


def test_search_no_match_returns_empty_strands_not_404(
    client, parent_user, cmcp_flag_on, patch_live_model, seeded_curriculum
):
    """Per #4415 acceptance: search with no matches returns the course
    shell with an empty ``strands`` array — not a 404 — so the UI can
    render a "no matches" state."""
    headers = _auth(client, parent_user.email)
    resp = client.get(
        "/api/curriculum/MTH1W/search?q=zzznotfound", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["course_code"] == "MTH1W"
    assert body["grade_level"] == 9
    assert body["strands"] == []


def test_search_unknown_course_returns_404(
    client, parent_user, cmcp_flag_on, patch_live_model, seeded_curriculum
):
    """When the course itself is unknown, search still 404s — the empty-
    strands-fallback only kicks in for known courses with no matches.
    """
    headers = _auth(client, parent_user.email)
    resp = client.get(
        "/api/curriculum/UNKNOWN1/search?q=anything", headers=headers
    )
    assert resp.status_code == 404


def test_search_empty_query_falls_through_to_full_course(
    client, parent_user, cmcp_flag_on, patch_live_model, seeded_curriculum
):
    """An empty (or whitespace-only) ``q`` should return the full course
    listing — same behavior as the phase-2 source.

    FastAPI rejects ``?q=`` with 422 because of ``min_length=1``; this
    test exercises the in-handler fallback by calling without ``q``.
    """
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/MTH1W/search", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {s["name"] for s in body["strands"]} == {"Number", "Algebra"}


# ── Role-agnostic read access (M0) ─────────────────────────────────────


@pytest.mark.parametrize(
    "user_fixture", ["parent_user", "student_user", "teacher_user"]
)
def test_every_authenticated_role_can_read(
    request, client, cmcp_flag_on, patch_live_model, seeded_curriculum,
    user_fixture,
):
    """M0 scope: any authenticated user can read curriculum data when
    the flag is ON. Restrictive board/admin RBAC arrives in later
    stripes (0A-3 + 0B-3a)."""
    user = request.getfixturevalue(user_fixture)
    headers = _auth(client, user.email)
    resp = client.get("/api/curriculum/courses", headers=headers)
    assert resp.status_code == 200, f"{user_fixture}: {resp.text}"
