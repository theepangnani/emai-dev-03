"""Tests for /api/v1/public/waitlist-stats (CB-DEMO-001 B2, #3604)."""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_waitlist(db_session):
    from app.api.routes.public import _clear_cache_for_tests
    from app.models.waitlist import Waitlist

    db_session.query(Waitlist).delete()
    db_session.commit()
    _clear_cache_for_tests()
    yield
    db_session.query(Waitlist).delete()
    db_session.commit()
    _clear_cache_for_tests()


def _seed(db_session, count: int) -> None:
    from app.models.waitlist import Waitlist

    for i in range(count):
        db_session.add(
            Waitlist(
                name=f"User {i}",
                email=f"user{i}@example.com",
                status="pending",
            )
        )
    db_session.commit()


class TestWaitlistStats:
    def test_unauthenticated_allowed(self, client):
        resp = client.get("/api/v1/public/waitlist-stats")
        assert resp.status_code == 200

    def test_total_hidden_below_threshold(self, client, db_session):
        _seed(db_session, 10)
        resp = client.get("/api/v1/public/waitlist-stats")
        assert resp.status_code == 200
        body = resp.json()
        # FR-106 — hide total when below 50.
        assert body["total"] is None
        assert body["by_municipality"] == []

    def test_total_visible_at_threshold(self, client, db_session):
        _seed(db_session, 50)
        resp = client.get("/api/v1/public/waitlist-stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 50
        assert isinstance(body["by_municipality"], list)

    def test_by_municipality_is_array(self, client, db_session):
        _seed(db_session, 5)
        resp = client.get("/api/v1/public/waitlist-stats")
        assert resp.status_code == 200
        assert isinstance(resp.json()["by_municipality"], list)

    def test_cache_avoids_second_db_hit(self, client, db_session):
        from app.api.routes import public as public_module

        _seed(db_session, 3)

        # First call populates the cache.
        resp1 = client.get("/api/v1/public/waitlist-stats")
        assert resp1.status_code == 200

        # Second call: assert _compute_stats is NOT called again.
        with patch.object(
            public_module, "_compute_stats", wraps=public_module._compute_stats
        ) as spy:
            resp2 = client.get("/api/v1/public/waitlist-stats")
            assert resp2.status_code == 200
            assert spy.call_count == 0

        assert resp1.json() == resp2.json()

    def test_cache_clear_forces_recompute(self, client, db_session):
        from app.api.routes import public as public_module
        from app.api.routes.public import _clear_cache_for_tests

        _seed(db_session, 3)
        # Prime cache.
        client.get("/api/v1/public/waitlist-stats")

        _clear_cache_for_tests()
        with patch.object(
            public_module, "_compute_stats", wraps=public_module._compute_stats
        ) as spy:
            resp = client.get("/api/v1/public/waitlist-stats")
            assert resp.status_code == 200
            assert spy.call_count == 1
