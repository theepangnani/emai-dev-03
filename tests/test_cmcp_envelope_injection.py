"""Tests for CB-CMCP-001 M1-B 1B-3 envelope injection + telemetry (#4479).

Three required scenarios per the issue body:

1. Route call with ``course_id`` populated → prompt includes envelope
   content (course materials excerpt, GC announcements, etc.) AND the
   SE list from CEG.
2. Route call with no ``course_id`` → CEG-only fallback path; envelope's
   ``fallback_used=True`` is logged.
3. Telemetry log line ``cmcp.generation.envelope`` carries all 5
   required fields (envelope_size, cited_source_count, fallback_used,
   course_id, target_se_codes_count).

Plus guards that fall out of the implementation cheaply:
- The legacy 1A-1 dict-shape envelope (``summary`` + ``cited_sources``)
  still renders correctly — back-compat for callers that pass a
  hand-built dict.
- The new envelope shape renders course_contents under a labelled
  subheading and announcements under another, so a Claude-side
  template author can tell the categories apart.

No real Claude/OpenAI calls — the route never crosses an external API
in this stripe; the resolver hits the test SQLite DB only.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── Flag fixtures ──────────────────────────────────────────────────────


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

    email = f"cmcpenv_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPEnv {role.value}",
        role=role,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def teacher_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.TEACHER)


@pytest.fixture()
def teacher_record(db_session, teacher_user):
    """Teacher row backing the user — needed for the ``Course.teacher_id`` FK."""
    from app.models.teacher import Teacher

    t = Teacher(user_id=teacher_user.id, school_name="Envelope Test School")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture()
def course_with_materials(db_session, teacher_record, teacher_user):
    """A course with one CourseContent row + one CourseAnnouncement row.

    Both inputs are course-level, no per-student fields — preserves the
    1B-2 privacy invariant transitively.

    ``created_by_user_id=teacher_user.id`` is required by M3α 3B-1's
    ``validate_class_distribution_authority`` guard — without it, the
    teacher requestor cannot class-distribute and the route returns 403.
    """
    from app.models.course import Course
    from app.models.course_announcement import CourseAnnouncement
    from app.models.course_content import CourseContent

    course = Course(
        name="Envelope Test Math",
        subject="Math",
        teacher_id=teacher_record.id,
        created_by_user_id=teacher_user.id,
        google_classroom_id=f"gc-env-{uuid4().hex[:8]}",
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    cc = CourseContent(
        course_id=course.id,
        title="Slope-intercept form notes",
        description=(
            "Distinctive course material describing slope-intercept form "
            "and how to graph linear equations from y=mx+b."
        ),
        content_type="notes",
        created_by_user_id=teacher_record.user_id,
    )
    db_session.add(cc)

    ann = CourseAnnouncement(
        course_id=course.id,
        google_announcement_id=f"gca-env-{uuid4().hex[:8]}",
        text="Distinctive announcement about Friday quiz on slope-intercept.",
        creator_name="Mr. EnvelopeTeacher",
        creation_time=datetime.now(timezone.utc) - timedelta(days=2),
    )
    db_session.add(ann)
    db_session.commit()
    return course


# ── CEG seed ───────────────────────────────────────────────────────────


@pytest.fixture()
def seeded_curriculum(db_session):
    """Seed a Grade-7 ``MATH-XXXX`` slice with one OE + two SEs.

    Mirrors the ``seeded_cmcp_curriculum`` fixture from the 1A-2 route
    tests but with its own uuid-suffixed subject code so the two test
    files can share the session-scoped DB without colliding.
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
    subject_code = f"E{suffix}"
    strand_code = "B"
    version_slug = f"test-env-{uuid4().hex[:6]}"

    subject = CEGSubject(code=subject_code, name="Envelope Math")
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
        notes="env test seed",
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
# Scenario 1 — happy path: course_id populated → envelope content in prompt
# ─────────────────────────────────────────────────────────────────────


def test_envelope_injection_with_course_id_populates_prompt(
    client,
    teacher_user,
    cmcp_flag_on,
    seeded_curriculum,
    course_with_materials,
):
    """Route call with ``course_id`` populated → prompt includes the
    envelope's course-materials excerpt AND the GC announcement AND the
    SE list from CEG. Mutation-test guard: revert the
    ``class_context_envelope=envelope.model_dump()`` arg in
    ``cmcp_generate.py`` and the ``[CLASS_CONTEXT]`` block disappears.
    """
    headers = _auth(client, teacher_user.email)
    body = _payload(
        seeded_curriculum, course_id=course_with_materials.id
    )
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    prompt = payload["prompt"]

    # SE list from CEG (the curriculum guardrail block).
    assert "[CURRICULUM_GUARDRAIL]" in prompt
    assert "B2.1" in prompt
    assert "B2.2" in prompt

    # Envelope content (course materials + announcements) — the [CLASS_CONTEXT]
    # block must appear and carry the distinctive strings we seeded.
    assert "[CLASS_CONTEXT]" in prompt
    assert "Course materials" in prompt
    assert "Slope-intercept form notes" in prompt
    assert "slope-intercept form" in prompt.lower()
    assert "Recent classroom announcements" in prompt
    assert "Distinctive announcement" in prompt
    assert "Mr. EnvelopeTeacher" in prompt

    # The SE list is preserved (per acceptance: "BOTH the SE list (from
    # CEG) AND the envelope content").
    assert payload["se_codes_targeted"] == ["B2.1", "B2.2"]


