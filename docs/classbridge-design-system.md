# ClassBridge — Design System & UI/UX Documentation

**Version**: 2.1
**Date**: 2026-03-20
**Author**: Sarah (Product Owner)
**Platform**: Web (React 19) + Mobile (React Native / Expo SDK 54)

---

## 1. Design Philosophy

ClassBridge's design draws from leading Canadian consumer-tech products, prioritizing clarity, warmth, and progressive disclosure.

| Principle | Inspired By | Application |
|-----------|-------------|-------------|
| Clarity over cleverness | Shopify Admin | Every element earns its place. No decorative complexity. |
| Warm minimalism | Wealthsimple | Education is personal. The interface should feel supportive, not clinical. |
| Progressive disclosure | Figma | Show what matters now. Reveal details on demand. |
| Contextual intelligence | Notion | The right information at the right time for the right role. |
| Forgiving design | Stripe Dashboard | Undo over confirm. Guide over guard. |

### Core Design Values

- **Parent-first**: Parent experience is the primary design focus. Parent option is always first and prominent.
- **Urgency-first**: Lead with what needs action NOW (overdue > due today > upcoming).
- **No scroll / single viewport**: Dashboards should fit in one screen at 1080p. Overflow via expandable sections.
- **Single child selection model**: One mechanism (pills), one effect (filters everything).
- **Positive reinforcement**: "All caught up!" when no urgent tasks.

---

## 2. Theme System

### 2.1 Three Themes

| Theme | Primary Accent | Description | Use Case |
|-------|---------------|-------------|----------|
| Light (default) | Teal #49B8C0 | Clean, bright UI with white surfaces | General use, daytime |
| Dark | Purple #8B5CF6 / Cyan #22D3EE | Deep dark with purple glow, turbo.ai inspired | Evening study, reduced eye strain |
| Focus | Sage #5A9E8F / Amber #C47F3B | Warm muted tones | Study sessions, focused work |

### 2.2 CSS Custom Properties (50+)

All visual styling is driven by CSS custom properties with per-theme overrides via `[data-theme]` attribute on `<html>`.

| Category | Key Variables | Example |
|----------|--------------|---------|
| Core palette | `--color-ink`, `--color-surface`, `--color-border` | Text, backgrounds, dividers |
| Accent colors | `--color-accent`, `--color-accent-strong`, `--color-accent-light` | Buttons, active states, highlights |
| Semantic | `--color-success`, `--color-danger`, `--color-warning` | Status indicators |
| Priority badges | `--color-priority-high`, `--color-priority-medium`, `--color-priority-low` | Task priority indicators |
| Content type badges | `--badge-syllabus`, `--badge-labs`, `--badge-readings`, `--badge-resources` | Course material types |
| Role badges | `--badge-parent`, `--badge-teacher`, `--badge-admin` | User role indicators |
| Brand | `--color-google` | Google sign-in button |
| Shadows | `--shadow-sm`, `--shadow-md`, `--shadow-lg` | Card elevation |

### 2.3 Theme Architecture

- `ThemeContext.tsx` provides `useTheme()` hook
- `ThemeToggle` component in header cycles themes
- OS preference auto-detection via `prefers-color-scheme`
- Persisted to `localStorage` under `classbridge-theme`

### 2.4 Default Style: Flat (Non-Gradient)

