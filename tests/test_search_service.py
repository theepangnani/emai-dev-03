"""Tests for SearchService."""

import pytest
from unittest.mock import MagicMock, patch

from app.services.search_service import SearchService, SearchResult


# --- Preset detection tests ---

def test_detect_preset_upload():
    svc = SearchService()
    assert svc.detect_preset("upload a file") == "upload"
    assert svc.detect_preset("add material here") == "upload"
    assert svc.detect_preset("add file to course") == "upload"


def test_detect_preset_create():
    svc = SearchService()
    assert svc.detect_preset("create a new course") == "create"
    assert svc.detect_preset("new task for today") == "create"
    assert svc.detect_preset("add a course") == "create"
    assert svc.detect_preset("add a task") == "create"


def test_detect_preset_due():
    svc = SearchService()
    assert svc.detect_preset("due this week") == "due"
    assert svc.detect_preset("due tomorrow") == "due"
    assert svc.detect_preset("tasks due today") == "due"


def test_detect_preset_overdue():
    svc = SearchService()
    assert svc.detect_preset("overdue tasks") == "overdue"
    assert svc.detect_preset("past due assignments") == "overdue"
    assert svc.detect_preset("what's due") == "overdue"
    assert svc.detect_preset("whats due") == "overdue"


def test_detect_preset_none():
    svc = SearchService()
    assert svc.detect_preset("show me math class") is None
    assert svc.detect_preset("how do I login") is None
    assert svc.detect_preset("algebra") is None


# --- Action card tests ---

def test_search_returns_upload_action_card():
    svc = SearchService()
    db = MagicMock()
    results = svc.search("upload a file", user_id=1, user_role="student", db=db)
    assert len(results) == 1
    assert results[0].entity_type == "action"
    assert results[0].title == "Upload Material"
    assert results[0].actions[0]["route"] == "/study-tools"


def test_search_returns_create_action_cards():
    svc = SearchService()
    db = MagicMock()
    results = svc.search("create a new course", user_id=1, user_role="teacher", db=db)
    assert len(results) == 3
    titles = [r.title for r in results]
    assert "New Course" in titles
    assert "New Task" in titles
    assert "Generate Study Guide" in titles


def test_search_returns_due_tasks(monkeypatch):
    """When query is 'due today', get_due_tasks is called."""
    svc = SearchService()
    db = MagicMock()
    called = []

    def fake_get_due_tasks(user_id, user_role, db):
        called.append(True)
        return [SearchResult(entity_type="task", id=1, title="Math HW", description="Due: Mar 14", actions=[])]

    monkeypatch.setattr(svc, "get_due_tasks", fake_get_due_tasks)
    results = svc.search("due today", user_id=1, user_role="student", db=db)
    assert called
    assert results[0].entity_type == "task"
    assert results[0].title == "Math HW"