# ─────────────────────────────────────────────────────────────────────
# Scenario 2 — no course_id → CEG-only fallback path
# ─────────────────────────────────────────────────────────────────────


def test_envelope_injection_without_course_id_falls_back_to_ceg_only(
    client, teacher_user, cmcp_flag_on, seeded_curriculum
):
    """Route call with no ``course_id`` → CEG-only prompt; envelope's
    ``fallback_used=True`` and the [CLASS_CONTEXT] block carries the
    fallback placeholder, not real envelope content.
    """
    headers = _auth(client, teacher_user.email)
    body = _payload(seeded_curriculum)  # no course_id
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    prompt = payload["prompt"]

    # The CEG SE list still appears.
    assert "[CURRICULUM_GUARDRAIL]" in prompt
    assert "B2.1" in prompt
    assert "B2.2" in prompt

    # The [CLASS_CONTEXT] block appears (the route always passes an
    # envelope now, even an empty fallback one) and carries the
    # placeholder marker — NOT the real "Course materials" subheading.
    assert "[CLASS_CONTEXT]" in prompt
    assert "fallback to CEG-only grounding" in prompt
    assert "Course materials" not in prompt
    assert "Recent classroom announcements" not in prompt


# ─────────────────────────────────────────────────────────────────────
# Scenario 3 — telemetry log carries the 5 required fields
# ─────────────────────────────────────────────────────────────────────


def test_envelope_injection_telemetry_log_carries_all_five_fields(
    client,
    teacher_user,
    cmcp_flag_on,
    seeded_curriculum,
    course_with_materials,
    caplog,
):
    """Acceptance: the structured telemetry line ``cmcp.generation.envelope``
    must carry envelope_size, cited_source_count, fallback_used,
    course_id, target_se_codes_count. Mutation-test guard: drop any one
    of the 5 ``extra=`` keys in the route and one of the assertions
    below fails.
    """
    caplog.set_level(logging.INFO, logger="app.api.routes.cmcp_generate")

    headers = _auth(client, teacher_user.email)
    body = _payload(
        seeded_curriculum, course_id=course_with_materials.id
    )
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 200, resp.text

    # Find the telemetry record by its event marker on ``extra``.
    records = [
        r for r in caplog.records
        if getattr(r, "event", None) == "cmcp.generation.envelope"
    ]
    assert len(records) == 1, (
        f"expected exactly one cmcp.generation.envelope log line, "
        f"got {len(records)}: {[r.getMessage() for r in records]}"
    )
    rec = records[0]

    # All five required fields must be on the LogRecord.
    assert rec.course_id == course_with_materials.id
    # envelope_size = course_contents(1) + announcements(1) = 2 (no
    # digest because no TeacherCommunication seeded; no library because
    # no APPROVED StudyGuide seeded).
    assert rec.envelope_size == 2
    assert rec.cited_source_count == 2
    assert rec.fallback_used is False
    assert rec.target_se_codes_count == 2


def test_envelope_injection_telemetry_logs_fallback_when_no_course(
    client, teacher_user, cmcp_flag_on, seeded_curriculum, caplog
):
    """Fallback branch: no ``course_id`` → ``fallback_used=True`` on the
    telemetry log, ``envelope_size=0``, ``cited_source_count=0``,
    ``course_id=None``. Mutation-test guard for the resolver wiring: if
    the route stops calling ``ClassContextResolver``, the fields below
    won't match.
    """
    caplog.set_level(logging.INFO, logger="app.api.routes.cmcp_generate")

    headers = _auth(client, teacher_user.email)
    body = _payload(seeded_curriculum)  # no course_id
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 200, resp.text

    records = [
        r for r in caplog.records
        if getattr(r, "event", None) == "cmcp.generation.envelope"
    ]
    assert len(records) == 1
    rec = records[0]

    assert rec.course_id is None
    assert rec.envelope_size == 0
    assert rec.cited_source_count == 0
    assert rec.fallback_used is True
    # SEs were still resolved from CEG even though no envelope content.
    assert rec.target_se_codes_count == 2


# ─────────────────────────────────────────────────────────────────────
# Engine-level rendering guards (no DB writes — pure prompt composition)
# ─────────────────────────────────────────────────────────────────────


