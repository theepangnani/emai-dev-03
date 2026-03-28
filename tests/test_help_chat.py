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
