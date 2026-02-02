# /teacher-comms - Scaffold Teacher Email Monitoring Feature

Monitor Gmail inbox and Google Classroom announcements from teachers. Display in EMAI with AI summaries, searchable archive, and in-app notifications.

## Feature Overview

Teacher communication monitoring provides:
- Gmail inbox polling for teacher emails (primary category)
- Google Classroom announcement fetching
- AI-powered summarization (action items, deadlines, key info)
- Searchable/filterable communication archive
- Unread tracking and in-app notifications
- Background sync every 15 minutes via APScheduler
- Manual sync trigger
- OAuth re-consent flow for new scopes

## Architecture

```
Gmail API ──┐                    ┌── TeacherCommunication DB
             ├── sync job (15m) ──┤── AI Summary (OpenAI)
Classroom ──┘                    └── Notification (in-app)
```

Deduplication via unique composite index on `(user_id, source_id)`. Gmail messages use the Gmail message ID. Classroom announcements use `ann_{announcement_id}` prefix.

## Instructions

When implementing or modifying this feature, the following files are involved:

### 1. Backend Model (app/models/teacher_communication.py)

```python
import enum

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class CommunicationType(str, enum.Enum):
    EMAIL = "email"
    ANNOUNCEMENT = "announcement"
    COMMENT = "comment"


class TeacherCommunication(Base):
    __tablename__ = "teacher_communications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(Enum(CommunicationType), nullable=False)

    # Source identification (dedup key)
    source_id = Column(String(255), nullable=False, index=True)

    # Sender info
    sender_name = Column(String(255), nullable=True)
    sender_email = Column(String(255), nullable=True)

    # Content
    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    snippet = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)

    # Context (for Classroom items)
    course_name = Column(String(255), nullable=True)
    course_id = Column(String(255), nullable=True)

    # Metadata
    received_at = Column(DateTime(timezone=True), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    __table_args__ = (
        Index("ix_teacher_comm_user_source", "user_id", "source_id", unique=True),
    )
```

### 2. User Model Additions (app/models/user.py)

Add sync state columns to track last poll timestamps:

```python
# Teacher communication sync state
gmail_last_sync = Column(DateTime(timezone=True), nullable=True)
classroom_last_sync = Column(DateTime(timezone=True), nullable=True)
```

For existing databases, run:
```sql
ALTER TABLE users ADD COLUMN gmail_last_sync DATETIME;
ALTER TABLE users ADD COLUMN classroom_last_sync DATETIME;
```

### 3. OAuth Scopes (app/services/google_classroom.py)

Add these scopes to the `SCOPES` list:
```python
"https://www.googleapis.com/auth/classroom.announcements.readonly",
"https://www.googleapis.com/auth/gmail.readonly",
```

Add helper functions:
- `get_gmail_service(access_token, refresh_token)` - Build Gmail API service
- `get_email_monitoring_auth_url(state)` - OAuth re-consent URL with `prompt="consent"`

### 4. Gmail Monitor (app/services/gmail_monitor.py)

```python
def fetch_teacher_emails(access_token, refresh_token, after_timestamp=None, max_results=50):
    """Fetch primary inbox emails via Gmail API with after: timestamp filtering."""
    # Returns (list[dict], credentials)
    # Each dict has: source_id, sender_name, sender_email, subject, body, snippet, received_at

def _parse_gmail_message(msg: dict) -> dict:
    """Parse Gmail API message into clean dict."""

def _extract_body_text(payload: dict) -> str:
    """Recursively extract plain text from MIME parts."""

def _extract_sender_name(from_header: str) -> str:
    """Extract display name from 'Name <email>' format."""

def _extract_sender_email(from_header: str) -> str:
    """Extract email from 'Name <email>' format."""
```

### 5. Classroom Monitor (app/services/classroom_monitor.py)

```python
def fetch_classroom_announcements(access_token, refresh_token, course_ids=None):
    """Fetch announcements from all active Google Classroom courses."""
    # Returns (list[dict], credentials)
    # Each dict has: source_id (ann_ prefix), sender_name, subject, body, snippet,
    #                course_name, course_id, received_at
```

### 6. AI Summarization (app/services/ai_service.py)

```python
async def summarize_teacher_communication(subject, body, sender_name, comm_type="email"):
    """Generate 1-3 sentence summary highlighting action items, deadlines, key info."""
    # Uses generate_content() with temperature=0.3, max_tokens=200
    # Summary cached in ai_summary column (never regenerated)
```

### 7. Schemas (app/schemas/teacher_communication.py)

```python
class TeacherCommunicationResponse(BaseModel):  # Full response
class TeacherCommunicationList(BaseModel):       # Paginated list (items, total, page, page_size)
class EmailMonitoringStatus(BaseModel):          # Status with sync timestamps and counts
```

