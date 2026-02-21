# ClassBridge UI/UX Audit Report

**Date:** 2026-02-21
**Author:** ClassBridge Product Team
**Scope:** Phase 1 UI/UX Audit — All 4 Role Dashboards + Key User Journeys
**Design Philosophy:** Inspired by Canadian consumer-tech leaders (Shopify, Wealthsimple, Figma)

---

## Executive Summary

ClassBridge has a solid functional foundation with role-based dashboards, AI study tools, calendar integration, and parent-teacher messaging. However, the current UI exhibits common patterns of feature-first development: information density that overwhelms rather than guides, inconsistent interaction patterns across roles, and navigation that assumes user familiarity rather than building intuition.

This audit identifies **28 actionable UI improvements** across four role-based dashboards and proposes **4 user journey maps** grounded in real parent, student, teacher, and admin workflows. Improvements are prioritized as Phase 1 (current sprint, UX polish) with new feature requirements tagged as Phase 2.

---

## Design Philosophy

Drawing from the best of Canadian consumer tech:

| Principle | Inspired By | Application to ClassBridge |
|-----------|-------------|---------------------------|
| **Clarity over cleverness** | Shopify Admin | Every element earns its place. No decorative complexity. |
| **Warm minimalism** | Wealthsimple | Education is personal. The interface should feel supportive, not clinical. |
| **Progressive disclosure** | Figma | Show what matters now. Reveal details on demand. |
| **Contextual intelligence** | Notion | The right information at the right time for the right role. |
| **Forgiving design** | Stripe Dashboard | Undo over confirm. Guide over guard. |

---

## 1. User Journey Maps

### 1.1 Parent Journey: "What's happening with my kids?"

The parent's core anxiety: **"Am I missing something?"** ClassBridge must answer this in under 3 seconds.

```
LOGIN
  │
  ▼
DASHBOARD (Today's Focus)
  │ "Good morning, Sarah! Emma has 2 overdue items."
  │
  ├──→ [Tap urgency badge] → TASKS PAGE (filtered: overdue)
  │     └── Complete/reschedule tasks
  │
  ├──→ [Select child pill: "Emma"] → STUDENT DETAIL PANEL
  │     ├── View courses (3)
  │     ├── View recent materials
  │     └── View tasks by urgency
  │         └──→ [Tap task] → TASK DETAIL → Mark complete / Reschedule
  │
  ├──→ [Quick Action: "Create Task"] → CREATE TASK MODAL
  │     └── Assign to child → Set due date → Save
  │
  ├──→ [Quick Action: "Create Study Material"] → STUDY MATERIAL MODAL
  │     ├── Paste text / Upload file
  │     └── Generate Guide / Quiz / Flashcards → Auto-creates tasks
  │
  ├──→ [Upload Report Card] → REPORT CARD UPLOAD (Phase 2)
  │     └── AI analysis → Trend tracking → Recommendations
  │
  ├──→ [Expand Calendar] → CALENDAR VIEW
  │     ├── View month/week/day
  │     ├── Drag tasks to reschedule
  │     └── [Click day] → DAY DETAIL MODAL → Add task / View assignments
  │
  ├──→ [Sidebar: Messages] → MESSAGES PAGE
  │     └── Teacher conversations → Read / Reply
  │
  └──→ [Sidebar: My Kids] → MY KIDS PAGE
        ├── View all children profiles
        ├── Add/link new child
        └── Manage teacher connections
```

**Key Friction Points Identified:**
1. Parent must click 3 times to understand a child's full picture (select child → expand panel → scroll to tasks)
2. No "bird's eye" comparison view across multiple children
3. Calendar is collapsed by default — parents may never discover it
4. Study material creation requires knowing what to paste/upload; no guided flow
5. No report card upload or AI analysis capability (Phase 2)

---

### 1.2 Student Journey: "What do I need to do?"

The student's core need: **"Help me stay organized and study smarter."**

