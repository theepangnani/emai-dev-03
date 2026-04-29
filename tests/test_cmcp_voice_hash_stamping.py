"""CB-CMCP-001 M1-C 1C-2 — Voice module hash stamping tests (#4480).

Verifies that ``POST /api/cmcp/generate`` stamps:

- ``voice_module_id`` resolved via ``VoiceRegistry.active_module_id(persona)``
- ``voice_module_hash`` resolved via ``VoiceRegistry.module_hash(module_id)``

on the response, for all three personas (student / teacher / parent).

Five required scenarios per the issue body:

1. persona=student → ``voice_module_id='arc_voice_v1'`` + valid SHA-256 hash.
2. persona=teacher → ``voice_module_id='professional_v1'`` + valid SHA-256 hash.
3. persona=parent  → ``voice_module_id='parent_coach_v1'`` + valid SHA-256 hash.
4. Hash is stable across two calls for the same persona (same bytes → same digest).
5. Hash changes when the underlying voice-module file's contents change
   (validated against a tmp-dir voice module to avoid mutating the
   committed ``prompt_modules/voice/`` files).

Plus a couple of guards that fall out of the implementation cheaply:

- The hash matches what ``VoiceRegistry.module_hash`` returns directly
  (mutation-test guard against the route re-implementing the hash).
- ``GuardrailEngine.build_prompt(voice_module_id=None)`` returns a
  ``None`` hash (the pre-1C-2 contract still works for callers that
  don't supply an id).
- Pointing the engine at a missing module surfaces ``FileNotFoundError``
  (fail fast — the artifact would otherwise carry a NULL hash and bypass
  the wave-3 audit).

No real Claude/OpenAI calls — voice hashing is a pure file-read +
SHA-256, so this stripe never crosses an external API.

Issue: #4480
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── Flag fixture ───────────────────────────────────────────────────────


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

    email = f"cmcphash_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPHash {role.value}",
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
    """Seed a Grade-7 ``M<suffix>`` slice with one OE + two SEs.

    Mirrors the seed used by ``test_cmcp_generate_route.py`` so the route
    can resolve ``subject_code`` / ``strand_code`` to real CEG IDs and the
    1A-1 engine query returns SE rows. The uuid suffix dodges the
    ``ceg_subjects.code`` UNIQUE constraint on the session-scoped DB.
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
    version_slug = f"test-hash-{uuid4().hex[:6]}"

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
# Scenarios 1-3 — per-persona voice_module_id + voice_module_hash
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "user_fixture, expected_module_id",
    [
        ("student_user", "arc_voice_v1"),
        ("teacher_user", "professional_v1"),
        ("parent_user", "parent_coach_v1"),
    ],
)
def test_response_includes_voice_module_id_and_hash_per_persona(
    request,
    client,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
    user_fixture,
    expected_module_id,
):
    """Per #4480 acceptance: the response carries the active voice module
    ID for the persona AND its SHA-256 hex digest. Mutation-test guard
    against a regression where the route forgets to call
    ``VoiceRegistry.active_module_id`` and emits ``None``.
    """
    from app.services.cmcp.voice_registry import VoiceRegistry

    user = request.getfixturevalue(user_fixture)
    headers = _auth(client, user.email)
    resp = client.post(
        "/api/cmcp/generate",
        json=_payload(seeded_cmcp_curriculum),
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["voice_module_id"] == expected_module_id
    assert body["voice_module_hash"] is not None
    # SHA-256 hex digest is exactly 64 chars.
    assert len(body["voice_module_hash"]) == 64

    # The route must compute the hash via VoiceRegistry, not by
    # re-implementing SHA-256 over a different input. Verify the
    # response hash matches what VoiceRegistry.module_hash returns
    # directly for the same module ID.
    expected_hash = VoiceRegistry.module_hash(expected_module_id)
    assert body["voice_module_hash"] == expected_hash


# ─────────────────────────────────────────────────────────────────────
# Scenario 4 — hash is stable across calls
# ─────────────────────────────────────────────────────────────────────


def test_voice_hash_is_stable_across_calls(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Two back-to-back calls for the same persona return the same hash.

    The voice module file isn't being edited between the two calls, so
    the digest must match. Catches a regression where the registry
    accidentally hashes a timestamped wrapper or a per-request salt.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum)

    resp1 = client.post("/api/cmcp/generate", json=body, headers=headers)
    resp2 = client.post("/api/cmcp/generate", json=body, headers=headers)

    assert resp1.status_code == 200, resp1.text
    assert resp2.status_code == 200, resp2.text

    payload1 = resp1.json()
    payload2 = resp2.json()

    # voice_module_id must also be stable (no flipping under hot-swap
    # absent an explicit set_active_module call).
    assert payload1["voice_module_id"] == payload2["voice_module_id"]
    assert payload1["voice_module_hash"] == payload2["voice_module_hash"]
    # And both digests are the right shape.
    assert len(payload1["voice_module_hash"]) == 64


# ─────────────────────────────────────────────────────────────────────
# Scenario 5 — hash changes when the underlying file changes
# ─────────────────────────────────────────────────────────────────────


def test_voice_hash_changes_when_module_file_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Editing the .txt under VOICE_MODULES_DIR shifts the hash returned
    by ``GuardrailEngine.build_prompt(voice_module_id=...)``.

    We exercise the engine directly (rather than the HTTP route) so we
    can monkeypatch the voice-modules dir without re-seeding the route's
    flag + curriculum + auth fixtures. The route-side hash flow is
    covered by the per-persona parametrized test above.
    """
    from app.services.cmcp import voice_registry as voice_registry_module
    from app.services.cmcp.voice_registry import VoiceRegistry

    # Point the registry at a tmp dir we can mutate freely.
    monkeypatch.setattr(
        voice_registry_module, "VOICE_MODULES_DIR", tmp_path
    )

    module_id = "synthetic_hash_test_v1"
    module_file = tmp_path / f"{module_id}.txt"

    # First version of the voice — write + hash.
    first_text = "ARC v1: warm, curious, short sentences."
    module_file.write_text(first_text, encoding="utf-8")
    h_before = VoiceRegistry.module_hash(module_id)

    # Sanity: the hash matches what we'd compute by hand.
    assert h_before == hashlib.sha256(first_text.encode("utf-8")).hexdigest()

    # Edit the module file → hash must change.
    second_text = "ARC v1 — REVISED: even warmer, more curious."
    module_file.write_text(second_text, encoding="utf-8")
    h_after = VoiceRegistry.module_hash(module_id)

    assert h_after == hashlib.sha256(second_text.encode("utf-8")).hexdigest()
    assert h_before != h_after, (
        "Voice hash must change when the underlying module file is edited "
        "— otherwise the wave-3 audit can't flag voice-inconsistent artifacts"
    )


# ─────────────────────────────────────────────────────────────────────
# Engine-level guards (don't go through the HTTP route)
# ─────────────────────────────────────────────────────────────────────


def _seed_grade7_math_b(db_session, *, subject_code: str):
    """Compact seeder for engine-level tests (mirrors the route fixture).

    Returns ``(subject, strand)`` so the test can build a
    ``GenerationRequest`` against real IDs.
    """
    from app.models.curriculum import (
        CEGExpectation,
        CEGStrand,
        CEGSubject,
        CurriculumVersion,
        EXPECTATION_TYPE_OVERALL,
        EXPECTATION_TYPE_SPECIFIC,
    )

    subject = CEGSubject(code=subject_code, name=f"{subject_code} subject")
    db_session.add(subject)
    db_session.flush()

    strand = CEGStrand(subject_id=subject.id, code="B", name="Number Sense")
    version = CurriculumVersion(
        subject_id=subject.id,
        grade=7,
        version=f"hash-engine-{uuid4().hex[:6]}",
        change_severity=None,
    )
    db_session.add_all([strand, version])
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
        subject_id=subject.id,
        strand_id=strand.id,
        grade=7,
        expectation_type=EXPECTATION_TYPE_SPECIFIC,
        parent_oe_id=oe.id,
        description="Add and subtract fractions with unlike denominators.",
        curriculum_version_id=version.id,
    )
    db_session.add(se1)
    db_session.commit()

    return subject, strand


def _make_request(*, subject_id, strand_id):
    from app.schemas.cmcp import GenerationRequest

    return GenerationRequest(
        grade=7,
        subject_id=subject_id,
        strand_id=strand_id,
        content_type="quiz",
        difficulty="medium",
    )


def test_build_prompt_without_voice_module_id_returns_none_hash(db_session):
    """The pre-1C-2 contract still works: callers that don't supply a
    ``voice_module_id`` get ``None`` for the hash, not an exception.

    Mutation-test guard against accidentally making the parameter
    required (which would break 1A-1's existing call sites).
    """
    from app.services.cmcp.guardrail_engine import GuardrailEngine

    _, strand = _seed_grade7_math_b(db_session, subject_code="HASHENG_NONE")
    request = _make_request(
        subject_id=strand.subject_id, strand_id=strand.id
    )

    engine = GuardrailEngine(db_session)
    prompt, se_codes, voice_hash = engine.build_prompt(
        request, voice_module_id=None
    )

    assert "[CURRICULUM_GUARDRAIL]" in prompt
    assert se_codes == ["B2.1"]
    assert voice_hash is None


def test_build_prompt_with_voice_module_id_returns_registry_hash(db_session):
    """Supplying a ``voice_module_id`` returns the SHA-256 from
    ``VoiceRegistry.module_hash`` — verbatim, no re-hashing in the engine.
    """
    from app.services.cmcp.guardrail_engine import GuardrailEngine
    from app.services.cmcp.voice_registry import VoiceRegistry

    _, strand = _seed_grade7_math_b(db_session, subject_code="HASHENG_OK")
    request = _make_request(
        subject_id=strand.subject_id, strand_id=strand.id
    )

    engine = GuardrailEngine(db_session)
    _, _, voice_hash = engine.build_prompt(
        request, voice_module_id="arc_voice_v1"
    )

    expected = VoiceRegistry.module_hash("arc_voice_v1")
    assert voice_hash == expected
    assert len(voice_hash) == 64


def test_build_prompt_with_unknown_voice_module_id_raises_file_not_found(
    db_session,
):
    """An unknown ``voice_module_id`` surfaces FileNotFoundError from
    the registry — fail fast rather than silently emitting a NULL hash
    that bypasses the wave-3 audit (#4480 design).
    """
    from app.services.cmcp.guardrail_engine import GuardrailEngine

    _, strand = _seed_grade7_math_b(
        db_session, subject_code="HASHENG_MISS"
    )
    request = _make_request(
        subject_id=strand.subject_id, strand_id=strand.id
    )

    engine = GuardrailEngine(db_session)
    with pytest.raises(FileNotFoundError):
        engine.build_prompt(
            request, voice_module_id="does_not_exist_v9"
        )
