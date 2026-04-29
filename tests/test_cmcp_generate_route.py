"""Tests for the CB-CMCP-001 M1-A 1A-2 generation route (#4471).

Five required scenarios per the issue body:

1. ``cmcp.enabled`` flag OFF → 403.
2. Unauthenticated request → 401.
3. Happy path → 200, returns prompt + SE codes.
4. Persona auto-derivation from ``current_user.role``
   (parent → "parent", student → "student", teacher → "teacher").
5. Validation: invalid ``content_type`` → 422.

Plus a couple of guards that fall out of the implementation cheaply:
- Unknown ``subject_code`` → 422.
- Unknown ``strand_code`` for a known subject → 422.
- Empty CEG result for the resolved (subject, strand, grade) → 422.
- ``target_persona`` override beats the role-derived default.

No real Claude/OpenAI calls — the engine is pure prompt composition,
so this stripe never crosses an external API.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── Flag fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def cmcp_flag_off(db_session):
    """Force ``cmcp.enabled`` OFF for the test."""
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
    db_session.refresh(flag)
    flag.enabled = False
    db_session.commit()


# ── User fixtures ──────────────────────────────────────────────────────


def _make_user(db_session, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"cmcpgen_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPGen {role.value}",
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


# ── CEG seed ───────────────────────────────────────────────────────────


@pytest.fixture()
def seeded_cmcp_curriculum(db_session):
    """Seed a Grade-7 ``MATH-XXXX`` slice with one OE + two SEs.

    Matches the layout used by ``test_cmcp_guardrail_engine.py`` but
    with a uuid-suffixed subject code so this test file's seed doesn't
    collide with sibling fixtures on the session-scoped DB.
    """
    from app.models.curriculum import (
        CEGExpectation,
        CEGStrand,
        CEGSubject,
        CurriculumVersion,
        EXPECTATION_TYPE_OVERALL,
        EXPECTATION_TYPE_SPECIFIC,
    )

    suffix = uuid4().hex[:6].upper()
    subject_code = f"M{suffix}"
    strand_code = "B"
    version_slug = f"test-gen-{uuid4().hex[:6]}"

    subject = CEGSubject(code=subject_code, name="Mathematics")
    db_session.add(subject)
    db_session.flush()

    strand = CEGStrand(
        subject_id=subject.id, code=strand_code, name="Number Sense"
    )
    db_session.add(strand)
    db_session.flush()

    version = CurriculumVersion(
        subject_id=subject.id,
        grade=7,
        version=version_slug,
        change_severity=None,
        notes="test seed",
    )
    db_session.add(version)
    db_session.flush()

    oe = CEGExpectation(
        ministry_code="B2",
        cb_code=f"CB-G7-{subject_code}-B2",
        subject_id=subject.id,
        strand_id=strand.id,
        grade=7,
        expectation_type=EXPECTATION_TYPE_OVERALL,
        description="Demonstrate understanding of fractions, decimals, percents.",
        curriculum_version_id=version.id,
    )
    db_session.add(oe)
    db_session.flush()

    se1 = CEGExpectation(
        ministry_code="B2.1",
        cb_code=f"CB-G7-{subject_code}-B2-SE1",
        subject_id=subject.id,
        strand_id=strand.id,
        grade=7,
        expectation_type=EXPECTATION_TYPE_SPECIFIC,
        parent_oe_id=oe.id,
        description="Add and subtract fractions with unlike denominators.",
        curriculum_version_id=version.id,
    )
    se2 = CEGExpectation(
        ministry_code="B2.2",
        cb_code=f"CB-G7-{subject_code}-B2-SE2",
        subject_id=subject.id,
        strand_id=strand.id,
        grade=7,
        expectation_type=EXPECTATION_TYPE_SPECIFIC,
        parent_oe_id=oe.id,
        description="Multiply and divide decimal numbers to thousandths.",
        curriculum_version_id=version.id,
    )
    db_session.add_all([se1, se2])
    db_session.commit()

    expectation_ids = [oe.id, se1.id, se2.id]
    yield {
        "subject_code": subject_code,
        "strand_code": strand_code,
        "subject": subject,
        "strand": strand,
        "version": version,
    }

    # Cleanup. Order matters — expectations → version → strand → subject.
    from app.models.curriculum import CEGExpectation as _E

    db_session.query(_E).filter(_E.id.in_(expectation_ids)).delete(
        synchronize_session=False
    )
    db_session.query(CurriculumVersion).filter(
        CurriculumVersion.id == version.id
    ).delete(synchronize_session=False)
    db_session.query(CEGStrand).filter(
        CEGStrand.id == strand.id
    ).delete(synchronize_session=False)
    db_session.query(CEGSubject).filter(
        CEGSubject.id == subject.id
    ).delete(synchronize_session=False)
    db_session.commit()


def _payload(seeded, **overrides):
    """Build a baseline ``CMCPGenerateRequest`` body for the seeded subject."""
    body = {
        "grade": 7,
        "subject_code": seeded["subject_code"],
        "strand_code": seeded["strand_code"],
        "content_type": "QUIZ",
        "difficulty": "GRADE_LEVEL",
    }
    body.update(overrides)
    return body


# ─────────────────────────────────────────────────────────────────────
# Scenario 1 — flag OFF → 403
# ─────────────────────────────────────────────────────────────────────


def test_generate_flag_off_returns_403(
    client, parent_user, cmcp_flag_off, seeded_cmcp_curriculum
):
    headers = _auth(client, parent_user.email)
    resp = client.post(
        "/api/cmcp/generate",
        json=_payload(seeded_cmcp_curriculum),
        headers=headers,
    )
    assert resp.status_code == 403
    assert "CB-CMCP-001" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────────────
# Scenario 2 — unauthenticated → 401
# ─────────────────────────────────────────────────────────────────────


def test_generate_without_auth_returns_401(
    client, cmcp_flag_on, seeded_cmcp_curriculum
):
    """No Authorization header → 401, regardless of flag state."""
    resp = client.post(
        "/api/cmcp/generate",
        json=_payload(seeded_cmcp_curriculum),
    )
    assert resp.status_code == 401


def test_generate_without_auth_returns_401_even_when_flag_off(
    client, cmcp_flag_off, seeded_cmcp_curriculum
):
    """Unauth check fires *before* the flag check — flag-state probing
    without a valid token is not possible. Mutation-test guard for the
    ``require_cmcp_enabled`` ordering: if the flag check ran first this
    would return 403 instead of 401.
    """
    resp = client.post(
        "/api/cmcp/generate",
        json=_payload(seeded_cmcp_curriculum),
    )
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────
# Scenario 3 — happy path
# ─────────────────────────────────────────────────────────────────────


def test_generate_happy_path_returns_prompt_and_se_codes(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    headers = _auth(client, parent_user.email)
    resp = client.post(
        "/api/cmcp/generate",
        json=_payload(seeded_cmcp_curriculum),
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Response shape (matches GenerationPreview). M3α prequel (#4575)
    # adds the persisted ``id`` field.
    assert set(body.keys()) == {
        "id",
        "prompt",
        "se_codes_targeted",
        "voice_module_id",
        "voice_module_hash",
        "persona",
    }

    # SE codes from the seeded slice.
    assert body["se_codes_targeted"] == ["B2.1", "B2.2"]

    # Prompt contains the curriculum guardrail block + persona block.
    assert "[CURRICULUM_GUARDRAIL]" in body["prompt"]
    assert "[PERSONA]" in body["prompt"]
    # SE ministry codes appear in the prompt (load-bearing for
    # downstream Claude calls).
    assert "B2.1" in body["prompt"]
    assert "B2.2" in body["prompt"]

    # 1C-2 wires the voice registry — parent persona resolves to
    # parent_coach_v1 and the hash is stamped from VoiceRegistry.
    assert body["voice_module_id"] == "parent_coach_v1"
    assert body["voice_module_hash"] is not None
    assert len(body["voice_module_hash"]) == 64  # SHA-256 hex digest


def test_generate_subject_code_is_case_insensitive(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Subject lookup uppercases via ``func.upper`` — a lowercase
    ``subject_code`` resolves the same row. Mutation-test guard for a
    naive ``CEGSubject.code == subject_code`` regression.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum)
    body["subject_code"] = body["subject_code"].lower()
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 200, resp.text


def test_generate_strand_code_is_case_insensitive(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Strand lookup is also case-insensitive on the strand's
    ministry code (``B`` vs ``b``).
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, strand_code="b")
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 200, resp.text


# ─────────────────────────────────────────────────────────────────────
# Scenario 4 — persona auto-derivation from current_user.role
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "user_fixture, expected_persona, marker",
    [
        ("parent_user", "parent", "PARENT"),
        ("student_user", "student", "STUDENT"),
        ("teacher_user", "teacher", "TEACHER"),
    ],
)
def test_generate_derives_persona_from_role(
    request,
    client,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
    user_fixture,
    expected_persona,
    marker,
):
    """Per #4471 acceptance: when ``target_persona`` is omitted, the
    route derives it from ``current_user.role``. Mutation-test guard for
    ``_derive_persona``: revert the role → persona map and one of the
    three parametrized variants will fail.
    """
    user = request.getfixturevalue(user_fixture)
    headers = _auth(client, user.email)
    body = _payload(seeded_cmcp_curriculum)
    # Don't set target_persona — exercise the auto-derivation path.
    assert "target_persona" not in body

    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["persona"] == expected_persona
    # The persona overlay block carries an ALL-CAPS audience marker
    # ("Audience: PARENT", etc.) — verify the engine actually picked
    # the right block, not just that the response field is correct.
    assert f"Audience: {marker}" in payload["prompt"]


def test_generate_target_persona_override_beats_role(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """An explicit ``target_persona`` in the body overrides the role-
    derived default. Parent user + body persona "teacher" → response
    persona is "teacher", and the prompt carries the TEACHER marker.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, target_persona="teacher")
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["persona"] == "teacher"
    assert "Audience: TEACHER" in payload["prompt"]


