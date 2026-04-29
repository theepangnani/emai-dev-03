"""Tests for the CB-CMCP-001 M1-E 1E-2 latency telemetry helper (#4495).

Three-layer test plan:

1. **Unit tests on ``emit_latency_telemetry``** — pure-logic helper, no
   route involvement. Cover every content type's SLO threshold, the
   breach / no-breach branches, the unknown-content-type fallback, and
   the negative-clamp defensive guard.

2. **Integration test on the sync route (1A-2)** — patch the route's
   own ``perf_counter`` symbol so the latency delta is deterministic,
   fire a ``POST /api/cmcp/generate`` request, and assert the telemetry
   log line lands with the expected ``content_type`` / ``latency_ms`` /
   ``slo_breached`` fields. Covers both happy-path and 422 paths.

3. **Integration test on the streaming route (1E-1)** — same pattern,
   but with a fake ``generate_content_stream`` so we can simulate a long
   stream (latency > SLO) and a short stream (latency < SLO) without
   actual Claude calls.

Mutation-test guards
--------------------
- Drop any single content type from ``_SLO_THRESHOLDS_MS`` → its
  threshold test fails.
- Flip the breach comparison from ``>`` to ``>=`` → the boundary-equal
  test catches it (latency == threshold should be ``slo_breached=False``).
- Forget to wire telemetry into one of the routes → the route-side
  caplog assertion fails.

Mocking strategy
----------------
The unit tests use ``caplog`` to capture the LogRecord ``extra=`` payload
directly — no patching needed. The integration tests patch the routes'
own ``perf_counter`` symbol (each route module imports
``perf_counter`` from ``time`` directly so the patch is route-local
and doesn't leak into FastAPI / sqlalchemy timing). Patches return
deterministic values so the asserted ``latency_ms`` is exact rather
than wobbling on CPU jitter.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator
from unittest.mock import patch
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ──────────────────────────────────────────────────────────────────────
# Layer 1 — Unit tests on emit_latency_telemetry
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "content_type, expected_threshold_ms",
    [
        ("QUIZ", 8_000),
        ("WORKSHEET", 12_000),
        ("STUDY_GUIDE", 25_000),
        ("SAMPLE_TEST", 40_000),
        ("ASSIGNMENT", 30_000),
        ("PARENT_COMPANION", 8_000),
    ],
)
def test_slo_threshold_table_is_complete_per_locked_spec(
    content_type, expected_threshold_ms
):
    """Per locked plan §10 + D6=B: every HTTP content type has the
    documented SLO P95 threshold. Mutation-test guard: drop any single
    entry from ``_SLO_THRESHOLDS_MS`` and one of these parametrize
    branches fails.
    """
    from app.services.cmcp.generation_telemetry import get_slo_threshold_ms

    assert get_slo_threshold_ms(content_type) == expected_threshold_ms


def test_get_slo_threshold_ms_returns_none_for_unknown_type():
    """Unknown content type → ``None`` rather than raising. Telemetry
    must never fail closed and break a request.
    """
    from app.services.cmcp.generation_telemetry import get_slo_threshold_ms

    assert get_slo_threshold_ms("BOGUS") is None
    assert get_slo_threshold_ms("") is None


@pytest.mark.parametrize(
    "content_type, latency_ms, expected_breached",
    [
        # Below the SLO — no breach.
        ("QUIZ", 1_000, False),
        ("QUIZ", 7_999, False),
        # At-the-boundary — locked plan says "P95 < 8s", so equal-to is
        # NOT a breach. Mutation-test guard for ``>=`` vs ``>``.
        ("QUIZ", 8_000, False),
        # Just over — breach.
        ("QUIZ", 8_001, True),
        # Long-form types stretch further before breaching.
        ("STUDY_GUIDE", 24_999, False),
        ("STUDY_GUIDE", 25_001, True),
        ("SAMPLE_TEST", 39_999, False),
        ("SAMPLE_TEST", 40_001, True),
        ("ASSIGNMENT", 30_001, True),
        ("WORKSHEET", 12_001, True),
        ("PARENT_COMPANION", 8_001, True),
    ],
)
def test_emit_latency_telemetry_breach_flag(
    content_type, latency_ms, expected_breached, caplog
):
    """slo_breached fires only when ``latency_ms > threshold`` (strict
    greater-than). Mutation-test guard: flipping the comparison to
    ``>=`` fails the at-the-boundary case.
    """
    from app.services.cmcp.generation_telemetry import emit_latency_telemetry

    caplog.set_level(
        logging.INFO, logger="app.services.cmcp.generation_telemetry"
    )
    request_id = uuid4().hex
    emit_latency_telemetry(
        content_type=content_type,
        latency_ms=latency_ms,
        request_id=request_id,
    )

    records = [
        r for r in caplog.records
        if getattr(r, "event", None) == "cmcp.generation.latency"
    ]
    assert len(records) == 1
    rec = records[0]
    assert rec.content_type == content_type
    assert rec.latency_ms == latency_ms
    assert rec.slo_breached is expected_breached
    assert rec.request_id == request_id
    # ``cmcp.generation.latency`` numeric field for log-based metric
    # extraction must equal the raw latency, regardless of breach state.
    assert getattr(rec, "cmcp.generation.latency") == latency_ms


def test_emit_latency_telemetry_unknown_content_type_warns(caplog):
    """Unknown content type → WARNING log + ``slo_threshold_ms=None`` +
    ``slo_breached=False``. Telemetry must never crash the route.
    """
    from app.services.cmcp.generation_telemetry import emit_latency_telemetry

    caplog.set_level(
        logging.WARNING, logger="app.services.cmcp.generation_telemetry"
    )
    emit_latency_telemetry(
        content_type="BOGUS_TYPE",
        latency_ms=1_000_000,  # would be a breach for any real type
        request_id="rid-x",
    )

    records = [
        r for r in caplog.records
        if getattr(r, "event", None) == "cmcp.generation.latency"
    ]
    assert len(records) == 1
    rec = records[0]
    assert rec.content_type == "BOGUS_TYPE"
    assert rec.slo_threshold_ms is None
    assert rec.slo_breached is False
    assert rec.levelname == "WARNING"


def test_emit_latency_telemetry_clamps_negative_latency(caplog):
    """Negative latency (defensive — would only happen if a future
    caller passed bad arithmetic) is clamped to 0 rather than emitted
    as a negative ``latency_ms``.
    """
    from app.services.cmcp.generation_telemetry import emit_latency_telemetry

    caplog.set_level(
        logging.INFO, logger="app.services.cmcp.generation_telemetry"
    )
    emit_latency_telemetry(
        content_type="QUIZ",
        latency_ms=-50,
        request_id="rid-clamp",
    )

    records = [
        r for r in caplog.records
        if getattr(r, "event", None) == "cmcp.generation.latency"
    ]
    assert len(records) == 1
    assert records[0].latency_ms == 0
    assert records[0].slo_breached is False


# ──────────────────────────────────────────────────────────────────────
# Layer 2 — Integration tests on the sync route
# ──────────────────────────────────────────────────────────────────────
#
# Reuse the same fixture pattern as ``test_cmcp_generate_route.py`` so
# the route's flag-gate + DB resolution path is exercised end-to-end.
# The freeze-time-style assertion is a deterministic ``perf_counter``
# patch so ``latency_ms`` is exact.


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

    email = f"cmcptel_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPTel {role.value}",
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
def seeded_curriculum(db_session):
    """Seed a Grade-7 ``MATH-XXXX`` slice with one OE + two SEs.

    Mirrors ``test_cmcp_generate_route.py`` / ``test_cmcp_generate_stream.py``
    seeds; uses a uuid-suffixed subject code so this test file's seed
    doesn't collide on the session-scoped DB.
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
    subject_code = f"T{suffix}"
    strand_code = "B"
    version_slug = f"test-tel-{uuid4().hex[:6]}"

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


