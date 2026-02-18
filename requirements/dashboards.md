## 7. Role-Based Dashboards - IMPLEMENTED

Each user role has a customized dashboard (dispatcher pattern via `Dashboard.tsx`):

| Dashboard | Key Features | Status |
|-----------|--------------|--------|
| **Parent Dashboard** | Persistent sidebar, child filter pills, alert banner, urgency-grouped tasks, student detail panel, Quick Actions bar, collapsible calendar | Implemented (v3 simplification — #540, PR #545) |
| **Student Dashboard** | Courses, assignments, study tools, Google Classroom sync, file upload | Implemented |
| **Teacher Dashboard** | Courses teaching, manual course creation, multi-Google account management, messages, teacher communications | Implemented (partial) |
| **Admin Dashboard** | Platform stats, user management table (search, filter, pagination), role management, broadcast messaging, individual user messaging | Implemented (messaging planned) |

> **Note:** Phase 4 adds marketplace features (bookings, availability, profiles) to the existing Teacher Dashboard for teachers with `teacher_type=private_tutor`. No separate "Tutor Dashboard" is needed.

### Parent Dashboard Layout (v3 — Simplified) - IMPLEMENTED

**GitHub Issues:** #540 (parent), #541 (sidebar), #542 (alert banner + pills), #543 (actions + detail panel), #544 (calendar + cleanup) — all closed, deployed via PR #545

The Parent Dashboard uses an **urgency-first, single-hub layout**: persistent sidebar, child filter pills, alert banner, quick actions, student detail panel, and collapsible calendar. Replaces the v2 calendar-centric layout.

#### Design Principles
- **No scroll / single viewport**: The entire dashboard should fit within one screen (no vertical scrolling on desktop). All content visible without scrolling at 1080p resolution. Overflow handled via expandable sections and collapsed panels, not page length.
- **Urgency-first**: Lead with what needs action NOW (overdue → due today → due soon)
- **Progressive disclosure**: Summary counts at top, expandable detail below
- **Single child selection model**: One mechanism (pills), one effect (filters everything)
- **Consistent creation patterns**: Every creatable entity gets a button in the same action bar
- **Calendar as reference, not center**: Default collapsed with item count badge

#### Layout Structure
```
┌─────────────────────────────────────────────────────────────┐
│ Header: Logo | Search (Ctrl+K) | Bell | User ▼ | Sign Out  │
├────────────┬────────────────────────────────────────────────┤
│ PERSISTENT │  [Child1] [Child2] [All]   ← Child Filter Pills│
│ SIDEBAR    │─────────────────────────────────────────────────│
│            │  ⚠ ALERT BANNER (overdue, invites, messages)   │
│ Overview   │─────────────────────────────────────────────────│
│ My Kids    │  STATUS CARDS                                   │
│ Courses    │  [Overdue ❗] [Due Today] [Next 3 Days] [Tasks] │
│ Materials  │─────────────────────────────────────────────────│
│ Tasks      │  QUICK ACTIONS                                  │
│ Messages 3 │  [+ Material] [+ Task] [+ Child] [+ Course]    │
│ Help       │─────────────────────────────────────────────────│
│            │  STUDENT DETAIL PANEL (for selected child)      │
│ ─────────  │  ┌ Courses (3) ─────────────────────────┐      │
│ + Material │  │ Math 101 | Science | English          │      │
│ + Task     │  ├ Course Materials (5) ─────────────────┤      │
│ + Child    │  │ Ch5 Guide | Quiz 3 | Flashcards...    │      │
│ + Course   │  ├ Tasks by Urgency ─────────────────────┤      │
│            │  │ 🔴 Overdue: Math HW (2 days ago)       │      │
│            │  │ 🟡 Today: Science Lab Report            │      │
│            │  │ 🟢 Next 3 Days: English Essay (Wed)     │      │
│            │  └───────────────────────────────────────┘      │
│            │─────────────────────────────────────────────────│
│            │  ▶ Calendar (collapsed by default)              │
└────────────┴────────────────────────────────────────────────┘
```

#### 1. Persistent Sidebar (#541)
The `DashboardLayout` renders a **persistent left sidebar** on desktop (≥1024px), replacing the hamburger slide-out menu.

**Navigation items** (all roles):
- **Overview** — Dashboard view
- **Child Profiles** — `/my-kids`
- **Courses** — `/courses`
- **Course Materials** — `/course-materials`
- **Tasks** — `/tasks`
- **Messages** — `/messages` (with unread badge)
- **Help** — `/help`

**Quick Actions** (below divider):
- **+ Course Material** — Opens CreateStudyMaterialModal
- **+ Task** — Opens CreateTaskModal
- **+ Child** — Opens Link Child modal
- **+ Course** — Opens Create Course modal

**Responsive behavior:**
- ≥1024px: Full sidebar with labels
- 768-1023px: Icon-only sidebar
- <768px: Hamburger overlay (existing behavior)

All non-dashboard pages include a back button (←) in the header (#529).

#### 2. Child Filter Pills (#542)
- Single row of clickable pill buttons at the top of the content area (parent only)
- "All Children" pill shown when >1 child
- **Click** a pill → filters everything below (status cards, detail panel, calendar, tasks)
- **Click again** → deselects back to "All"
- Single-child families: child auto-selected, no pills shown
- Replaces the old child tab bar AND child highlight cards (removed as redundant)

#### 3. Alert Banner (#542)
- Appears below child pills when there are urgent items
- **Red section**: Overdue items (count + "View" link to `/tasks?due=overdue`)
- **Amber section**: Pending invites (with Resend button), unread messages (count + link)
- **Blue section**: Upcoming deadlines (next 24h)
- Sections are independently dismissible per session
- Hidden when no urgent items

#### 4. Status Summary Cards
Four cards showing key metrics (filtered by selected child):
- **Overdue** — red accent when >0, links to `/tasks?due=overdue`
- **Due Today** — accent when >0, links to `/tasks?due=today`
- **Next 3 Days** — count of items due in next 3 days
- **Total Tasks** — links to `/tasks`

#### 5. Quick Actions Bar (#543)
Row of 4 buttons always visible above the main content:
- **+ Course Material** → CreateStudyMaterialModal (existing)
- **+ Task** → CreateTaskModal (reuse from TasksPage)
- **+ Child** → Link Child modal (existing)
- **+ Course** → Create Course modal (existing)

#### 6. Student Detail Panel (#543)
When a child is selected, shows their world inline:

**Courses** (expandable section):
- List of enrolled courses with color dots

**Course Materials** (expandable section):
- Recent materials with type badges (guide/quiz/flashcards)

**Tasks by Urgency** (always expanded):
- 🔴 **Overdue**: red items with "X days overdue" badge
- 🟡 **Due Today**: amber items
- 🟢 **Next 3 Days**: green items with day label
- Remaining tasks collapsed under "Other"

**"All Children" mode** — merges tasks from all children with child-name labels on each item.

#### 7. Calendar Section (#544)
- **Defaults to collapsed** (localStorage key `calendar-collapsed` defaults to `true`)
- Collapsed bar shows item count: "Calendar (N items)" with expand chevron
- When expanded: full calendar with Month/Week/3-Day/Day views (unchanged from v2)
- Day Detail Modal, drag-and-drop rescheduling, and popovers all preserved

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

