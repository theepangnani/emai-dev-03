"""Tests for demo public routes (CB-DEMO-001 B1, #3603).

Covers POST /api/v1/demo/sessions and POST /api/v1/demo/generate.
Anthropic streaming is mocked using the same FakeStream pattern used
by tests/test_ai_service_streaming.py.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────


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


# ── Anthropic streaming mock (mirrors test_ai_service_streaming.py) ───


class FakeTextStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._idx]
        self._idx += 1
        return chunk


class FakeStreamContext:
    def __init__(self, chunks, input_tokens=12, output_tokens=34, stop_reason="end_turn"):
        self._chunks = chunks
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._stop_reason = stop_reason

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    @property
    def text_stream(self):
        return FakeTextStream(self._chunks)

    async def get_final_message(self):
        msg = MagicMock()
        msg.usage.input_tokens = self._input_tokens
        msg.usage.output_tokens = self._output_tokens
        msg.stop_reason = self._stop_reason
        return msg


def _mock_anthropic_client(chunks, input_tokens=12, output_tokens=34):
    client = MagicMock()
    client.messages.stream.return_value = FakeStreamContext(
        chunks, input_tokens=input_tokens, output_tokens=output_tokens
    )
    return client


# ── POST /sessions ────────────────────────────────────────────────────


class TestCreateSession:
    def _payload(self, **overrides):
        base = {
            "email": "alice@example.com",
            "full_name": "Alice A",
            "role": "parent",
            "consent": True,
        }
        base.update(overrides)
        return base

    def test_happy_path_creates_row_and_sends_email(self, client, db_session):
        from app.models.demo_session import DemoSession

        with patch(
            "app.api.routes.demo.send_email_sync", return_value=True
        ) as mock_send:
            resp = client.post(
                "/api/v1/demo/sessions",
                json=self._payload(email="happy@example.com"),
            )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["verification_required"] is True
        assert isinstance(data["session_jwt"], str) and data["session_jwt"]
        assert isinstance(data["waitlist_preview_position"], int)
        assert data["waitlist_preview_position"] >= 0

        # Row inserted with a hash + pending status.
        row = (
            db_session.query(DemoSession)
            .filter(DemoSession.email == "happy@example.com")
            .first()
        )
        assert row is not None
        assert row.email_hash == _email_hash("happy@example.com")
        assert row.admin_status == "pending"
        assert row.consent_ts is not None
        assert row.verification_token_hash  # credentials persisted
        assert row.fallback_code_hash

        # Email attempted exactly once.
        assert mock_send.call_count == 1
        args, _kwargs = mock_send.call_args
        assert args[0] == "happy@example.com"

    def test_disposable_email_rejected(self, client, db_session):
        with patch("app.api.routes.demo.send_email_sync", return_value=True):
            resp = client.post(
                "/api/v1/demo/sessions",
                json=self._payload(email="spam@mailinator.com"),
            )
        assert resp.status_code == 400

        from app.models.demo_session import DemoSession
        assert db_session.query(DemoSession).count() == 0

    def test_consent_false_rejected(self, client, db_session):
        with patch("app.api.routes.demo.send_email_sync", return_value=True):
            resp = client.post(
                "/api/v1/demo/sessions",
                json=self._payload(consent=False),
            )
        assert resp.status_code == 400

        from app.models.demo_session import DemoSession
        assert db_session.query(DemoSession).count() == 0

    def test_honeypot_rejected(self, client, db_session):
        with patch("app.api.routes.demo.send_email_sync", return_value=True):
            resp = client.post(
                "/api/v1/demo/sessions",
                json={**self._payload(), "_hp": "i-am-a-bot"},
            )
        assert resp.status_code == 400

        from app.models.demo_session import DemoSession
        assert db_session.query(DemoSession).count() == 0

    def test_honeypot_empty_string_accepted(self, client, db_session):
        """Honeypot only trips on non-empty values — empty string is fine."""
        with patch("app.api.routes.demo.send_email_sync", return_value=True):
            resp = client.post(
                "/api/v1/demo/sessions",
                json={**self._payload(email="hp-ok@example.com"), "_hp": ""},
            )
        assert resp.status_code == 201


# ── POST /generate — auth / validation ────────────────────────────────


def _make_session_row(
    db_session,
    *,
    email: str = "gen@example.com",
    ip_hash: str = "ip-abc",
    admin_status: str = "pending",
):
    from app.models.demo_session import DemoSession

    session = DemoSession(
        email_hash=_email_hash(email),
        email=email,
        role="parent",
        source_ip_hash=ip_hash,
        admin_status=admin_status,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def _jwt_for(session_id: str) -> str:
    from app.api.routes.demo import _create_demo_session_jwt
    return _create_demo_session_jwt(session_id)


class TestGenerateAuth:
    def test_missing_jwt_returns_401(self, client):
        resp = client.post(
            "/api/v1/demo/generate",
            json={"demo_type": "ask", "question": "hi"},
        )
        assert resp.status_code == 401

    def test_blocklisted_session_returns_403(self, client, db_session):
        session = _make_session_row(
            db_session, email="blk@example.com", admin_status="blocklisted"
        )
        token = _jwt_for(session.id)
        resp = client.post(
            "/api/v1/demo/generate",
            json={"demo_type": "ask", "question": "hi"},
            headers={"X-Demo-Session": token},
        )
        assert resp.status_code == 403

    def test_input_over_500_words_returns_400(self, client, db_session):
        session = _make_session_row(db_session, email="long@example.com")
        token = _jwt_for(session.id)
        # 501 one-letter "words" — passes the 4000-char source_text cap
        # but trips the 500-word demo_rate_limit check.
        long_text = " ".join("x" for _ in range(501))
        resp = client.post(
            "/api/v1/demo/generate",
            json={"demo_type": "study_guide", "source_text": long_text},
            headers={"X-Demo-Session": token},
        )
        assert resp.status_code == 400


class TestGenerateCostCap:
    def test_over_cost_cap_returns_503(self, client, db_session):
        """Pre-seed >= $10 (1000 cents) of generations → 503 warming up."""
        from app.services.demo_rate_limit import record_generation

        session = _make_session_row(
            db_session, email="capped@example.com", ip_hash="ip-cap"
        )
        # One expensive row is enough to breach the cap.
        record_generation(
            db_session, session,
            demo_type="ask",
            latency_ms=100, input_tokens=0, output_tokens=0,
            cost_cents=1000,
        )

        token = _jwt_for(session.id)
        resp = client.post(
            "/api/v1/demo/generate",
            json={"demo_type": "ask", "question": "What is photosynthesis?"},
            headers={"X-Demo-Session": token},
        )
        assert resp.status_code == 503
        body = resp.json()
        detail = body["detail"] if isinstance(body.get("detail"), dict) else body
        assert detail.get("error") == "demo_warming_up"
        assert "warming up" in detail.get("message", "").lower()


class TestGenerateHappyPath:
    def test_streams_and_records(self, client, db_session):
        from app.models.demo_session import DemoSession

        session = _make_session_row(
            db_session, email="ok@example.com", ip_hash="ip-ok"
        )
        token = _jwt_for(session.id)

        mock_client = _mock_anthropic_client(
            ["Hello ", "world", "!"], input_tokens=15, output_tokens=30
        )
        with patch(
            "app.services.demo_generation.get_async_anthropic_client",
            return_value=mock_client,
        ):
            resp = client.post(
                "/api/v1/demo/generate",
                json={"demo_type": "ask", "question": "What is a cell?"},
                headers={"X-Demo-Session": token},
            )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = resp.text
        # SSE frames present.
        assert "event: token" in body
        assert '"chunk": "Hello "' in body
        assert '"chunk": "world"' in body
        assert "event: done" in body

        # Generation was recorded on the demo session.
        db_session.expire_all()
        refreshed = (
            db_session.query(DemoSession)
            .filter(DemoSession.id == session.id)
            .first()
        )
        assert refreshed is not None
        assert refreshed.generations_count == 1
        events = refreshed.generations_json or []
        assert len(events) == 1
        assert events[0]["demo_type"] == "ask"
        assert events[0]["input_tokens"] == 15
        assert events[0]["output_tokens"] == 30
        assert events[0]["cost_cents"] >= 1

    def test_uses_reserve_and_update_helpers(self, client, db_session):
        """#3666 — /generate must reserve a slot BEFORE streaming and
        update it AFTER, not call the legacy record_generation path."""
        session = _make_session_row(
            db_session, email="wire@example.com", ip_hash="ip-wire"
        )
        token = _jwt_for(session.id)

        mock_client = _mock_anthropic_client(
            ["a", "b"], input_tokens=5, output_tokens=7
        )
        with patch(
            "app.services.demo_generation.get_async_anthropic_client",
            return_value=mock_client,
        ), patch(
            "app.api.routes.demo.reserve_generation_slot",
            wraps=__import__(
                "app.services.demo_rate_limit",
                fromlist=["reserve_generation_slot"],
            ).reserve_generation_slot,
        ) as mock_reserve, patch(
            "app.api.routes.demo.update_generation_slot",
            wraps=__import__(
                "app.services.demo_rate_limit",
                fromlist=["update_generation_slot"],
            ).update_generation_slot,
        ) as mock_update:
            resp = client.post(
                "/api/v1/demo/generate",
                json={"demo_type": "ask", "question": "Q?"},
                headers={"X-Demo-Session": token},
            )

        assert resp.status_code == 200
        assert mock_reserve.call_count == 1
        assert mock_update.call_count == 1


# ── Prompt + cost helpers ─────────────────────────────────────────────


class TestPromptAndCostHelpers:
    def test_load_prompt_ask_returns_system_and_user(self):
        from app.services.demo_generation import load_prompt

        system, user = load_prompt("ask")
        assert system
        # The ask prompt enforces the demo footer rule in its system text.
        assert "This is a ClassBridge demo preview." in system
        # User template contains the {{question}} placeholder.
        assert "{{question}}" in user

    def test_load_prompt_unknown_raises(self):
        from app.services.demo_generation import load_prompt

        with pytest.raises(ValueError):
            load_prompt("nope")

    def test_estimate_cost_cents_zero_tokens_floors_at_one(self):
        from app.services.demo_generation import estimate_cost_cents

        assert estimate_cost_cents(0, 0) == 1

    def test_estimate_cost_cents_positive_for_any_tokens(self):
        from app.services.demo_generation import estimate_cost_cents

        assert estimate_cost_cents(1, 1) >= 1
        assert estimate_cost_cents(1_000_000, 1_000_000) > 1


# ── Missing coverage (#3668) ──────────────────────────────────────────


class _RaisingStreamContext:
    """Mimics ``client.messages.stream(...)`` but raises on __aenter__."""
    def __init__(self, exc):
        self._exc = exc

    async def __aenter__(self):
        raise self._exc

    async def __aexit__(self, *args):
        return False


def _mock_client_that_raises(exc):
    client = MagicMock()
    client.messages.stream.return_value = _RaisingStreamContext(exc)
    return client


class TestGenerateStreamFailure:
    def test_anthropic_stream_error_emits_sse_error_and_skips_update(
        self, client, db_session
    ):
        """Anthropic raises APIStatusError → SSE 'event: error'.

        With the #3666 rate-limit race fix, the slot is RESERVED before
        the stream starts (generations_count becomes 1). On stream error
        the placeholder persists as defensive rate-limit accounting, but
        ``update_generation_slot`` must NOT fire — so the placeholder
        keeps ``cost_cents=0`` and does not falsely pad the daily cap.
        """
        import anthropic
        import httpx
        from app.models.demo_session import DemoSession

        session = _make_session_row(
            db_session, email="err@example.com", ip_hash="ip-err"
        )
        assert session.generations_count == 0
        token = _jwt_for(session.id)

        # Build a real APIStatusError — it requires an httpx.Response + body.
        response = httpx.Response(
            status_code=500,
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        )
        stream_exc = anthropic.APIStatusError(
            "upstream blew up", response=response, body=None
        )
        mock_client = _mock_client_that_raises(stream_exc)

        with patch(
            "app.services.demo_generation.get_async_anthropic_client",
            return_value=mock_client,
        ), patch(
            "app.api.routes.demo.update_generation_slot"
        ) as mock_update:
            resp = client.post(
                "/api/v1/demo/generate",
                json={"demo_type": "ask", "question": "hi"},
                headers={"X-Demo-Session": token},
            )

        assert resp.status_code == 200
        body = resp.text
        assert "event: error" in body
        # Stream failed → update_generation_slot must not fire; the
        # reserved placeholder row remains with cost_cents=0.
        assert mock_update.call_count == 0

        db_session.expire_all()
        refreshed = (
            db_session.query(DemoSession)
            .filter(DemoSession.id == session.id)
            .first()
        )
        assert refreshed is not None
        # #3666 — reserved placeholder persists (rate-limit race fix).
        assert refreshed.generations_count == 1
        events = refreshed.generations_json or []
        assert len(events) == 1
        assert events[0]["cost_cents"] == 0  # placeholder, never updated


class TestLoadPromptUnknownTypeRaises:
    def test_nonexistent_demo_type_raises_value_error(self):
        """load_prompt('nonexistent_type') raises ValueError (#3668)."""
        from app.services.demo_generation import load_prompt

        with pytest.raises(ValueError):
            load_prompt("nonexistent_type")


class TestGenerateExpiredJwt:
    def test_expired_jwt_returns_401(self, client, db_session):
        """Expired demo session JWT → 401 (#3668)."""
        from jose import jwt

        from app.core.config import settings

        session = _make_session_row(
            db_session, email="exp@example.com", ip_hash="ip-exp"
        )

        # Hand-craft a demo session JWT with exp in the past.
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {
            "sub": str(session.id),
            "exp": past,
            "iat": past - timedelta(minutes=30),
            "type": "demo_session",
            "jti": "expired-test",
        }
        expired_token = jwt.encode(
            payload, settings.secret_key, algorithm=settings.algorithm
        )

        resp = client.post(
            "/api/v1/demo/generate",
            json={"demo_type": "ask", "question": "hi"},
            headers={"X-Demo-Session": expired_token},
        )
        assert resp.status_code == 401