```
LOGIN
  │
  ▼
DASHBOARD
  │ Stats cards: Classes (4) | Assignments (7) | Materials (12) | Streak: 5 days
  │
  ├──→ [View Assignment] → ASSIGNMENT DETAIL
  │     └──→ [Study Tools button] → Generate study guide/quiz/flashcards
  │
  ├──→ [Create Custom Material] → STUDY MATERIAL MODAL
  │     ├── Paste notes / Upload downloaded PDF
  │     └── ClassBridge generates organized study guide
  │         └── Auto-creates task if due date detected
  │             └── If no due date → Prompt student to select one
  │
  ├──→ [View Courses] → COURSES PAGE
  │     ├── Synced from Google Classroom
  │     └── Manually created courses/subjects
  │         └──→ [Create Course] → COURSE CREATION MODAL
  │
  ├──→ [Upload Class Materials] → COURSE MATERIALS PAGE
  │     └── Upload PDFs, images, docs from:
  │         Google Classroom / TeachAssist / Edsby (manual download)
  │
  ├──→ [Notifications] → NOTIFICATION PANEL
  │     ├── Assignment requests from parents
  │     ├── Quiz/test completion requests from teachers
  │     └── Upcoming deadlines
  │
  └──→ [Study Guide] → STUDY GUIDE VIEW
        ├── Read formatted guide
        ├── Convert to Quiz → Take quiz → View score
        └── Convert to Flashcards → Study flashcards
```

**Key Friction Points Identified:**
1. Dashboard is list-heavy with no visual hierarchy — all 5 cards carry equal weight
2. No clear "what's due next" urgency indicator like the parent dashboard has
3. Course creation buried — students must navigate to Courses page first
4. No guided onboarding for "download from Google Classroom → upload here" workflow
5. Study streak metric is cosmetic — no gamification or incentive structure
6. Notifications from parents/teachers not prominently surfaced

---

### 1.3 Teacher Journey: "Manage my classroom efficiently"

The teacher's core need: **"One place to organize, communicate, and track student progress."**

```
LOGIN
  │
  ▼
DASHBOARD
  │ Stats cards: Classes (3) | Messages | Communications | Announcements
  │
  ├──→ [View Class] → COURSE DETAIL PAGE
  │     ├── View enrolled students
  │     ├── View/create assignments
  │     ├── Upload class materials
  │     │    ├── Upload notes/handouts/PDFs
  │     │    ├── Upload Tests/Quizzes/Exams
  │     │    └── Upload Labs/Projects/Assignments
  │     ├── Upload report cards (Phase 2)
  │     └── Assign grades per term/semester (Phase 2)
  │         └── Add feedback with grades (Phase 2)
  │
  ├──→ [Create Class] → CREATE CLASS MODAL
  │     └── Name + Subject + Description
  │
  ├──→ [Send Announcement] → ANNOUNCEMENT MODAL
  │     └── Select class → Subject → Message → Send to all parents
  │
  ├──→ [Invite Parent] → INVITE MODAL
  │     └── Enter parent email → Send invitation
  │
  ├──→ [Messages] → MESSAGES PAGE
  │     └── Direct conversations with parents
  │
  ├──→ [Google Classroom] → SYNC / MANAGE ACCOUNTS
  │     ├── Connect account(s)
  │     ├── Sync courses
  │     └── Manage linked accounts
  │
  └──→ [Generate Mock Exam] → MOCK EXAM GENERATOR (Phase 2)
        └── AI generates exam → Assign to students in bulk
```

**Key Friction Points Identified:**
1. Dashboard cards are action launchers, not information displays — teacher gets no at-a-glance view of their day
2. No unified "upload" experience — materials, tests, and labs should use same interface with type tagging
3. "Announcement" vs "Message" distinction is unclear (broadcast vs 1:1)
4. No student progress overview — teacher can't see which students are struggling
5. No grade/feedback entry capability (Phase 2 requirement)
6. Report card upload not available (Phase 2 requirement)
7. Course creation form is minimal — no template or guided setup

---

### 1.4 Admin Journey: "Platform health and user support"

