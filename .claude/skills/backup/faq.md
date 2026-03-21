# /faq - Implement FAQ / Knowledge Base Feature

Implement the community-driven FAQ/Knowledge Base system with admin approval workflow.

## Feature Overview

The FAQ system provides:
- Community Q&A where all users can ask questions and provide answers
- Admin approval workflow: answers are hidden until approved
- Global search integration (Ctrl+K searches FAQ)
- Error-to-FAQ references: errors can link to relevant FAQ entries
- Pinned questions and official answers curated by admin
- Markdown-formatted answers
- Categorized questions (getting-started, google-classroom, study-tools, account, courses, messaging, tasks, other)

## GitHub Issues

- #437: Backend models (FAQQuestion + FAQAnswer tables)
- #438: Pydantic schemas
- #439: API routes (CRUD + admin approval)
- #440: Global search integration
- #441: Error-to-FAQ reference system
- #442: Frontend pages (list, detail, admin)
- #443: Tests
- #444: Seed initial how-to entries

## Instructions

Implement in this order. After each step, run tests to verify.

### Step 1: Backend Models (`app/models/faq.py`)

Create FAQQuestion and FAQAnswer models following existing patterns:

```python
import enum
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class FAQCategory(str, enum.Enum):
    GETTING_STARTED = "getting-started"
    GOOGLE_CLASSROOM = "google-classroom"
    STUDY_TOOLS = "study-tools"
    ACCOUNT = "account"
    COURSES = "courses"
    MESSAGING = "messaging"
    TASKS = "tasks"
    OTHER = "other"


class FAQQuestionStatus(str, enum.Enum):
    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"


class FAQAnswerStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class FAQQuestion(Base):
    __tablename__ = "faq_questions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), default=FAQCategory.OTHER.value)  # String, NOT Enum()
    status = Column(String(20), default=FAQQuestionStatus.OPEN.value)
    error_code = Column(String(100), nullable=True, index=True)  # Maps errors to FAQ
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_pinned = Column(Boolean, default=False)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    archived_at = Column(DateTime(timezone=True), nullable=True)

    creator = relationship("User", foreign_keys=[created_by_user_id])
    answers = relationship("FAQAnswer", back_populates="question", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_faq_questions_category_status", "category", "status"),
    )


class FAQAnswer(Base):
    __tablename__ = "faq_answers"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("faq_questions.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default=FAQAnswerStatus.PENDING.value)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    is_official = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    question = relationship("FAQQuestion", back_populates="answers")
    creator = relationship("User", foreign_keys=[created_by_user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id])

    __table_args__ = (
        Index("ix_faq_answers_question_status", "question_id", "status"),
        Index("ix_faq_answers_pending", "status", "created_at"),
    )
```

**CRITICAL cross-DB rules:**
- Store enums as `String(N)` NOT `Enum(PythonEnum)` (PostgreSQL stores enum NAMES not values)
- Use `DateTime(timezone=True)` NOT raw `DATETIME`
- Use `default=False` for booleans NOT `default=0`

**Registration:**
- Import models in `app/models/__init__.py`
- Import in `main.py` so `Base.metadata.create_all()` picks them up
- New tables — no ALTER TABLE migration needed

### Step 2: Pydantic Schemas (`app/schemas/faq.py`)

Create request/response schemas:
- FAQQuestionCreate (title required, description optional, category defaults to "other")
- FAQQuestionUpdate (all fields optional)
- FAQQuestionResponse (all fields + computed creator_name, answer_count)
- FAQQuestionDetail (extends Response + includes answers list)
- FAQAnswerCreate (content required)
- FAQAnswerUpdate (content optional)
- FAQAnswerResponse (all fields + computed creator_name, reviewer_name)
- FAQQuestionPin (is_pinned bool)

Use `from_attributes = True` (Pydantic 2.x).

### Step 3: API Routes (`app/api/routes/faq.py`)

Create router with `prefix="/faq"`. Follow existing patterns from tasks.py.

