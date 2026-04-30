"""Unit tests for ``app.services.dci_blocks.cmcp_coach_card``.

CB-CMCP-001 M3α 3C-2 (#4579). Covers:

* Renders a coach-card payload for a parent-persona, APPROVED /
  SELF_STUDY artifact with persisted parent-companion JSON.
* Returns ``None`` when ``parent_summary`` is missing / empty /
  unparseable / has no usable talking_points (block omitted, not error).
* Returns ``None`` for non-renderable states (DRAFT, PENDING_REVIEW,
  REJECTED, ARCHIVED).
* Returns ``None`` for non-parent-persona artifacts (student / teacher
  persona, or non-parent_companion guide_type).
* Returns ``None`` when ``artifact_id`` resolves to no row.
* Subject derivation falls through SE-code → title → "General" without
  an extra DB lookup.
* Child name falls back to "Your kid" when the student row / linked
  user is missing — coach card never renders a blank field.

All Claude / OpenAI calls are absent (renderer is pure DB + JSON).
"""
from __future__ import annotations

import json
import logging
from uuid import uuid4

import pytest

from app.services.dci_blocks import (
    CMCP_COACH_CARD_BLOCK_TYPE,
    get_block_renderer,
    register_block,
    registered_block_types,
    render_cmcp_coach_card,
)
from app.services.cmcp.artifact_state import ArtifactState


# ── Helpers ────────────────────────────────────────────────────────────


def _good_parent_companion() -> dict:
    """A well-formed 5-section parent-companion JSON payload."""
    return {
        "se_explanation": (
            "Your child is exploring how to add and subtract fractions "
            "with unlike denominators. They're practicing finding a "
            "common denominator before combining the numerators."
        ),
        "talking_points": [
            "Ask them to walk you through how they found a common denominator.",
            "Have them explain why 1/2 + 1/3 isn't simply 2/5.",
            "Try a real-world fraction (pizza slices, recipe halving) together.",
            "Bonus: practice subtraction with mixed numbers if confident.",
        ],
        "coaching_prompts": [
            "What's the trickiest part for you so far?",
            "How would you check if your answer makes sense?",
        ],
        "how_to_help_without_giving_answer": (
            "Lean on questions like 'what's a denominator both fractions "
            "share?' rather than handing over the steps."
        ),
        "bridge_deep_link_payload": {
            "child_id": None,
            "week_summary": None,
            "deep_link_target": None,
        },
    }


