"""Tests for structured JSON logging and request correlation IDs (#2219)."""

import json
import logging

import pytest

from app.core.logging_config import (
    JSONFormatter,
    generate_trace_id,
    trace_id_var,
    user_id_var,
    endpoint_var,
)


# -- JSONFormatter tests --


class TestJSONFormatter:
    def test_basic_log_entry(self):
        """JSON formatter produces valid JSON with required fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="hello world",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["message"] == "hello world"
        assert data["lineno"] == 42
        assert "timestamp" in data

    def test_includes_trace_id_from_context(self):
        """JSON formatter picks up trace_id from context var."""
        formatter = JSONFormatter()
        token = trace_id_var.set("abc-123")
        try:
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="t.py",
                lineno=1, msg="ctx test", args=None, exc_info=None,
            )
            data = json.loads(formatter.format(record))
            assert data["trace_id"] == "abc-123"
        finally:
            trace_id_var.reset(token)

    def test_includes_user_id_from_context(self):
        """JSON formatter picks up user_id from context var."""
        formatter = JSONFormatter()
        token = user_id_var.set(99)
        try:
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="t.py",
                lineno=1, msg="uid test", args=None, exc_info=None,
            )
            data = json.loads(formatter.format(record))
            assert data["user_id"] == 99
        finally:
            user_id_var.reset(token)

    def test_includes_endpoint_from_context(self):
        """JSON formatter picks up endpoint from context var."""
        formatter = JSONFormatter()
        token = endpoint_var.set("/api/test")
        try:
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="t.py",
                lineno=1, msg="ep test", args=None, exc_info=None,
            )
            data = json.loads(formatter.format(record))
            assert data["endpoint"] == "/api/test"
        finally:
            endpoint_var.reset(token)

    def test_omits_empty_context(self):
        """Fields not set in context vars should be absent from output."""
        formatter = JSONFormatter()
        t1 = trace_id_var.set("")
        t2 = user_id_var.set(None)
        t3 = endpoint_var.set("")
        try:
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="t.py",
                lineno=1, msg="no ctx", args=None, exc_info=None,
            )
            data = json.loads(formatter.format(record))
            assert "trace_id" not in data
            assert "user_id" not in data
            assert "endpoint" not in data
        finally:
            trace_id_var.reset(t1)
            user_id_var.reset(t2)
            endpoint_var.reset(t3)

    def test_exception_info_included(self):
        """Exception traceback is included when present."""
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="t.py",
            lineno=1, msg="boom", args=None, exc_info=exc_info,
        )
        data = json.loads(formatter.format(record))
        assert "exception" in data
        assert "ValueError" in data["exception"]


# -- Trace ID generation --


def test_generate_trace_id_unique():
    """Each trace ID should be unique."""
    ids = {generate_trace_id() for _ in range(100)}
    assert len(ids) == 100


# -- Middleware integration tests --


class TestCorrelationMiddleware:
    def test_response_has_x_request_id(self, client):
        """Every response should include X-Request-ID header."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers
        # Should be a valid UUID-like string
        assert len(resp.headers["X-Request-ID"]) == 36

    def test_client_provided_request_id_is_echoed(self, client):
        """If the client sends X-Request-ID, the server should reuse it."""
        custom_id = "client-trace-abc-123-def"
        resp = client.get("/health", headers={"X-Request-ID": custom_id})
        assert resp.headers["X-Request-ID"] == custom_id

    def test_each_request_gets_unique_id(self, client):
        """Two requests without X-Request-ID should get different IDs."""
        r1 = client.get("/health")
        r2 = client.get("/health")
        assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]