The admin's core need: **"Is everything running smoothly? Who needs help?"**

```
LOGIN
  │
  ▼
DASHBOARD
  │ Stats: Total Users | Students | Teachers | Classes
  │
  ├──→ [Quick Link: Users] → USER MANAGEMENT TABLE
  │     ├── Search by name/email
  │     ├── Filter by role
  │     ├── Manage roles (add/remove)
  │     └── Send direct message
  │
  ├──→ [Quick Link: Broadcast] → BROADCAST MODAL
  │     └── Subject + Message → Send to all users
  │
  ├──→ [Quick Link: Audit Log] → AUDIT LOG PAGE
  │     └── View system events (logins, CRUD operations)
  │
  ├──→ [Quick Link: Inspiration] → INSPIRATION MESSAGES PAGE
  │     └── CRUD motivational quotes by role
  │
  ├──→ [Quick Link: FAQ] → FAQ MANAGEMENT PAGE
  │     └── CRUD FAQ entries, approve user submissions
  │
  └──→ [Broadcast History] → VIEW PAST BROADCASTS
        └── Date, subject, recipients, email counts
```

**Key Friction Points Identified:**
1. Stats cards are static counters — no trend indicators (growth, active users today)
2. No "recent activity" feed showing what's happening on the platform right now
3. Broadcast is "all or nothing" — no audience segmentation (by role, school, activity)
4. No user health indicators (inactive users, users with issues, new signups today)
5. Audit log is a separate page with no dashboard preview
6. No platform health metrics (API response times, error rates, AI usage)

---

## 2. Current State Assessment

### 2.1 Strengths

| Area | Assessment |
|------|-----------|
| **Role separation** | Clean dispatcher pattern. Each role gets a tailored experience. |
| **Parent Dashboard v3** | Best-in-class role dashboard. Urgency-first design, collapsible sections, calendar integration. |
| **Design system** | 50+ CSS variables, 3 themes (light/dark/focus), consistent color palette. |
| **Responsive foundation** | Mobile breakpoints at 768px/480px. Icon-only sidebar on desktop. |
| **Accessibility** | ARIA labels, keyboard navigation, skip-to-content, focus indicators. |
| **Modal system** | useConfirm hook, consistent modal overlay styling, keyboard dismissal. |
| **Calendar** | Month/week/day views, drag-and-drop rescheduling, course color-coding. |

### 2.2 Weaknesses

| Area | Severity | Description |
|------|----------|-------------|
| **Dashboard parity** | High | Parent Dashboard is v3.1 with extensive UX polish. Student, Teacher, and Admin dashboards are still v1 — simple card grids with no urgency indicators, no progressive disclosure, no "Today's Focus" equivalent. |
| **Navigation inconsistency** | High | Parent sees "Home / My Kids / Tasks / Messages / Help". Student/Teacher/Admin see "Dashboard / Classes / Materials / Quiz History / Tasks / Messages / Help". Different mental models for different roles. |
| **Component size** | High | ParentDashboard.tsx is 1600 lines with 40+ useState hooks. Difficult to maintain, debug, and test. |
| **Empty states** | Medium | Most empty states show placeholder text ("No assignments yet") without contextual CTAs or onboarding guidance. |
| **Status messages** | Medium | Auto-dismiss after 5 seconds. No persistent notification center beyond the bell icon. |
| **Search/filter persistence** | Medium | Filters reset on navigation. No URL-based filter state. |
| **Typography** | Medium | Space Grotesk + Source Sans 3 are functional but common. No typographic hierarchy beyond font-weight. |
| **Information architecture** | Medium | Student dashboard treats all cards equally. No visual priority hierarchy. |
| **Onboarding** | Low | Tour exists but only runs once. No contextual guidance for new features or empty sections. |

---

## 3. Phase 1 UI Improvement Recommendations

These improvements enhance the **existing** UI without adding new features. They are CSS/layout/component changes that improve usability, consistency, and polish.

