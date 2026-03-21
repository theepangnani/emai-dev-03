# Reusable Components

## Overview
ClassBridge has a library of reusable frontend components designed for consistency across dashboards and pages. When building new features, always check for existing components before creating new ones.

## Component Inventory

### Layout & Navigation

| Component | Location | Purpose |
|-----------|----------|---------|
| `DashboardLayout` | `frontend/src/components/DashboardLayout.tsx` | Shared layout wrapper — header, left nav sidebar (role-specific items), welcome subtitle. Parent role adds: Courses, Study Guides, Messages nav + action buttons (Add Child, Add Course, Create Study Guide, Add Task) |
| `ProtectedRoute` | `frontend/src/components/ProtectedRoute.tsx` | Route guard with `allowedRoles` prop for RBAC |
| `NotificationBell` | `frontend/src/components/NotificationBell.tsx` | Notification dropdown in header |

### Calendar Components (`frontend/src/components/calendar/`)

Reusable calendar system for displaying date-based items (assignments, tasks, events).

| Component | Purpose |
|-----------|---------|
| `CalendarView` | Main orchestrator — renders header + active grid view + popover. Props: `assignments`, `onCreateStudyGuide`, `onDayClick?`, `onTaskDrop?` |
| `CalendarHeader` | Navigation buttons (< Today >), title label, view toggle (Day/3-Day/Week/Month) |
| `CalendarMonthGrid` | 7-column month grid with day cells. Accepts `onTaskDrop?` |
| `CalendarDayCell` | Single day cell — day number + assignment chips + "+N more" overflow. **Drop target** for task drag-and-drop |
| `CalendarWeekGrid` | N-column layout (7 for week, 3 for 3-day) with stacked assignment cards. **Drop targets** on column bodies |
| `CalendarDayGrid` | Single-column day list view |
| `CalendarEntry` | Assignment/task rendered as `chip` (month) or `card` (week/day), color-coded by course/priority. **Tasks are draggable** via native HTML5 DnD |
| `CalendarEntryPopover` | Click popover — title, course, due time, description, action button |
| `DayDetailModal` | Full CRUD modal for a specific date — lists assignments + tasks as sticky note cards, inline add task |
| `useCalendarNav` | Hook — currentDate, viewMode, goNext/goPrev/goToday, rangeStart/rangeEnd, headerLabel |

**Key types** (`frontend/src/components/calendar/types.ts`):
```typescript
interface CalendarAssignment {
  id: number; title: string; description: string | null;
  courseId: number; courseName: string; courseColor: string;
  dueDate: Date; childName: string; maxPoints: number | null;
}
type CalendarViewMode = 'day' | '3day' | 'week' | 'month';
const COURSE_COLORS: string[] // 10-color palette
function getCourseColor(courseId: number, courseIds: number[]): string
function dateKey(d: Date): string  // 'YYYY-MM-DD'
function isSameDay(a: Date, b: Date): boolean
```

**Usage example** (from ParentDashboard):
```tsx
import { CalendarView } from '../components/calendar/CalendarView';
import type { CalendarAssignment } from '../components/calendar/types';
import { getCourseColor } from '../components/calendar/types';

// Derive assignments from data
const calendarAssignments: CalendarAssignment[] = assignments.map(a => ({
  id: a.id, title: a.title, description: a.description,
  courseId: a.course_id,
  courseName: courses.find(c => c.id === a.course_id)?.name || 'Unknown',
  courseColor: getCourseColor(a.course_id, courseIds),
  dueDate: new Date(a.due_date),
  childName: '', maxPoints: a.max_points,
}));

// Render
<CalendarView
  assignments={calendarAssignments}
  onCreateStudyGuide={(assignment) => { /* open study modal */ }}
  onDayClick={(date) => { /* open day detail modal */ }}
  onTaskDrop={(calendarId, newDate) => { /* reschedule task via API */ }}
/>
```

### Parent Sub-components (`frontend/src/components/parent/`)

| Component | Purpose |
|-----------|---------|
| `ParentActionBar` | Top action buttons — Add Child, Add Course, Create Study Guide |
| `ParentSidebar` | Right sidebar — collapsible Courses, Study Materials, Messages, Undated Assignments |

### Form & Data Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `CourseAssignSelect` | `frontend/src/components/CourseAssignSelect.tsx` | Dropdown to assign a study guide to a course. Fetches courses, calls PATCH endpoint. |

**CourseAssignSelect usage:**
```tsx
import { CourseAssignSelect } from '../components/CourseAssignSelect';

<CourseAssignSelect
  guideId={guide.id}
  currentCourseId={guide.course_id}
  onCourseChanged={(courseId) => setGuide({ ...guide, course_id: courseId })}
/>
```

## CSS Architecture

### Shared Styles
- **`Dashboard.css`** (loaded via `DashboardLayout`): Modal styles (`.modal-overlay`, `.modal`, `.modal-form`, `.modal-actions`, `.generate-btn`, `.cancel-btn`), card styles (`.dashboard-card`), inline controls (`.inline-course-select`)
- **`Calendar.css`** (`frontend/src/components/calendar/Calendar.css`): All calendar styles — header, grids, entries, popover, responsive

### CSS Naming Conventions
- Calendar: `cal-` prefix (e.g., `cal-header`, `cal-nav-btn`, `cal-month-grid`, `cal-entry-chip`)
- Sidebar: `sidebar-` prefix (e.g., `sidebar-section`, `sidebar-list-item`, `sidebar-action-btn`)
- Parent layout: `parent-` prefix (e.g., `parent-layout`, `parent-calendar-area`, `parent-sidebar-area`)

### CSS Scoping Reminder
Modal styles (`.modal-overlay`, `.modal`) are in `Dashboard.css`, which is shared via `DashboardLayout`. Don't define shared modal styles in page-specific CSS files.

## Design Tokens (CSS Variables)
All components use CSS custom properties from the design system:
```css
--color-accent        /* Primary blue #4a90d9 */
--color-accent-warm   /* Warm accent for gradients */
--color-accent-strong /* Darker accent for hover */
--color-surface       /* Card/panel background */
--color-surface-alt   /* Hover/secondary background */
--color-border        /* Borders and dividers */
--color-ink           /* Primary text */
--color-ink-muted     /* Secondary text */
--color-danger        /* Error/delete red */
--color-success       /* Success green */
```

## Guidelines for New Components

1. **Check this inventory first** — don't duplicate existing components
2. **Use design tokens** — never hardcode colors, use `var(--color-*)` variables
3. **Follow naming conventions** — use descriptive CSS prefixes scoped to the component
4. **Keep components focused** — one responsibility per component
5. **Export types** — define TypeScript interfaces for props and share types via `types.ts`
6. **Responsive by default** — include `@media` breakpoints for mobile support
7. **Avoid external dependencies** — prefer custom components over adding npm packages
