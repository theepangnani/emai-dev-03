## 7. Role-Based Dashboards - IMPLEMENTED

> **UI/UX Audit:** See [design/UI_AUDIT_REPORT.md](../design/UI_AUDIT_REPORT.md) for comprehensive audit of all dashboards with user journey maps, friction points, and prioritized improvements. Epic: #668.

Each user role has a customized dashboard (dispatcher pattern via `Dashboard.tsx`):

| Dashboard | Key Features | Status |
|-----------|--------------|--------|
| **Parent Dashboard** | Icon-only sidebar, child filter pills (no "All Kids" — toggle-deselect instead), Today's Focus header, simplified alert banner, collapsible student detail panel, + icon popover for quick actions (replaces action bar) | Implemented (v3 simplification — #540, PR #545; v3.1 UX polish — #557; v3.2 + popover — #692, PR #693) |
| **Student Dashboard** | Courses, assignments, study tools, Google Classroom sync, file upload | Implemented |
| **Teacher Dashboard** | Courses teaching, manual course creation, multi-Google account management, messages, teacher communications | Implemented (partial) |
| **Admin Dashboard** | Platform stats, user management table (search, filter, pagination), role management, broadcast messaging, individual user messaging | Implemented (messaging planned) |

> **Note:** Phase 4 adds marketplace features (bookings, availability, profiles) to the existing Teacher Dashboard for teachers with `teacher_type=private_tutor`. No separate "Tutor Dashboard" is needed.

### Parent Dashboard Layout (v3.1 — Simplified + UX Polish) - IMPLEMENTED

**GitHub Issues:** #540 (parent), #541 (sidebar), #542 (alert banner + pills), #543 (actions + detail panel), #544 (calendar + cleanup), #557 (UX polish: Today's Focus, icon-only sidebar, collapsible panel) — all closed, deployed via PR #545

The Parent Dashboard uses an **urgency-first, single-hub layout**: icon-only sidebar, child filter pills, Today's Focus header, simplified alert banner, primary/secondary quick actions, collapsible student detail panel, and collapsible calendar. Replaces the v2 calendar-centric layout.

#### Design Principles
- **No scroll / single viewport**: The entire dashboard should fit within one screen (no vertical scrolling on desktop). All content visible without scrolling at 1080p resolution. Overflow handled via expandable sections and collapsed panels, not page length.
- **Urgency-first**: Lead with what needs action NOW (overdue → due today → due soon)
- **Progressive disclosure**: Summary counts in Today's Focus header, expandable detail below
- **Single child selection model**: One mechanism (pills), one effect (filters everything)
- **Consistent creation patterns**: Every creatable entity gets a button in the same action bar, with primary/secondary visual hierarchy
- **Calendar as reference, not center**: Default collapsed with item count badge
- **Positive reinforcement**: "All caught up!" message when no urgent tasks

#### Layout Structure
```
┌─────────────────────────────────────────────────────────────┐
│ Header: Logo | Search (Ctrl+K) | Bell | User ▼ | Sign Out  │
├─────┬───────────────────────────────────────────────────────┤
│ICON │  [Child1] [Child2] [+]     ← Child Filter Pills + Add │
│ONLY │───────────────────────────────────────────────────────│
│SIDE │  TODAY'S FOCUS HEADER                                 │
│BAR  │  "Good morning, Name!"                                │
│     │  [3 Overdue] [2 Due Today] [5 Upcoming]               │
│ 🏠  │  "Small steps lead to big achievements" (quote)       │
│ 👨‍👩‍👧 │  — OR —                                               │
│ 📚  │  "All caught up! Great job staying on top of things." │
│ 📄  │───────────────────────────────────────────────────────│
│ ✅  │  ⚠ ALERT BANNER (overdue + pending invites only)     │
│ 💬  │───────────────────────────────────────────────────────│
│ ❓  │  (Quick actions via [+] popover on child pills row)    │
│     │───────────────────────────────────────────────────────│
│     │  STUDENT DETAIL PANEL (collapsible)                   │
│     │  ┌─ Summary Header (click to collapse) ──────┐       │
│     │  │ "Emma — 3 courses, 2 overdue tasks"       │       │
│     │  ├─ Courses (3) ─────────────────────────────┤       │
│     │  │ Math 101 | Science | English              │       │
│     │  ├─ Course Materials (5) ────────────────────┤       │
│     │  │ Ch5 Guide | Quiz 3 | Flashcards...        │       │
│     │  ├─ Tasks by Urgency ────────────────────────┤       │
│     │  │ Overdue: Math HW (2 days ago)             │       │
│     │  │ Today: Science Lab Report                  │       │
│     │  │ Next 3 Days: English Essay (Wed)           │       │
│     │  └────────────────────────────────────────────┘       │
│     │  (Calendar moved to Tasks page — #691)                 │
└─────┴───────────────────────────────────────────────────────┘
```