### 3.1 Dashboard Parity — Give Student Dashboard a "Today's Focus"

**Issue:** Student dashboard shows 5 equal-weight stat cards with no urgency indicators. Students don't see what's due soon at a glance.

**Recommendation:**
- Add a "Today's Focus" header to StudentDashboard similar to ParentDashboard
- Show urgency badges: overdue assignments, due today, upcoming this week
- Replace stat cards with a more meaningful layout: upcoming deadlines list, recent study materials, study streak
- Add quick action buttons: "Upload Material", "Create Course"

**Impact:** High — Students immediately see what needs attention.

### 3.2 Dashboard Parity — Give Teacher Dashboard an Activity Summary

**Issue:** Teacher dashboard is 6 action-launcher cards with no information preview. Teachers don't see what's happening in their classes.

**Recommendation:**
- Add a "Class Activity" summary showing: recent parent messages, new student enrollments, upcoming assignment deadlines
- Replace card grid with a more informative layout: class overview cards (with student count, recent activity), pending actions
- Add quick action buttons: "Upload Material", "Create Assignment", "Send Announcement"

**Impact:** High — Teachers get actionable overview instead of a menu screen.

### 3.3 Dashboard Parity — Give Admin Dashboard Health Indicators

**Issue:** Admin dashboard shows static user counts with no trend data.

**Recommendation:**
- Add trend indicators to stat cards (e.g., "+5 this week" or a sparkline)
- Add a "Recent Activity" feed showing latest audit log entries inline
- Add "new users today" and "active users today" metrics
- Surface any system health warnings (failed syncs, error spikes)

**Impact:** Medium — Admins understand platform health without navigating to audit log.

### 3.4 Navigation Consistency

**Issue:** Parent sees different nav items than other roles. "My Kids" only appears for parents, but equivalent pages exist for other roles.

**Recommendation:**
- Standardize nav item naming across roles while keeping role-appropriate items
- Use consistent icon set (currently mix of emoji and icon styles)
- Add active state indicator (current page highlight) to all sidebar items consistently
- Ensure all roles have a "Home/Dashboard" entry as first item

**Impact:** Medium — Reduces cognitive load when users switch roles.

### 3.5 Empty State Enhancement

**Issue:** Empty states show minimal text with no guidance.

**Recommendation:**
- Add contextual illustrations or icons to empty states
- Include primary CTA button (e.g., "No courses yet" → "Create Your First Course" button)
- Add brief helper text explaining what this section will show once populated
- For student empty states, include links to relevant onboarding steps

**Impact:** Medium — New users understand how to get started.

### 3.6 Student Dashboard — Upcoming Deadlines Prominence

**Issue:** Assignments are listed without urgency sorting. Students can't quickly see what's due soon.

**Recommendation:**
- Sort assignments by due date (nearest first)
- Add urgency color-coding (red: overdue, amber: today, green: this week)
- Add a "Due This Week" summary badge at the top of the assignments section
- Group assignments by urgency tier (like parent dashboard tasks)

**Impact:** High — Directly addresses student need "I want to know what's coming up."

### 3.7 Teacher Dashboard — Unified Upload Experience

**Issue:** No upload flow exists on the teacher dashboard itself. Teachers must navigate to individual course pages.

**Recommendation:**
- Add "Upload Material" quick action to teacher dashboard
- Upload flow should allow: select course → select type (notes, test/quiz, lab/project, assignment) → upload file → optionally tag/describe
- Reuse CreateStudyMaterialModal pattern with teacher-specific type options

**Impact:** High — Reduces clicks for most common teacher action.

### 3.8 Calendar Discoverability

**Issue:** Calendar is collapsed by default on parent dashboard. New users may never discover it.

**Recommendation:**
- On first visit (no localStorage flag), show calendar expanded with a one-time tooltip: "Your calendar shows all assignments and tasks. Drag tasks to reschedule."
- After first visit, remember user's collapse preference
- Add a subtle calendar icon with item count badge in the collapsed state

