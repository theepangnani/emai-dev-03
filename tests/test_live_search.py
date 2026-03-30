"""Tests for YouTube Data API v3 live search service (§6.57.3, #2493)."""

import time
from unittest.mock import patch, MagicMock

import pytest
from conftest import PASSWORD, _auth


# ---------------------------------------------------------------------------
# Unit tests for the service layer
# ---------------------------------------------------------------------------


class TestBuildQuery:
    def test_full_query(self):
        from app.services.live_search_service import _build_query

        result = _build_query("Quadratic equations", "Math", "Grade 10")
        assert "Quadratic equations" in result
        assert "Math" in result
        assert "Grade 10" in result
        assert "Ontario curriculum" in result

    def test_empty_course_and_grade(self):
        from app.services.live_search_service import _build_query

        result = _build_query("Photosynthesis", "", "")
        assert result == "Photosynthesis Ontario curriculum"


class TestRateLimiting:
    def setup_method(self):
        from app.services import live_search_service
        live_search_service._rate_limit_store.clear()

    def test_allows_under_limit(self):
        from app.services.live_search_service import _check_rate_limit, _record_search

        for _ in range(10):
            assert _check_rate_limit(999) is True
            _record_search(999)
        assert _check_rate_limit(999) is False

    def test_window_expiry(self):
        from app.services.live_search_service import (
            _check_rate_limit,
            _rate_limit_store,
            _RATE_LIMIT_WINDOW,
        )

        # Simulate old timestamps outside the window
        old_time = time.time() - _RATE_LIMIT_WINDOW - 1
        _rate_limit_store[999] = [old_time] * 10
        assert _check_rate_limit(999) is True


class TestCaching:
    def setup_method(self):
        from app.services import live_search_service
        live_search_service._cache.clear()

    def test_cache_hit(self):
        from app.services.live_search_service import (
            _cache_key,
            _get_cached,
            _set_cache,
            YouTubeSearchResult,
        )

        key = _cache_key("algebra", "grade 9")
        results = [
            YouTubeSearchResult(
                title="Test", description="desc", video_id="abc123",
                thumbnail_url="http://img.youtube.com/vi/abc123/mqdefault.jpg",
                channel_title="TestChannel",
            )
        ]
        _set_cache(key, results)
        cached = _get_cached(key)
        assert cached is not None
        assert len(cached) == 1
        assert cached[0].video_id == "abc123"

    def test_cache_miss_after_ttl(self):
        from app.services.live_search_service import (
            _cache_key,
            _get_cached,
            _cache,
            _CACHE_TTL,
            YouTubeSearchResult,
        )

        key = _cache_key("algebra", "grade 9")
        results = [
            YouTubeSearchResult(
                title="Test", description="desc", video_id="abc123",
                thumbnail_url="http://img.youtube.com/vi/abc123/mqdefault.jpg",
                channel_title="TestChannel",
            )
        ]
        _cache[key] = (results, time.time() - _CACHE_TTL - 1)
        assert _get_cached(key) is None


class TestSearchYoutube:
    _MOCK_RESPONSE = {
        "items": [
            {
                "id": {"videoId": "dQw4w9WgXcQ"},
                "snippet": {
                    "title": "Test Video",
                    "description": "A test description",
                    "channelTitle": "Test Channel",
                    "thumbnails": {
                        "medium": {"url": "http://img.youtube.com/vi/dQw4w9WgXcQ/mqdefault.jpg"},
                    },
                },
            }
        ]
    }

    @patch("app.services.live_search_service.settings")
    @patch("app.services.live_search_service.httpx.Client")
    def test_successful_search(self, mock_client_cls, mock_settings):
        from app.services.live_search_service import search_youtube

        mock_settings.youtube_api_key = "test-key"
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._MOCK_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        results = search_youtube("test query")
        assert len(results) == 1
        assert results[0].video_id == "dQw4w9WgXcQ"
        assert results[0].title == "Test Video"
        assert results[0].channel_title == "Test Channel"

    @patch("app.services.live_search_service.settings")
    def test_no_api_key_raises(self, mock_settings):
        from app.services.live_search_service import search_youtube

        mock_settings.youtube_api_key = ""
        with pytest.raises(RuntimeError, match="not configured"):
            search_youtube("test query")

    @patch("app.services.live_search_service.settings")
    @patch("app.services.live_search_service.httpx.Client")
    def test_quota_exhausted(self, mock_client_cls, mock_settings):
        import httpx as httpx_mod
        from app.services.live_search_service import search_youtube

        mock_settings.youtube_api_key = "test-key"
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "quotaExceeded"
        mock_resp.raise_for_status.side_effect = httpx_mod.HTTPStatusError(
            "403", request=MagicMock(), response=mock_resp
        )
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="quota exhausted"):
            search_youtube("test query")


