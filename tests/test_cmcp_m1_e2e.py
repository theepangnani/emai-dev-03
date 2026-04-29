"""CB-CMCP-001 M1 end-to-end integration tests (#4536).

Stripe-by-stripe unit tests already cover each slice of the M1 chain in
isolation, but each test mocks the boundary above its target stripe.
None of them assert the **full** integrated path:

    POST /api/cmcp/generate/stream
        → require_cmcp_enabled (flag gate)
        → _resolve_subject_and_strand (CEG lookup)
        → _derive_persona (role → persona)
        → VoiceRegistry.active_module_id (voice resolution)
        → GuardrailEngine.build_prompt (prompt + SE codes + voice hash)
        → ai_service.generate_content_stream (Claude — mocked)
        → ParentCompanionService.generate_5_section (auto-emit gate)
        → ValidationPipeline.validate (alignment scoring)
        → SSE event: complete (StreamCompletionEvent shape)
        → emit_latency_telemetry (per-type latency log line)

A cross-stripe regression — e.g., a build_prompt signature change, a
schema-extra-forbid drift, or a swapped persona-gate — would slip
through the unit tests but break the integrated flow. These tests
exercise the full chain in one shot per persona path so any cross-cut
break surfaces before merge.

Mocking strategy
----------------
- ``ai_service.generate_content_stream`` patched at the route's import
  site to yield a deterministic 3-chunk + ``done`` stream.
- ``ParentCompanionService.generate_5_section`` patched only on the
  student-persona auto-emit path. The mock returns a ``ParentCompanion
  Content`` instance so the route's serializer round-trips through
  ``model_dump()`` and the wire shape on the completion frame matches
  what the frontend (1E-3) will read.
- ``ValidationPipeline.validate`` is mocked on its import site inside
  the stream route's helper so the alignment scorer does not need a
  populated CEG taxonomy or text-extraction backend in tests.
- All DB seeds reuse the ``seeded_cmcp_curriculum`` shape from
  ``test_cmcp_generate_stream.py`` (one OE + two SEs in a Grade-7
  Math-shaped subject), keeping fixture parity with stripe tests.

NO real Claude/OpenAI calls are made.

Note on issue-vs-implementation divergence (#4536)
--------------------------------------------------
The issue body's acceptance-criteria phrasing ("student persona — no
parent_companion expected") is inverted relative to the actual M1
behavior wired up by 1F-3 (#4497): it is the **student** persona that
auto-emits the 5-section Parent Companion alongside a student-facing
artifact, while **parent + teacher** personas explicitly do not. These
tests assert the actually-shipped behavior — that is the regression
surface an integration test must protect.
"""
from __future__ import annotations

import json as _json
from typing import AsyncIterator
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── Flag + user fixtures (mirror test_cmcp_generate_stream.py) ─────────


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


def _make_user(db_session, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"cmcpe2e_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"E2E {role.value}",
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


# ── CEG seed (one OE + two SEs, isolated subject_code per test session) ─


@pytest.fixture()
def seeded_cmcp_curriculum(db_session):
    """Seed Grade-7 Math-shaped CEG with one OE + two SEs."""
    from app.models.curriculum import (
        CEGExpectation,
        CEGStrand,
        CEGSubject,
        CurriculumVersion,
        EXPECTATION_TYPE_OVERALL,
        EXPECTATION_TYPE_SPECIFIC,
    )

    suffix = uuid4().hex[:6].upper()
    subject_code = f"E{suffix}"
    strand_code = "B"
    version_slug = f"test-e2e-{uuid4().hex[:6]}"

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

    db_session.query(CEGExpectation).filter(
        CEGExpectation.id.in_(expectation_ids)
    ).delete(synchronize_session=False)
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


# ── Stream-mock helpers ────────────────────────────────────────────────


def _make_fake_stream(chunks: list[str]):
    """Async generator factory matching ``generate_content_stream``."""
    full = "".join(chunks)

    async def fake(*_args, **_kwargs) -> AsyncIterator[dict]:
        for c in chunks:
            yield {"event": "chunk", "data": c}
        yield {
            "event": "done",
            "data": {"is_truncated": False, "full_content": full},
        }

    return fake


def _patch_stream(fake):
    return patch(
        "app.api.routes.cmcp_generate_stream.generate_content_stream",
        side_effect=fake,
    )


def _parse_sse(text: str) -> list[dict]:
    """Parse SSE response body into ``[{event, data}, ...]``."""
    frames: list[dict] = []
    for raw in text.split("\n\n"):
        block = raw.strip("\n")
        if not block:
            continue
        event = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].lstrip())
        frames.append({"event": event, "data": "\n".join(data_lines)})
    return frames


def _payload(seeded, **overrides):
    body = {
        "grade": 7,
        "subject_code": seeded["subject_code"],
        "strand_code": seeded["strand_code"],
        "content_type": "STUDY_GUIDE",
        "difficulty": "GRADE_LEVEL",
    }
    body.update(overrides)
    return body