**Impact:** Medium — Calendar is a key feature that shouldn't be hidden from new users.

### 3.9 Task Creation — Auto-Task from Study Guide Generation

**Issue:** When study guides are generated, tasks are not auto-created. Parent/student must manually create follow-up tasks.

**Recommendation:**
- After study guide generation, prompt: "Would you like to create a study task for this material?"
- If assignment has due date, pre-fill task due date (1 day before assignment due)
- If no due date, prompt to select one
- This implements the student journey requirement: "ClassBridge will automatically create tasks"

**Impact:** High — Closes a gap in the study workflow.

### 3.10 Mobile Touch Improvements

**Issue:** Calendar drag-and-drop uses HTML5 API which doesn't work on mobile touch devices. Modals can overflow on small screens.

**Recommendation:**
- Add touch event handlers for calendar task rescheduling on mobile
- Ensure all modals are scrollable within viewport on mobile
- Test and fix any overflow issues at 320px width
- Add swipe gestures for calendar month/week navigation (useTouchDrag hook exists but needs wider adoption)

**Impact:** Medium — Many parents access ClassBridge on phones.

### 3.11 Notification Center Enhancement

**Issue:** NotificationBell shows a dropdown but notifications are ephemeral. No persistent notification history.

**Recommendation:**
- Add a "View All Notifications" link in the dropdown that navigates to a notifications page
- Group notifications by type (task reminders, messages, invites, system)
- Add "Mark all as read" button
- Show notification timestamps relative (e.g., "2 hours ago")

**Impact:** Medium — Parents need reliable notification tracking.

### 3.12 ParentDashboard Component Refactoring

**Issue:** ParentDashboard.tsx is 1600 lines. AlertBanner, StudentDetailPanel, and QuickActionsBar were extracted but significant logic remains.

**Recommendation:**
- Extract ChildFilterPills into its own component
- Extract TodaysFocusHeader into its own component
- Extract all modal forms (AddChild, InviteStudent, EditChild) into separate files
- Move state management for modals into a useParentModals() custom hook
- Target: ParentDashboard.tsx under 500 lines

**Impact:** Medium — Developer experience improvement. Reduces bugs and improves maintainability.

### 3.13 Filter State Persistence

**Issue:** Course filters, task filters, and child selection reset when navigating away and back.

**Recommendation:**
- Persist filter state in URL query parameters (e.g., `/tasks?status=pending&priority=high`)
- Use `useSearchParams()` from React Router for filter management
- Persist child selection in sessionStorage (survives page navigation but not tab close)

**Impact:** Medium — Reduces frustration from lost filter state.

### 3.14 Loading State Consistency

**Issue:** Google sync, invite resend, and study generation show inconsistent loading feedback.

**Recommendation:**
- Add inline spinner to all async action buttons (button text → "Syncing..." with spinner)
- Add progress indication for study material generation (animated skeleton in list)
- Show "Last synced: 5 minutes ago" timestamp on Google sections
- Add retry button on failed async operations

**Impact:** Medium — Users understand what's happening during async operations.

### 3.15 Breadcrumb Navigation

**Issue:** Deep pages (task detail, course detail, study guide view) have no breadcrumb trail. Users lose context.

**Recommendation:**
- Add breadcrumb component: "Dashboard > Courses > Math 101 > Assignment 5"
- Use existing back button pattern but augment with full breadcrumb on desktop
- Collapse to back button only on mobile

**Impact:** Low — Quality-of-life improvement for deep navigation.

### 3.16 Invite Cooldown UX

**Issue:** Teacher invite resend has a 1-hour cooldown. The disabled "Wait Xm" button gives no context.

**Recommendation:**
- Add tooltip on hover explaining cooldown purpose: "To prevent spam, invitations can only be resent once per hour."
- Show countdown timer: "Resend available in 47 minutes"
- When cooldown expires, animate button to "Resend" state with subtle pulse

**Impact:** Low — Minor UX polish.

### 3.17 Admin Role Management Clarity