def test_engine_renders_new_envelope_shape_with_all_four_categories(
    db_session, seeded_curriculum
):
    """The engine's ``_render_envelope_block`` must surface all four
    M1-B 1B-2 input categories under labelled subheadings. Mutation-
    test guard: drop any of the four ``if`` branches in the renderer
    and one of the assertions below fails.
    """
    from app.schemas.cmcp import GenerationRequest
    from app.services.cmcp.guardrail_engine import GuardrailEngine

    request = GenerationRequest(
        grade=7,
        subject_id=seeded_curriculum["subject"].id,
        strand_id=seeded_curriculum["strand"].id,
        content_type="quiz",
    )

    envelope = {
        "course_contents": [
            {
                "id": 1,
                "title": "Notes A",
                "content_type": "notes",
                "summary": "Distinctive course content summary.",
            }
        ],
        "classroom_announcements": [
            {
                "id": 2,
                "text": "Distinctive announcement text.",
                "creator_name": "Ms. Brown",
                "creation_time": None,
            }
        ],
        "teacher_digest_summary": {
            "count": 1,
            "window_days": 30,
            "items": [
                {
                    "subject": "Distinctive subject",
                    "ai_summary": "Distinctive AI digest summary.",
                    "received_at": None,
                }
            ],
        },
        "teacher_library_artifacts": [
            {
                "id": 3,
                "title": "Distinctive artifact",
                "guide_type": "study_guide",
                "state": "APPROVED",
                "matched_se_codes": ["B2.1"],
            }
        ],
        "envelope_size": 4,
        "cited_source_count": 4,
        "fallback_used": False,
    }

    engine = GuardrailEngine(db_session)
    prompt, _, _ = engine.build_prompt(
        request,
        class_context_envelope=envelope,
        target_persona="teacher",
    )

    # All four category subheadings appear.
    assert "Course materials" in prompt
    assert "Recent classroom announcements" in prompt
    assert "Teacher email digest" in prompt
    assert "Approved library artifacts" in prompt

    # Distinctive content from each category surfaces.
    assert "Distinctive course content summary" in prompt
    assert "Distinctive announcement text" in prompt
    assert "Distinctive AI digest summary" in prompt
    assert "Distinctive artifact" in prompt
    assert "B2.1" in prompt


def test_engine_legacy_dict_envelope_still_renders(
    db_session, seeded_curriculum
):
    """Back-compat: the legacy 1A-1 stub envelope shape (``summary`` +
    ``cited_sources``) still renders. Mutation-test guard: removing the
    legacy branch from ``_render_envelope_block`` will break this test
    while leaving the new-shape tests passing.
    """
    from app.schemas.cmcp import GenerationRequest
    from app.services.cmcp.guardrail_engine import GuardrailEngine

    request = GenerationRequest(
        grade=7,
        subject_id=seeded_curriculum["subject"].id,
        strand_id=seeded_curriculum["strand"].id,
        content_type="quiz",
    )

    envelope = {
        "summary": "Legacy stub summary text.",
        "cited_sources": ["legacy-source-1", "legacy-source-2"],
    }

    engine = GuardrailEngine(db_session)
    prompt, _, _ = engine.build_prompt(
        request,
        class_context_envelope=envelope,
        target_persona="teacher",
    )

    assert "Legacy stub summary text" in prompt
    assert "legacy-source-1" in prompt
    assert "legacy-source-2" in prompt


def test_engine_empty_envelope_renders_fallback_placeholder(
    db_session, seeded_curriculum
):
    """An empty dict (or one with all-empty new-shape lists) renders the
    stable fallback placeholder so callers can tell ``no envelope`` from
    ``empty envelope`` in downstream tooling.
    """
    from app.schemas.cmcp import GenerationRequest
    from app.services.cmcp.guardrail_engine import GuardrailEngine

    request = GenerationRequest(
        grade=7,
        subject_id=seeded_curriculum["subject"].id,
        strand_id=seeded_curriculum["strand"].id,
        content_type="quiz",
    )

    engine = GuardrailEngine(db_session)
    prompt, _, _ = engine.build_prompt(
        request,
        class_context_envelope={
            "course_contents": [],
            "classroom_announcements": [],
            "teacher_digest_summary": None,
            "teacher_library_artifacts": [],
            "envelope_size": 0,
            "cited_source_count": 0,
            "fallback_used": True,
        },
        target_persona="teacher",
    )
    assert "[CLASS_CONTEXT]" in prompt
    assert "fallback to CEG-only grounding" in prompt


def test_engine_get_target_se_codes_returns_codes(
    db_session, seeded_curriculum
):
    """The ``get_target_se_codes`` helper introduced for 1B-3 returns the
    SE list without composing the full prompt. Mutation-test guard:
    making the method return ``[]`` or the OE codes instead of SE codes
    breaks the route's resolver-driving path and the assertions below.
    """
    from app.schemas.cmcp import GenerationRequest
    from app.services.cmcp.guardrail_engine import GuardrailEngine

    request = GenerationRequest(
        grade=7,
        subject_id=seeded_curriculum["subject"].id,
        strand_id=seeded_curriculum["strand"].id,
        content_type="quiz",
    )
    engine = GuardrailEngine(db_session)
    codes = engine.get_target_se_codes(request)
    assert codes == ["B2.1", "B2.2"]
