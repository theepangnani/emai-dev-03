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
    assert results[0].actions[0]["route"] == "/study"


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


# --- Person filter priority tests (#1746) ---

def test_search_person_filter_takes_priority_over_list_tasks(monkeypatch):
    """'show tasks for Thanushan' must route to _list_tasks_for_person, not _list_tasks."""
    svc = SearchService()
    db = MagicMock()
    called_with = []

    def fake_list_tasks_for_person(user_id, user_role, db, person_name):
        called_with.append(person_name)
        return [SearchResult(entity_type="task", id=1, title="Task", description="", actions=[])]

    monkeypatch.setattr(svc, "_list_tasks_for_person", fake_list_tasks_for_person)
    results = svc.search("show tasks for Thanushan", user_id=1, user_role="teacher", db=db)
    assert called_with == ["Thanushan"]
    assert len(results) == 1


def test_search_tasks_for_noah_routes_to_person_filter(monkeypatch):
    """'tasks for noah' must route to _list_tasks_for_person, not list_tasks preset."""
    svc = SearchService()
    db = MagicMock()
    called_with = []

    def fake_list_tasks_for_person(user_id, user_role, db, person_name):
        called_with.append(person_name)
        return [SearchResult(entity_type="task", id=2, title="Noah Task", description="", actions=[])]

    monkeypatch.setattr(svc, "_list_tasks_for_person", fake_list_tasks_for_person)
    results = svc.search("tasks for noah", user_id=1, user_role="teacher", db=db)
    assert called_with == ["noah"]
    assert len(results) == 1


# --- Person filter false-positive tests (#1722) ---

def test_extract_person_filter_ignores_entity_keywords():
    """'search for tasks' must NOT treat 'tasks' as a person name."""
    svc = SearchService()
    assert svc._extract_person_filter("search for tasks") is None
    assert svc._extract_person_filter("search for courses") is None
    assert svc._extract_person_filter("looking for notes") is None
    assert svc._extract_person_filter("search for assignments") is None
    assert svc._extract_person_filter("looking for something") is None


def test_extract_person_filter_allows_real_names():
    """'show tasks for Thanushan' must still extract 'Thanushan' as a person name."""
    svc = SearchService()
    assert svc._extract_person_filter("show tasks for Thanushan") == "Thanushan"
    assert svc._extract_person_filter("tasks for noah") == "noah"
    assert svc._extract_person_filter("list tasks for Emma") == "Emma"


# --- Result limit and summary card tests (#1749) ---

def test_list_tasks_returns_max_5_plus_summary_when_over_limit():
    """_list_tasks with 25 tasks returns 5 task cards + 1 summary card."""
    from unittest.mock import MagicMock, patch
    from app.models.task import Task as _Task

    svc = SearchService()
    db = MagicMock()

    # Build 25 fake tasks
    fake_tasks = []
    for i in range(25):
        t = MagicMock(spec=_Task)
        t.id = i + 1
        t.title = f"Task {i + 1}"
        t.description = None
        t.archived_at = None
        fake_tasks.append(t)

    # Simulate: q.count() returns 25, q.order_by(...).limit(5).all() returns first 5
    mock_q = MagicMock()
    mock_q.filter.return_value = mock_q
    mock_q.count.return_value = 25
    mock_q.order_by.return_value = mock_q
    mock_q.limit.return_value = mock_q
    mock_q.all.return_value = fake_tasks[:5]

    db.query.return_value = mock_q

    results = svc._list_tasks(user_id=1, user_role="teacher", db=db)

    task_results = [r for r in results if r.entity_type == "task"]
    summary_results = [r for r in results if r.entity_type == "summary"]

    assert len(task_results) <= 5
    assert len(summary_results) == 1
    assert "5 of 25" in summary_results[0].title
    assert summary_results[0].actions[0]["route"] == "/tasks"