def _make_perf_counter(start_s: float, end_s: float):
    """Build a ``perf_counter`` replacement that returns ``start_s`` on
    first call and ``end_s`` on every subsequent call.

    Mirrors the ``freeze_time`` style requested in the issue: tests
    assert exact ``latency_ms`` values, which only works if the timing
    function is deterministic. Returning ``end_s`` on every call after
    the first keeps the helper resilient to a future revision that
    measures intermediate splits without re-writing every test's value
    list.
    """
    state = {"first": True}

    def fake_perf_counter() -> float:
        if state["first"]:
            state["first"] = False
            return start_s
        return end_s

    return fake_perf_counter


def test_sync_route_emits_latency_telemetry_below_slo(
    client, parent_user, cmcp_flag_on, seeded_curriculum, caplog
):
    """Happy-path QUIZ generation under 8s → telemetry line emitted with
    ``slo_breached=False`` and the exact patched latency.
    """
    caplog.set_level(
        logging.INFO, logger="app.services.cmcp.generation_telemetry"
    )

    # 0.0s entry, 0.5s exit → latency_ms=500. Well under QUIZ's 8000ms.
    fake_pc = _make_perf_counter(0.0, 0.5)
    with patch(
        "app.api.routes.cmcp_generate.perf_counter",
        side_effect=fake_pc,
    ):
        headers = _auth(client, parent_user.email)
        resp = client.post(
            "/api/cmcp/generate",
            json=_payload(seeded_curriculum, content_type="QUIZ"),
            headers=headers,
        )

    assert resp.status_code == 200, resp.text

    records = [
        r for r in caplog.records
        if getattr(r, "event", None) == "cmcp.generation.latency"
    ]
    assert len(records) == 1
    rec = records[0]
    assert rec.content_type == "QUIZ"
    assert rec.latency_ms == 500
    assert rec.slo_threshold_ms == 8_000
    assert rec.slo_breached is False
    assert isinstance(rec.request_id, str) and len(rec.request_id) > 0