### 8. API Routes (app/api/routes/teacher_communications.py)

```python
GET    /api/teacher-communications/                    # List with pagination, type filter, search, unread_only
GET    /api/teacher-communications/status              # Monitoring status + stats
GET    /api/teacher-communications/auth/email-monitoring  # OAuth URL for re-consent
GET    /api/teacher-communications/{comm_id}           # Get single (auto-marks as read)
PUT    /api/teacher-communications/{comm_id}/read      # Mark as read
POST   /api/teacher-communications/sync                # Manual sync trigger
```

### 9. Background Sync Job (app/jobs/teacher_comm_sync.py)

```python
async def sync_user_communications(user_id, db):
    """Sync Gmail + Classroom for a single user. Handles dedup, AI summary, notifications."""

async def check_teacher_communications():
    """Background job: iterate all Google-connected users every 15 minutes."""
```

Register in `main.py` startup:
```python
from apscheduler.triggers.interval import IntervalTrigger
scheduler.add_job(
    check_teacher_communications,
    IntervalTrigger(minutes=15),
    id="teacher_comm_sync",
    replace_existing=True,
)
```

### 10. Frontend API Client (frontend/src/api/client.ts)

```typescript
// Types
interface TeacherCommunication { id, user_id, type, source_id, sender_name, sender_email,
                                  subject, body, snippet, ai_summary, course_name, is_read,
                                  received_at, created_at }
interface TeacherCommunicationList { items, total, page, page_size }
interface EmailMonitoringStatus { gmail_enabled, classroom_enabled, last_gmail_sync,
                                  last_classroom_sync, total_communications, unread_count }

// API methods
teacherCommsApi.list(page, pageSize, type?, search?, unreadOnly?)
teacherCommsApi.get(id)
teacherCommsApi.getStatus()
teacherCommsApi.markAsRead(id)
teacherCommsApi.triggerSync()
teacherCommsApi.getEmailMonitoringAuthUrl()
```

### 11. Frontend Page (frontend/src/pages/TeacherCommsPage.tsx)

Split-pane layout:
- **Left panel (400px)**: Communication list with unread dots, type icons, AI summary preview
- **Right panel**: Full detail with AI summary card (purple gradient) + full message body
- **Header**: Search box, type filter dropdown (All/Emails/Announcements), Sync Now button
- **Connect banner**: Shown when Gmail is not connected, with "Connect Google" link

### 12. App Integration

- `App.tsx`: Add `/teacher-communications` route with ProtectedRoute
- `Dashboard.tsx`: Add "Teacher Comms" nav button in header
- `NotificationBell.tsx`: Handle `teacher_communication` notification type icon

## API Usage Examples

```bash
# List communications (paginated, with search)
curl "http://localhost:8000/api/teacher-communications/?page=1&page_size=20&search=math" \
  -H "Authorization: Bearer <token>"

# Filter by type
curl "http://localhost:8000/api/teacher-communications/?type=email" \
  -H "Authorization: Bearer <token>"

# Get monitoring status
curl http://localhost:8000/api/teacher-communications/status \
  -H "Authorization: Bearer <token>"

# View single communication (auto-marks as read)
curl http://localhost:8000/api/teacher-communications/1 \
  -H "Authorization: Bearer <token>"

# Manual sync trigger
curl -X POST http://localhost:8000/api/teacher-communications/sync \
  -H "Authorization: Bearer <token>"

# Get OAuth re-consent URL
curl http://localhost:8000/api/teacher-communications/auth/email-monitoring \
  -H "Authorization: Bearer <token>"
```

## Sync Flow

1. Background job runs every 15 minutes (APScheduler IntervalTrigger)
2. For each user with `google_access_token` set:
   - Fetch Gmail emails using `after:` timestamp from `gmail_last_sync`
   - Fetch Classroom announcements from all active courses
   - Dedup by `source_id` (skip existing)
   - Generate AI summary (temperature=0.3, max 200 tokens) — cached, never regenerated
   - Store `TeacherCommunication` record
   - Create in-app `Notification` (type=MESSAGE, link=/teacher-communications)
   - Update user's sync timestamps
3. Token refresh tracked — updated tokens saved back to DB
4. Per-user error isolation (one failure doesn't block others)

## Dependencies

- `google-api-python-client` (Gmail + Classroom APIs)
- `google-auth-oauthlib` (OAuth flow)
- `apscheduler` (background polling)
- `openai` (AI summarization)

## Related Issues

- GitHub Issue #31: Implement AI email communication agent
- GitHub Issue #20-23: Notification system
- GitHub Issue #8: Parent-teacher messaging
