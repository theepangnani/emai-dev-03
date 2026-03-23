"""Tests for streaming study guide generation (SSE endpoint).

Covers POST /api/study/generate-stream which returns Server-Sent Events.
"""
import json
import uuid
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from conftest import PASSWORD, _login, _auth


# ── SSE parsing helper ──────────────────────────────────────────────


def parse_sse_events(response_text: str) -> list[dict]:
    """Parse SSE text into list of {event, data} dicts."""
    events = []
    for block in response_text.split("\n\n"):
        if not block.strip():
            continue
        event = {}
        for line in block.strip().split("\n"):
            if line.startswith("event: "):
                event["event"] = line[7:]
            elif line.startswith("data: "):
                try:
                    event["data"] = json.loads(line[6:])
                except json.JSONDecodeError:
                    event["data"] = line[6:]
        if event:
            events.append(event)
    return events


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def stream_users(db_session):
    """Create users needed for streaming tests (isolated from other test files)."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students, RelationshipType
    from app.models.teacher import Teacher
    from app.models.course import Course, student_courses
    from sqlalchemy import insert

    existing = db_session.query(User).filter(User.email == "stream_parent@test.com").first()
    if existing:
        student = db_session.query(User).filter(User.email == "stream_student@test.com").first()
        return {"parent": existing, "student": student}

    hashed = get_password_hash(PASSWORD)
    parent = User(email="stream_parent@test.com", full_name="Stream Parent", role=UserRole.PARENT, hashed_password=hashed)
    student = User(email="stream_student@test.com", full_name="Stream Student", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add_all([parent, student])
    db_session.flush()

    student_rec = Student(user_id=student.id)
    db_session.add(student_rec)
    db_session.flush()

    db_session.execute(insert(parent_students).values(
        parent_id=parent.id, student_id=student_rec.id,
        relationship_type=RelationshipType.GUARDIAN,
    ))
    db_session.commit()
    return {"parent": parent, "student": student}


# ── Helper: mock the AI streaming generator ──────────────────────────


async def _fake_stream(chunks, is_truncated=False, **kwargs):
    """Async generator that yields chunk events then a done event."""
    full = ""
    for chunk in chunks:
        full += chunk
        yield {"event": "chunk", "data": chunk}
    yield {
        "event": "done",
        "data": {"is_truncated": is_truncated, "full_content": full},
    }


async def _fake_error_stream(**kwargs):
    """Async generator that yields an error event."""
    yield {"event": "error", "data": "AI service is temporarily unavailable. Please try again."}


# ── Tests ────────────────────────────────────────────────────────────


class TestStreamEndpointSSE:
    """POST /api/study/generate-stream SSE tests."""

    ENDPOINT = "/api/study/generate-stream"

    @pytest.fixture(autouse=True)
    def _mock_safety_check(self):
        """Content safety check requires Anthropic API — mock it for all stream tests."""
        with patch("app.api.routes.study.check_content_safe", return_value=(True, "")):
            yield

    @staticmethod
    def _body(suffix=None):
        """Return a unique request body to avoid duplicate-detection."""
        tag = suffix or uuid.uuid4().hex[:8]
        return {
            "content": f"Photosynthesis converts light energy into chemical energy. [{tag}]",
            "title": f"Biology Study Guide {tag}",
        }

    def test_stream_requires_auth(self, client):
        """POST without auth token returns 401."""
        resp = client.post(self.ENDPOINT, json=self._body())
        assert resp.status_code == 401

    def test_stream_endpoint_returns_sse_content_type(self, client, stream_users):
        """Response content-type is text/event-stream."""
        headers = _auth(client, stream_users["parent"].email)
        chunks = ["Hello ", "world", "!"]

        with patch(
            "app.api.routes.study.generate_study_guide_stream",
            side_effect=lambda **kw: _fake_stream(chunks, **kw),
        ):
            resp = client.post(self.ENDPOINT, json=self._body(), headers=headers)

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_stream_yields_start_event_with_guide_id(self, client, stream_users):
        """First SSE event is 'start' with a guide_id."""
        headers = _auth(client, stream_users["parent"].email)
        chunks = ["Test content"]

        with patch(
            "app.api.routes.study.generate_study_guide_stream",
            side_effect=lambda **kw: _fake_stream(chunks, **kw),
        ):
            resp = client.post(self.ENDPOINT, json=self._body(), headers=headers)

        events = parse_sse_events(resp.text)
        assert len(events) >= 1
        assert events[0]["event"] == "start"
        assert "guide_id" in events[0]["data"]
        assert isinstance(events[0]["data"]["guide_id"], int)

    def test_stream_yields_chunk_events(self, client, stream_users):
        """Mock AI yields 3 chunks — verify 3 chunk events with correct text."""
        headers = _auth(client, stream_users["parent"].email)
        chunks = ["Hello ", "world", "!"]

        with patch(
            "app.api.routes.study.generate_study_guide_stream",
            side_effect=lambda **kw: _fake_stream(chunks, **kw),
        ):
            resp = client.post(self.ENDPOINT, json=self._body(), headers=headers)

        events = parse_sse_events(resp.text)
        chunk_events = [e for e in events if e["event"] == "chunk"]
        assert len(chunk_events) == 3
        assert chunk_events[0]["data"]["text"] == "Hello "
        assert chunk_events[1]["data"]["text"] == "world"
        assert chunk_events[2]["data"]["text"] == "!"

    def test_stream_yields_done_event_with_full_guide(self, client, stream_users):
        """Final event is 'done' with StudyGuideResponse data including content."""
        headers = _auth(client, stream_users["parent"].email)
        chunks = ["Full ", "guide ", "content"]

        with patch(
            "app.api.routes.study.generate_study_guide_stream",
            side_effect=lambda **kw: _fake_stream(chunks, **kw),
        ):
            resp = client.post(self.ENDPOINT, json=self._body(), headers=headers)

        events = parse_sse_events(resp.text)
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
        done_data = done_events[0]["data"]
        assert "id" in done_data
        assert done_data["content"] == "Full guide content"
        assert done_data["guide_type"] == "study_guide"

    def test_stream_saves_guide_to_db(self, client, stream_users, db_session):
        """After stream completes, the guide is saved in DB with correct content."""
        from app.models.study_guide import StudyGuide

        headers = _auth(client, stream_users["parent"].email)
        chunks = ["Saved ", "content"]

        with patch(
            "app.api.routes.study.generate_study_guide_stream",
            side_effect=lambda **kw: _fake_stream(chunks, **kw),
        ):
            resp = client.post(self.ENDPOINT, json=self._body(), headers=headers)

        events = parse_sse_events(resp.text)
        start_event = [e for e in events if e["event"] == "start"][0]
        guide_id = start_event["data"]["guide_id"]

        db_session.expire_all()
        guide = db_session.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
        assert guide is not None
        assert guide.content == "Saved content"
        assert guide.is_truncated is False

    def test_stream_debits_ai_usage(self, client, stream_users, db_session):
        """AI credit is debited after stream completes successfully."""
        headers = _auth(client, stream_users["parent"].email)
        chunks = ["Content"]

        with patch(
            "app.api.routes.study.generate_study_guide_stream",
            side_effect=lambda **kw: _fake_stream(chunks, **kw),
        ), patch(
            "app.api.routes.study.increment_ai_usage",
        ) as mock_incr:
            resp = client.post(self.ENDPOINT, json=self._body(), headers=headers)

        events = parse_sse_events(resp.text)
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
        # increment_ai_usage should have been called once
        assert mock_incr.call_count == 1
        call_kwargs = mock_incr.call_args
        assert call_kwargs[1]["generation_type"] == "study_guide"

    def test_stream_handles_error(self, client, stream_users):
        """When AI service yields error, an error SSE event is sent."""
        headers = _auth(client, stream_users["parent"].email)

        with patch(
            "app.api.routes.study.generate_study_guide_stream",
            side_effect=lambda **kw: _fake_error_stream(**kw),
        ):
            resp = client.post(self.ENDPOINT, json=self._body(), headers=headers)

        events = parse_sse_events(resp.text)
        # start is emitted first (before the generator runs), then error
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) >= 1
        assert "message" in error_events[0]["data"]

    def test_stream_checks_ai_quota(self, client, stream_users):
        """When AI usage is at limit, appropriate error response is returned."""
        from fastapi import HTTPException

        headers = _auth(client, stream_users["parent"].email)

        with patch(
            "app.api.routes.study.check_ai_usage",
            side_effect=HTTPException(status_code=429, detail="AI usage limit reached"),
        ):
            resp = client.post(self.ENDPOINT, json=self._body(), headers=headers)

        assert resp.status_code == 429
        assert "limit" in resp.json()["detail"].lower()

    def test_stream_truncated_flag_propagated(self, client, stream_users, db_session):
        """When AI signals truncation, is_truncated=True is saved and returned."""
        from app.models.study_guide import StudyGuide

        headers = _auth(client, stream_users["parent"].email)
        chunks = ["Truncated content"]

        with patch(
            "app.api.routes.study.generate_study_guide_stream",
            side_effect=lambda **kw: _fake_stream(chunks, is_truncated=True, **kw),
        ):
            resp = client.post(self.ENDPOINT, json=self._body(), headers=headers)

        events = parse_sse_events(resp.text)
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
        assert done_events[0]["data"]["is_truncated"] is True

        start_event = [e for e in events if e["event"] == "start"][0]
        guide_id = start_event["data"]["guide_id"]
        db_session.expire_all()
        guide = db_session.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
        assert guide.is_truncated is True
