"""Tests for demo rate limits, cost cap, disposable-email blocklist (CB-DEMO-001, #3605)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from app.core.disposable_emails import BLOCKED_DOMAINS, is_disposable
from app.services import demo_rate_limit as drl


@pytest.fixture(autouse=True)
def _clean_demo_sessions(db_session):
    """Isolate demo_sessions state between tests in this module."""
    from app.models.demo_session import DemoSession

    db_session.query(DemoSession).delete()
    db_session.commit()
    yield
    db_session.query(DemoSession).delete()
    db_session.commit()


def _email_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _make_session(db, email: str, ip_hash: str = "ip-hash-a"):
    from app.models.demo_session import DemoSession

    session = DemoSession(
        email_hash=_email_hash(email),
        email=email,
        role="parent",
        source_ip_hash=ip_hash,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _record(db, session, *, cost_cents: int = 1, when: datetime | None = None):
    """Append a generation event directly, optionally backdated."""
    if when is None:
        drl.record_generation(
            db,
            session,
            demo_type="ask",
            latency_ms=100,
            input_tokens=10,
            output_tokens=10,
            cost_cents=cost_cents,
        )
        return

    # Backdated: write JSON directly (record_generation uses "now")
    existing = list(session.generations_json or [])
    existing.append(
        {
            "demo_type": "ask",
            "latency_ms": 100,
            "input_tokens": 10,
            "output_tokens": 10,
            "cost_cents": cost_cents,
            "created_at": when.strftime("%Y-%m-%dT%H:%M:%S"),
        }
    )
    session.generations_json = existing
    session.generations_count = (session.generations_count or 0) + 1
    db.add(session)
    db.commit()
    db.refresh(session)


# ── Disposable email blocklist ──────────────────────────────────────


class TestDisposableEmails:
    def test_blocked_domain_rejected(self):
        assert is_disposable("alice@mailinator.com") is True

    def test_clean_domain_allowed(self):
        assert is_disposable("alice@example.com") is False

    def test_case_insensitive(self):
        assert is_disposable("Alice@MaiLinaTor.COM") is True

    def test_all_known_disposables_block(self):
        for domain in BLOCKED_DOMAINS:
            assert is_disposable(f"user@{domain}") is True

    def test_malformed_input_returns_false(self):
        assert is_disposable("") is False
        assert is_disposable("not-an-email") is False

    def test_blocklist_includes_expected_entries(self):
        # Sanity — make sure the well-known set is present.
        expected = {
            "mailinator.com",
            "10minutemail.com",
            "guerrillamail.com",
            "tempmail.io",
            "yopmail.com",
        }
        assert expected.issubset(BLOCKED_DOMAINS)


# ── Email rate limit (FR-050) ───────────────────────────────────────


class TestEmailRateLimit:
    def test_two_generations_allowed(self, db_session):
        session = _make_session(db_session, "rate1@example.com")
        _record(db_session, session)
        _record(db_session, session)

        allowed, _ = drl.check_email_rate_limit(db_session, session.email_hash)
        assert allowed is True

    def test_third_still_allowed(self, db_session):
        session = _make_session(db_session, "rate2@example.com")
        _record(db_session, session)
        _record(db_session, session)

        allowed, _ = drl.check_email_rate_limit(db_session, session.email_hash)
        assert allowed is True  # third generation not yet recorded — still allowed

    def test_fourth_blocked(self, db_session):
        session = _make_session(db_session, "rate3@example.com")
        _record(db_session, session)
        _record(db_session, session)
        _record(db_session, session)  # 3 successful generations in window

        allowed, reason = drl.check_email_rate_limit(db_session, session.email_hash)
        assert allowed is False
        assert reason != ""

    def test_old_generations_outside_window_do_not_count(self, db_session):
        session = _make_session(db_session, "rate4@example.com")
        long_ago = datetime.now(timezone.utc) - timedelta(days=3)
        _record(db_session, session, when=long_ago)
        _record(db_session, session, when=long_ago)
        _record(db_session, session, when=long_ago)

        allowed, _ = drl.check_email_rate_limit(db_session, session.email_hash)
        assert allowed is True


# ── IP rate limit (FR-051) ──────────────────────────────────────────


class TestIpRateLimit:
    def test_ten_allowed_from_single_ip(self, db_session):
        ip_hash = "ip-single"
        for i in range(10):
            s = _make_session(db_session, f"ip{i}@example.com", ip_hash=ip_hash)
            _record(db_session, s)

        # 10 events now recorded under this IP — next check should block
        allowed, reason = drl.check_ip_rate_limit(db_session, ip_hash)
        assert allowed is False
        assert reason != ""

    def test_nine_allowed(self, db_session):
        ip_hash = "ip-nine"
        for i in range(9):
            s = _make_session(db_session, f"ipn{i}@example.com", ip_hash=ip_hash)
            _record(db_session, s)

        allowed, _ = drl.check_ip_rate_limit(db_session, ip_hash)
        assert allowed is True

    def test_different_ip_unaffected(self, db_session):
        for i in range(10):
            s = _make_session(db_session, f"other{i}@example.com", ip_hash="ip-busy")
            _record(db_session, s)

        allowed, _ = drl.check_ip_rate_limit(db_session, "ip-quiet")
        assert allowed is True


# ── Daily cost cap (FR-053) ─────────────────────────────────────────


class TestDailyCostCap:
    def test_under_cap_allowed(self, db_session):
        session = _make_session(db_session, "cost1@example.com")
        _record(db_session, session, cost_cents=500)  # $5
        _record(db_session, session, cost_cents=499)  # $9.99 total

        allowed, _ = drl.check_daily_cost_cap(db_session)
        assert allowed is True

    def test_at_cap_blocked(self, db_session):
        s1 = _make_session(db_session, "cost2@example.com")
        s2 = _make_session(db_session, "cost3@example.com")
        _record(db_session, s1, cost_cents=600)
        _record(db_session, s2, cost_cents=400)  # total = 1000

        allowed, reason = drl.check_daily_cost_cap(db_session)
        assert allowed is False
        assert "warming up" in reason.lower()

    def test_previous_day_not_counted(self, db_session):
        session = _make_session(db_session, "cost4@example.com")
        yesterday = datetime.now(timezone.utc) - timedelta(days=2)
        _record(db_session, session, cost_cents=5000, when=yesterday)

        allowed, _ = drl.check_daily_cost_cap(db_session)
        assert allowed is True


# ── Input word count (FR-052) ───────────────────────────────────────


class TestInputWordCount:
    def test_none_allowed(self):
        ok, _ = drl.check_input_word_count(None)
        assert ok is True

    def test_empty_allowed(self):
        ok, _ = drl.check_input_word_count("")
        assert ok is True

    def test_500_words_allowed(self):
        text = " ".join(["word"] * 500)
        ok, _ = drl.check_input_word_count(text)
        assert ok is True

    def test_501_words_rejected(self):
        text = " ".join(["word"] * 501)
        ok, reason = drl.check_input_word_count(text)
        assert ok is False
        assert "501" in reason or "too long" in reason.lower()


# ── record_generation ───────────────────────────────────────────────


class TestRecordGeneration:
    def test_appends_to_generations_json(self, db_session):
        session = _make_session(db_session, "rec1@example.com")
        assert (session.generations_json or []) == []
        assert session.generations_count == 0

        event = drl.record_generation(
            db_session,
            session,
            demo_type="study_guide",
            latency_ms=250,
            input_tokens=100,
            output_tokens=200,
            cost_cents=3,
        )

        assert event.demo_type == "study_guide"
        assert event.cost_cents == 3
        assert len(session.generations_json) == 1
        assert session.generations_count == 1

        stored = session.generations_json[0]
        assert stored["demo_type"] == "study_guide"
        assert stored["latency_ms"] == 250
        assert stored["input_tokens"] == 100
        assert stored["output_tokens"] == 200
        assert stored["cost_cents"] == 3
        assert "created_at" in stored

    def test_appends_preserves_existing(self, db_session):
        session = _make_session(db_session, "rec2@example.com")
        drl.record_generation(
            db_session, session,
            demo_type="ask", latency_ms=10, input_tokens=1, output_tokens=1, cost_cents=1,
        )
        drl.record_generation(
            db_session, session,
            demo_type="flash_tutor", latency_ms=20, input_tokens=2, output_tokens=2, cost_cents=2,
        )

        assert len(session.generations_json) == 2
        assert session.generations_count == 2
        assert session.generations_json[0]["demo_type"] == "ask"
        assert session.generations_json[1]["demo_type"] == "flash_tutor"