**Public endpoints (any authenticated user):**
- `GET /questions` — List with filters: category, status, search, pinned_only, skip, limit
- `GET /questions/{id}` — Detail with approved answers (all answers for admin), increment view_count
- `POST /questions` — Create question
- `PATCH /questions/{id}` — Edit own question (admin can edit any)
- `DELETE /questions/{id}` — Soft delete (archived_at)
- `POST /questions/{id}/answers` — Submit answer (status=pending), notify admins
- `PATCH /answers/{id}` — Edit own pending answer only

**Admin endpoints:**
- `GET /admin/pending` — List pending answers
- `PATCH /admin/answers/{id}/approve` — Approve, notify author + question author
- `PATCH /admin/answers/{id}/reject` — Reject, notify author
- `PATCH /admin/questions/{id}/pin` — Pin/unpin
- `PATCH /admin/answers/{id}/mark-official` — Set official (unmark others)
- `DELETE /admin/answers/{id}` — Hard delete
- `POST /admin/questions` — Create official FAQ (auto-approved Q+A)

**Error hint endpoint:**
- `GET /by-error-code/{code}` — Returns matching FAQ question if exists

**Key patterns:**
- Use `selectinload()` for eager loading relationships
- Use `escape_like()` for search patterns (from `app.core.utils`)
- Use `log_action()` for audit logging
- Filter `archived_at.is_(None)` by default
- Non-admin: filter answers to status=approved only
- Send notifications via Notification model

Register in main.py: `app.include_router(faq.router, prefix="/api")`

### Step 4: Search Integration (`app/api/routes/search.py`)

1. Import FAQQuestion model
2. Add "faq" to `all_types` set
3. Add "faq" to ENTITY_LABELS dict
4. Create `_search_faq()` helper — search title + description, filter archived, sort pinned first
5. Call in global_search() when "faq" in requested types

### Step 5: Frontend API Client (`frontend/src/api/faq.ts`)

Create TypeScript interfaces and faqApi object:
- FAQQuestion, FAQAnswer, FAQQuestionDetail interfaces
- Methods for all endpoints (listQuestions, getQuestion, createQuestion, createAnswer, etc.)
- Admin methods (listPendingAnswers, approveAnswer, rejectAnswer, pinQuestion, markAnswerOfficial)

### Step 6: Frontend Pages

**FAQPage** (`/faq`) — All users:
- Search bar, category filter buttons, pinned-only toggle
- Question cards with title, category badge, answer count, view count, status
- "Ask a Question" modal
- DashboardLayout wrapper

**FAQDetailPage** (`/faq/:id`) — All users:
- Question card with metadata
- Approved answers list (official first)
- Submit answer form with "pending review" help text
- Edit pending answers inline
- Delete button for owner/admin with useConfirm()

**AdminFAQPage** (`/admin/faq`) — Admin only:
- Tabs: Pending Answers | All Questions
- Pending: approve/reject buttons per answer
- Questions: pin/unpin, view links

### Step 7: Routing & Navigation

**App.tsx:** Add routes /faq, /faq/:id, /admin/faq (admin only via ProtectedRoute)

**DashboardLayout.tsx:** Add "FAQ" nav item for all roles, "FAQ Management" for admin

### Step 8: Tests (`tests/test_faq.py`)

Cover: CRUD, authorization, visibility rules (pending hidden from non-admin), search integration, approval workflow, notifications.

### Step 9: Seed Data

Create 10-15 initial FAQ entries covering common how-to questions. Use the admin endpoint or a startup seed script. Pin the "Getting Started" entries.

## Cross-DB Compatibility Reminders

- Enums as String(N) not Enum(PythonEnum)
- DateTime(timezone=True) not DATETIME
- Boolean default=False not default=0
- New tables: create_all() handles them, no migration needed

## Verification

After implementation:
1. `python -m pytest --tb=short -q` — all tests pass
2. `cd frontend && npm run build` — no build errors
3. `cd frontend && npm test` — all frontend tests pass
4. Manual test: create question, submit answer, approve as admin, verify visibility
5. Manual test: global search returns FAQ results