**Status**: Planned (#486-#489)

All UI uses solid accent colors instead of gradients. The previous gradient style (teal-to-orange diagonal) was considered too flashy based on user feedback.

| Element | Flat Style |
|---------|-----------|
| Buttons | `background: var(--color-accent)`, hover: `var(--color-accent-strong)` |
| Active tabs | `background: var(--color-accent)`, `color: white` |
| Text accents | `color: var(--color-accent)` (no gradient text) |
| Flashcards | Front: `var(--color-accent)`, Back: `var(--color-accent-strong)` |
| Page background | Flat `var(--color-surface-bg)` |
| Skeleton loader | Keep gradient (animation, not decorative) |

---

## 3. Layout System

### 3.1 Dashboard Layout (turbo.ai-inspired)

All authenticated pages use `DashboardLayout` as a shared shell:

```
+-----------------------------------------------------------+
| HEADER: Logo | Search (Ctrl+K) | Bell | User | Sign Out   |
+------+----------------------------------------------------+
| ICON | CONTENT AREA                                       |
| ONLY |                                                    |
| SIDE | (Role-specific dashboard or page content)          |
| BAR  |                                                    |
|      |                                                    |
| Home |                                                    |
| Kids |                                                    |
| ...  |                                                    |
| Help |                                                    |
+------+----------------------------------------------------+
```

### 3.2 Sidebar Navigation

- **Desktop (>768px)**: Always icon-only with hover tooltips
- **Mobile (<768px)**: Hamburger overlay
- Bigger icons for easy recognition
- Compact width maximizes content area

### 3.3 Header Components

| Component | Position | Purpose |
|-----------|----------|---------|
| Logo icon | Left | Brand identity (80px height, transparent BG) |
| Global Search | Center | Ctrl+K, searches courses/guides/tasks/content |
| Notification Bell | Right | Unread count badge, dropdown with notifications |
| User dropdown | Right | Name, role switcher (if multi-role), settings |
| Sign Out | Right | Logout action |

### 3.4 Back Navigation

All non-dashboard pages include a back button (left arrow) in the header. This provides consistent navigation without relying solely on browser back.

---

## 4. Component Library

### 4.1 Buttons

| Class | Usage | Style |
|-------|-------|-------|
| `.btn-primary` | Primary actions | Solid accent color, white text |
| `.btn-secondary` | Secondary actions | Outlined, accent border |
| `.btn-danger` | Destructive actions | Red background |
| `.btn-icon` | Icon-only buttons | Transparent, icon centered |

### 4.2 AddActionButton (+ Icon Popover)

A shared component used across Dashboard, Tasks, My Kids, and Course Material Detail pages:
- 40x40px circle with dashed border
- Click opens a popover with action items
- Click-outside-to-dismiss
- Each action has icon + label

### 4.3 ConfirmModal + useConfirm Hook

Custom styled confirmation modals replacing native browser `confirm()`:
- Standard variant for normal confirmations
- Danger variant (red styling) for destructive operations
- Custom title, message, confirm/cancel button text
- "Request More Credits" shown when at 0 AI credits

### 4.4 Toast Notifications

Global `ToastProvider` wraps the app:
- Three types: success (green), error (red), info (blue)
- Auto-dismiss: 3s success/info, 5s errors
- Max 5 visible, animated entrance
- Full-width on mobile (480px)

### 4.5 Loading Skeletons

Reusable skeleton components replacing "Loading..." text:
- `Skeleton` — base shimmer animation
- `PageSkeleton` — full page loading state
- `CardSkeleton` — card-shaped loading state
- `ListSkeleton` — list of loading rows
- `DetailSkeleton` — detail page loading state
- Applied to 16+ pages

### 4.6 ErrorBoundary

React class component wrapping all routes:
- Catches unhandled render errors gracefully
- Shows "Something went wrong" card
- Try Again / Reload Page buttons
- Dev mode shows error message for debugging

### 4.7 GlobalSearch

Unified search in header (Ctrl+K / Cmd+K):
- Debounced input (300ms)
- Grouped results by type with icons
- Searchable entities: Courses, Study Guides, Tasks, Course Content
- Keyboard: Escape closes, click outside closes

### 4.8 Calendar Components

Located in `frontend/src/components/calendar/`:

| Component | Purpose |
|-----------|---------|
| `CalendarView` | Orchestrator (header + grid + popover) |
| `CalendarHeader` | Nav buttons, title, view toggle |
| `CalendarMonthGrid` / `CalendarDayCell` | Month view grid |
| `CalendarWeekGrid` | Week/3-day column layout |
| `CalendarDayGrid` | Single-day list view |
| `CalendarEntry` | Assignment/task chip or card |
| `CalendarEntryPopover` | Detail popover on click |
| `DayDetailModal` | Full CRUD for a specific date |
| `useCalendarNav` | Hook for date navigation |

### 4.9 NotesPanel + NotesFAB

- **NotesPanel**: Floating, draggable, closable panel with rich text editing
- **NotesFAB**: Persistent bottom-right FAB to toggle Notes panel
- **SelectionTooltip**: Floating amber "Add to Notes" pill near text selection
- Auto-save with 1s debounce and status indicator

### 4.10 HelpChatbot

- **FAB**: Bottom-right 56px circle, above NotesFAB
- **Panel**: 380x520px desktop, full-width bottom sheet mobile
- **Suggestion chips**: Role-based and context-aware
- **Video embeds**: YouTube/Loom inline players

### 4.11 usePageVisible Hook

Custom hook that tracks `document.visibilityState` for pausing background operations when the browser tab is hidden. Returns a boolean indicating whether the page is currently visible. Used by polling intervals (e.g., NotificationBell) to avoid unnecessary network requests when the user is on another tab.

### 4.12 GenerationSpinner

Consistent AI generation loading spinner used across all study tool endpoints (study guide, quiz, flashcard generation). Provides a branded, uniform loading experience during AI operations.

### 4.13 SpeedDialFAB

Speed dial floating action button with expandable menu options. Click to reveal a radial or vertical list of contextual actions. Used for quick-access creation flows (e.g., upload material, create task).

### 4.14 UploadMaterialWizard

Multi-step wizard component for uploading documents:
- **Step 1**: File upload (drag-and-drop zone, paste text, class selector)
- **Step 2**: Study tool selection (Study Guide, Quiz, Flashcards)
- "Just Upload" shortcut to skip AI tool generation
- Slide animation between steps
- Used across all roles (parent, student, teacher)

### 4.15 ChildSelectorTabs

Tab component for selecting a child account in parent views. Displays child names as horizontal tabs with colored indicators matching the child avatar palette. Selecting a tab filters all downstream content to that child.

### 4.16 SetupChecklist

Onboarding checklist component for new user setup. Displays a list of setup steps (e.g., link Google Classroom, add a child, upload first material) with completion checkmarks. Dismissible once all steps are done or manually closed.

### 4.17 BotProtection Fields

Honeypot + timing validation on public-facing forms (survey, waitlist, registration). Invisible honeypot input field traps bots that auto-fill all fields. Timing validation rejects submissions completed faster than a human threshold.

### 4.18 SurveyPage Components

Role-based questionnaire system supporting multiple question types:
- **Likert scale**: 5-point agreement scale
- **Matrix**: Grid of rows x columns for multi-item rating
- **Multi-select**: Checkbox-based multiple choice
- **Free-text**: Open-ended text input
- Responses stored per role with analytics dashboard for admins.

### 4.19 NotificationBell (Updated)

Updated with visibility-aware polling via `usePageVisible` hook. Polling for new notifications pauses automatically when the browser tab is hidden and resumes when the tab becomes visible again, reducing unnecessary API calls.

---

## 5. Role-Specific Dashboard Designs

### 5.1 Parent Dashboard (v3.1)

**Design Goal**: Answer "What's happening with my kids?" in under 3 seconds.

```
+-----------------------------------------------------------+
| HEADER                                                     |
+------+----------------------------------------------------+
| ICON | [Child1] [Child2] [+]    <- Child Filter Pills      |
| SIDE |----------------------------------------------------+
| BAR  | TODAY'S FOCUS                                       |
|      | "Good morning, Sarah!"                              |
|      | [3 Overdue] [2 Due Today] [5 Upcoming]              |
|      | "Small steps lead to big achievements" (quote)      |
|      |----------------------------------------------------+
|      | ALERT BANNER (overdue + pending invites)            |
|      |----------------------------------------------------+
|      | STUDENT DETAIL PANEL (collapsible)                  |
|      | - Courses (3)                                       |
|      | - Course Materials (5)                              |
|      | - Tasks by Urgency (Overdue/Today/Next 3 Days)      |
+------+----------------------------------------------------+
```

**Key Design Decisions:**
- No "All Children" button — toggle-deselect instead
- Today's Focus replaces status summary cards
- Calendar moved to Tasks page
- Quick actions via + icon popover (not action bar)
- Alert banner: red (overdue) + amber (invites), dismissible

### 5.2 Student Dashboard (v2 — "Focused Command Center")

**Design Goal**: Help students stay organized and study smarter.

```
+-----------------------------------------------------------+
| HEADER                                                     |
+------+----------------------------------------------------+
| ICON | HERO: "Good morning, Alex!"                        |
| SIDE | [3 Overdue] [2 Due Today]  <- urgency pills        |
| BAR  | 5 Courses | 12 Materials | 8 Tasks  <- stat chips |
|      |----------------------------------------------------+
|      | NOTIFICATION ALERTS (parent/teacher requests)       |
|      |----------------------------------------------------+
|      | QUICK ACTIONS (2x2 grid)                            |
|      | [Upload Materials] [Create Course]                   |
|      | [Generate Study Guide] [Sync Classroom]              |
|      |----------------------------------------------------+
|      | COMING UP (timeline - next 7 days)                  |
|      | - Tomorrow: Math HW (Math 101)                      |
|      | - Wed: Science Lab Report                            |
|      |----------------------------------------------------+
|      | RECENT MATERIALS + COURSE CHIPS                     |
+------+----------------------------------------------------+
```

**Key Design Decisions:**
- Hero greeting with urgency awareness
- Notification alerts for parent/teacher requests
- 4 quick action cards with colored left borders
- Unified timeline (assignments + tasks)
- Onboarding card for new students (no courses/materials)

### 5.3 Teacher Dashboard

**Features:**
- Courses teaching list with student counts
- Manual course creation modal
- Multi-Google account management
- Messages section
- Teacher communications (email monitoring)
- Invite parent card

### 5.4 Admin Dashboard

**Features:**
- Platform stats cards (users, courses, study guides)
- User management table: search, filter by role, pagination
- Send Broadcast button with modal
- Individual message per user row
- Links to: Audit Log, Inspiration Messages, Waitlist, AI Usage

---

## 6. Page-Level Designs

### 6.1 My Kids Page

- **Child selector tabs** with colored dots matching avatar colors
- **Child cards**: Avatar + name/grade + school + stats + progress bar + deadline countdown
- **Sections** (collapsible with icons): Courses, Course Materials, Tasks, Teachers
- **+ icon popover**: Add Child, Add Class, Class Materials, Quiz History
- **8-color avatar palette** assigned by child index

### 6.2 Course Material Detail Page

**Tabbed interface:**

| Tab | Content |
|-----|---------|
| Study Guide | AI-generated markdown, print/PDF, regenerate, delete |
| Quiz | Interactive stepper, results saving, parent student banner |
| Flashcards | Flip animation, keyboard nav, shuffle |
| Videos & Links | YouTube embeds grouped by topic, external links |
| Document | Original text, inline editing, upload/replace |

- Notes toolbar button toggles floating panel
- LinkedTasksBanner shows auto-created tasks
- Print + Download PDF on all tabs
- Focus prompt with history pre-population

### 6.3 Messages Page

- Conversation list with unread badges
- Chat view with sent/received message bubbles
- Date separators between message groups
- New conversation modal with recipient selector
- Admin badge on admin conversations

### 6.4 Analytics Page

- Summary cards: Average, Completion Rate, Graded Count, Trend
- Grade trend LineChart (Recharts)
- Course averages BarChart
- Child selector dropdown for parents
- Time range filter (30d/60d/90d/All) + course filter
- AI insights panel (on-demand)

### 6.5 Tasks Page

- Task list with due date, priority, assignee, linked resources
- Filter dropdowns: Status, Priority, Due (overdue/today/week), Assignee
- Calendar section (collapsible, default collapsed)
- + icon popover for new task
- Click row -> Task Detail Page

### 6.6 Tutorial Page

- Role-based sections with step-by-step viewer
- Image + description side-by-side layout
- Progress dots (clickable, checkmark for visited)
- Tip boxes with contextual hints
- Previous/Next navigation

### 6.7 Waitlist Landing Page

- Hero section with ClassBridge branding
- Value proposition and feature highlights
- Two CTAs: "Join the Waitlist" + "Login"
- Clean, modern design matching design system

---

## 7. Responsive Design

### 7.1 Breakpoints

| Breakpoint | Target | Layout Changes |
|------------|--------|----------------|
| > 1024px | Desktop | Full layout, icon-only sidebar |
| 768px - 1024px | Tablet | Sidebar collapses to icons, cards stack |
| 480px - 768px | Large mobile | Hamburger nav, single column |
| < 480px | Small mobile | Full-width cards, stacked actions |

### 7.2 Mobile Adaptations

| Component | Desktop | Mobile |
|-----------|---------|--------|
| Sidebar | Icon-only, always visible | Hamburger overlay |
| Modals | Centered overlay | Full-screen |
| Tables | Horizontal scroll | Card layout or scroll |
| Calendar | Multi-column grid | Single-day view |
| Touch targets | Standard | Minimum 44px |
| Help Chatbot | 380x520px panel | Full-width bottom sheet |
| Notes Panel | 350px side panel | Full-width overlay |
| Child cards | Grid layout | Single column |

### 7.3 CSS Architecture

- CSS custom properties for all visual values
- Breakpoints: 768px (tablet), 480px (phone) — primary `max-width` values for all new work
- 75 CSS files have `@media` breakpoints; ~55+ files still need 768px/480px breakpoints (audit March 2026, #1641)
- High-priority gaps: CourseDetailPage, TeacherCommsPage, MessagesPage, FlashcardsPage, StudyGuidePage, QuizPage, TasksPage, AdminDashboard
- CSS-only solutions preferred over JavaScript

### 7.4 Mind Map Layout

| Viewport | Layout |
|----------|--------|
| Desktop (≥768px) | Horizontal — center node in middle, branches split left/right with vertical stacking to prevent overlap (#1653) |
| Mobile (<768px) | Vertical stacked list layout |

- Connector lines from center node to each branch label
- Branches must not overlap when child items are expanded
- Available via "Learn Your Way" format selector and Help Study menu

---

## 8. Logo & Branding

### 8.1 Logo Assets

| Logo Type | File | Usage | Dimensions |
|-----------|------|-------|-----------|
| Auth Logo | classbridge-logo.png | Login, Register, Reset pages | max-width: 280px (220px mobile) |
| Header Icon | logo-icon.png | Dashboard header | height: 80px |
| Landing Nav | classbridge-logo.png | Landing page navigation | height: 100px |
| Landing Hero | classbridge-hero-logo.png | Landing page hero section | height: 300px |
| Favicon | favicon.png/ico/svg | Browser tab, PWA icon | 16/32/48/192px |

### 8.2 Theme-Aware Logo Rendering

All logos use transparent backgrounds that work across all three themes. CSS swaps between logo variants based on `[data-theme]` attribute.

### 8.3 Brand Colors

| Color | Hex | Usage |
|-------|-----|-------|
| ClassBridge Teal | #49B8C0 | Primary accent (light theme) |
| Deep Blue | #1B4F72 | Headings, dark accents |
| Purple | #8B5CF6 | Dark theme accent |
| Cyan | #22D3EE | Dark theme secondary |
| Sage | #5A9E8F | Focus theme accent |
| Amber | #C47F3B | Focus theme secondary |

---

## 9. Color Coding Systems

### 9.1 Course Colors

10-color palette assigned by course index, consistent across all views:
- Used for: course dots, calendar entries, sidebar pills, material badges
- Colors are CSS variables: `--course-color-0` through `--course-color-9`

### 9.2 Priority Colors

| Priority | Color | Usage |
|----------|-------|-------|
| High | Red | Task badges, calendar entries |
| Medium | Amber/Orange | Task badges, calendar entries |
| Low | Green | Task badges, calendar entries |

### 9.3 Status Colors

| Status | Color | Usage |
|--------|-------|-------|
| Success | Green | Toast, confirmation, verified |
| Danger | Red | Errors, destructive actions, overdue |
| Warning | Amber | Warnings, pending states |
| Info | Blue | Informational messages |

### 9.4 Content Type Badge Colors

Each course material type has a distinct color for visual scanning:
- Syllabus, Labs, Readings, Resources, Assignments, Notes, Other

### 9.5 Child Avatar Colors

8-color palette for child initials avatars in My Kids:
- Consistent across tabs, cards, and child selector pills

---

## 10. Animation & Interaction Patterns

### 10.1 Existing Animations

| Animation | Usage | Implementation |
|-----------|-------|---------------|
| Skeleton shimmer | Loading states | CSS keyframe animation |
| Toast slide-in | Notifications | CSS transition |
| Flashcard flip | Study flashcards | CSS 3D transform |
| Calendar drag | Task rescheduling | HTML5 Drag and Drop API |
| Modal fade | All modals | CSS opacity transition |
| Panel slide | Notes panel | CSS transform |
| Chatbot slide-up | Help widget | CSS transform + opacity |

### 10.2 Drag and Drop

- Tasks can be dragged to different days in calendar (month/week views)
- Native HTML5 DnD API (no external library)
- Drop targets highlight with blue dashed outline
- Optimistic UI with rollback on API failure
- Only tasks are draggable (assignments fixed)

### 10.3 Planned: Lottie Animation Loader (#424)

Replace emoji + CSS pulse during AI generation with branded Lottie animation:
- Education/book themed, ClassBridge teal colors
- `lottie-react` package
- `frontend/public/animations/classbridge-loader.json`
- Target: under 50KB

---

## 11. Performance Design Patterns

### 11.1 Eager Loading

All backend endpoints use SQLAlchemy `selectinload()` for relationship access. This prevents N+1 query problems by loading related objects in a single batch query rather than issuing individual queries per row.

### 11.2 Batch API Pattern

Prefer a single batch endpoint over N individual calls. For example, enrollment status checks use a batch endpoint that accepts multiple IDs and returns all statuses in one response, reducing round-trips and improving page load time.

### 11.3 Visibility-Aware Polling

Use the `usePageVisible` hook to pause `setInterval`-based polling when the browser tab is hidden. This applies to notification polling, dashboard refresh, and any periodic data fetch. Polling resumes immediately when the tab becomes visible.

### 11.4 Request Timeout Pattern

- **Default timeout**: 30 seconds for standard API calls
- **Extended timeout**: 120 seconds for AI generation and file upload operations
- Configured in the Axios client instance; overridable per-request

### 11.5 In-Memory Caching

Token blacklist uses a TTL (time-to-live) cache to reduce database queries on every authenticated request. Blacklisted tokens are cached in memory with automatic expiry, avoiding repeated DB lookups for the same token.

---

## 12. Accessibility (Current + Planned)

### 12.1 Current

- Keyboard-navigable flashcards (arrows + space)
- `aria-label` on icon-only buttons
- Semantic HTML headings
- Focus visible styles
- Color contrast in all three themes
- Touch targets minimum 44px on mobile

### 12.2 Planned (#719)

- Full ARIA tab pattern for tabbed interfaces
- Focus trapping in modals
- Expanded/collapsed state communication
- Screen reader announcements for dynamic content
- Skip-to-content link

---

## 13. Design Consistency Initiative

**Status**: Planned | **Issues**: #1246-#1254

### 13.1 Universal Page Shell

Every page will be wrapped in `DashboardLayout` with `PageNav` breadcrumbs. Pages to update:
- StudyGuidePage, QuizPage, FlashcardsPage, TeacherCommsPage, CoursesPage, CourseDetailPage

### 13.2 Shared CSS Patterns

Standardized classes to be defined in `Dashboard.css`:
- `.btn-primary`, `.btn-secondary`, `.btn-danger`, `.btn-icon`
- `.section-card`, `.section-card-header`, `.section-card-body`
- `.list-row`, `.list-row-icon`, `.list-row-body`, `.list-row-action`
- `.empty-state` (icon + title + description + CTA)

### 13.3 Upload Modal Redesign (Two-Step Wizard)

Replace the single dense upload form with a progressive wizard:
- **Step 1**: Add material (file drop zone, paste text, class selector)
- **Step 2**: Generate study tools (card-based selection: Study Guide, Quiz, Flashcards)
- "Just Upload" shortcut to skip AI tools
- Slide animation between steps
- Same component for all roles

---

## 14. Mobile App Design

### 14.1 Design System

| Token | Value |
|-------|-------|
| Primary | #49B8C0 (ClassBridge Teal) |
| Background | #FFFFFF |
| Surface | #F8F9FA |
| Text | #1A1A2E |
| Border | #E5E7EB |
| Border Radius | 8px (cards), 12px (buttons) |
| Spacing | 4px base unit |

### 14.2 Navigation

- Bottom tab bar: Home, Calendar, Messages, Notifications, Profile
- Nested stacks for detail screens (ChildOverview, Chat)
- Native headers on most screens
- SafeArea handling via `useSafeAreaInsets`

### 14.3 Mobile Components

| Component | Purpose |
|-----------|---------|
| Status cards | Overdue / Due Today / Messages counts |
| Child cards | Avatar + name + status badges |
| Message bubbles | Sent (teal, right) / Received (gray, left) |
| Calendar grid | Month view with color-coded date dots |
| Notification cards | Type-specific icons, unread styling |
| Pull-to-refresh | RefreshControl on all list screens |
| Empty states | Icon + message for empty data |

### 14.4 Mobile Boundary

- Mobile is read-heavy with limited writes
- Complex workflows (registration, course management, study generation) are web-only
- Tab bar badges poll every 30 seconds

---

## 15. Email Template Design

### 15.1 Template Style

All 14 email templates follow a consistent design:
- ClassBridge logo header
- Indigo (#4F46E5) accent bar
- White card body on light gray background
- Responsive table layout
- Role-based inspirational message footer
- Branded CTA buttons

### 15.2 Templates

| Template | Trigger | CTA |
|----------|---------|-----|
| welcome.html | Registration | "Get Started" -> login |
| email_verification.html | Registration | "Verify Email" -> verify link |
| email_verified_welcome.html | Verification success | "Explore Dashboard" |
| password_reset.html | Forgot password | "Reset Password" |
| message_notification.html | New message received | "View Message" |
| task_reminder.html | Task due in 1/3 days | "View Task" |
| teacher_invite.html | Parent links non-EMAI teacher | "Join ClassBridge" |
| teacher_linked_notification.html | Parent links EMAI teacher | "View Dashboard" |
| student_course_invite.html | Teacher adds new student | "Join Course" |
| parent_invite.html | Teacher invites parent | "Join ClassBridge" |
| waitlist_confirmation.html | Waitlist signup | N/A |
| waitlist_admin_notification.html | New waitlist signup (to admins) | "View Waitlist" |
| waitlist_approved.html | Admin approves | "Register Now" |
| waitlist_declined.html | Admin declines | N/A |
| waitlist_reminder.html | Admin sends reminder | "Complete Registration" |

---

---

## 16. Dashboard Redesign — Persona-Based Layouts (§6.65)

All dashboards follow the **one-screen rule** (no scrolling at 1080p) with a **3-section maximum** layout. White space is a feature, not wasted space.

### 16.1 Design Principles

| Principle | Rule |
|-----------|------|
| One-Screen Rule | Everything visible at 1080p without scrolling |
| 3-Section Max | No dashboard exceeds 3 content sections |
| White Space | Generous padding; density = clutter |
| Progressive Disclosure | Summary first → click to expand |
| Role-Appropriate | Each role sees only what matters to them |

### 16.2 Parent Dashboard v5

**Persona:** Busy parent, checks app 1-2x/day, wants quick snapshot.

| Section | Content | Size |
|---------|---------|------|
| 1. Daily Briefing | Today's tasks, upcoming deadlines, alerts per child | 40% |
| 2. Kids Snapshot | One card per child: grade trend sparkline, next due item, mood indicator | 40% |
| 3. Quick Actions | "Help My Kid", "View Study Guides", "Message Teacher" | 20% |

- **No widgets, no charts on landing.** Charts live in a dedicated Analytics tab.
- Child selector tabs if >1 child; default = all children combined view.

### 16.3 Student Dashboard v4

**Persona:** Student (ages 10-18), needs to know what's due and stay motivated.

| Section | Content | Size |
|---------|---------|------|
| 1. What's Due | Prioritized task list: overdue (red), today (amber), upcoming (green) | 50% |
| 2. My Progress | Current course grades, streak counter, recent achievements | 30% |
| 3. Study Tools | "Generate Study Guide", "Practice Quiz", "Flashcards" | 20% |

- Gamification elements: streak counter, achievement badges (subtle, not distracting).
- Dark mode default option for older students.

### 16.4 Teacher Dashboard v2

**Persona:** Teacher managing multiple classes, needs class-level overview.

| Section | Content | Size |
|---------|---------|------|
| 1. Class Overview | Cards per active course: student count, pending submissions, avg grade | 50% |
| 2. Action Items | Unread messages, pending approvals, upcoming deadlines | 30% |
| 3. Quick Actions | "Create Assignment", "Message Parents", "View Analytics" | 20% |

- Class selector dropdown; default = all classes aggregated.
- No individual student data on landing (click into class for roster).

### 16.5 Admin Dashboard v2

**Persona:** Platform administrator, monitors system health and user activity.

| Section | Content | Size |
|---------|---------|------|
| 1. Platform Health | Active users (24h), API uptime, AI usage/budget gauge | 40% |
| 2. User Activity | New registrations, pending waitlist, flagged accounts | 40% |
| 3. Quick Actions | "Manage Users", "AI Usage Limits", "View Logs" | 20% |

- Metric cards with sparkline trends (7-day).
- Alert badges on sections requiring attention.

### 16.6 Responsive Behavior

| Breakpoint | Layout |
|------------|--------|
| Desktop (≥1024px) | 3-column grid or 2+1 split |
| Tablet (768-1023px) | 2-column, section 3 moves below |
| Mobile (<768px) | Single column stack, sections become collapsible accordions |

### 16.7 Color & Typography

- Section headers: `text-lg font-semibold` in role accent color
- Cards: White background, `rounded-xl`, `shadow-sm`, 24px padding
- Status colors: Overdue `#EF4444`, Today `#F59E0B`, Upcoming `#10B981`
- No borders between sections — use spacing (32px gap) for visual separation

---

*This design system document captures the complete visual language, component library (60+ reusable components, 13+ custom hooks), 54+ page components, 40+ API modules, layout patterns, and design decisions for ClassBridge as of March 20, 2026.*
