"""CB-CMCP-001 M2-B 2B-4 (#4555) — ``generate_content`` MCP tool tests.

Exercises the route surface (``POST /mcp/call_tool`` with
``name='generate_content'``) end-to-end:

- Happy path: TEACHER + ADMIN can generate; the response carries the
  full ``GenerationPreview`` dict (prompt, se_codes, voice_module_id,
  voice_module_hash, persona).
- Role gating: PARENT + STUDENT receive 403 BEFORE the handler runs
  (role check fires in the dispatcher).
- Bad arguments: missing required field → 422 (Pydantic
  ``ValidationError`` re-raised as ``HTTPException(422)``).
- Curriculum-resolution miss: unknown subject_code → 422.
- ``additionalProperties: false`` on the schema is honoured: an extra
  field at the MCP boundary is rejected.
- The MCP tool delegates to the **same** service layer the REST route
  uses (``generate_cmcp_preview_sync``) — i.e., we don't re-implement
  prompt construction.

No real Claude/OpenAI calls anywhere. The whole pipeline is pure
prompt composition (engine.build_prompt) over local CEG rows; nothing
in this stripe ever crosses an external API.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── Flag fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def mcp_flag_on(db_session):
    """Force ``mcp.enabled`` ON for the test; restore prior state after.

    Captures the flag's pre-test value rather than blindly committing
    ``False`` post-yield (#4561 review pass-1) — a copy-paste of this
    fixture into a parallel-execution context (e.g., pytest-xdist)
    would otherwise silently disable the flag for tests that expect
    it ON. Today's tests share a session-scoped SQLite DB so the bug
    is theoretical, but the pattern is the safe one.
    """
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "mcp.enabled")
        .first()
    )
    assert flag is not None, "mcp.enabled flag must be seeded"
    original = flag.enabled
    flag.enabled = True
    db_session.commit()
    yield flag
    db_session.refresh(flag)
    flag.enabled = original
    db_session.commit()


@pytest.fixture()
def cmcp_flag_on(db_session):
    """Force ``cmcp.enabled`` ON; restore prior state after.

    The MCP ``generate_content`` tool re-checks ``cmcp.enabled`` (see
    #4561 review pass-1) — the curriculum-content surface is gated
    independently of the MCP transport flag, so an admin can roll
    back the curriculum surface without touching ``mcp.enabled``. The
    fixture restores the pre-test value so tests that toggle the flag
    don't pollute siblings.
    """
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "cmcp.enabled")
        .first()
    )
    assert flag is not None, "cmcp.enabled flag must be seeded"
    original = flag.enabled
    flag.enabled = True
    db_session.commit()
    yield flag
    db_session.refresh(flag)
    flag.enabled = original
    db_session.commit()


@pytest.fixture()
def cmcp_flag_off(db_session):
    """Force ``cmcp.enabled`` OFF; restore prior state after.

    Companion to ``cmcp_flag_on`` for the new
    test_cmcp_flag_off_returns_403 case (#4561 review pass-1).
    """
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "cmcp.enabled")
        .first()
    )
    assert flag is not None, "cmcp.enabled flag must be seeded"
    original = flag.enabled
    flag.enabled = False
    db_session.commit()
    yield flag
    db_session.refresh(flag)
    flag.enabled = original
    db_session.commit()


# ── User fixtures ──────────────────────────────────────────────────────


def _make_user(db_session, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"mcpgen_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"MCPGen {role.value}",
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


# ── CEG seed (mirrors test_cmcp_generate_route.py) ────────────────────


@pytest.fixture()
def seeded_cmcp_curriculum(db_session):
    """Seed a Grade-7 ``MATH`` slice with one OE + two SEs.

    Uses a uuid-suffixed subject code so this fixture's seed never
    collides with sibling fixtures on the session-scoped DB.
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
    version_slug = f"test-mcpgen-{uuid4().hex[:6]}"

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


def _arguments(seeded, **overrides):
    """Build a baseline ``CMCPGenerateRequest``-shaped arguments dict."""
    args = {
        "grade": 7,
        "subject_code": seeded["subject_code"],
        "strand_code": seeded["strand_code"],
        "content_type": "STUDY_GUIDE",
        "difficulty": "GRADE_LEVEL",
    }
    args.update(overrides)
    return args


# ─────────────────────────────────────────────────────────────────────
# Happy path — TEACHER + ADMIN
# ─────────────────────────────────────────────────────────────────────


def test_teacher_generates_study_guide_returns_preview_shape(
    client,
    teacher_user,
    mcp_flag_on,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """TEACHER generates STUDY_GUIDE → 200 with full GenerationPreview shape.

    Asserts every field of the preview dict is populated — including
    ``voice_module_id`` + ``voice_module_hash`` (both set by the M1-C
    1C-2 voice-registry wiring; both must be present here because the
    MCP tool delegates to the same ``generate_cmcp_preview_sync``
    helper the REST route uses).
    """
    headers = _auth(client, teacher_user.email)
    resp = client.post(
        "/mcp/call_tool",
        json={
            "name": "generate_content",
            "arguments": _arguments(seeded_cmcp_curriculum),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "generate_content"
    content = body["content"]

    # Full GenerationPreview shape — keys match the REST route exactly.
    # M3α prequel (#4575): adds the persisted ``id`` field.
    assert set(content.keys()) == {
        "id",
        "prompt",
        "se_codes_targeted",
        "voice_module_id",
        "voice_module_hash",
        "persona",
    }
    # Curriculum anchoring — SEs from the seeded slice appear in order.
    assert content["se_codes_targeted"] == ["B2.1", "B2.2"]
    # Persona is teacher (derived from current_user.role since the
    # arguments dict doesn't override it).
    assert content["persona"] == "teacher"
    # Voice-module wiring is populated (M1-C 1C-2): the active teacher
    # module + its SHA-256 hash both come back non-None.
    assert content["voice_module_id"] is not None
    assert content["voice_module_hash"] is not None
    # Prompt carries the curriculum guardrail block + persona block —
    # mirrors the REST route's load-bearing assertions.
    assert "[CURRICULUM_GUARDRAIL]" in content["prompt"]
    assert "[PERSONA]" in content["prompt"]
    assert "B2.1" in content["prompt"]
    assert "B2.2" in content["prompt"]


def test_admin_generates_quiz_returns_preview_shape(
    client,
    admin_user,
    mcp_flag_on,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """ADMIN can also invoke ``generate_content`` (per the role tuple).

    Persona derivation falls back to ``"student"`` for ADMIN (the route
    helper's ``_derive_persona`` rule for non-PARENT/STUDENT/TEACHER
    roles), so the persona block + voice module reflect the student
    overlay — captured here so a future change to the fallback rule
    doesn't silently slip past.
    """
    headers = _auth(client, admin_user.email)
    resp = client.post(
        "/mcp/call_tool",
        json={
            "name": "generate_content",
            "arguments": _arguments(
                seeded_cmcp_curriculum, content_type="QUIZ"
            ),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    content = resp.json()["content"]
    assert content["persona"] == "student"  # ADMIN → fallback
    assert content["se_codes_targeted"] == ["B2.1", "B2.2"]


def test_target_persona_override_beats_role_default(
    client,
    teacher_user,
    mcp_flag_on,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """Explicit ``target_persona`` in arguments wins over role default."""
    headers = _auth(client, teacher_user.email)
    resp = client.post(
        "/mcp/call_tool",
        json={
            "name": "generate_content",
            "arguments": _arguments(
                seeded_cmcp_curriculum, target_persona="parent"
            ),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["content"]["persona"] == "parent"


# ─────────────────────────────────────────────────────────────────────
# Curriculum-flag gate — cmcp.enabled OFF returns 403 even when
# mcp.enabled is ON (defense-in-depth: #4561 review pass-1).
# ─────────────────────────────────────────────────────────────────────


def test_cmcp_flag_off_returns_403(
    client,
    teacher_user,
    mcp_flag_on,
    cmcp_flag_off,
    seeded_cmcp_curriculum,
):
    """``cmcp.enabled`` OFF + ``mcp.enabled`` ON → 403.

    The MCP transport gates only on ``mcp.enabled``; without an
    explicit re-check inside the handler, an admin flipping
    ``cmcp.enabled`` OFF would disable the REST surface but leave the
    MCP path serving content. Pinned here so a future refactor that
    drops the curriculum-flag check immediately fails this test.

    Note: 403 (not 404) — matches the REST route's
    ``require_cmcp_enabled`` semantics so a misconfigured rollback
    looks identical on both transports.
    """
    headers = _auth(client, teacher_user.email)
    resp = client.post(
        "/mcp/call_tool",
        json={
            "name": "generate_content",
            "arguments": _arguments(seeded_cmcp_curriculum),
        },
        headers=headers,
    )
    assert resp.status_code == 403
    assert "cmcp.enabled" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────────────
# Role gating — PARENT + STUDENT denied at the dispatcher
# ─────────────────────────────────────────────────────────────────────


def test_parent_call_returns_403_without_running_handler(
    client,
    parent_user,
    mcp_flag_on,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """PARENT calling ``generate_content`` → 403 (role allowlist).

    The role check fires in the dispatcher BEFORE the handler runs, so
    we get 403 even with a valid arguments body. This is the
    self-study-deferred-to-M3-B contract: PARENT/STUDENT are NOT in
    the M2 role tuple.
    """
    headers = _auth(client, parent_user.email)
    resp = client.post(
        "/mcp/call_tool",
        json={
            "name": "generate_content",
            "arguments": _arguments(seeded_cmcp_curriculum),
        },
        headers=headers,
    )
    assert resp.status_code == 403
    assert "generate_content" in resp.json()["detail"]


def test_student_call_returns_403(
    client,
    student_user,
    mcp_flag_on,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """STUDENT calling ``generate_content`` → 403 (same M3-B carve-out)."""
    headers = _auth(client, student_user.email)
    resp = client.post(
        "/mcp/call_tool",
        json={
            "name": "generate_content",
            "arguments": _arguments(seeded_cmcp_curriculum),
        },
        headers=headers,
    )
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# Bad arguments — Pydantic validation errors → 422
# ─────────────────────────────────────────────────────────────────────


def test_missing_required_field_returns_422(
    client,
    teacher_user,
    mcp_flag_on,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """Missing ``content_type`` → Pydantic 422 (re-raised as HTTPException)."""
    headers = _auth(client, teacher_user.email)
    args = _arguments(seeded_cmcp_curriculum)
    args.pop("content_type")
    resp = client.post(
        "/mcp/call_tool",
        json={"name": "generate_content", "arguments": args},
        headers=headers,
    )
    assert resp.status_code == 422


def test_bad_content_type_returns_422(
    client,
    teacher_user,
    mcp_flag_on,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """An out-of-enum ``content_type`` → 422 from Pydantic Literal check."""
    headers = _auth(client, teacher_user.email)
    args = _arguments(seeded_cmcp_curriculum, content_type="NOT_A_THING")
    resp = client.post(
        "/mcp/call_tool",
        json={"name": "generate_content", "arguments": args},
        headers=headers,
    )
    assert resp.status_code == 422


def test_extra_field_returns_422(
    client,
    teacher_user,
    mcp_flag_on,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """Extra field at the MCP boundary → 422 (``extra='forbid'``).

    Mutation-test guard for the schema's ``model_config = ConfigDict(
    extra='forbid')`` — if it ever got loosened to ``"allow"`` the
    MCP transport would silently swallow typo'd field names.
    """
    headers = _auth(client, teacher_user.email)
    args = _arguments(seeded_cmcp_curriculum, unknown_field="oops")
    resp = client.post(
        "/mcp/call_tool",
        json={"name": "generate_content", "arguments": args},
        headers=headers,
    )
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────
# Curriculum resolution — unknown subject → 422
# ─────────────────────────────────────────────────────────────────────


def test_unknown_subject_code_returns_422(
    client,
    teacher_user,
    mcp_flag_on,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """Subject_code that isn't in CEG → 422 from the route helper."""
    headers = _auth(client, teacher_user.email)
    args = _arguments(seeded_cmcp_curriculum, subject_code="NOPE_ZZZ")
    resp = client.post(
        "/mcp/call_tool",
        json={"name": "generate_content", "arguments": args},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "NOPE_ZZZ" in resp.json()["detail"]


def test_unknown_strand_code_returns_422(
    client,
    teacher_user,
    mcp_flag_on,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """Strand_code that doesn't belong to the subject → 422."""
    headers = _auth(client, teacher_user.email)
    args = _arguments(seeded_cmcp_curriculum, strand_code="ZZ")
    resp = client.post(
        "/mcp/call_tool",
        json={"name": "generate_content", "arguments": args},
        headers=headers,
    )
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────
# Service-layer reuse — same helper, no duplicated logic
# ─────────────────────────────────────────────────────────────────────


def test_handler_delegates_to_route_helper(
    client,
    teacher_user,
    mcp_flag_on,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
    monkeypatch,
):
    """The MCP handler MUST call ``generate_cmcp_preview_sync``.

    Mutation-test guard for the "no duplicated prompt-build logic" rule
    in the locked plan §7. If a future refactor re-implements the
    pipeline inline (e.g., calls GuardrailEngine directly), this spy
    won't fire and the test fails — surfacing the divergence before
    the MCP and REST surfaces drift apart.
    """
    from app.api.routes import cmcp_generate as route_module
    from app.mcp.tools import generate_content as tool_module

    calls = []
    real_helper = route_module.generate_cmcp_preview_sync

    def _spy(payload, current_user, db):
        calls.append(payload)
        return real_helper(payload=payload, current_user=current_user, db=db)

    # Patch the symbol the tool imported into its own namespace —
    # patching ``route_module.generate_cmcp_preview_sync`` directly
    # would miss this call site (Python binds at import time).
    monkeypatch.setattr(
        tool_module, "generate_cmcp_preview_sync", _spy
    )

    headers = _auth(client, teacher_user.email)
    resp = client.post(
        "/mcp/call_tool",
        json={
            "name": "generate_content",
            "arguments": _arguments(seeded_cmcp_curriculum),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert len(calls) == 1, "MCP handler did not delegate to route helper"
    # The spy received a CMCPGenerateRequest model — confirms
    # validation ran before delegation.
    from app.schemas.cmcp import CMCPGenerateRequest

    assert isinstance(calls[0], CMCPGenerateRequest)
    assert calls[0].content_type == "STUDY_GUIDE"


# ─────────────────────────────────────────────────────────────────────
# Catalog visibility — list_tools includes generate_content for TEACHER
# ─────────────────────────────────────────────────────────────────────


def test_list_tools_exposes_generate_content_input_schema(
    client, teacher_user, mcp_flag_on
):
    """TEACHER's catalog includes ``generate_content`` with the full
    ``input_schema``. Ensures the MCP transport advertises the same
    request shape this stripe wired the handler to validate.
    """
    headers = _auth(client, teacher_user.email)
    resp = client.get("/mcp/list_tools", headers=headers)
    assert resp.status_code == 200, resp.text
    tools = {t["name"]: t for t in resp.json()["tools"]}
    assert "generate_content" in tools
    schema = tools["generate_content"]["input_schema"]
    # Required fields advertised in the catalog match
    # CMCPGenerateRequest's required set.
    assert set(schema["required"]) == {
        "subject_code",
        "strand_code",
        "grade",
        "content_type",
        "difficulty",
    }
    # Content-type enum carries every locked HTTPContentType literal —
    # mutation-test guard for the schema definition in TOOLS.
    assert set(schema["properties"]["content_type"]["enum"]) == {
        "STUDY_GUIDE",
        "WORKSHEET",
        "QUIZ",
        "SAMPLE_TEST",
        "ASSIGNMENT",
        "PARENT_COMPANION",
    }