# ─────────────────────────────────────────────────────────────────────
# Scenario 5 — invalid content_type → 422
# ─────────────────────────────────────────────────────────────────────


def test_generate_invalid_content_type_returns_422(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Pydantic literal validation rejects a content_type that isn't in
    the locked HTTP literal set.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(
        seeded_cmcp_curriculum, content_type="NOT_A_REAL_CONTENT_TYPE"
    )
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 422


def test_generate_invalid_difficulty_returns_422(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Same gate for the difficulty literal."""
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, difficulty="EASY_PEASY")
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 422


def test_generate_invalid_persona_returns_422(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Persona literal is also gated."""
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, target_persona="alien-overlord")
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 422


def test_generate_grade_out_of_range_returns_422(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """``grade`` is bounded 1-12 by the schema."""
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, grade=99)
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────
# Resolution failures — surface 422 with the bad code in the message
# ─────────────────────────────────────────────────────────────────────


def test_generate_unknown_subject_code_returns_422(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, subject_code="UNKNOWNXYZ")
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 422
    assert "UNKNOWNXYZ" in resp.json()["detail"]


def test_generate_unknown_strand_code_returns_422(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, strand_code="ZZZ")
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 422
    assert "ZZZ" in resp.json()["detail"]


def test_generate_missing_strand_code_returns_422(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """The 1A-1 engine contract requires both subject + strand IDs;
    omitting ``strand_code`` is rejected with 422 + a clear message.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum)
    body.pop("strand_code")
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 422


def test_generate_no_curriculum_match_returns_422(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """The seed has G7 SEs only — request G2 to get an empty CEG match
    and surface ``NoCurriculumMatchError`` as a 422.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, grade=2)
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 422
    assert "specific expectations" in resp.json()["detail"].lower()
