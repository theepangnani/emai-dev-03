"""Tests for help chat service error handling and intent classification."""

import sys
import pytest
from unittest.mock import patch, MagicMock
from types import ModuleType

from app.services.help_chat_service import HelpChatService
from app.services.intent_classifier import classify_intent


def _make_mock_embedding_module(side_effect):
    """Create a mock module for help_embedding_service with a given side_effect on search."""
    mod = ModuleType("app.services.help_embedding_service")
    mock_service = MagicMock()
    mock_service.search.side_effect = side_effect
    mod.help_embedding_service = mock_service  # type: ignore[attr-defined]
    return mod


@pytest.mark.asyncio
async def test_auth_error_returns_specific_message():
    """Regression: generic errors should include error type + /help link."""
    service = HelpChatService()

    class AuthenticationError(Exception):
        pass

    mock_mod = _make_mock_embedding_module(AuthenticationError("Invalid API key"))
    with patch.dict(sys.modules, {"app.services.help_embedding_service": mock_mod}):
        result = await service.generate_response(
            message="How do I connect Google Classroom?",
            user_id=1,
            user_role="parent",
        )

    assert "/help" in result.reply, "Error reply must include /help link"
    assert "configuration" in result.reply.lower() or "error" in result.reply.lower()
    assert "I'm having trouble right now" not in result.reply


@pytest.mark.asyncio
async def test_timeout_error_returns_unreachable_message():
    """Timeout errors should say the service is unreachable."""
    service = HelpChatService()

    class TimeoutError(Exception):
        pass

    mock_mod = _make_mock_embedding_module(TimeoutError("Connection timed out"))
    with patch.dict(sys.modules, {"app.services.help_embedding_service": mock_mod}):
        result = await service.generate_response(
            message="Help me",
            user_id=2,
            user_role="student",
        )

    assert "/help" in result.reply
    assert "unreachable" in result.reply.lower()


@pytest.mark.asyncio
async def test_generic_error_returns_unexpected_message():
    """Unknown errors should say 'unexpected' and still include /help link."""
    service = HelpChatService()

    mock_mod = _make_mock_embedding_module(ValueError("something weird"))
    with patch.dict(sys.modules, {"app.services.help_embedding_service": mock_mod}):
        result = await service.generate_response(
            message="What is this?",
            user_id=3,
            user_role="teacher",
        )

    assert "/help" in result.reply
    assert "unexpected" in result.reply.lower()


@pytest.mark.asyncio
async def test_rate_limit_error_returns_overloaded_message():
    """API rate limit errors should mention overloaded."""
    service = HelpChatService()

    class RateLimitError(Exception):
        pass

    mock_mod = _make_mock_embedding_module(RateLimitError("Rate limit exceeded"))
    with patch.dict(sys.modules, {"app.services.help_embedding_service": mock_mod}):
        result = await service.generate_response(
            message="Help",
            user_id=4,
            user_role="admin",
        )

    assert "/help" in result.reply
    assert "overloaded" in result.reply.lower()


# --- Intent classifier tests ---


def test_classify_intent_search():
    assert classify_intent("find my courses") == "search"
    assert classify_intent("show me my tasks") == "search"
    assert classify_intent("list my study guides") == "search"
    assert classify_intent("where is my assignment") == "search"


def test_classify_intent_action():
    assert classify_intent("upload a file") == "action"
    assert classify_intent("create a new task") == "action"
    assert classify_intent("add a course") == "action"
    assert classify_intent("generate study guide") == "action"


def test_classify_intent_help():
    assert classify_intent("how do I connect Google Classroom") == "help"
    assert classify_intent("what is ClassBridge") == "help"
    assert classify_intent("explain the dashboard") == "help"
    assert classify_intent("how to create a task") == "help"
    assert classify_intent("how to find my courses") == "help"


def test_classify_intent_topic_keywords():
    assert classify_intent("messages") == "help"
    assert classify_intent("google classroom") == "help"
    assert classify_intent("grades") == "help"
    assert classify_intent("mind map") == "help"
    assert classify_intent("course") == "help"
    assert classify_intent("task") == "help"
    assert classify_intent("dark mode") == "help"
    assert classify_intent("todo") == "help"


def test_classify_intent_defaults_to_help():
    assert classify_intent("") == "help"
    assert classify_intent("how does this platform work for teachers") == "help"


# --- Streaming endpoint tests ---