**Issue:** Role checkboxes don't explain what each role allows. Some role combinations may be unexpected.

**Recommendation:**
- Add brief description under each role checkbox (e.g., "Parent — Can view children's courses and assignments, create tasks, generate study materials")
- Show warning when adding unusual combinations (e.g., student + teacher)
- Add confirmation for role removal

**Impact:** Low — Prevents admin confusion.

### 3.18 Student Onboarding Guide for Material Upload

**Issue:** Students must manually download from Google Classroom/TeachAssist/Edsby and upload to ClassBridge. No guidance is provided for this workflow.

**Recommendation:**
- Add a dismissible onboarding card: "How to add your class materials"
- Step-by-step: "1. Open Google Classroom → 2. Download your course PDF → 3. Upload here → 4. ClassBridge generates study tools"
- Include logos of supported platforms (Google Classroom, TeachAssist, Edsby)
- Show only for students with < 3 uploaded materials

**Impact:** Medium — Critical for student adoption since DTAP approval is pending.

---

## 4. Phase 2 UI Feature Requirements (New Capabilities)

The following are **new features** identified from the user journey brainstorm. These are Phase 2 scope.

### 4.1 Report Card Upload & AI Analysis (Parent + Teacher)
- Parents upload report cards (PDF/image)
- AI extracts grades, comments, and subject breakdowns
- Store report cards per child per term/semester
- Track trends across report cards (improvements, declines, patterns)
- AI-generated observations and recommendations
- **GitHub Issues:** To be created

### 4.2 Task Assignment with Quiz Complexity Levels (Parent → Student)
- Parents assign quizzes to children with selectable difficulty (easy/medium/hard)
- Quiz difficulty adjusts AI question generation parameters
- Student receives notification of assigned quiz
- Parent tracks completion status
- **GitHub Issues:** To be created

### 4.3 Teacher Grade & Feedback Entry
- Teachers assign grades per student per course per term/semester
- Grade entry interface with bulk entry (spreadsheet-style)
- Feedback textarea per student per grade entry
- Grades visible to parents and students on their dashboards
- **GitHub Issues:** To be created

### 4.4 Teacher Upload Types (Tests, Labs, Projects)
- Unified upload interface with material type classification
- Type tags: Class Notes, Test/Quiz/Exam, Lab/Project, Assignment, Report Card
- Each type can have metadata (date, term, weight/percentage)
- Filterable by type on course detail page
- **GitHub Issues:** To be created

### 4.5 AI Mock Exam Generator (Teacher → Students)
- Teacher selects course + topic + difficulty level
- AI generates mock exam/quiz
- Teacher reviews and optionally edits
- Bulk assign to all students in course
- Students receive notification
- Track completion and scores
- **GitHub Issues:** To be created

### 4.6 Student Course/Subject Creation Enhancement
- Guided course creation with suggested subjects
- Link to relevant curriculum (Ontario curriculum, Phase 3)
- Auto-suggest study schedule based on course load
- **GitHub Issues:** To be created

---

## 5. Design Recommendations

### 5.1 Typography Upgrade

Current: Space Grotesk (display) + Source Sans 3 (body)

**Recommendation:** Keep the current pairing but enhance hierarchy:
- Use 3 distinct heading sizes (H1: 28px, H2: 22px, H3: 18px) with consistent spacing
- Add a subtle letter-spacing difference between headings and body
- Use font-weight variations more aggressively (300 for secondary text, 600 for emphasis, 700 for headings)

### 5.2 Color System Enhancement

Current system is solid. Recommended additions:
- Add **surface elevation** levels (surface-1, surface-2, surface-3) for visual depth
- Add **role accent colors** visible on each role's dashboard (warm amber for parents, cool blue for students, forest green for teachers, slate purple for admin)
- Ensure all color combinations pass WCAG AA contrast ratios

### 5.3 Micro-Interactions

Add subtle polish:
- Button press: scale(0.98) on mousedown
- Card hover: translateY(-2px) with shadow lift
- Section collapse: smooth height transition (not instant display:none)
- Badge count change: subtle bounce animation
- Task completion: checkmark animation with brief celebration
- Notification arrival: bell icon gentle shake

