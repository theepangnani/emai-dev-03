# /tasks - Task Management & Calendar

## Overview
Cross-role task manager with visual calendar. Any user can create tasks and optionally assign to related users. Tasks appear alongside assignments on the calendar. Custom React calendar components (no external library).

## Cross-Role Assignment

| Creator | Can Assign To | Check |
|---------|---------------|-------|
| Parent | Linked children | `parent_students` join |
| Teacher | Students in courses | `courses` + `student_courses` |
| Student | Linked parents | `parent_students` reverse |
| Admin | Self only | N/A |

## Data Model (`tasks` table)
Key fields: `created_by_user_id`, `assigned_to_user_id`, `title`, `description`, `due_date`, `reminder_at`, `is_completed`, `priority` (low/medium/high), `category`, `linked_assignment_id`, `archived_at`, `google_calendar_event_id`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tasks/` | GET | List tasks (filters: status, priority, date, include_archived) |
| `/api/tasks/` | POST | Create task (optional cross-role assignment) |
| `/api/tasks/{id}` | PATCH | Update (creator: all; assignee: completion only) |
| `/api/tasks/{id}` | DELETE | Soft-delete (archive) |
| `/api/tasks/{id}/restore` | PATCH | Restore archived task |
| `/api/tasks/{id}/permanent` | DELETE | Hard-delete (must be archived first) |
| `/api/tasks/assignable-users` | GET | List assignable users |
| `/api/calendar/events` | GET | Calendar events for date range (role-aware) |
| `/api/calendar/google-sync` | POST | Push task to Google Calendar |

## Archival System
- Delete = soft-delete (`archived_at`). Restore clears it. Permanent delete requires archived first.
- Auto-archive on completion; un-archive on un-completion.

## Calendar Views
- **Month**: 7-col grid, day cells with chips + "+N more" overflow
- **Week/3-Day**: Column layout with stacked cards
- **Day**: Single-column list

## Calendar Component Tree
```
CalendarView → CalendarHeader, CalendarMonthGrid, CalendarWeekGrid, CalendarDayGrid, CalendarEntryPopover
CalendarMonthGrid → CalendarDayCell → CalendarEntry
```

## Drag-and-Drop Rescheduling
- HTML5 DnD API. Only tasks draggable (not assignments).
- Optimistic UI with rollback. Task calendar IDs use `id + 1_000_000` offset.

## Visual Treatment
- Assignments: solid border + course color. Tasks: dashed border + priority color.
- Priority colors: high=#ef5350, medium=#ff9800, low=#66bb6a

## Role-Aware Calendar Data
- Student: tasks + assignments from enrolled courses
- Parent: tasks + children's assignments (filtered by child selector)
- Teacher: tasks + assignment deadlines for taught courses
- Admin: tasks only

## Key Files
Backend: `app/models/task.py`, `app/schemas/task.py`, `app/api/routes/tasks.py`, `app/api/routes/calendar.py`, `app/schemas/calendar.py`
Frontend: `frontend/src/pages/TasksPage.tsx`, `frontend/src/components/calendar/` (CalendarView, Header, MonthGrid, DayCell, WeekGrid, DayGrid, Entry, EntryPopover, types.ts, Calendar.css), `frontend/src/pages/ParentDashboard.tsx`

## Reminders
APScheduler job `task_reminder_{task_id}` fires at `reminder_at` → creates in-app notification.

## Google Calendar Push
User sets `sync_to_google=True` → backend creates/updates Google Calendar event → stores `google_calendar_event_id`.