@pytest.fixture()
def stream_user(db_session):
    """Create a user for streaming endpoint tests."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = db_session.query(User).filter(User.email == "streamuser@test.com").first()
    if user:
        return user
    hashed = get_password_hash("Password123!")
    user = User(email="streamuser@test.com", full_name="Stream User", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add(user)
    db_session.commit()
    return user


def test_stream_endpoint_returns_sse_for_search_intent(client, stream_user):
    """POST /api/help/chat/stream returns 200 text/event-stream for a search intent."""
    from conftest import _auth

    mock_result = MagicMock()
    mock_result.entity_type = "course"
    mock_result.id = 1
    mock_result.title = "Math 101"
    mock_result.description = "A math course"
    mock_result.actions = []

    with patch("app.services.intent_classifier.classify_intent", return_value="search"), \
         patch("app.services.search_service.search_service.search", return_value=[mock_result]):
        headers = _auth(client, "streamuser@test.com")
        resp = client.post(
            "/api/help/chat/stream",
            json={"message": "find my courses", "conversation": [], "page_context": ""},
            headers=headers,
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    body = resp.text
    assert "data:" in body
    assert "search" in body


# --- §6.114 Study Q&A access control tests (#2528) ---


@pytest.fixture()
def study_qa_users(db_session):
    """Create parent, student, unrelated user, Student record, parent-student link, and a study guide."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students
    from app.models.study_guide import StudyGuide

    hashed = get_password_hash("Password123!")

    # Parent user
    parent = db_session.query(User).filter(User.email == "qa_parent@test.com").first()
    if not parent:
        parent = User(email="qa_parent@test.com", full_name="QA Parent", role=UserRole.PARENT, hashed_password=hashed)
        db_session.add(parent)
        db_session.flush()

    # Student user
    student_user = db_session.query(User).filter(User.email == "qa_student@test.com").first()
    if not student_user:
        student_user = User(email="qa_student@test.com", full_name="QA Student", role=UserRole.STUDENT, hashed_password=hashed)
        db_session.add(student_user)
        db_session.flush()

    # Student record (needed for parent_students link)
    student_rec = db_session.query(Student).filter(Student.user_id == student_user.id).first()
    if not student_rec:
        student_rec = Student(user_id=student_user.id, grade_level=10)
        db_session.add(student_rec)
        db_session.flush()

    # Parent-student link
    existing_link = db_session.execute(
        parent_students.select().where(
            parent_students.c.parent_id == parent.id,
            parent_students.c.student_id == student_rec.id,
        )
    ).first()
    if not existing_link:
        db_session.execute(parent_students.insert().values(parent_id=parent.id, student_id=student_rec.id))

    # Unrelated user (not owner, not shared, not parent)
    unrelated = db_session.query(User).filter(User.email == "qa_unrelated@test.com").first()
    if not unrelated:
        unrelated = User(email="qa_unrelated@test.com", full_name="QA Unrelated", role=UserRole.PARENT, hashed_password=hashed)
        db_session.add(unrelated)
        db_session.flush()

    # Study guide owned by student
    guide = StudyGuide(
        user_id=student_user.id,
        title="Test Study Guide",
        content="Some study content for testing.",
        guide_type="study_guide",
    )
    db_session.add(guide)
    db_session.commit()

    return {
        "parent": parent,
        "student_user": student_user,
        "student_rec": student_rec,
        "unrelated": unrelated,
        "guide": guide,
    }


async def _fake_stream_answer(**kwargs):
    """Fake async generator for study_qa_service.stream_answer."""
    yield {"type": "chunk", "text": "Hello "}
    yield {"type": "chunk", "text": "world"}
    yield {"type": "done", "input_tokens": 10, "output_tokens": 5, "estimated_cost_usd": 0.001}


def test_parent_can_access_child_study_guide_qa(client, study_qa_users):
    """Regression #2528: parent linked via parent_students can access child's study guide Q&A."""
    from conftest import _auth

    data = study_qa_users
    with patch("app.services.study_qa_service.study_qa_service.stream_answer", side_effect=_fake_stream_answer), \
         patch("app.services.ai_usage.check_ai_usage"), \
         patch("app.services.ai_usage.increment_ai_usage"):
        headers = _auth(client, "qa_parent@test.com")
        resp = client.post(
            "/api/help/chat/stream",
            json={
                "message": "Explain this topic",
                "conversation": [],
                "page_context": "",
                "study_guide_id": data["guide"].id,
            },
            headers=headers,
        )

    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
    assert "text/event-stream" in resp.headers.get("content-type", "")


def test_unrelated_user_gets_403_for_study_guide_qa(client, study_qa_users):
    """Unrelated user (not owner, not shared, not parent) gets 403 for study guide Q&A."""
    from conftest import _auth

    data = study_qa_users
    headers = _auth(client, "qa_unrelated@test.com")
    resp = client.post(
        "/api/help/chat/stream",
        json={
            "message": "Explain this topic",
            "conversation": [],
            "page_context": "",
            "study_guide_id": data["guide"].id,
        },
        headers=headers,
    )

    assert resp.status_code == 403