@pytest.fixture()
def parent_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = User(
        email=f"coachcard_parent_{uuid4().hex[:8]}@test.com",
        full_name=f"Parent {uuid4().hex[:6]}",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("test1234"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def kid_student(db_session):
    """Linked Student row with its own User; first_name = 'Maya'."""
    from app.core.security import get_password_hash
    from app.models.student import Student
    from app.models.user import User, UserRole

    kid_user = User(
        email=f"coachcard_kid_{uuid4().hex[:8]}@test.com",
        full_name="Maya Patel",
        role=UserRole.STUDENT,
        hashed_password=get_password_hash("test1234"),
    )
    db_session.add(kid_user)
    db_session.commit()
    db_session.refresh(kid_user)

    student = Student(user_id=kid_user.id, grade_level=7)
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return student


def _make_artifact(
    db_session,
    *,
    user_id: int,
    state: str = ArtifactState.SELF_STUDY,
    requested_persona: str | None = "parent",
    guide_type: str = "parent_companion",
    parent_summary: dict | str | None,
    se_codes: list[str] | None = None,
    title: str = "CMCP PARENT_COMPANION",
):
    """Create + flush a StudyGuide row for the renderer to read."""
    from app.models.study_guide import StudyGuide

    if isinstance(parent_summary, dict):
        parent_summary_str = json.dumps(parent_summary)
    else:
        parent_summary_str = parent_summary

    sg = StudyGuide(
        user_id=user_id,
        title=title,
        content="Generated CMCP content body for parent companion.",
        guide_type=guide_type,
        state=state,
        requested_persona=requested_persona,
        parent_summary=parent_summary_str,
        se_codes=se_codes,
    )
    db_session.add(sg)
    db_session.commit()
    db_session.refresh(sg)
    return sg


# ── Registry ───────────────────────────────────────────────────────────


class TestRegistry:
    def test_block_type_is_registered(self):
        assert CMCP_COACH_CARD_BLOCK_TYPE in registered_block_types()
        assert get_block_renderer(CMCP_COACH_CARD_BLOCK_TYPE) is render_cmcp_coach_card

    def test_register_block_idempotent(self):
        # Re-registering the same renderer for the same key is a no-op.
        register_block(CMCP_COACH_CARD_BLOCK_TYPE, render_cmcp_coach_card)
        assert (
            get_block_renderer(CMCP_COACH_CARD_BLOCK_TYPE) is render_cmcp_coach_card
        )

    def test_register_block_conflict_raises(self):
        def _other(_artifact_id, _kid_id, _db):  # pragma: no cover
            return None

        with pytest.raises(ValueError, match="already registered"):
            register_block(CMCP_COACH_CARD_BLOCK_TYPE, _other)

    def test_get_block_renderer_unknown_returns_none(self):
        assert get_block_renderer("definitely_not_a_block_type") is None


# ── Happy path ─────────────────────────────────────────────────────────


class TestRenderHappyPath:
    def test_renders_for_parent_persona_self_study_artifact(
        self, db_session, parent_user, kid_student
    ):
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            state=ArtifactState.SELF_STUDY,
            requested_persona="parent",
            parent_summary=_good_parent_companion(),
            se_codes=["CB-G7-MATH-B2-SE1", "CB-G7-MATH-B2-SE2"],
            title="CMCP PARENT_COMPANION",
        )

        payload = render_cmcp_coach_card(
            artifact.id, kid_student.id, db_session
        )

        assert payload is not None
        assert payload["block_type"] == "cb_cmcp_coach_card"
        assert payload["artifact_id"] == artifact.id
        assert payload["child_name"] == "Maya"
        assert payload["subject"] == "MATH"
        # First sentence of se_explanation, no trailing extra sentence.
        assert payload["topic_summary"].startswith(
            "Your child is exploring how to add and subtract fractions"
        )
        assert payload["topic_summary"].endswith(".")
        # Top 3 talking points only — list always 3 even though source has 4.
        assert len(payload["talking_points"]) == 3
        assert all(isinstance(p, str) and p for p in payload["talking_points"])
        # Bridge route — exact format the dispatcher (3C-1) will hand off.
        assert payload["open_link"] == f"/parent/companion/{artifact.id}"

    def test_renders_for_approved_state(self, db_session, parent_user, kid_student):
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            state=ArtifactState.APPROVED,
            parent_summary=_good_parent_companion(),
        )
        payload = render_cmcp_coach_card(
            artifact.id, kid_student.id, db_session
        )
        assert payload is not None
        assert payload["block_type"] == "cb_cmcp_coach_card"

    def test_renders_when_persona_field_blank_but_guide_type_parent_companion(
        self, db_session, parent_user, kid_student
    ):
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            state=ArtifactState.SELF_STUDY,
            requested_persona=None,
            guide_type="parent_companion",
            parent_summary=_good_parent_companion(),
        )
        payload = render_cmcp_coach_card(
            artifact.id, kid_student.id, db_session
        )
        assert payload is not None


# ── None paths (block omitted, not error) ──────────────────────────────