def _companion_5_section_payload() -> dict:
    """Lint-clean 5-section parent-companion JSON for the mocked AI call."""
    return {
        "se_explanation": (
            "Your child is working on adding fractions with unlike "
            "denominators. This week focuses on finding common "
            "denominators before combining."
        ),
        "talking_points": [
            "Ask them to walk you through one practice problem out loud.",
            "Explore where fractions show up in cooking together.",
            "Share a real-world example you encountered today.",
        ],
        "coaching_prompts": [
            "What does the denominator tell us about the size of each piece?",
            "Why did you pick that as the common denominator?",
        ],
        "how_to_help_without_giving_answer": (
            "Stay curious and ask questions instead of solving it for them. "
            "If they get stuck, prompt them to draw a fraction model and try again."
        ),
    }


def _patch_validation_pipeline(score: float = 0.92, flag: bool = False):
    """Patch ``ValidationPipeline.validate`` at the route's import site.

    Returns a ``ValidationPipelineResult``-shaped value with a stub
    second-pass nested result so the route's ``_run_alignment_pipeline``
    helper can read ``alignment_score`` + ``flag_for_review`` off it
    without invoking Claude.
    """
    from app.services.cmcp.alignment_validator import ValidationResult
    from app.services.cmcp.validation_pipeline import ValidationPipelineResult

    second_pass = ValidationResult(
        passed=not flag,
        coverage_rate=score,
        matched_se_codes=[],
        uncovered_se_codes=[],
        flag_for_review=flag,
        second_pass_concepts=[],
        error=None,
    )
    pipeline_result = ValidationPipelineResult(
        both_passed=not flag,
        alignment_score=score,
        first_pass_coverage_rate=score,
        second_pass_result=second_pass,
        flag_for_review=flag,
        matched_se_codes_union=[],
        uncovered_se_codes_intersection=[],
    )

    async def fake_validate(self, **_kwargs):  # noqa: ANN001
        return pipeline_result

    return patch(
        "app.api.routes.cmcp_generate_stream.ValidationPipeline.validate",
        new=fake_validate,
    )


# ─────────────────────────────────────────────────────────────────────
# E2E #1 — student persona full chain (the only persona that exercises
# every M1 stripe end-to-end, including parent-companion auto-emit).
# ─────────────────────────────────────────────────────────────────────


def test_m1_e2e_student_persona_full_chain(
    client, student_user, cmcp_flag_on, seeded_cmcp_curriculum, caplog
):
    """Student + STUDY_GUIDE — assert the entire M1 chain ran:

    - SSE chunks delivered in order (Claude streaming).
    - ``event: complete`` carries every M1 field populated together:
      * ``se_codes_targeted`` from CEG lookup
      * ``voice_module_id`` + ``voice_module_hash`` from VoiceRegistry
      * ``persona`` + ``content_type`` echoed
      * ``parent_companion`` populated with 5 sections (auto-emit gate)
      * ``alignment_score`` populated by ValidationPipeline
      * ``flag_for_review`` populated by ValidationPipeline
    - Per-type latency telemetry log line emitted on stream close.
    """
    import logging as _logging

    headers = _auth(client, student_user.email)
    body = _payload(seeded_cmcp_curriculum, content_type="STUDY_GUIDE")

    fake = _make_fake_stream(
        ["Section A: ", "fractions overview. ", "End of guide."]
    )
    companion_json = _json.dumps(_companion_5_section_payload())

    caplog.set_level(_logging.INFO, logger="app.services.cmcp.generation_telemetry")

    with _patch_stream(fake), patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_companion_call, _patch_validation_pipeline(
        score=0.92, flag=False
    ):
        mock_companion_call.return_value = (companion_json, "end_turn")
        resp = client.post(
            "/api/cmcp/generate/stream", json=body, headers=headers
        )

    # Wire-level: 200 + event-stream content type.
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")

    frames = _parse_sse(resp.text)

    # Token chunks delivered in order.
    chunks = [f["data"] for f in frames if f["event"] == "message"]
    assert chunks == ["Section A: ", "fractions overview. ", "End of guide."]

    # Exactly one completion frame.
    completion_frames = [f for f in frames if f["event"] == "complete"]
    assert len(completion_frames) == 1

    completion = _json.loads(completion_frames[0]["data"])

    # Every M1 stripe contributed a populated field on the completion event.
    # ── ClassContextResolver / GuardrailEngine: SE codes ──
    assert completion["se_codes_targeted"] == ["B2.1", "B2.2"]
    # ── VoiceRegistry: id + hash ──
    # Student persona's active voice module per VoiceRegistry._ACTIVE_MODULES.
    assert completion["voice_module_id"] == "arc_voice_v1"
    assert isinstance(completion["voice_module_hash"], str)
    assert len(completion["voice_module_hash"]) == 64  # SHA-256 hex
    # ── Persona derivation + echo ──
    assert completion["persona"] == "student"
    assert completion["content_type"] == "STUDY_GUIDE"
    # ── ParentCompanionService: 5-section auto-emit ──
    pc = completion["parent_companion"]
    assert pc is not None, (
        "Student + STUDY_GUIDE must auto-emit the 5-section companion"
    )
    assert pc["se_explanation"].startswith("Your child")
    assert len(pc["talking_points"]) == 3
    assert len(pc["coaching_prompts"]) == 2
    assert "Stay curious" in pc["how_to_help_without_giving_answer"]
    assert "bridge_deep_link_payload" in pc  # constructed by service
    # The companion service was handed the accumulated artifact, not just
    # the last chunk — guards against a regression that mis-wires the
    # auto-emit input to a partial buffer.
    assert mock_companion_call.await_count == 1
    assert (
        "End of guide."
        in mock_companion_call.await_args.kwargs["prompt"]
    )
    # ── ValidationPipeline: alignment_score + flag_for_review ──
    assert completion["alignment_score"] == 0.92
    assert completion["flag_for_review"] is False

    # Per-type latency telemetry emitted (1E-2).
    latency_records = [
        r for r in caplog.records
        if getattr(r, "event", None) == "cmcp.generation.latency"
    ]
    assert len(latency_records) >= 1
    rec = latency_records[-1]
    assert rec.content_type == "STUDY_GUIDE"
    assert rec.latency_ms >= 0
    assert hasattr(rec, "request_id")


