# /unit-tester - Write and Run Tests

Write and run unit/integration tests for the ClassBridge platform.

## Test Infrastructure

### Backend (pytest)
- **Runner:** `python -m pytest` from project root
- **Config:** `tests/conftest.py` — session-scoped SQLite test DB, FastAPI TestClient
- **Location:** `tests/test_*.py`
- **Current coverage:** auth, admin, messages, notifications, tasks, courses, assignments, course contents, parent, study guides, invites (159 tests)

### Frontend (Vitest — not yet set up)
- **Runner:** Would be `npm test` from `frontend/`
- **E2E only:** `frontend/e2e/smoke.spec.ts` (Playwright)
- **No unit tests exist yet** — this is a gap

## Backend Test Patterns

### Fixtures (conftest.py)
```python
@pytest.fixture(scope="session")
def app(test_db_url):
    """Create FastAPI app with isolated SQLite test DB."""
    os.environ["DATABASE_URL"] = test_db_url
    # Reload modules to pick up test DB
    ...
    database.Base.metadata.create_all(bind=database.engine)
    return app_instance

@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture()
def db_session(app):
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### User Setup Pattern
```python
PASSWORD = "password123!"

def _login(client, email):
    resp = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]

def _auth(client, email):
    return {"Authorization": f"Bearer {_login(client, email)}"}

@pytest.fixture()
def users(db_session):
    """Create test users. Check-or-create pattern for session-scoped DB."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    parent = db_session.query(User).filter(User.email == "test@test.com").first()
    if parent:
        return {"parent": parent, ...}  # Reuse existing

    # Create fresh users
    hashed = get_password_hash(PASSWORD)
    parent = User(email="test@test.com", ..., hashed_password=hashed)
    ...
```

### Test Class Pattern (from test_tasks.py)
```python
class TestTaskCRUD:
    def test_create_task(self, client, users):
        headers = _auth(client, "taskparent@test.com")
        resp = client.post("/api/tasks/", json={"title": "Test"}, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["title"] == "Test"

    def test_list_tasks(self, client, users):
        headers = _auth(client, "taskparent@test.com")
        resp = client.get("/api/tasks/", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

class TestPermissions:
    def test_outsider_cannot_edit(self, client, users):
        headers = _auth(client, "outsider@test.com")
        resp = client.patch(f"/api/tasks/{task_id}", json={...}, headers=headers)
        assert resp.status_code == 403
```

## Writing New Backend Tests

### Instructions

When writing tests for a new feature or domain:

1. **Create test file:** `tests/test_{domain}.py`
2. **Import fixtures:** Use `client`, `db_session`, and create domain-specific `users` fixture
3. **Test CRUD:** Create, Read (list + get), Update, Delete
4. **Test permissions:** RBAC (parent, student, teacher, admin, outsider)
5. **Test edge cases:** Missing fields, invalid IDs, duplicate data
6. **Test business rules:** Domain-specific validation (e.g., assignment relationship checks)

### Test Naming Convention
```python
class TestFeatureCRUD:
    def test_create_{entity}(self, client, users): ...
    def test_list_{entities}(self, client, users): ...
    def test_get_{entity}(self, client, users): ...
    def test_update_{entity}(self, client, users): ...
    def test_delete_{entity}(self, client, users): ...

class TestFeaturePermissions:
    def test_{role}_can_{action}(self, client, users): ...
    def test_{role}_cannot_{action}(self, client, users): ...

class TestFeatureEdgeCases:
    def test_{scenario}(self, client, users): ...
```

### Running Tests
```bash
# All tests
python -m pytest

# Specific file
python -m pytest tests/test_tasks.py

# Specific class
python -m pytest tests/test_tasks.py::TestTaskCRUD

# Specific test
python -m pytest tests/test_tasks.py::TestTaskCRUD::test_create_task

# Verbose output
python -m pytest -v

# Short traceback
python -m pytest --tb=short -q
```

## Test Coverage Gaps

### Currently Tested (159 tests across 10 files)
- **Auth** (10 tests) — register, login, token validation, accept-invite
- **Admin** (7 tests) — stats, user listing, search, filter, pagination, RBAC
- **Messages** — conversations, send, unread count
- **Notifications** — list, mark read
- **Tasks** (44 tests) — full CRUD, permissions, archival, filters
- **Courses** (24 tests) — CRUD, enrollment/unenroll, visibility, teaching, enrolled/me
- **Assignments** (9 tests) — CRUD, filter by course, permissions
- **Course Contents** (18 tests) — CRUD, creator-only edit/delete, type validation
- **Parent** (21 tests) — children CRUD, link, overview, update, assign/unassign courses
- **Study Guides** (17 tests) — list/get/update/delete, visibility, duplicate check, versions
- **Invites** (12 tests) — create, RBAC, duplicate/existing checks, list sent

### Needs Tests (Priority Order)
1. **AI generation endpoints** — Require OpenAI mocking
2. **Google Classroom/OAuth** — Require Google API mocking
3. **File upload/extract** — Integration tests with file fixtures
4. **Domain services** (when extracted) — Unit tests with mocked DB

### Related Issues
- #10: Add pytest unit tests for API endpoints
- #71: Add baseline test suite (auth, RBAC, core routes)
- #80: Add E2E smoke tests (Playwright)

## Frontend Testing (Future)

### Setup Needed
```bash
cd frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

### vitest.config.ts
```typescript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
});
```

### Test Priorities
1. **API client modules** — Mock axios, test request/response mapping
2. **Custom hooks** — Test with renderHook, mock API responses
3. **Form components** — Test validation, submission, error states
4. **Calendar logic** — Date calculations, filtering, drag-drop mapping

### Component Test Pattern
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { TaskList } from './TaskList';

describe('TaskList', () => {
  it('renders task items', () => {
    render(<TaskList tasks={mockTasks} />);
    expect(screen.getByText('Test Task')).toBeInTheDocument();
  });

  it('calls onToggle when checkbox clicked', () => {
    const onToggle = vi.fn();
    render(<TaskList tasks={mockTasks} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onToggle).toHaveBeenCalledWith(mockTasks[0].id);
  });
});
```

## Key Reminders

- **Session-scoped DB**: Test DB persists across all tests in a session. Use check-or-create pattern in fixtures.
- **No Alembic**: Tables created via `Base.metadata.create_all()` — no migration needed for tests.
- **Cross-DB issues**: Tests run on SQLite. See MEMORY.md for PostgreSQL compatibility notes.
- **Test isolation**: Each test function gets its own `client` and `db_session` fixtures, but the underlying DB is shared.