def test_nonexistent_study_guide_returns_404(client, stream_user):
    """Non-existent study_guide_id returns 404."""
    from conftest import _auth

    headers = _auth(client, "streamuser@test.com")
    resp = client.post(
        "/api/help/chat/stream",
        json={
            "message": "Explain this",
            "conversation": [],
            "page_context": "",
            "study_guide_id": 999999,
        },
        headers=headers,
    )

    assert resp.status_code == 404


def test_enrolled_student_can_access_study_guide_qa(client, db_session):
    """Regression #2535: enrolled student can use Q&A on a course's study guide."""
    from conftest import _auth
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student
    from app.models.course import Course, student_courses
    from app.models.course_content import CourseContent
    from app.models.study_guide import StudyGuide

    hashed = get_password_hash("Password123!")

    # Guide owner (student A)
    owner = User(email="qa_owner_2535@test.com", full_name="Owner Student", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add(owner)
    db_session.flush()

    # Enrolled student (student B)
    enrolled = User(email="qa_enrolled_2535@test.com", full_name="Enrolled Student", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add(enrolled)
    db_session.flush()

    enrolled_student_rec = Student(user_id=enrolled.id, grade_level=10)
    db_session.add(enrolled_student_rec)
    db_session.flush()

    # Course + enroll student B
    course = Course(name="Test Course 2535", created_by_user_id=owner.id, is_private=True)
    db_session.add(course)
    db_session.flush()

    db_session.execute(student_courses.insert().values(student_id=enrolled_student_rec.id, course_id=course.id))

    # CourseContent linked to the course
    cc = CourseContent(course_id=course.id, title="Lesson 1", content_type="document", created_by_user_id=owner.id)
    db_session.add(cc)
    db_session.flush()

    # Study guide owned by student A, linked to CourseContent
    guide = StudyGuide(
        user_id=owner.id,
        title="Guide for Lesson 1",
        content="Study content.",
        guide_type="study_guide",
        course_content_id=cc.id,
    )
    db_session.add(guide)
    db_session.commit()

    with patch("app.services.study_qa_service.study_qa_service.stream_answer", side_effect=_fake_stream_answer), \
         patch("app.services.ai_usage.check_ai_usage"), \
         patch("app.services.ai_usage.increment_ai_usage"):
        headers = _auth(client, "qa_enrolled_2535@test.com")
        resp = client.post(
            "/api/help/chat/stream",
            json={
                "message": "Explain this topic",
                "conversation": [],
                "page_context": "",
                "study_guide_id": guide.id,
            },
            headers=headers,
        )

    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
    assert "text/event-stream" in resp.headers.get("content-type", "")


# --- Existing help chat service tests ---


@pytest.mark.asyncio
async def test_embedding_service_retries_after_failed_init():
    """Regression: embedding service should retry initialization after failure, not stay broken."""
    from app.services.help_embedding_service import HelpEmbeddingService

    service = HelpEmbeddingService()

    # Simulate failed init (e.g. OpenAI key missing)
    with patch.object(service, "_load_yaml", side_effect=RuntimeError("API down")):
        await service.initialize()

    # After failure, _initialized should still be False so it retries
    assert service._initialized is False, "Service should allow retry after failed init"
    assert service.chunks == [], "Chunks should be empty after failed init"


# --- §6.114 Resource links in Q&A tests (#2543) ---


def test_build_system_prompt_includes_resource_links():
    """build_system_prompt includes RELATED RESOURCES section when links are provided."""
    from app.services.study_qa_service import StudyQAService

    service = StudyQAService()

    class FakeLink:
        def __init__(self, title, url, resource_type, topic_heading=None, description=None):
            self.title = title
            self.url = url
            self.resource_type = resource_type
            self.topic_heading = topic_heading
            self.description = description

    links = [
        FakeLink("Algebra Basics", "https://youtube.com/watch?v=abc", "youtube", topic_heading="Algebra"),
        FakeLink("Math Reference", "https://example.com/math", "external_link", description="Helpful reference"),
    ]

    prompt = service.build_system_prompt(
        guide_title="Math Guide",
        guide_content="Content about algebra.",
        resource_links=links,
    )

    assert "RELATED RESOURCES" in prompt
    assert "Algebra Basics" in prompt
    assert "Math Reference" in prompt
    assert "youtube.com" in prompt
    assert "example.com" in prompt


def test_build_system_prompt_no_resource_links():
    """build_system_prompt omits RELATED RESOURCES section when no links are provided."""
    from app.services.study_qa_service import StudyQAService

    service = StudyQAService()
    prompt = service.build_system_prompt(
        guide_title="Math Guide",
        guide_content="Content about algebra.",
        resource_links=[],
    )

    assert "RELATED RESOURCES" not in prompt


def test_match_resource_links_keyword_matching():
    """_match_resource_links returns relevant links based on keyword overlap."""
    from app.services.study_qa_service import StudyQAService

    class FakeLink:
        def __init__(self, title, url, resource_type, topic_heading=None, description=None, youtube_video_id=None, thumbnail_url=None):
            self.title = title
            self.url = url
            self.resource_type = resource_type
            self.topic_heading = topic_heading
            self.description = description
            self.youtube_video_id = youtube_video_id
            self.thumbnail_url = thumbnail_url

    links = [
        FakeLink("Algebra Basics", "https://youtube.com/watch?v=abc", "youtube", topic_heading="Algebra", youtube_video_id="abc"),
        FakeLink("Chemistry Lab", "https://youtube.com/watch?v=xyz", "youtube", topic_heading="Chemistry", youtube_video_id="xyz"),
        FakeLink("Algebra Formulas", "https://example.com/algebra", "external_link", description="Key algebra formulas"),
    ]

    sources, videos = StudyQAService._match_resource_links("Tell me about algebra basics", links)

    # Should match algebra-related links, not chemistry
    video_titles = [v["title"] for v in videos]
    assert "Algebra Basics" in video_titles
    assert "Algebra Formulas" in video_titles  # external link goes to videos with provider=external
    assert "Chemistry Lab" not in video_titles


def test_match_resource_links_empty_list():
    """_match_resource_links returns empty lists for no links."""
    from app.services.study_qa_service import StudyQAService

    sources, videos = StudyQAService._match_resource_links("some question", [])
    assert sources == []
    assert videos == []


def test_study_qa_stream_returns_resource_links(client, db_session):
    """Study Q&A stream populates sources/videos in done event from resource_links (#2543)."""
    from conftest import _auth
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.course import Course
    from app.models.course_content import CourseContent
    from app.models.study_guide import StudyGuide
    from app.models.resource_link import ResourceLink

    hashed = get_password_hash("Password123!")

    owner = User(email="qa_resource_owner@test.com", full_name="Resource Owner", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add(owner)
    db_session.flush()

    course = Course(name="Resource Test Course", created_by_user_id=owner.id)
    db_session.add(course)
    db_session.flush()

    cc = CourseContent(course_id=course.id, title="Lesson on Algebra", content_type="notes", created_by_user_id=owner.id)
    db_session.add(cc)
    db_session.flush()

    guide = StudyGuide(
        user_id=owner.id, title="Algebra Guide", content="Study algebra content.",
        guide_type="study_guide", course_content_id=cc.id,
    )
    db_session.add(guide)
    db_session.flush()

    # Add resource links
    db_session.add(ResourceLink(
        course_content_id=cc.id, url="https://youtube.com/watch?v=alg1",
        resource_type="youtube", title="Algebra Video", topic_heading="Algebra",
        youtube_video_id="alg1", display_order=0,
    ))
    db_session.add(ResourceLink(
        course_content_id=cc.id, url="https://example.com/algebra-ref",
        resource_type="external_link", title="Algebra Reference", topic_heading="Algebra",
        display_order=1,
    ))
    db_session.commit()

    async def _fake_stream(**kwargs):
        assert kwargs.get("resource_links") is not None
        assert len(kwargs["resource_links"]) == 2
        # Delegate to real service for done event with resource links
        from app.services.study_qa_service import StudyQAService
        svc = StudyQAService()
        matched_sources, matched_videos = svc._match_resource_links(
            kwargs["message"], kwargs["resource_links"]
        )
        yield {"type": "token", "text": "Here is an algebra answer."}
        yield {
            "type": "done", "sources": matched_sources, "videos": matched_videos,
            "mode": "study_qa", "credits_used": 0.25,
            "input_tokens": 10, "output_tokens": 5, "estimated_cost_usd": 0.001,
        }

    with patch("app.services.study_qa_service.study_qa_service.stream_answer", side_effect=_fake_stream), \
         patch("app.services.ai_usage.check_ai_usage"), \
         patch("app.services.ai_usage.increment_ai_usage"):
        headers = _auth(client, "qa_resource_owner@test.com")
        resp = client.post(
            "/api/help/chat/stream",
            json={
                "message": "Explain algebra",
                "conversation": [],
                "page_context": "",
                "study_guide_id": guide.id,
            },
            headers=headers,
        )

    assert resp.status_code == 200
    # Parse SSE events
    import json
    done_event = None
    for line in resp.text.split("\n"):
        if line.startswith("data: "):
            event = json.loads(line[6:])
            if event.get("type") == "done":
                done_event = event

    assert done_event is not None, "Expected a done event in SSE stream"
    assert len(done_event["videos"]) >= 1, "Expected at least one video link"
    video_titles = [v["title"] for v in done_event["videos"]]
    assert "Algebra Video" in video_titles