# ─────────────────────────────────────────────────────────────────────
# E2E #2 — parent persona happy path (no companion auto-emit).
# ─────────────────────────────────────────────────────────────────────


def test_m1_e2e_parent_persona_no_companion(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Parent + STUDY_GUIDE — primary fields populated, companion skipped.

    Asserts the parent-facing path of the chain: persona derivation
    routes to the parent voice module, the validator still scores the
    artifact, and the auto-emit gate is closed (no token spend on
    companion). Mutation-test guard for an inverted persona check that
    would over-trigger companion generation on parent-facing artifacts.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, content_type="STUDY_GUIDE")

    fake = _make_fake_stream(["Parent-facing ", "study guide."])

    with _patch_stream(fake), patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_companion_call, _patch_validation_pipeline(
        score=0.88, flag=False
    ):
        resp = client.post(
            "/api/cmcp/generate/stream", json=body, headers=headers
        )

    assert resp.status_code == 200, resp.text
    frames = _parse_sse(resp.text)
    completion = _json.loads(
        next(f for f in frames if f["event"] == "complete")["data"]
    )

    # Primary fields all populated by the chain.
    assert completion["se_codes_targeted"] == ["B2.1", "B2.2"]
    assert completion["voice_module_id"] == "parent_coach_v1"
    assert isinstance(completion["voice_module_hash"], str)
    assert len(completion["voice_module_hash"]) == 64
    assert completion["persona"] == "parent"
    assert completion["content_type"] == "STUDY_GUIDE"
    assert completion["alignment_score"] == 0.88
    assert completion["flag_for_review"] is False

    # Auto-emit gate closed: no companion field, no companion service call.
    assert completion["parent_companion"] is None
    assert mock_companion_call.await_count == 0


# ─────────────────────────────────────────────────────────────────────
# E2E #3 — fallback path (no class context — M1 always runs this path).
# ─────────────────────────────────────────────────────────────────────


def test_m1_e2e_fallback_no_class_context(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """M1 never wires a course_id into the engine — every request runs
    through ``class_context_envelope=None`` (the "fallback" path of the
    ClassContextResolver design). This test asserts the chain still
    completes cleanly and surfaces a fully-populated completion event
    when no class context is available.

    Guard for a future regression that would 422 / 500 the request when
    course_id is omitted instead of degrading to the generic prompt.
    """
    headers = _auth(client, parent_user.email)
    # Explicit: no ``course_id`` field in the request body. The route
    # hardcodes ``class_context_envelope=None`` in M1 regardless, so this
    # both documents the field's absence and pins the contract that
    # request-omission is supported (not 422'd).
    body = _payload(seeded_cmcp_curriculum, content_type="ASSIGNMENT")
    assert "course_id" not in body

    fake = _make_fake_stream(["Generic ", "assignment."])

    with _patch_stream(fake), _patch_validation_pipeline(
        score=0.75, flag=False
    ):
        resp = client.post(
            "/api/cmcp/generate/stream", json=body, headers=headers
        )

    assert resp.status_code == 200, resp.text
    frames = _parse_sse(resp.text)

    # Stream still produced chunks + completion despite no class context.
    chunks = [f["data"] for f in frames if f["event"] == "message"]
    assert chunks == ["Generic ", "assignment."]

    completion = _json.loads(
        next(f for f in frames if f["event"] == "complete")["data"]
    )

    # Primary fields populated even on the fallback (no course_id) path.
    assert completion["se_codes_targeted"] == ["B2.1", "B2.2"]
    assert completion["voice_module_id"] == "parent_coach_v1"
    assert completion["persona"] == "parent"
    assert completion["content_type"] == "ASSIGNMENT"
    assert completion["alignment_score"] == 0.75
    # No parent persona ⇒ no companion auto-emit on the fallback either.
    assert completion["parent_companion"] is None