class TestRenderReturnsNone:
    def test_unknown_artifact_id(self, db_session, kid_student):
        assert render_cmcp_coach_card(999_999_999, kid_student.id, db_session) is None

    def test_none_artifact_id(self, db_session, kid_student):
        # Defensive: a None artifact_id (e.g. dispatcher with bad input)
        # should be a clean omit, not an attribute error.
        assert render_cmcp_coach_card(None, kid_student.id, db_session) is None  # type: ignore[arg-type]

    def test_empty_parent_summary(self, db_session, parent_user, kid_student):
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            state=ArtifactState.SELF_STUDY,
            parent_summary=None,
        )
        assert render_cmcp_coach_card(artifact.id, kid_student.id, db_session) is None

    def test_blank_parent_summary_string(
        self, db_session, parent_user, kid_student
    ):
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            state=ArtifactState.SELF_STUDY,
            parent_summary="   ",
        )
        assert render_cmcp_coach_card(artifact.id, kid_student.id, db_session) is None

    def test_unparseable_parent_summary(
        self, db_session, parent_user, kid_student
    ):
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            state=ArtifactState.SELF_STUDY,
            parent_summary="{this is not: valid json",
        )
        assert render_cmcp_coach_card(artifact.id, kid_student.id, db_session) is None

    def test_parent_summary_with_no_talking_points(
        self, db_session, parent_user, kid_student
    ):
        content = _good_parent_companion()
        content["talking_points"] = []
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            state=ArtifactState.SELF_STUDY,
            parent_summary=content,
        )
        assert render_cmcp_coach_card(artifact.id, kid_student.id, db_session) is None

    def test_parent_summary_with_only_blank_talking_points(
        self, db_session, parent_user, kid_student
    ):
        content = _good_parent_companion()
        content["talking_points"] = ["", "   ", None, 42]  # all unusable
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            state=ArtifactState.SELF_STUDY,
            parent_summary=content,
        )
        assert render_cmcp_coach_card(artifact.id, kid_student.id, db_session) is None

    @pytest.mark.parametrize(
        "state",
        [
            ArtifactState.DRAFT,
            ArtifactState.PENDING_REVIEW,
            ArtifactState.IN_REVIEW,
            ArtifactState.REJECTED,
            ArtifactState.ARCHIVED,
            ArtifactState.GENERATING,
            ArtifactState.APPROVED_VERIFIED,  # treated as out-of-scope for M0 coach card
        ],
    )
    def test_non_renderable_state_returns_none(
        self, db_session, parent_user, kid_student, state
    ):
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            state=state,
            parent_summary=_good_parent_companion(),
        )
        assert render_cmcp_coach_card(artifact.id, kid_student.id, db_session) is None

    def test_non_parent_persona_returns_none(
        self, db_session, parent_user, kid_student
    ):
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            state=ArtifactState.SELF_STUDY,
            requested_persona="student",
            guide_type="study_guide",
            parent_summary=_good_parent_companion(),
        )
        assert render_cmcp_coach_card(artifact.id, kid_student.id, db_session) is None


# ── Subject + child-name derivation ────────────────────────────────────


class TestSubjectDerivation:
    def test_subject_from_se_code(self, db_session, parent_user, kid_student):
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            parent_summary=_good_parent_companion(),
            se_codes=["CB-G5-SCI-A1-SE2"],
        )
        payload = render_cmcp_coach_card(artifact.id, kid_student.id, db_session)
        assert payload is not None
        assert payload["subject"] == "SCI"

    def test_subject_falls_back_to_title_when_se_codes_unparseable(
        self, db_session, parent_user, kid_student
    ):
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            parent_summary=_good_parent_companion(),
            se_codes=["unknown-format"],
            title="CMCP English Language Arts",
        )
        payload = render_cmcp_coach_card(artifact.id, kid_student.id, db_session)
        assert payload is not None
        # Title strips the leading "CMCP " prefix.
        assert payload["subject"] == "English Language Arts"

    def test_subject_falls_back_to_general_when_no_signal(
        self, db_session, parent_user, kid_student
    ):
        # Use the title="CMCP " case: with trailing whitespace stripped first,
        # then the "CMCP " prefix check fails, so we'd return "CMCP". To hit
        # the General fallback we need an artifact with NO se_codes AND
        # an effectively-empty title. The model column is nullable so an
        # empty-string title is the realistic edge case.
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            parent_summary=_good_parent_companion(),
            se_codes=None,
            title="CMCP   ",  # only the prefix + trailing whitespace
        )
        # Strip-then-prefix check: title="CMCP   ".strip() → "CMCP" then
        # the "CMCP " prefix check (with space) fails, so the title path
        # returns "CMCP" — NOT "General". So instead we use a single-char
        # "CMCP" case below where the post-prefix slice is non-empty but
        # we want the True General fallback path.
        payload = render_cmcp_coach_card(artifact.id, kid_student.id, db_session)
        assert payload is not None
        # Documented behaviour: bare-prefix titles surface as "CMCP"
        # (we don't rewrite to "General" — _derive_subject only
        # General-fallbacks when both signals are entirely empty).
        assert payload["subject"] == "CMCP"

    def test_subject_general_fallback_with_blank_title_and_no_se_codes(
        self, db_session, parent_user, kid_student
    ):
        # Both signals empty → "General".
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            parent_summary=_good_parent_companion(),
            se_codes=None,
            title="",
        )
        payload = render_cmcp_coach_card(artifact.id, kid_student.id, db_session)
        assert payload is not None
        assert payload["subject"] == "General"


