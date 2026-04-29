"""
CB-CMCP-001 M1-A 1A-1 — GuardrailEngine tests.

Five scenarios per the issue body:

1. Build prompt with only CEG SEs (no envelope, no voice) — SE codes appear.
2. Build prompt with class-context envelope — envelope summary appears.
3. Build prompt with ``voice_module_path`` — voice content embedded.
4. Build prompt with ``persona='parent'`` — tone block differs from student.
5. Empty CEG result → ``NoCurriculumMatchError`` raised.

Plus a couple of sanity guards (invalid persona, voice path missing,
topic substring filter).

No real Claude API calls — the engine is pure prompt composition.
"""
from __future__ import annotations

import pytest


def _seed_grade7_math_b(db_session, *, subject_code: str = "MATH"):
    """Seed a Grade-7 ``subject_code`` "Number Sense" slice with one OE + two SEs.

    Returns ``(subject, strand, version, oe, se1, se2)`` so individual
    tests can build ``GenerationRequest`` instances bound to real IDs.

    The conftest ``db_session`` fixture rides on a *session-scoped* SQLite
    DB — rows persist across tests in the same run. Each test that calls
    this helper must pass a unique ``subject_code`` to dodge the
    ``ceg_subjects.code`` UNIQUE constraint.
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
        version="2020-rev1",
        change_severity=None,
    )
    db_session.add_all([strand, version])
    db_session.flush()

    oe = CEGExpectation(
        ministry_code="B2",
        cb_code="CB-G7-MATH-B2",
        subject_id=subject.id,
        strand_id=strand.id,
        grade=7,
        expectation_type=EXPECTATION_TYPE_OVERALL,
        description="Demonstrate understanding of fractions, decimals and percents.",
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
    se2 = CEGExpectation(
        ministry_code="B2.2",
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

    return subject, strand, version, oe, se1, se2


def _make_request(*, subject_id, strand_id, **overrides):
    from app.schemas.cmcp import GenerationRequest

    payload = {
        "grade": 7,
        "subject_id": subject_id,
        "strand_id": strand_id,
        "content_type": "quiz",
        "difficulty": "medium",
    }
    payload.update(overrides)
    return GenerationRequest(**payload)


# ---------------------------------------------------------------------------
# Scenario 1 — only CEG SEs
# ---------------------------------------------------------------------------


class TestSeOnlyPrompt:
    def test_se_codes_appear_and_are_returned(self, db_session):
        from app.services.cmcp.guardrail_engine import GuardrailEngine

        _, strand, _, _, se1, se2 = _seed_grade7_math_b(
            db_session, subject_code="GE_MATH_SE_ONLY"
        )
        request = _make_request(
            subject_id=strand.subject_id, strand_id=strand.id
        )

        engine = GuardrailEngine(db_session)
        prompt, se_codes = engine.build_prompt(request)

        assert se_codes == ["B2.1", "B2.2"]
        # SE codes must appear inside the curriculum guardrail block.
        assert "[CURRICULUM_GUARDRAIL]" in prompt
        assert "B2.1" in prompt
        assert "B2.2" in prompt
        # OE should also appear since it rolls up the SEs.
        assert "B2:" in prompt
        # No envelope, no voice — those blocks must be absent.
        assert "[CLASS_CONTEXT]" not in prompt
        assert "[VOICE]" not in prompt
        # Persona always present (default = student).
        assert "[PERSONA]" in prompt
        assert "STUDENT" in prompt


# ---------------------------------------------------------------------------
# Scenario 2 — class-context envelope
# ---------------------------------------------------------------------------


class TestEnvelopeInjection:
    def test_envelope_summary_and_sources_appear(self, db_session):
        from app.services.cmcp.guardrail_engine import GuardrailEngine

        _, strand, _, _, _, _ = _seed_grade7_math_b(
            db_session, subject_code="GE_MATH_ENVELOPE"
        )
        request = _make_request(
            subject_id=strand.subject_id, strand_id=strand.id
        )

        envelope = {
            "summary": "Class is mid-unit on fractions; teacher emphasized common denominators last week.",
            "cited_sources": [
                "course_contents:doc_4521",
                "gc_announcement:abc123",
            ],
        }

        engine = GuardrailEngine(db_session)
        prompt, _ = engine.build_prompt(
            request, class_context_envelope=envelope
        )

        assert "[CLASS_CONTEXT]" in prompt
        assert "common denominators" in prompt
        assert "course_contents:doc_4521" in prompt
        assert "gc_announcement:abc123" in prompt


# ---------------------------------------------------------------------------
# Scenario 3 — voice module path
# ---------------------------------------------------------------------------


class TestVoiceOverlay:
    def test_voice_module_contents_embedded(self, db_session, tmp_path):
        from app.services.cmcp.guardrail_engine import GuardrailEngine

        _, strand, _, _, _, _ = _seed_grade7_math_b(
            db_session, subject_code="GE_MATH_VOICE_OK"
        )
        request = _make_request(
            subject_id=strand.subject_id, strand_id=strand.id
        )

        voice_text = (
            "ARC_VOICE_V1 — speak with curious warmth. Short sentences. "
            "Encourage effort over correctness."
        )
        voice_path = tmp_path / "arc_voice_v1.txt"
        voice_path.write_text(voice_text, encoding="utf-8")

        engine = GuardrailEngine(db_session)
        prompt, _ = engine.build_prompt(
            request, voice_module_path=str(voice_path)
        )

        assert "[VOICE]" in prompt
        assert "ARC_VOICE_V1" in prompt
        assert "curious warmth" in prompt

    def test_voice_module_missing_renders_placeholder(self, db_session, tmp_path):
        from app.services.cmcp.guardrail_engine import GuardrailEngine

        _, strand, _, _, _, _ = _seed_grade7_math_b(
            db_session, subject_code="GE_MATH_VOICE_MISS"
        )
        request = _make_request(
            subject_id=strand.subject_id, strand_id=strand.id
        )

        missing = tmp_path / "does_not_exist.txt"
        engine = GuardrailEngine(db_session)
        prompt, _ = engine.build_prompt(
            request, voice_module_path=str(missing)
        )

        assert "[VOICE]" in prompt
        assert "placeholder" in prompt
        assert "1C-2" in prompt


# ---------------------------------------------------------------------------
# Scenario 4 — persona overlay differs
# ---------------------------------------------------------------------------


class TestPersonaOverlay:
    def test_parent_persona_differs_from_student(self, db_session):
        from app.services.cmcp.guardrail_engine import GuardrailEngine

        _, strand, _, _, _, _ = _seed_grade7_math_b(
            db_session, subject_code="GE_MATH_PARENT"
        )
        request = _make_request(
            subject_id=strand.subject_id, strand_id=strand.id
        )

        engine = GuardrailEngine(db_session)
        student_prompt, _ = engine.build_prompt(
            request, target_persona="student"
        )
        parent_prompt, _ = engine.build_prompt(
            request, target_persona="parent"
        )

        # Both contain the persona block.
        assert "[PERSONA]" in student_prompt
        assert "[PERSONA]" in parent_prompt
        # Student carries the Arc / STUDENT marker.
        assert "STUDENT" in student_prompt
        assert "Arc" in student_prompt
        # Parent carries the warm-coaching marker; STUDENT marker is absent.
        assert "PARENT" in parent_prompt
        assert "warm-coaching" in parent_prompt
        assert "Audience: STUDENT" not in parent_prompt
        # The two prompts must differ on the persona line.
        assert student_prompt != parent_prompt

    def test_teacher_persona_block_loads(self, db_session):
        from app.services.cmcp.guardrail_engine import GuardrailEngine

        _, strand, _, _, _, _ = _seed_grade7_math_b(
            db_session, subject_code="GE_MATH_TEACHER"
        )
        request = _make_request(
            subject_id=strand.subject_id, strand_id=strand.id
        )

        engine = GuardrailEngine(db_session)
        prompt, _ = engine.build_prompt(request, target_persona="teacher")
        assert "TEACHER" in prompt
        assert "neutral-professional" in prompt

    def test_invalid_persona_raises(self, db_session):
        from app.services.cmcp.guardrail_engine import GuardrailEngine

        _, strand, _, _, _, _ = _seed_grade7_math_b(
            db_session, subject_code="GE_MATH_BAD_PERSONA"
        )
        request = _make_request(
            subject_id=strand.subject_id, strand_id=strand.id
        )

        engine = GuardrailEngine(db_session)
        with pytest.raises(ValueError, match="target_persona"):
            engine.build_prompt(request, target_persona="alien-overlord")


# ---------------------------------------------------------------------------
# Scenario 5 — empty CEG result raises
# ---------------------------------------------------------------------------


class TestEmptyCurriculum:
    def test_no_se_match_raises(self, db_session):
        from app.services.cmcp.guardrail_engine import (
            GuardrailEngine,
            NoCurriculumMatchError,
        )

        _, strand, _, _, _, _ = _seed_grade7_math_b(
            db_session, subject_code="GE_MATH_NO_SE"
        )
        # Request a grade with no SE rows — same subject/strand but
        # grade=2 was never seeded.
        request = _make_request(
            grade=2,
            subject_id=strand.subject_id,
            strand_id=strand.id,
        )
        engine = GuardrailEngine(db_session)

        with pytest.raises(NoCurriculumMatchError):
            engine.build_prompt(request)

    def test_topic_filter_with_no_match_raises(self, db_session):
        from app.services.cmcp.guardrail_engine import (
            GuardrailEngine,
            NoCurriculumMatchError,
        )

        _, strand, _, _, _, _ = _seed_grade7_math_b(
            db_session, subject_code="GE_MATH_TOPIC_NONE"
        )
        # SEs exist, but the topic substring filter yields nothing.
        request = _make_request(
            subject_id=strand.subject_id,
            strand_id=strand.id,
            topic="quantum chromodynamics",
        )
        engine = GuardrailEngine(db_session)

        with pytest.raises(NoCurriculumMatchError):
            engine.build_prompt(request)


# ---------------------------------------------------------------------------
# Bonus guard — topic substring filter narrows the SE list
# ---------------------------------------------------------------------------


class TestTopicFilter:
    def test_topic_filter_narrows_se_list(self, db_session):
        from app.services.cmcp.guardrail_engine import GuardrailEngine

        _, strand, _, _, _, _ = _seed_grade7_math_b(
            db_session, subject_code="GE_MATH_TOPIC_OK"
        )
        # Only SE B2.1 mentions "fractions"; B2.2 is about decimals.
        request = _make_request(
            subject_id=strand.subject_id,
            strand_id=strand.id,
            topic="fractions",
        )
        engine = GuardrailEngine(db_session)
        prompt, codes = engine.build_prompt(request)

        assert codes == ["B2.1"]
        assert "B2.1" in prompt
        # B2.2 must not appear in the SE list section. The OE listing
        # still shows OE B2 because OEs aren't subject to the topic filter.
        # We assert that the SE description for B2.2 ("Multiply and divide
        # decimal numbers ...") is absent.
        assert "decimal numbers to thousandths" not in prompt
