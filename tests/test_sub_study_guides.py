"""Tests for sub-study guide generation and listing endpoints (issue #1594, section 6.100).

Covers:
- POST /api/study/guides/{guide_id}/generate-child
- GET /api/study/guides/{guide_id}/children
"""
import json
from unittest.mock import AsyncMock, patch

import pytest
from conftest import PASSWORD, _auth


# ── Fixtures ─────────────────────────────────────────────────

UNIQUE = "subsg"


@pytest.fixture()
def student_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student

    email = f"{UNIQUE}_student@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if user:
        return user

    hashed = get_password_hash(PASSWORD)
    user = User(
        email=email,
        full_name="SubSG Student",
        role=UserRole.STUDENT,
        hashed_password=hashed,
        ai_usage_count=0,
        ai_usage_limit=100,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    s = Student(user_id=user.id)
    db_session.add(s)
    db_session.commit()

    return user


@pytest.fixture()
def parent_guide(db_session, student_user):
    """Create a parent study guide owned by the student."""
    from app.models.study_guide import StudyGuide

    guide = StudyGuide(
        user_id=student_user.id,
        title="Biology Chapter 5",
        content="# Biology Chapter 5\n\nPhotosynthesis overview content here.",
        guide_type="study_guide",
        version=1,
        relationship_type="version",
    )
    db_session.add(guide)
    db_session.commit()
    db_session.refresh(guide)
    return guide


# ── Mock helpers ──────────────────────────────────────────────

def _mock_generate_study_guide():
    """Return a mock for generate_study_guide that returns (content, is_truncated)."""
    mock = AsyncMock(return_value=("# Child Study Guide\n\nGenerated content about the topic.", False))
    return mock


def _mock_generate_quiz():
    """Return a mock for generate_quiz that returns quiz JSON string."""
    quiz_data = json.dumps([
        {"question": "What is photosynthesis?", "options": {"A": "Light", "B": "Process", "C": "Water", "D": "None"}, "correct_answer": "B", "explanation": "It is a process."}
    ])
    return AsyncMock(return_value=quiz_data)


def _mock_generate_flashcards():
    """Return a mock for generate_flashcards that returns flashcards JSON string."""
    cards_data = json.dumps([
        {"front": "What is chlorophyll?", "back": "A green pigment in plants."}
    ])
    return AsyncMock(return_value=cards_data)


MOCK_AI_SERVICE = "app.api.routes.study"


# ── generate-child tests ─────────────────────────────────────


class TestGenerateChildGuide:

    def test_generate_child_study_guide(self, client, student_user, parent_guide):
        headers = _auth(client, student_user.email)
        with (
            patch(f"{MOCK_AI_SERVICE}.generate_study_guide", _mock_generate_study_guide()),
            patch(f"{MOCK_AI_SERVICE}.get_last_ai_usage", return_value={}),
            patch(f"{MOCK_AI_SERVICE}.check_ai_usage"),
            patch(f"{MOCK_AI_SERVICE}.increment_ai_usage"),
            patch(f"{MOCK_AI_SERVICE}.enforce_study_guide_limit"),
        ):
            resp = client.post(
                f"/api/study/guides/{parent_guide.id}/generate-child",
                json={"topic": "Photosynthesis light reactions", "guide_type": "study_guide"},
                headers=headers,
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["parent_guide_id"] == parent_guide.id
        assert data["relationship_type"] == "sub_guide"
        assert data["generation_context"] == "Photosynthesis light reactions"
        assert data["guide_type"] == "study_guide"
        assert "Study Guide:" in data["title"]

    def test_generate_child_quiz(self, client, student_user, parent_guide):
        headers = _auth(client, student_user.email)
        with (
            patch(f"{MOCK_AI_SERVICE}.generate_quiz", _mock_generate_quiz()),
            patch(f"{MOCK_AI_SERVICE}.get_last_ai_usage", return_value={}),
            patch(f"{MOCK_AI_SERVICE}.check_ai_usage"),
            patch(f"{MOCK_AI_SERVICE}.increment_ai_usage"),
            patch(f"{MOCK_AI_SERVICE}.enforce_study_guide_limit"),
        ):
            resp = client.post(
                f"/api/study/guides/{parent_guide.id}/generate-child",
                json={"topic": "Quiz on cell biology", "guide_type": "quiz"},
                headers=headers,
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["parent_guide_id"] == parent_guide.id
        assert data["relationship_type"] == "sub_guide"
        assert data["guide_type"] == "quiz"
        assert "Quiz:" in data["title"]

    def test_generate_child_flashcards(self, client, student_user, parent_guide):
        headers = _auth(client, student_user.email)
        with (
            patch(f"{MOCK_AI_SERVICE}.generate_flashcards", _mock_generate_flashcards()),
            patch(f"{MOCK_AI_SERVICE}.get_last_ai_usage", return_value={}),
            patch(f"{MOCK_AI_SERVICE}.check_ai_usage"),
            patch(f"{MOCK_AI_SERVICE}.increment_ai_usage"),
            patch(f"{MOCK_AI_SERVICE}.enforce_study_guide_limit"),
        ):
            resp = client.post(
                f"/api/study/guides/{parent_guide.id}/generate-child",
                json={"topic": "Flashcards on enzymes", "guide_type": "flashcards"},
                headers=headers,
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["parent_guide_id"] == parent_guide.id
        assert data["relationship_type"] == "sub_guide"
        assert data["guide_type"] == "flashcards"
        assert "Flashcards:" in data["title"]

    def test_generate_child_not_found(self, client, student_user):
        headers = _auth(client, student_user.email)
        resp = client.post(
            "/api/study/guides/999999/generate-child",
            json={"topic": "Some topic here"},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_generate_child_invalid_type(self, client, student_user, parent_guide):
        headers = _auth(client, student_user.email)
        resp = client.post(
            f"/api/study/guides/{parent_guide.id}/generate-child",
            json={"topic": "Some topic here", "guide_type": "invalid_type"},
            headers=headers,
        )
        assert resp.status_code == 422


# ── list-children tests ──────────────────────────────────────


class TestListChildGuides:

    def test_list_children_empty(self, client, student_user, parent_guide):
        headers = _auth(client, student_user.email)
        resp = client.get(
            f"/api/study/guides/{parent_guide.id}/children",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_children_returns_sub_guides(self, client, db_session, student_user, parent_guide):
        from app.models.study_guide import StudyGuide

        child1 = StudyGuide(
            user_id=student_user.id,
            title="Sub-guide: Topic A",
            content="Content A",
            guide_type="study_guide",
            version=1,
            parent_guide_id=parent_guide.id,
            relationship_type="sub_guide",
            generation_context="Topic A",
        )
        child2 = StudyGuide(
            user_id=student_user.id,
            title="Sub-guide: Topic B",
            content="Content B",
            guide_type="quiz",
            version=1,
            parent_guide_id=parent_guide.id,
            relationship_type="sub_guide",
            generation_context="Topic B",
        )
        db_session.add_all([child1, child2])
        db_session.commit()

        headers = _auth(client, student_user.email)
        resp = client.get(
            f"/api/study/guides/{parent_guide.id}/children",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        titles = {d["title"] for d in data}
        assert "Sub-guide: Topic A" in titles
        assert "Sub-guide: Topic B" in titles
        for item in data:
            assert item["relationship_type"] == "sub_guide"

    def test_list_children_excludes_versions(self, client, db_session, student_user, parent_guide):
        from app.models.study_guide import StudyGuide

        version_child = StudyGuide(
            user_id=student_user.id,
            title="Version 2 of parent",
            content="Regenerated content",
            guide_type="study_guide",
            version=2,
            parent_guide_id=parent_guide.id,
            relationship_type="version",
        )
        sub_child = StudyGuide(
            user_id=student_user.id,
            title="Sub-guide: Unique topic XYZ",
            content="Sub content",
            guide_type="study_guide",
            version=1,
            parent_guide_id=parent_guide.id,
            relationship_type="sub_guide",
            generation_context="Unique topic XYZ",
        )
        db_session.add_all([version_child, sub_child])
        db_session.commit()

        headers = _auth(client, student_user.email)
        resp = client.get(
            f"/api/study/guides/{parent_guide.id}/children",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should only include sub_guide items, not version items
        sub_guide_titles = [d["title"] for d in data if d["relationship_type"] == "sub_guide"]
        version_titles = [d["title"] for d in data if d["relationship_type"] == "version"]
        assert len(version_titles) == 0
        assert any("Unique topic XYZ" in t for t in sub_guide_titles)

    def test_list_children_not_found(self, client, student_user):
        headers = _auth(client, student_user.email)
        resp = client.get(
            "/api/study/guides/999999/children",
            headers=headers,
        )
        assert resp.status_code == 404


# ── tree endpoint tests ──────────────────────────────────────


class TestStudyGuideTree:

    def test_tree_single_root(self, client, student_user, parent_guide):
        """A root guide with no children returns tree with just the root."""
        headers = _auth(client, student_user.email)
        resp = client.get(
            f"/api/study/guides/{parent_guide.id}/tree",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["root"]["id"] == parent_guide.id
        assert data["root"]["title"] == parent_guide.title
        assert data["root"]["children"] == []
        assert data["current_path"] == [parent_guide.id]

    def test_tree_hierarchy(self, client, db_session, student_user, parent_guide):
        """parent -> child -> grandchild: tree is correct and path is correct."""
        from app.models.study_guide import StudyGuide

        child = StudyGuide(
            user_id=student_user.id,
            title="Child Guide",
            content="Child content",
            guide_type="study_guide",
            version=1,
            parent_guide_id=parent_guide.id,
            relationship_type="sub_guide",
        )
        db_session.add(child)
        db_session.commit()
        db_session.refresh(child)

        grandchild = StudyGuide(
            user_id=student_user.id,
            title="Grandchild Guide",
            content="Grandchild content",
            guide_type="quiz",
            version=1,
            parent_guide_id=child.id,
            relationship_type="sub_guide",
        )
        db_session.add(grandchild)
        db_session.commit()
        db_session.refresh(grandchild)

        headers = _auth(client, student_user.email)

        # Request tree from grandchild
        resp = client.get(
            f"/api/study/guides/{grandchild.id}/tree",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        # Root should be the parent_guide
        assert data["root"]["id"] == parent_guide.id
        assert data["root"]["title"] == parent_guide.title

        # Root has child
        assert len(data["root"]["children"]) >= 1
        child_node = next(c for c in data["root"]["children"] if c["id"] == child.id)
        assert child_node["title"] == "Child Guide"

        # Child has grandchild
        assert len(child_node["children"]) >= 1
        gc_node = next(c for c in child_node["children"] if c["id"] == grandchild.id)
        assert gc_node["title"] == "Grandchild Guide"
        assert gc_node["guide_type"] == "quiz"

        # current_path goes root -> child -> grandchild
        assert data["current_path"] == [parent_guide.id, child.id, grandchild.id]

    def test_tree_current_path_from_middle(self, client, db_session, student_user, parent_guide):
        """When requesting tree from a middle node, current_path stops at that node."""
        from app.models.study_guide import StudyGuide

        child = StudyGuide(
            user_id=student_user.id,
            title="Mid Child",
            content="Mid content",
            guide_type="study_guide",
            version=1,
            parent_guide_id=parent_guide.id,
            relationship_type="sub_guide",
        )
        db_session.add(child)
        db_session.commit()
        db_session.refresh(child)

        headers = _auth(client, student_user.email)
        resp = client.get(
            f"/api/study/guides/{child.id}/tree",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_path"] == [parent_guide.id, child.id]

    def test_tree_excludes_version_children(self, client, db_session, student_user, parent_guide):
        """Version regenerations should not appear in the tree."""
        from app.models.study_guide import StudyGuide

        version_child = StudyGuide(
            user_id=student_user.id,
            title="Version 2",
            content="Version 2 content",
            guide_type="study_guide",
            version=2,
            parent_guide_id=parent_guide.id,
            relationship_type="version",
        )
        sub_child = StudyGuide(
            user_id=student_user.id,
            title="Sub Guide",
            content="Sub content",
            guide_type="study_guide",
            version=1,
            parent_guide_id=parent_guide.id,
            relationship_type="sub_guide",
        )
        db_session.add_all([version_child, sub_child])
        db_session.commit()

        headers = _auth(client, student_user.email)
        resp = client.get(
            f"/api/study/guides/{parent_guide.id}/tree",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        child_ids = [c["id"] for c in data["root"]["children"]]
        assert sub_child.id in child_ids
        assert version_child.id not in child_ids

    def test_tree_not_found(self, client, student_user):
        headers = _auth(client, student_user.email)
        resp = client.get(
            "/api/study/guides/999999/tree",
            headers=headers,
        )
        assert resp.status_code == 404