def test_sync_route_emits_breach_telemetry_when_over_slo(
    client, parent_user, cmcp_flag_on, seeded_curriculum, caplog
):
    """Patched 9s latency for QUIZ → ``slo_breached=True``. Mutation-test
    guard for the integration wiring: a route that fails to call
    ``emit_latency_telemetry`` would have zero records, and a route that
    uses the wrong content_type literal would log against the wrong
    threshold table entry.
    """
    caplog.set_level(
        logging.INFO, logger="app.services.cmcp.generation_telemetry"
    )

    # 0.0s entry, 9.0s exit → 9000ms. QUIZ SLO=8000ms → breach.
    fake_pc = _make_perf_counter(0.0, 9.0)
    with patch(
        "app.api.routes.cmcp_generate.perf_counter",
        side_effect=fake_pc,
    ):
        headers = _auth(client, parent_user.email)
        resp = client.post(
            "/api/cmcp/generate",
            json=_payload(seeded_curriculum, content_type="QUIZ"),
            headers=headers,
        )

    assert resp.status_code == 200, resp.text

    records = [
        r for r in caplog.records
        if getattr(r, "event", None) == "cmcp.generation.latency"
    ]
    assert len(records) == 1
    rec = records[0]
    assert rec.content_type == "QUIZ"
    assert rec.latency_ms == 9_000
    assert rec.slo_breached is True


def test_sync_route_emits_telemetry_on_422_path(
    client, parent_user, cmcp_flag_on, seeded_curriculum, caplog
):
    """Even when the route 422s (e.g., unknown subject_code), the
    telemetry line still fires from the ``finally`` block. Important:
    breach analytics must include failed requests so per-type 4xx +
    success share one denominator.
    """
    caplog.set_level(
        logging.INFO, logger="app.services.cmcp.generation_telemetry"
    )

    fake_pc = _make_perf_counter(0.0, 0.05)
    with patch(
        "app.api.routes.cmcp_generate.perf_counter",
        side_effect=fake_pc,
    ):
        headers = _auth(client, parent_user.email)
        body = _payload(seeded_curriculum, subject_code="UNKNOWNXYZ")
        resp = client.post(
            "/api/cmcp/generate", json=body, headers=headers
        )

    assert resp.status_code == 422

    records = [
        r for r in caplog.records
        if getattr(r, "event", None) == "cmcp.generation.latency"
    ]
    assert len(records) == 1
    rec = records[0]
    assert rec.content_type == "QUIZ"
    assert rec.latency_ms == 50
    assert rec.slo_breached is False


# ──────────────────────────────────────────────────────────────────────
# Layer 3 — Integration tests on the streaming route
# ──────────────────────────────────────────────────────────────────────


def _make_fake_stream(chunks):
    """Same fake-stream factory as ``test_cmcp_generate_stream.py``."""
    async def fake(*_args, **_kwargs) -> AsyncIterator[dict]:
        for c in chunks:
            yield {"event": "chunk", "data": c}
        yield {
            "event": "done",
            "data": {"is_truncated": False, "full_content": "".join(chunks)},
        }

    return fake


def _patch_stream(fake):
    return patch(
        "app.api.routes.cmcp_generate_stream.generate_content_stream",
        side_effect=fake,
    )


