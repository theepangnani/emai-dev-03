# Task Manager & Calendar

## Overview
A personal task/todo manager and visual calendar for all EMAI users. Provides a unified view of upcoming deadlines and personal tasks with role-aware data sources and one-way push to Google Calendar.

## Data Model

### `tasks` Table
```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    due_date TIMESTAMP,
    reminder_at TIMESTAMP,
    is_completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    priority VARCHAR(20) DEFAULT 'medium',        -- low, medium, high
    category VARCHAR(100),                         -- e.g., "homework", "meeting", "personal"
    linked_assignment_id INTEGER REFERENCES assignments(id),  -- optional link to assignment
    google_calendar_event_id VARCHAR(255),         -- for sync tracking
    sync_to_google BOOLEAN DEFAULT FALSE,          -- user toggle per task
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Notes:**
- Tasks are personal to each user — no shared tasks
- `linked_assignment_id` lets students create a task tied to an assignment (e.g., "Study for Math test")
- `google_calendar_event_id` tracks the pushed event for updates/deletes
- Assignment due dates are NOT stored as tasks — they're queried from the `assignments` table at calendar render time

## Role-Aware Calendar Data Sources

### Student
```
Calendar Items = user's tasks + assignments from student_courses
```
- Tasks: `SELECT * FROM tasks WHERE user_id = :user_id`
- Assignments: `SELECT * FROM assignments WHERE course_id IN (SELECT course_id FROM student_courses WHERE student_id = :student_id)`

### Parent
```
Calendar Items = user's tasks + children's assignments
```
- Tasks: `SELECT * FROM tasks WHERE user_id = :user_id`
- Assignments: via `parent_students` → `students` → `student_courses` → `assignments`

### Teacher
```
Calendar Items = user's tasks + assignment deadlines for courses they teach
```
- Tasks: `SELECT * FROM tasks WHERE user_id = :user_id`
- Assignments: `SELECT * FROM assignments WHERE course_id IN (SELECT id FROM courses WHERE teacher_id = :teacher_id)`

### Admin
```
Calendar Items = user's tasks only
```
- Tasks: `SELECT * FROM tasks WHERE user_id = :user_id`

## API Endpoints

### Task CRUD (all authenticated users)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tasks/` | GET | List tasks with filters (status, priority, date range) |
| `/api/tasks/` | POST | Create a new task |
| `/api/tasks/{id}` | PUT | Update a task |
| `/api/tasks/{id}` | DELETE | Delete a task |
| `/api/tasks/{id}/complete` | POST | Mark task as completed |

### Calendar (all authenticated users)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/calendar/events` | GET | Get calendar events for date range (role-aware) |
| `/api/calendar/google-sync` | POST | Push a task/reminder to Google Calendar |

## Request/Response Schemas

### CreateTaskRequest
```python
class CreateTaskRequest(BaseModel):
    title: str
    description: Optional[str]
    due_date: Optional[datetime]
    reminder_at: Optional[datetime]
    priority: str = "medium"           # low, medium, high
    category: Optional[str]
    linked_assignment_id: Optional[int]
    sync_to_google: bool = False
```

### UpdateTaskRequest
```python
class UpdateTaskRequest(BaseModel):
    title: Optional[str]
    description: Optional[str]
    due_date: Optional[datetime]
    reminder_at: Optional[datetime]
    priority: Optional[str]
    category: Optional[str]
    sync_to_google: Optional[bool]
```

### TaskResponse
```python
class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    due_date: Optional[datetime]
    reminder_at: Optional[datetime]
    is_completed: bool
    completed_at: Optional[datetime]
    priority: str
    category: Optional[str]
    linked_assignment_id: Optional[int]
    sync_to_google: bool
    created_at: datetime
```

### CalendarEventResponse
```python
class CalendarEventResponse(BaseModel):
    id: str                            # "task-{id}" or "assignment-{id}"
    type: str                          # "task" or "assignment"
    title: str
    description: Optional[str]
    start: datetime                    # due_date for assignments, due_date for tasks
    end: Optional[datetime]
    color: str                         # color code by type
    priority: Optional[str]            # only for tasks
    is_completed: Optional[bool]       # only for tasks
    course_name: Optional[str]         # only for assignments
    child_name: Optional[str]          # only for parent view
```

### CalendarEventsRequest (query params)
```python
class CalendarEventsRequest(BaseModel):
    start_date: date                   # range start
    end_date: date                     # range end
    include_tasks: bool = True
    include_assignments: bool = True
```

## Google Calendar Push Integration

### Flow
1. User creates/updates a task with `sync_to_google=True`
2. Backend checks user has Google OAuth tokens
3. Uses Google Calendar API to create/update an event
4. Stores `google_calendar_event_id` on the task
5. On task deletion: delete the Google Calendar event
6. On task update: update the Google Calendar event

### Google Calendar API
```python
from googleapiclient.discovery import build

service = build('calendar', 'v3', credentials=credentials)

event = {
    'summary': task.title,
    'description': task.description,
    'start': {'dateTime': task.due_date.isoformat()},
    'end': {'dateTime': (task.due_date + timedelta(hours=1)).isoformat()},
    'reminders': {
        'useDefault': False,
        'overrides': [
            {'method': 'popup', 'minutes': minutes_before},
        ],
    },
}

event = service.events().insert(calendarId='primary', body=event).execute()
```

### Requirements
- Add `google-api-python-client` scope for `https://www.googleapis.com/auth/calendar.events`
- Existing Google OAuth scopes need to include calendar access
- For teachers with multi-Google accounts, sync to the primary account by default

## Visual Calendar Frontend

### Views
- **Month view**: Grid with day cells showing item counts and titles
- **Week view**: 7-column layout with time slots
- **Day view**: Single column with hourly time slots

### UI Components
- Calendar header: navigation (prev/next), view toggle (day/week/month), today button
- Event items: color-coded chips (blue for assignments, green for tasks, red for high priority)
- Click event: open detail modal with edit/delete options
- Quick-add: click on empty time slot to create task
- Filter panel: toggle assignments, tasks, priority levels

### Recommended Library
- `@fullcalendar/react` — mature, feature-rich calendar component with day/week/month views, drag-and-drop, and event rendering

## Key Files

### Backend
| File | Purpose |
|------|---------|
| `app/models/task.py` | Task model (new) |
| `app/api/routes/tasks.py` | Task CRUD endpoints (new) |
| `app/api/routes/calendar.py` | Calendar events endpoint (new) |
| `app/schemas/task.py` | Task request/response schemas (new) |
| `app/schemas/calendar.py` | Calendar event schemas (new) |
| `app/services/google_calendar.py` | Google Calendar push service (new) |

### Frontend
| File | Purpose |
|------|---------|
| `frontend/src/pages/CalendarPage.tsx` | Visual calendar page (new) |
| `frontend/src/components/TaskList.tsx` | Task list sidebar/panel (new) |
| `frontend/src/components/TaskForm.tsx` | Create/edit task form (new) |
| `frontend/src/api/client.ts` | `tasksApi`, `calendarApi` methods |

## Implementation Notes
- The calendar page is accessible from all dashboards via nav link — it's a shared feature, not role-specific
- Tasks belong to users, not roles — the role determines what *additional* items (assignments) appear
- Assignment items on the calendar are read-only (can't edit assignment due dates from the calendar)
- Reminder notifications can leverage the existing `Notification` model and notification bell
- Google Calendar sync is optional — the calendar works fully without Google
- Consider adding a "My Tasks" widget to each role dashboard showing upcoming tasks
