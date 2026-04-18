"""Tests for the demo verification service (CB-DEMO-001 F3, #3602)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest


def _email_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _make_session(
    db_session,
    *,
    email: str,
    role: str = "parent",
    full_name: str | None = "Test User",
):
    from app.models.demo_session import DemoSession

    session = DemoSession(
        email_hash=_email_hash(email),
        email=email,
        full_name=full_name,
        role=role,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


class TestTokenIssuance:
    # All tests depend on `app` via `db_session` so conftest reloads the
    # models/services modules before our service is imported (prevents a
    # stale DemoSession mapper binding when this file runs in a full suite).

    def test_magic_link_returns_raw_and_hash(self, db_session):
        from app.services.demo_verification import create_magic_link_token

        raw, hashed = create_magic_link_token("sess-1", "a@b.com")
        assert raw
        assert hashed
        assert raw != hashed
        assert hashed == hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def test_magic_link_tokens_unique_across_calls(self, db_session):
        from app.services.demo_verification import create_magic_link_token

        raws = set()
        hashes = set()
        for _ in range(20):
            raw, hashed = create_magic_link_token("sess", "a@b.com")
            raws.add(raw)
            hashes.add(hashed)
        assert len(raws) == 20
        assert len(hashes) == 20

    def test_magic_link_raw_token_is_urlsafe(self, db_session):
        from app.services.demo_verification import create_magic_link_token

        raw, _ = create_magic_link_token("sess", "a@b.com")
        # token_urlsafe(32) => ~43 chars, url-safe alphabet only.
        allowed = set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        )
        assert set(raw) <= allowed
        assert len(raw) >= 32

    def test_fallback_code_is_six_digits_zero_padded(self, db_session):
        from app.services.demo_verification import create_fallback_code

        for _ in range(100):
            raw, hashed = create_fallback_code()
            assert len(raw) == 6, f"expected 6 digits, got {raw!r}"
            assert raw.isdigit()
            assert 100_000 <= int(raw) <= 999_999
            assert hashed == hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def test_fallback_codes_differ_across_calls(self, db_session):
        from app.services.demo_verification import create_fallback_code

        codes = {create_fallback_code()[0] for _ in range(50)}
        # With 900k possible codes the chance of a dup in 50 draws is tiny.
        assert len(codes) >= 49


class TestMagicLinkVerification:
    def test_valid_token_returns_session_and_marks_verified(self, db_session):
        from app.services.demo_verification import (
            create_magic_link_token,
            set_verification_credentials,
            verify_magic_link,
        )

        session = _make_session(db_session, email="mlv_ok@example.com")
        raw, tok_hash = create_magic_link_token(session.id, session.email)
        # Need a code hash too; use a stub since the test exercises magic link.
        set_verification_credentials(
            db_session, session, token_hash=tok_hash, code_hash="x" * 64
        )
        db_session.commit()

        result = verify_magic_link(db_session, raw)
        assert result is not None
        assert result.id == session.id
        assert result.verified is True
        assert result.verified_ts is not None
        # Single-use: credential columns cleared.
        assert result.verification_token_hash is None
        assert result.verification_expires_at is None
        assert result.fallback_code_hash is None
        assert result.fallback_code_expires_at is None

    def test_wrong_token_returns_none(self, db_session):
        from app.services.demo_verification import (
            create_magic_link_token,
            set_verification_credentials,
            verify_magic_link,
        )

        session = _make_session(db_session, email="mlv_wrong@example.com")
        _, tok_hash = create_magic_link_token(session.id, session.email)
        set_verification_credentials(
            db_session, session, token_hash=tok_hash, code_hash="x" * 64
        )
        db_session.commit()

        assert verify_magic_link(db_session, "not-the-real-token") is None
        db_session.refresh(session)
        assert session.verified is False

    def test_expired_token_returns_none(self, db_session):
        from app.services.demo_verification import (
            create_magic_link_token,
            verify_magic_link,
        )

        session = _make_session(db_session, email="mlv_expired@example.com")
        raw, tok_hash = create_magic_link_token(session.id, session.email)
        session.verification_token_hash = tok_hash
        session.verification_expires_at = datetime.now(timezone.utc) - timedelta(
            seconds=1
        )
        db_session.commit()

        assert verify_magic_link(db_session, raw) is None
        db_session.refresh(session)
        assert session.verified is False

    def test_already_verified_token_returns_none(self, db_session):
        """Replay attempt after session already marked verified."""
        from app.services.demo_verification import (
            create_magic_link_token,
            verify_magic_link,
        )

        session = _make_session(db_session, email="mlv_replay@example.com")
        raw, tok_hash = create_magic_link_token(session.id, session.email)
        # Put the hash back (simulating DB where someone cleared `verified`
        # reset via admin but still kept stale hash).
        session.verification_token_hash = tok_hash
        session.verification_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=1
        )
        session.verified = True
        session.verified_ts = datetime.now(timezone.utc)
        db_session.commit()

        assert verify_magic_link(db_session, raw) is None

    def test_empty_token_returns_none(self, db_session):
        from app.services.demo_verification import verify_magic_link

        assert verify_magic_link(db_session, "") is None

    def test_expiry_boundary_one_second_before_works(self, db_session):
        from app.services.demo_verification import (
            create_magic_link_token,
            verify_magic_link,
        )

        session = _make_session(db_session, email="mlv_boundary_ok@example.com")
        raw, tok_hash = create_magic_link_token(session.id, session.email)
        session.verification_token_hash = tok_hash
        # +5s safety buffer vs. test wall time.
        session.verification_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=5
        )
        db_session.commit()

        assert verify_magic_link(db_session, raw) is not None

    def test_expiry_boundary_one_second_after_fails(self, db_session):
        from app.services.demo_verification import (
            create_magic_link_token,
            verify_magic_link,
        )

        session = _make_session(db_session, email="mlv_boundary_fail@example.com")
        raw, tok_hash = create_magic_link_token(session.id, session.email)
        session.verification_token_hash = tok_hash
        session.verification_expires_at = datetime.now(timezone.utc) - timedelta(
            seconds=1
        )
        db_session.commit()

        assert verify_magic_link(db_session, raw) is None


class TestFallbackCodeVerification:
    def test_valid_code_returns_session(self, db_session):
        from app.services.demo_verification import (
            create_fallback_code,
            set_verification_credentials,
            verify_fallback_code,
        )

        email = "fc_ok@example.com"
        session = _make_session(db_session, email=email)
        raw_code, code_hash = create_fallback_code()
        set_verification_credentials(
            db_session, session, token_hash="y" * 64, code_hash=code_hash
        )
        db_session.commit()

        result = verify_fallback_code(db_session, email, raw_code)
        assert result is not None
        assert result.id == session.id
        assert result.verified is True
        assert result.fallback_code_hash is None

    def test_email_match_is_case_insensitive(self, db_session):
        from app.services.demo_verification import (
            create_fallback_code,
            set_verification_credentials,
            verify_fallback_code,
        )

        session = _make_session(db_session, email="fc_case@example.com")
        raw_code, code_hash = create_fallback_code()
        set_verification_credentials(
            db_session, session, token_hash="y" * 64, code_hash=code_hash
        )
        db_session.commit()

        result = verify_fallback_code(db_session, "FC_Case@Example.COM", raw_code)
        assert result is not None
        assert result.id == session.id

    def test_wrong_code_returns_none(self, db_session):
        from app.services.demo_verification import (
            create_fallback_code,
            set_verification_credentials,
            verify_fallback_code,
        )

        email = "fc_wrong@example.com"
        session = _make_session(db_session, email=email)
        _, code_hash = create_fallback_code()
        set_verification_credentials(
            db_session, session, token_hash="y" * 64, code_hash=code_hash
        )
        db_session.commit()

        assert verify_fallback_code(db_session, email, "000000") is None
        db_session.refresh(session)
        assert session.verified is False

    def test_wrong_email_returns_none(self, db_session):
        from app.services.demo_verification import (
            create_fallback_code,
            set_verification_credentials,
            verify_fallback_code,
        )

        session = _make_session(db_session, email="fc_right@example.com")
        raw_code, code_hash = create_fallback_code()
        set_verification_credentials(
            db_session, session, token_hash="y" * 64, code_hash=code_hash
        )
        db_session.commit()

        assert (
            verify_fallback_code(db_session, "fc_wrong_email@example.com", raw_code)
            is None
        )

    def test_expired_code_returns_none(self, db_session):
        from app.services.demo_verification import (
            create_fallback_code,
            verify_fallback_code,
        )

        email = "fc_expired@example.com"
        session = _make_session(db_session, email=email)
        raw_code, code_hash = create_fallback_code()
        session.fallback_code_hash = code_hash
        session.fallback_code_expires_at = datetime.now(timezone.utc) - timedelta(
            seconds=1
        )
        db_session.commit()

        assert verify_fallback_code(db_session, email, raw_code) is None

    def test_already_verified_returns_none(self, db_session):
        from app.services.demo_verification import (
            create_fallback_code,
            verify_fallback_code,
        )

        email = "fc_already@example.com"
        session = _make_session(db_session, email=email)
        raw_code, code_hash = create_fallback_code()
        session.fallback_code_hash = code_hash
        session.fallback_code_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=1
        )
        session.verified = True
        session.verified_ts = datetime.now(timezone.utc)
        db_session.commit()

        assert verify_fallback_code(db_session, email, raw_code) is None

    def test_empty_inputs_return_none(self, db_session):
        from app.services.demo_verification import verify_fallback_code

        assert verify_fallback_code(db_session, "", "123456") is None
        assert verify_fallback_code(db_session, "a@b.com", "") is None


class TestHashDeterminism:
    def test_sha256_matches_stored_hash(self, db_session):
        from app.services.demo_verification import (
            create_fallback_code,
            create_magic_link_token,
        )

        raw_tok, tok_hash = create_magic_link_token("sess", "a@b.com")
        raw_code, code_hash = create_fallback_code()

        assert hashlib.sha256(raw_tok.encode("utf-8")).hexdigest() == tok_hash
        assert hashlib.sha256(raw_code.encode("utf-8")).hexdigest() == code_hash

    def test_raw_token_is_not_stored(self, db_session):
        """Only the hash should ever be persisted on the row."""
        from app.services.demo_verification import (
            create_magic_link_token,
            set_verification_credentials,
        )

        session = _make_session(db_session, email="hash_check@example.com")
        raw, tok_hash = create_magic_link_token(session.id, session.email)
        set_verification_credentials(
            db_session, session, token_hash=tok_hash, code_hash="z" * 64
        )
        db_session.commit()
        db_session.refresh(session)

        assert session.verification_token_hash == tok_hash
        assert session.verification_token_hash != raw


class TestEmailTemplate:
    def test_builds_subject_and_html(self, db_session):
        from app.services.email_templates.demo_verification import (
            build_demo_verification_email,
        )

        subject, html = build_demo_verification_email(
            full_name="Jane Doe",
            email="jane@example.com",
            magic_link_url="https://www.classbridge.ca/demo/verify?token=abc",
            fallback_code="123456",
        )
        assert subject == "Verify your ClassBridge demo"
        assert "Jane Doe" in html
        assert "https://www.classbridge.ca/demo/verify?token=abc" in html
        assert "123456" in html
        assert "72 hours" in html
        assert "didn't start this demo" in html

    def test_greeting_falls_back_to_email_when_name_missing(self, db_session):
        from app.services.email_templates.demo_verification import (
            build_demo_verification_email,
        )

        _, html = build_demo_verification_email(
            full_name=None,
            email="jane@example.com",
            magic_link_url="https://example.com/x",
            fallback_code="000123",
        )
        assert "jane@example.com" in html

    def test_html_is_branded(self, db_session):
        """Wrapped body should include the branded header/footer layout."""
        from app.services.email_templates.demo_verification import (
            build_demo_verification_email,
        )

        _, html = build_demo_verification_email(
            full_name="X",
            email="x@y.com",
            magic_link_url="https://example.com/x",
            fallback_code="654321",
        )
        assert "<!DOCTYPE html>" in html
        assert "classbridge-logo.png" in html

    def test_html_escapes_user_supplied_full_name(self, db_session):
        """XSS guard: an HTML-tag full_name must be rendered as escaped text."""
        from app.services.email_templates.demo_verification import (
            build_demo_verification_email,
        )

        _, html = build_demo_verification_email(
            full_name='<script>alert(1)</script>',
            email="attacker@example.com",
            magic_link_url="https://example.com/verify?token=abc",
            fallback_code="000000",
        )
        # The literal tag must NOT appear; the escaped form must appear.
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html

    def test_html_escapes_magic_link_url(self, db_session):
        """An attacker-ish URL with quotes must not break out of the href attribute."""
        from app.services.email_templates.demo_verification import (
            build_demo_verification_email,
        )

        _, html = build_demo_verification_email(
            full_name="Jane",
            email="jane@example.com",
            magic_link_url='https://example.com/x"><script>bad()</script><a href="',
            fallback_code="123456",
        )
        assert '<script>bad()</script>' not in html
        # Escaped double-quote should appear in the href value.
        assert "&quot;" in html or "&#x27;" in html or "&#34;" in html