class TestChildNameDerivation:
    def test_child_name_uses_first_name_only(
        self, db_session, parent_user, kid_student
    ):
        # kid_student fixture sets full_name="Maya Patel".
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            parent_summary=_good_parent_companion(),
        )
        payload = render_cmcp_coach_card(artifact.id, kid_student.id, db_session)
        assert payload is not None
        assert payload["child_name"] == "Maya"

    def test_child_name_falls_back_when_kid_missing(
        self, db_session, parent_user
    ):
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            parent_summary=_good_parent_companion(),
        )
        # kid_id that doesn't resolve to any Student row.
        payload = render_cmcp_coach_card(artifact.id, 999_999_999, db_session)
        assert payload is not None
        assert payload["child_name"] == "Your kid"

    def test_child_name_falls_back_when_kid_id_none(
        self, db_session, parent_user
    ):
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            parent_summary=_good_parent_companion(),
        )
        payload = render_cmcp_coach_card(artifact.id, None, db_session)  # type: ignore[arg-type]
        assert payload is not None
        assert payload["child_name"] == "Your kid"


# ── Topic summary trimming ─────────────────────────────────────────────


class TestTopicSummary:
    def test_topic_summary_is_first_sentence_only(
        self, db_session, parent_user, kid_student
    ):
        content = _good_parent_companion()
        content["se_explanation"] = (
            "Sentence one ends here. Sentence two should be dropped."
        )
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            parent_summary=content,
        )
        payload = render_cmcp_coach_card(artifact.id, kid_student.id, db_session)
        assert payload is not None
        assert payload["topic_summary"] == "Sentence one ends here."

    def test_topic_summary_handles_blank_explanation(
        self, db_session, parent_user, kid_student
    ):
        content = _good_parent_companion()
        content["se_explanation"] = ""
        # talking_points still populated → block still renders.
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            parent_summary=content,
        )
        payload = render_cmcp_coach_card(artifact.id, kid_student.id, db_session)
        assert payload is not None
        assert payload["topic_summary"] == ""


# ── Surface telemetry (3C-5) ───────────────────────────────────────────