# ---------------------------------------------------------------------------
# Integration tests (API endpoints)
# ---------------------------------------------------------------------------


@pytest.fixture()
def setup(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.course import Course
    from app.models.course_content import CourseContent

    owner = db_session.query(User).filter(User.email == "yt_search_owner@test.com").first()
    if owner:
        cc = (
            db_session.query(CourseContent)
            .join(Course)
            .filter(Course.name == "YT Search Test Course")
            .first()
        )
        return {"owner": owner, "course_content": cc}

    hashed = get_password_hash(PASSWORD)
    owner = User(
        email="yt_search_owner@test.com",
        full_name="YT Owner",
        role=UserRole.PARENT,
        hashed_password=hashed,
    )
    db_session.add(owner)
    db_session.flush()

    course = Course(name="YT Search Test Course", created_by_user_id=owner.id)
    db_session.add(course)
    db_session.flush()

    cc = CourseContent(
        course_id=course.id,
        title="Lesson 1",
        text_content="Some content about math",
        created_by_user_id=owner.id,
    )
    db_session.add(cc)
    db_session.commit()

    return {"owner": owner, "course_content": cc}


def test_feature_flag_disabled(client, setup):
    headers = _auth(client, "yt_search_owner@test.com")
    with patch("app.api.routes.resource_links.settings") as mock_settings:
        mock_settings.youtube_api_key = ""
        resp = client.get("/api/features/youtube-search", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["available"] is False


def test_feature_flag_enabled(client, setup):
    headers = _auth(client, "yt_search_owner@test.com")
    with patch("app.api.routes.resource_links.settings") as mock_settings:
        mock_settings.youtube_api_key = "test-key"
        resp = client.get("/api/features/youtube-search", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["available"] is True


_MOCK_RESULTS = [
    {
        "title": "Mock Video",
        "description": "Mock desc",
        "video_id": "abc123",
        "thumbnail_url": "http://img.youtube.com/vi/abc123/mqdefault.jpg",
        "channel_title": "Mock Channel",
    }
]


@patch("app.api.routes.resource_links.search_youtube_for_topic")
def test_search_resources(mock_search, client, setup):
    from app.services.live_search_service import YouTubeSearchResult

    mock_search.return_value = [YouTubeSearchResult(**_MOCK_RESULTS[0])]
    headers = _auth(client, "yt_search_owner@test.com")
    content_id = setup["course_content"].id

    resp = client.post(
        f"/api/course-contents/{content_id}/search-resources",
        json={"topic": "algebra", "grade_level": "Grade 9", "course_name": "Math"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["video_id"] == "abc123"


@patch("app.api.routes.resource_links.search_youtube_for_topic")
def test_search_resources_save(mock_search, client, setup, db_session):
    from app.services.live_search_service import YouTubeSearchResult
    from app.models.resource_link import ResourceLink

    mock_search.return_value = [YouTubeSearchResult(**_MOCK_RESULTS[0])]
    headers = _auth(client, "yt_search_owner@test.com")
    content_id = setup["course_content"].id

    resp = client.post(
        f"/api/course-contents/{content_id}/search-resources",
        json={
            "topic": "algebra",
            "grade_level": "Grade 9",
            "course_name": "Math",
            "save": True,
        },
        headers=headers,
    )
    assert resp.status_code == 200

    # Verify saved in DB
    db_session.expire_all()
    saved = (
        db_session.query(ResourceLink)
        .filter(
            ResourceLink.course_content_id == content_id,
            ResourceLink.source == "api_search",
        )
        .all()
    )
    assert len(saved) >= 1
    assert saved[0].youtube_video_id == "abc123"


@patch("app.api.routes.resource_links.search_youtube_for_topic")
def test_search_resources_rate_limited(mock_search, client, setup):
    mock_search.side_effect = RuntimeError("Rate limit exceeded — max 10 searches per hour")
    headers = _auth(client, "yt_search_owner@test.com")
    content_id = setup["course_content"].id

    resp = client.post(
        f"/api/course-contents/{content_id}/search-resources",
        json={"topic": "algebra", "grade_level": "Grade 9", "course_name": "Math"},
        headers=headers,
    )
    assert resp.status_code == 429


@patch("app.api.routes.resource_links.search_youtube_for_topic")
def test_search_resources_service_unavailable(mock_search, client, setup):
    mock_search.side_effect = RuntimeError("YouTube search is not available")
    headers = _auth(client, "yt_search_owner@test.com")
    content_id = setup["course_content"].id

    resp = client.post(
        f"/api/course-contents/{content_id}/search-resources",
        json={"topic": "algebra", "grade_level": "Grade 9", "course_name": "Math"},
        headers=headers,
    )
    assert resp.status_code == 503
