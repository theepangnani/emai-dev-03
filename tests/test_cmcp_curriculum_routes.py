"""Tests for the CB-CMCP-001 M0-B 0B-1 curriculum REST API (#4415, #4426).

After the schema bridge in #4426, these tests run against the real
normalized CEG schema (``CEGSubject`` + ``CEGStrand`` + ``CEGExpectation``
+ ``CurriculumVersion`` from stripe 0A-1) — no stub model.

Covers
------
- ``cmcp.enabled`` flag is seeded as default-OFF.
- Endpoints return 401 when called without a token.
- Endpoints return 403 when the flag is OFF (and short-circuit before any
  DB work — verified by leaving the seed data empty).
- When the flag is ON and CEG rows are seeded, the three endpoints
  serve the expected payloads:
    * ``GET /api/curriculum/courses`` — list shape with subject code,
      grade level, and expectation count.
    * ``GET /api/curriculum/{course_code}`` — strands grouping (where
      ``course_code`` resolves to ``CEGSubject.code``).
    * ``GET /api/curriculum/{course_code}/search?q=...`` — keyword
      filter; empty-match returns the course shell with empty strands
      (NOT 404).
- ``GET /api/curriculum/{course_code}`` returns 404 for an unknown
  subject code.
- JOIN-related edge cases: subject with multiple grades returns the
  max grade; subject with no expectations is omitted from /courses;
  multiple strands group correctly under one subject.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


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


# ── CEG seed fixtures ──────────────────────────────────────────────────


@pytest.fixture()
def seeded_curriculum(db_session):
    """Seed a small CEG corpus that covers the three endpoints' query paths.

    Layout (subject codes use a uuid suffix to keep this fixture isolated
    from sibling fixtures in other test files — ``test_cmcp_ceg_schema.py``
    seeds ``MATH``/``SCI``/``LANG`` etc. on the same session-scoped DB
    and never cleans up)::

        MATH-XXXX (subject "Mathematics")
            B "Number Sense" (strand)
                B1.1 — overall — "Demonstrate understanding of fractions" (G9)
                B1.2 — specific — "Apply integer operations" (G9)
            C "Algebra" (strand)
                C1.1 — overall — "Solve linear equations using fractions" (G9)
        SCI-XXXX (subject "Science")
            A "Biology" (strand)
                A1.1 — overall — "Cellular processes and energy transfer" (G9)

    Yields a dict with the resolved subject codes (so test bodies can use
    them in URLs) plus the seeded model instances. Cleans up everything
    on teardown (subjects included — they're newly created per fixture
    invocation so the cleanup is unambiguous).
    """
    from app.models.curriculum import (
        CEGExpectation,
        CEGStrand,
        CEGSubject,
        CurriculumVersion,
        EXPECTATION_TYPE_OVERALL,
        EXPECTATION_TYPE_SPECIFIC,
    )

    # Use unique-per-test subject codes + version slugs so we don't
    # collide with other test files' seeds (the DB is session-scoped).
    # The fixture exposes the resolved codes via the yielded dict —
    # tests pull them from there rather than hard-coding "MATH"/"SCI".
    suffix = uuid4().hex[:6].upper()
    math_code = f"M{suffix}"
    sci_code = f"S{suffix}"
    version_slug = f"test-{uuid4().hex[:6]}"

    math = CEGSubject(code=math_code, name="Mathematics")
    sci = CEGSubject(code=sci_code, name="Science")
    db_session.add_all([math, sci])
    db_session.flush()

    math_b = CEGStrand(subject_id=math.id, code="B", name="Number Sense")
    math_c = CEGStrand(subject_id=math.id, code="C", name="Algebra")
    sci_a = CEGStrand(subject_id=sci.id, code="A", name="Biology")
    db_session.add_all([math_b, math_c, sci_a])
    db_session.flush()

    math_v = CurriculumVersion(
        subject_id=math.id,
        grade=9,
        version=version_slug,
        change_severity=None,
        notes="test seed",
    )
    sci_v = CurriculumVersion(
        subject_id=sci.id,
        grade=9,
        version=version_slug,
        change_severity=None,
        notes="test seed",
    )
    db_session.add_all([math_v, sci_v])
    db_session.flush()

    expectations = [
        CEGExpectation(
            ministry_code="B1.1",
            cb_code=f"CB-G9-{math_code}-B1-OE1",
            subject_id=math.id,
            strand_id=math_b.id,
            grade=9,
            expectation_type=EXPECTATION_TYPE_OVERALL,
            description="Demonstrate understanding of fractions",
            curriculum_version_id=math_v.id,
        ),
        CEGExpectation(
            ministry_code="B1.2",
            cb_code=f"CB-G9-{math_code}-B1-SE2",
            subject_id=math.id,
            strand_id=math_b.id,
            grade=9,
            expectation_type=EXPECTATION_TYPE_SPECIFIC,
            description="Apply integer operations",
            curriculum_version_id=math_v.id,
        ),
        CEGExpectation(
            ministry_code="C1.1",
            cb_code=f"CB-G9-{math_code}-C1-OE1",
            subject_id=math.id,
            strand_id=math_c.id,
            grade=9,
            expectation_type=EXPECTATION_TYPE_OVERALL,
            description="Solve linear equations using fractions",
            curriculum_version_id=math_v.id,
        ),
        CEGExpectation(
            ministry_code="A1.1",
            cb_code=f"CB-G9-{sci_code}-A1-OE1",
            subject_id=sci.id,
            strand_id=sci_a.id,
            grade=9,
            expectation_type=EXPECTATION_TYPE_OVERALL,
            description="Cellular processes and energy transfer",
            curriculum_version_id=sci_v.id,
        ),
    ]
    for r in expectations:
        db_session.add(r)
    db_session.commit()

    expectation_ids = [e.id for e in expectations]
    strand_ids = [math_b.id, math_c.id, sci_a.id]
    version_ids = [math_v.id, sci_v.id]
    subject_ids = [math.id, sci.id]

    yield {
        "math_code": math_code,
        "sci_code": sci_code,
        "subjects": {"MATH": math, "SCI": sci},
        "expectations": expectations,
    }

    # Cleanup. Order matters (FK chain): expectations → versions →
    # strands → subjects.
    db_session.query(CEGExpectation).filter(
        CEGExpectation.id.in_(expectation_ids)
    ).delete(synchronize_session=False)
    db_session.query(CurriculumVersion).filter(
        CurriculumVersion.id.in_(version_ids)
    ).delete(synchronize_session=False)
    db_session.query(CEGStrand).filter(
        CEGStrand.id.in_(strand_ids)
    ).delete(synchronize_session=False)
    db_session.query(CEGSubject).filter(
        CEGSubject.id.in_(subject_ids)
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
    resp = client.get("/api/curriculum/MATH")
    assert resp.status_code == 401


def test_search_without_auth_returns_401(client):
    resp = client.get("/api/curriculum/MATH/search?q=fraction")
    assert resp.status_code == 401


# ── Feature-flag gating (flag OFF) ─────────────────────────────────────


def test_courses_flag_off_returns_403(client, parent_user, cmcp_flag_off):
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/courses", headers=headers)
    assert resp.status_code == 403
    assert "CB-CMCP-001" in resp.json()["detail"]


def test_course_detail_flag_off_returns_403(client, parent_user, cmcp_flag_off):
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/MATH", headers=headers)
    assert resp.status_code == 403


def test_search_flag_off_returns_403(client, parent_user, cmcp_flag_off):
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/MATH/search?q=fraction", headers=headers)
    assert resp.status_code == 403


# ── Happy paths (flag ON + seeded CEG corpus) ──────────────────────────


def test_list_courses_returns_seeded_codes(
    client, parent_user, cmcp_flag_on, seeded_curriculum
):
    math_code = seeded_curriculum["math_code"]
    sci_code = seeded_curriculum["sci_code"]
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/courses", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    codes = {item["course_code"]: item for item in body}
    assert math_code in codes
    assert sci_code in codes
    assert codes[math_code]["grade_level"] == 9
    assert codes[math_code]["expectation_count"] == 3
    assert codes[sci_code]["expectation_count"] == 1


def test_get_course_groups_by_strand(
    client, parent_user, cmcp_flag_on, seeded_curriculum
):
    math_code = seeded_curriculum["math_code"]
    headers = _auth(client, parent_user.email)
    resp = client.get(f"/api/curriculum/{math_code}", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["course_code"] == math_code
    assert body["grade_level"] == 9
    strands = {s["name"]: s for s in body["strands"]}
    assert set(strands) == {"Number Sense", "Algebra"}
    number_codes = {e["code"] for e in strands["Number Sense"]["expectations"]}
    assert number_codes == {"B1.1", "B1.2"}
    # ``type`` must be projected from the model's ``expectation_type``.
    types = {e["type"] for e in strands["Number Sense"]["expectations"]}
    assert types == {"overall", "specific"}


def test_get_course_lowercases_input_and_uppercases_output(
    client, parent_user, cmcp_flag_on, seeded_curriculum
):
    """Course-code casing is normalized (``mXXXXXX`` → ``MXXXXXX``)."""
    math_code = seeded_curriculum["math_code"]
    headers = _auth(client, parent_user.email)
    resp = client.get(f"/api/curriculum/{math_code.lower()}", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["course_code"] == math_code


def test_get_course_returns_404_for_unknown(
    client, parent_user, cmcp_flag_on, seeded_curriculum
):
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/curriculum/UNKNOWN1", headers=headers)
    assert resp.status_code == 404
    assert "UNKNOWN1" in resp.json()["detail"]


# ── Search ─────────────────────────────────────────────────────────────


def test_search_filters_by_description(
    client, parent_user, cmcp_flag_on, seeded_curriculum
):
    math_code = seeded_curriculum["math_code"]
    headers = _auth(client, parent_user.email)
    resp = client.get(
        f"/api/curriculum/{math_code}/search?q=fraction", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["course_code"] == math_code
    # Two MATH rows mention "fraction": B1.1 (Number Sense) and C1.1 (Algebra)
    flat = [
        (s["name"], e["code"])
        for s in body["strands"]
        for e in s["expectations"]
    ]
    assert ("Number Sense", "B1.1") in flat
    assert ("Algebra", "C1.1") in flat
    assert ("Number Sense", "B1.2") not in flat


def test_search_filters_by_ministry_code(
    client, parent_user, cmcp_flag_on, seeded_curriculum
):
    """Search matches against the ministry code (e.g., ``B1.2``)."""
    math_code = seeded_curriculum["math_code"]
    headers = _auth(client, parent_user.email)
    resp = client.get(
        f"/api/curriculum/{math_code}/search?q=B1.2", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    flat = [
        e["code"] for s in body["strands"] for e in s["expectations"]
    ]
    assert flat == ["B1.2"]


def test_search_no_match_returns_empty_strands_not_404(
    client, parent_user, cmcp_flag_on, seeded_curriculum
):
    """Per #4415 acceptance: search with no matches returns the course
    shell with an empty ``strands`` array — not a 404 — so the UI can
    render a "no matches" state."""
    math_code = seeded_curriculum["math_code"]
    headers = _auth(client, parent_user.email)
    resp = client.get(
        f"/api/curriculum/{math_code}/search?q=zzznotfound", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["course_code"] == math_code
    assert body["grade_level"] == 9
    assert body["strands"] == []


def test_search_unknown_course_returns_404(
    client, parent_user, cmcp_flag_on, seeded_curriculum
):
    """When the subject itself is unknown, search still 404s — the empty-
    strands-fallback only kicks in for known subjects with no matches.
    """
    headers = _auth(client, parent_user.email)
    resp = client.get(
        "/api/curriculum/UNKNOWN1/search?q=anything", headers=headers
    )
    assert resp.status_code == 404


def test_search_empty_query_falls_through_to_full_course(
    client, parent_user, cmcp_flag_on, seeded_curriculum
):
    """An empty (or whitespace-only) ``q`` should return the full course
    listing — same behavior as the phase-2 source.

    FastAPI rejects ``?q=`` with 422 because of ``min_length=1``; this
    test exercises the in-handler fallback by calling without ``q``.
    """
    math_code = seeded_curriculum["math_code"]
    headers = _auth(client, parent_user.email)
    resp = client.get(f"/api/curriculum/{math_code}/search", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {s["name"] for s in body["strands"]} == {"Number Sense", "Algebra"}


# ── JOIN edge cases (#4426) ────────────────────────────────────────────


def test_courses_omits_subjects_with_no_expectations(
    client, parent_user, cmcp_flag_on, seeded_curriculum, db_session
):
    """A ``CEGSubject`` row with no ``CEGExpectation`` children must NOT
    appear in ``GET /courses`` — the inner JOIN drops it.
    """
    from app.models.curriculum import CEGSubject

    empty_code = f"EMPTY{uuid4().hex[:4].upper()}"
    empty_subject = CEGSubject(code=empty_code, name="Empty subject")
    db_session.add(empty_subject)
    db_session.commit()
    try:
        headers = _auth(client, parent_user.email)
        resp = client.get("/api/curriculum/courses", headers=headers)
        assert resp.status_code == 200, resp.text
        codes = [item["course_code"] for item in resp.json()]
        assert empty_code not in codes
    finally:
        db_session.delete(empty_subject)
        db_session.commit()


def test_get_course_with_multiple_grades_returns_max_grade(
    client, parent_user, cmcp_flag_on, seeded_curriculum, db_session
):
    """A subject with expectations across multiple grades reports the
    max grade (deterministic per the API-contract decision in #4426).
    """
    from app.models.curriculum import (
        CEGExpectation,
        CEGStrand,
        CurriculumVersion,
        EXPECTATION_TYPE_OVERALL,
    )

    math = seeded_curriculum["subjects"]["MATH"]
    math_code = seeded_curriculum["math_code"]

    # Add a G10 expectation under a new strand + version pair.
    extra_strand = CEGStrand(
        subject_id=math.id, code="D", name="Data Management"
    )
    db_session.add(extra_strand)
    db_session.flush()
    extra_version = CurriculumVersion(
        subject_id=math.id,
        grade=10,
        version=f"test-extra-{uuid4().hex[:6]}",
        change_severity=None,
        notes="test seed (G10)",
    )
    db_session.add(extra_version)
    db_session.flush()
    extra_exp = CEGExpectation(
        ministry_code="D1.1",
        cb_code=f"CB-G10-{math_code}-D1-OE1",
        subject_id=math.id,
        strand_id=extra_strand.id,
        grade=10,
        expectation_type=EXPECTATION_TYPE_OVERALL,
        description="Interpret data displays",
        curriculum_version_id=extra_version.id,
    )
    db_session.add(extra_exp)
    db_session.commit()
    try:
        headers = _auth(client, parent_user.email)
        resp = client.get(f"/api/curriculum/{math_code}", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["grade_level"] == 10
        # And the new strand + expectation appear in the response.
        strands = {s["name"]: s for s in body["strands"]}
        assert "Data Management" in strands
        codes = {
            e["code"] for e in strands["Data Management"]["expectations"]
        }
        assert "D1.1" in codes
    finally:
        db_session.delete(extra_exp)
        db_session.delete(extra_version)
        db_session.delete(extra_strand)
        db_session.commit()


def test_get_course_groups_strands_correctly_under_one_subject(
    client, parent_user, cmcp_flag_on, seeded_curriculum
):
    """The seeded MATH subject has two strands (Number Sense + Algebra);
    each must contain exactly the expectations seeded under it (JOIN
    correctness check).
    """
    math_code = seeded_curriculum["math_code"]
    headers = _auth(client, parent_user.email)
    resp = client.get(f"/api/curriculum/{math_code}", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    strands = {s["name"]: s for s in body["strands"]}

    number_codes = sorted(
        e["code"] for e in strands["Number Sense"]["expectations"]
    )
    algebra_codes = sorted(
        e["code"] for e in strands["Algebra"]["expectations"]
    )
    assert number_codes == ["B1.1", "B1.2"]
    assert algebra_codes == ["C1.1"]


# ── Role-agnostic read access (M0) ─────────────────────────────────────


@pytest.mark.parametrize(
    "user_fixture", ["parent_user", "student_user", "teacher_user"]
)
def test_every_authenticated_role_can_read(
    request, client, cmcp_flag_on, seeded_curriculum, user_fixture,
):
    """M0 scope: any authenticated user can read curriculum data when
    the flag is ON. Restrictive board/admin RBAC arrives in later
    stripes (0A-3 + 0B-3a)."""
    user = request.getfixturevalue(user_fixture)
    headers = _auth(client, user.email)
    resp = client.get("/api/curriculum/courses", headers=headers)
    assert resp.status_code == 200, f"{user_fixture}: {resp.text}"