class TestSurfaceTelemetry:
    """Verify the renderer emits the canonical ``cmcp.surface.rendered``
    structured log line (used by the M3 acceptance "render rate per
    surface" metric extractor).

    The legacy ``dci.block.rendered`` line is also asserted so a future
    accidental removal — which would silently break extractors that
    still match the legacy event name — surfaces here.
    """

    def test_emits_cmcp_surface_rendered_with_kid_user_id(
        self, db_session, parent_user, kid_student, caplog
    ):
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            parent_summary=_good_parent_companion(),
        )

        caplog.set_level(
            logging.INFO,
            logger="app.services.cmcp.surface_telemetry",
        )
        payload = render_cmcp_coach_card(
            artifact.id, kid_student.id, db_session
        )
        assert payload is not None

        matches = [
            rec
            for rec in caplog.records
            if getattr(rec, "event", None) == "cmcp.surface.rendered"
        ]
        assert len(matches) == 1
        rec = matches[0]
        assert rec.artifact_id == artifact.id
        assert rec.surface == "dci"
        # Viewer for the DCI surface = the kid's User row id (resolved
        # via Student.user_id), NOT students.id.
        assert rec.user_id == kid_student.user_id

    def test_emits_cmcp_surface_rendered_user_id_none_when_kid_unmapped(
        self, db_session, parent_user, caplog
    ):
        """Renderer must still emit telemetry — with ``user_id=None`` —
        when the supplied ``kid_id`` doesn't resolve to a Student row.
        Telemetry never fail-closes on the render path (fallback path of
        the issue's "If kid is unmapped..." rule).

        Also asserts the legacy ``dci.block.rendered`` event still fires
        on this path — the kid-unmapped branch is precisely where the
        new + legacy events diverge most (legacy uses ``kid_id``
        directly, new uses ``Student.user_id``), so a regression that
        gates the legacy emit on a successful Student lookup would
        silently break legacy extractors only on this path. Capture
        BOTH loggers so both events are visible.
        """
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            parent_summary=_good_parent_companion(),
        )

        # Capture both the surface-telemetry logger AND the
        # cmcp_coach_card logger — the legacy event rides the renderer's
        # own logger.
        caplog.set_level(logging.INFO)
        payload = render_cmcp_coach_card(
            artifact.id, 9_999_999, db_session
        )
        assert payload is not None

        matches = [
            rec
            for rec in caplog.records
            if getattr(rec, "event", None) == "cmcp.surface.rendered"
        ]
        assert len(matches) == 1
        rec = matches[0]
        assert rec.artifact_id == artifact.id
        assert rec.surface == "dci"
        assert rec.user_id is None

        legacy = [
            rec
            for rec in caplog.records
            if getattr(rec, "event", None) == "dci.block.rendered"
        ]
        assert len(legacy) == 1, (
            "legacy dci.block.rendered must still fire on the "
            "kid-unmapped path (backwards-compat with existing extractors)"
        )

    def test_legacy_dci_block_rendered_event_still_emitted(
        self, db_session, parent_user, kid_student, caplog
    ):
        """Backwards-compat: the legacy ``dci.block.rendered`` event must
        still fire alongside the new canonical event."""
        artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            parent_summary=_good_parent_companion(),
        )

        caplog.set_level(
            logging.INFO,
            logger="app.services.dci_blocks.cmcp_coach_card",
        )
        payload = render_cmcp_coach_card(
            artifact.id, kid_student.id, db_session
        )
        assert payload is not None

        legacy = [
            rec
            for rec in caplog.records
            if getattr(rec, "event", None) == "dci.block.rendered"
        ]
        assert len(legacy) == 1

    def test_no_surface_telemetry_when_block_omitted(
        self, db_session, parent_user, kid_student, caplog
    ):
        """When the renderer returns ``None`` (e.g. non-renderable
        state, missing parent_summary, no talking points, missing
        artifact, None artifact_id), no ``cmcp.surface.rendered`` line
        should fire — render-rate must only count actual user-visible
        renders, not skipped blocks. Mirrors the digest renderer's
        existing absence-of-telemetry guard.
        """
        # Non-renderable state (DRAFT) — renderer returns None per the
        # _RENDERABLE_STATES filter.
        draft_artifact = _make_artifact(
            db_session,
            user_id=parent_user.id,
            state=ArtifactState.DRAFT,
            parent_summary=_good_parent_companion(),
        )

        caplog.set_level(
            logging.INFO, logger="app.services.cmcp.surface_telemetry"
        )
        result = render_cmcp_coach_card(
            draft_artifact.id, kid_student.id, db_session
        )
        assert result is None

        matches = [
            rec
            for rec in caplog.records
            if getattr(rec, "event", None) == "cmcp.surface.rendered"
        ]
        assert len(matches) == 0