def test_stream_route_emits_latency_telemetry_below_slo(
    client, parent_user, cmcp_flag_on, seeded_curriculum, caplog
):
    """Long-form STUDY_GUIDE under SLO → ``slo_breached=False`` + correct
    latency. Telemetry fires from the ``event_stream`` ``finally`` block
    after the ``done`` frame is yielded.
    """
    caplog.set_level(
        logging.INFO, logger="app.services.cmcp.generation_telemetry"
    )

    # Stream needs perf_counter at entry (start) + after-stream (end).
    # 0s start, 10s end → 10_000ms. STUDY_GUIDE SLO=25_000 → no breach.
    fake_pc = _make_perf_counter(0.0, 10.0)
    fake_stream = _make_fake_stream(["chunk-1", "chunk-2"])
    with patch(
        "app.api.routes.cmcp_generate_stream.perf_counter",
        side_effect=fake_pc,
    ), _patch_stream(fake_stream):
        headers = _auth(client, parent_user.email)
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=_payload(seeded_curriculum, content_type="STUDY_GUIDE"),
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    # Force the streaming response to drain so the ``finally`` block
    # runs (TestClient already does this when ``.text`` is accessed).
    _ = resp.text

    records = [
        r for r in caplog.records
        if getattr(r, "event", None) == "cmcp.generation.latency"
    ]
    assert len(records) == 1
    rec = records[0]
    assert rec.content_type == "STUDY_GUIDE"
    assert rec.latency_ms == 10_000
    assert rec.slo_threshold_ms == 25_000
    assert rec.slo_breached is False


def test_stream_route_emits_breach_telemetry_when_over_slo(
    client, parent_user, cmcp_flag_on, seeded_curriculum, caplog
):
    """STUDY_GUIDE stream exceeds 25s → ``slo_breached=True``."""
    caplog.set_level(
        logging.INFO, logger="app.services.cmcp.generation_telemetry"
    )

    # 0s start, 30s end → 30_000ms. STUDY_GUIDE SLO=25_000 → breach.
    fake_pc = _make_perf_counter(0.0, 30.0)
    fake_stream = _make_fake_stream(["x"])
    with patch(
        "app.api.routes.cmcp_generate_stream.perf_counter",
        side_effect=fake_pc,
    ), _patch_stream(fake_stream):
        headers = _auth(client, parent_user.email)
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=_payload(seeded_curriculum, content_type="STUDY_GUIDE"),
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    _ = resp.text

    records = [
        r for r in caplog.records
        if getattr(r, "event", None) == "cmcp.generation.latency"
    ]
    assert len(records) == 1
    rec = records[0]
    assert rec.content_type == "STUDY_GUIDE"
    assert rec.latency_ms == 30_000
    assert rec.slo_breached is True


def test_stream_route_emits_telemetry_on_400_short_form_redirect(
    client, parent_user, cmcp_flag_on, seeded_curriculum, caplog
):
    """Short-form QUIZ on the stream endpoint → 400, but telemetry still
    fires for the gating-only path. Important: breach dashboards see the
    400 path as a fast no-breach sample, not a missing data point.
    """
    caplog.set_level(
        logging.INFO, logger="app.services.cmcp.generation_telemetry"
    )

    fake_pc = _make_perf_counter(0.0, 0.01)
    with patch(
        "app.api.routes.cmcp_generate_stream.perf_counter",
        side_effect=fake_pc,
    ):
        headers = _auth(client, parent_user.email)
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=_payload(seeded_curriculum, content_type="QUIZ"),
            headers=headers,
        )

    assert resp.status_code == 400

    records = [
        r for r in caplog.records
        if getattr(r, "event", None) == "cmcp.generation.latency"
    ]
    assert len(records) == 1
    rec = records[0]
    assert rec.content_type == "QUIZ"
    assert rec.latency_ms == 10
    assert rec.slo_breached is False


def test_stream_route_emits_telemetry_on_422_path(
    client, parent_user, cmcp_flag_on, seeded_curriculum, caplog
):
    """Stream-route 422 (unknown subject) → telemetry still fires from
    the prep-phase ``except HTTPException`` branch. Per-type failure
    rate dashboards depend on this.
    """
    caplog.set_level(
        logging.INFO, logger="app.services.cmcp.generation_telemetry"
    )

    fake_pc = _make_perf_counter(0.0, 0.02)
    with patch(
        "app.api.routes.cmcp_generate_stream.perf_counter",
        side_effect=fake_pc,
    ):
        headers = _auth(client, parent_user.email)
        body = _payload(
            seeded_curriculum,
            content_type="STUDY_GUIDE",
            subject_code="UNKNOWNXYZ",
        )
        resp = client.post(
            "/api/cmcp/generate/stream", json=body, headers=headers
        )

    assert resp.status_code == 422

    records = [
        r for r in caplog.records
        if getattr(r, "event", None) == "cmcp.generation.latency"
    ]
    assert len(records) == 1
    rec = records[0]
    assert rec.content_type == "STUDY_GUIDE"
    assert rec.latency_ms == 20
    assert rec.slo_breached is False