### 5.4 Information Density

Current: Variable — Parent Dashboard is dense, Student is sparse.

**Recommendation:** Establish a consistent density target:
- Dashboard: 3-5 distinct information groups per screen
- Each group: headline + 1-3 supporting data points + 1 action
- Use progressive disclosure (expand/collapse) for groups exceeding 5 items
- Whitespace ratios: 30% content, 20% whitespace, 50% navigation/chrome → adjust to 50% content, 25% whitespace, 25% chrome

---

## 6. Prioritized Implementation Plan

### Tier 1 — High Impact, Phase 1 (Sprint-ready)

| # | Improvement | Effort | Impact |
|---|-------------|--------|--------|
| 1 | Student Dashboard "Today's Focus" header | Medium | High |
| 2 | Student assignments urgency sorting | Small | High |
| 3 | Teacher Dashboard activity summary | Medium | High |
| 4 | Auto-task prompt after study guide generation | Medium | High |
| 5 | Teacher Dashboard upload quick action | Medium | High |
| 6 | Student onboarding card for material upload | Small | Medium |

### Tier 2 — Medium Impact, Phase 1 (Next sprint)

| # | Improvement | Effort | Impact |
|---|-------------|--------|--------|
| 7 | Empty state CTAs | Small | Medium |
| 8 | Admin Dashboard trend indicators | Medium | Medium |
| 9 | Calendar first-visit expanded + tooltip | Small | Medium |
| 10 | Filter state URL persistence | Medium | Medium |
| 11 | Notification center "View All" page | Medium | Medium |
| 12 | ParentDashboard component refactoring | Large | Medium |
| 13 | Navigation consistency across roles | Medium | Medium |
| 14 | Loading state consistency | Small | Medium |

### Tier 3 — Polish, Phase 1 (Backlog)

| # | Improvement | Effort | Impact |
|---|-------------|--------|--------|
| 15 | Micro-interactions (button press, card hover) | Small | Low |
| 16 | Breadcrumb navigation | Medium | Low |
| 17 | Invite cooldown UX | Small | Low |
| 18 | Admin role management descriptions | Small | Low |
| 19 | Mobile touch improvements | Large | Medium |

---

## 7. Metrics for Success

| Metric | Current Baseline | Target |
|--------|-----------------|--------|
| Time to first meaningful action (parent) | ~15 seconds (3+ clicks) | < 5 seconds (1 click) |
| Student dashboard bounce rate | Unknown | < 30% |
| Teacher dashboard engagement | Action-launcher only | Information + action |
| Admin response time to issues | Navigate to audit log | Visible on dashboard |
| Mobile usability score | Functional but not optimized | Full touch support |

---

## Appendix A: Component File Size Audit

| File | Lines | Recommendation |
|------|-------|----------------|
| ParentDashboard.tsx | ~1600 | Split to <500 via extraction |
| Dashboard.css | 1909 | Split into component CSS modules |
| ParentDashboard.css | ~1752 | Split alongside component extraction |
| DashboardLayout.tsx | 427 | Acceptable, minor extraction possible |
| StudentDashboard.tsx | ~700 | Acceptable |
| TeacherDashboard.tsx | ~650 | Acceptable |
| AdminDashboard.tsx | ~500 | Acceptable |

## Appendix B: Accessibility Compliance

| Standard | Status |
|----------|--------|
| ARIA labels on interactive elements | Implemented |
| Keyboard navigation | Implemented |
| Skip-to-content link | Implemented |
| Focus indicators | Implemented |
| Color contrast (WCAG AA) | Needs audit |
| Screen reader testing | Not conducted |
| Reduced motion support | Not implemented |

---

*This audit report should be reviewed alongside the existing [requirements/dashboards.md](../requirements/dashboards.md) specification and the [Phase 1 roadmap checklist](../requirements/roadmap.md).*