#### 1. Icon-Only Sidebar (#541, #557)
The `DashboardLayout` renders an **always icon-only left sidebar** on desktop (≥768px), replacing the previous full-width persistent sidebar.

**Navigation items** (all roles, icon-only with hover tooltips):
- **Overview** — Dashboard view
- **Child Profiles** — `/my-kids`
- **Courses** — `/courses`
- **Course Materials** — `/course-materials`
- **Tasks** — `/tasks`
- **Messages** — `/messages` (with unread badge)
- **Help** — `/help`

**Design:**
- Always displays as icon-only (no expanded label mode)
- Bigger icons for easy recognition
- Hover tooltips show the full navigation label
- Compact width maximizes content area

**Responsive behavior:**
- ≥768px: Icon-only sidebar with hover tooltips
- <768px: Hamburger overlay (existing behavior)

All non-dashboard pages include a back button (←) in the header (#529, #696). This includes Course Material Detail page (added in PR #697).

#### 2. Child Filter Pills (#542, #688)
- Single row of clickable pill buttons at the top of the content area (parent only)
- **No "All Children" button** — removed (#688); click selected child again to deselect (toggle behavior)
- **Click** a pill → filters everything below (Today's Focus, detail panel, tasks)
- **Click again** → deselects back to all-children mode
- Single-child families: child auto-selected, no pills shown
- A **+ icon button** (circle with dashed border) sits at the end of the pills row, opening a popover with quick actions (#692)
- Replaces the old child tab bar AND child highlight cards (removed as redundant)

#### 3. Today's Focus Header (#557)
Replaces the old welcome section and the removed status summary cards. Provides an at-a-glance view of the day's priorities.

- **Greeting**: "Good morning/afternoon/evening, [Name]!"
- **Urgency badges**: Compact inline badges showing overdue, due-today, and upcoming counts (filtered by selected child)
- **Inspiration quote**: Short, compact motivational quote (role-based)
- **All-clear state**: When no overdue or due-today items exist, displays a positive "All caught up! Great job staying on top of things." message instead of counts
- Badges link to filtered task views (e.g., clicking "3 Overdue" navigates to `/tasks?due=overdue`)

#### 4. Alert Banner (#542, #557 — simplified)
- Appears below Today's Focus header when there are urgent items
- **Red section**: Overdue items (count + "View" link to `/tasks?due=overdue`)
- **Amber section**: Pending invites (with Resend button)
- Sections are independently dismissible per session
- Hidden when no urgent items
- **Removed** (v3.1): Blue upcoming deadlines section and unread messages section — these are now covered by Today's Focus header and the notification bell respectively

#### 5. Quick Actions — + Icon Popover (#543, #557, #692 — redesigned)
Quick actions are now accessed via a **+ icon button** (circle with dashed border) at the end of the child filter pills row. Clicking the + opens a popover with action items:

- **Upload Documents** → CreateStudyMaterialModal (existing)
- **New Task** → CreateTaskModal (reuse from TasksPage)

The previous primary/secondary action bar layout was replaced by the compact popover pattern for a cleaner UI (#692, PR #693). The + icon button is a shared `AddActionButton` component reused across Dashboard, Tasks, My Kids, and Course Material Detail pages.

**AddActionButton component** (`frontend/src/components/AddActionButton.tsx`):
- Accepts an array of `ActionItem` objects (icon, label, onClick)
- 40×40px circle button with dashed border
- Click-outside-to-dismiss popover
- Reusable across all pages

#### 6. Collapsible Student Detail Panel (#543, #557 — collapsible)
When a child is selected, shows their world inline with a collapsible interface:

**Summary header** (always visible, click to collapse/expand):
- Shows child name with key stats (course count, overdue task count)
- Chevron indicator for expand/collapse state
- **Defaults to expanded** on page load

**Courses** (expandable section):
- List of enrolled courses with color dots

**Course Materials** (expandable section):
- Recent materials with type badges (guide/quiz/flashcards)

**Tasks by Urgency** (always expanded):
- **Overdue**: red items with "X days overdue" badge
- **Due Today**: amber items
- **Next 3 Days**: green items with day label
- Remaining tasks collapsed under "Other"

**"All Children" mode** — merges tasks from all children with child-name labels on each item.

#### 7. Calendar Section (#544, #691 — moved to Tasks page)
- **Moved from Parent Dashboard to Tasks page** (#691, PR `a35a329`) — Calendar is no longer on the main dashboard; it lives on the Tasks page (`/tasks`) where it is contextually more relevant alongside task management.
- **Defaults to collapsed** (localStorage key `calendar-collapsed` defaults to `true`)
- Collapsed bar shows item count: "Calendar (N items)" with expand chevron
- When expanded: full calendar with Month/Week/3-Day/Day views (unchanged from v2)
- Day Detail Modal, drag-and-drop rescheduling, and popovers all preserved
- Calendar collapse styles are in `TasksPage.css` (moved from `ParentDashboard.css` — #694, PR #695)

#### 8. Edit Child Modal (unchanged from v2)
- Accessible via child profile actions
- Tabs: Details, Courses, Reminders

#### 9. Courses View (Left Nav → `/courses`) — unchanged from v2
Dedicated page for course management (accessible to all roles):
- **List all courses** — parent-created + child-enrolled courses (parent view)
- **Click course card** → expands inline to show course materials preview panel
- **Child selector tabs** — pill buttons for parents with multiple children
- **Course Detail Page** — edit course, CRUD content, upload documents

#### 10. Course Materials View (Left Nav → `/course-materials`) — unchanged from v2
Dedicated page for course material management:
- **List all materials** — parent's own + children's materials
- **Create material** — opens Study Tools modal
- **CRUD operations** — view, edit, delete
- Filter by: type, course, child

#### Calendar Components (Reusable)
Located in `frontend/src/components/calendar/`:
- `useCalendarNav` — Hook for date navigation, view mode, range computation
- `CalendarView` — Orchestrator component (header + active grid + popover)
- `CalendarHeader` — Nav buttons, title, view toggle
- `CalendarMonthGrid` / `CalendarDayCell` — Month view grid
- `CalendarWeekGrid` — Week/3-day column layout
- `CalendarDayGrid` — Single-day list view
- `CalendarEntry` — Assignment/task rendered as chip (month) or card (week/day); tasks are draggable for rescheduling
- `CalendarEntryPopover` — Assignment/task detail popover
- `DayDetailModal` — Full CRUD modal for a specific date (new)

#### Drag-and-Drop Task Rescheduling
- Tasks can be dragged to a different day in month view (chips) or week/3-day view (cards)
- Uses native HTML5 Drag and Drop API (no external library)
- Drop targets (day cells, week columns) highlight with blue dashed outline during drag
- Optimistic UI: task moves immediately on drop, reverts if API update fails
- Only tasks are draggable — classroom assignments remain fixed
- Drag data carries task ID and `itemType: 'task'` for validation

#### Key Design Details
- **Course Color-Coding**: 10-color palette assigned by course index, consistent everywhere
- **Task vs Assignment**: Assignments have course color border; tasks have a distinct style (e.g., dashed border or priority-based color)
- **Responsive**: At < 1024px, left nav collapses to icons; calendar takes full width
- **Right sidebar removed**: Courses and Study Guides promoted to dedicated pages via left nav

### Parent-Student Relationship
Parents and students have a **many-to-many** relationship via the `parent_students` join table. A student can have multiple parents (mother, father, guardian), and parent linking is optional.

**Registration & Linking Methods:**
- **Parent Registers Child**: Create a student account from the Parent Dashboard; child receives an invite email to set their password
- **Link by Email**: Enter an existing student's registered email address
- **Via Google Classroom**: Connect Google account, auto-discover children enrolled in Google Classroom courses, select and bulk-link
- **Self-Registered Student**: Students can register independently and use the platform without any parent

### Role-Based Access Control
- Backend: `require_role()` dependency factory for endpoint-level role checking
- Frontend: `ProtectedRoute` component with optional `allowedRoles` prop
- Shared `DashboardLayout` component for common header/nav across all dashboards

---

