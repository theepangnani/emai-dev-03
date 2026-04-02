### 6.15 Theme System & UI Appearance (Phase 1) - IMPLEMENTED

The platform supports three visual themes that users can switch between via a toggle button in the header.

#### Themes

| Theme | Description | Primary Accent | Status |
|-------|-------------|----------------|--------|
| Light (default) | Clean, bright UI | Teal (#49b8c0) | IMPLEMENTED |
| Dark (turbo.ai-inspired) | Deep dark with purple glow | Purple (#8b5cf6) / Cyan (#22d3ee) | IMPLEMENTED |
| Focus | Warm muted tones for study sessions | Sage (#5a9e8f) / Amber (#c47f3b) | IMPLEMENTED |

#### Architecture
- CSS custom properties (50+ variables) in `index.css` with per-theme overrides via `[data-theme]` attribute
- `ThemeContext.tsx` provides `useTheme()` hook with `theme`, `setTheme()`, `cycleTheme()`
- `ThemeToggle` component in header cycles through themes
- OS preference auto-detection via `prefers-color-scheme`
- Persisted to `localStorage` under `classbridge-theme`

#### Variable Categories
- Core palette (ink, surface, border)
- Accent colors (primary, warm, dark variants)
- Semantic colors (success, danger, warning, purple)
- Priority badges (high, medium, low)
- Content type badges (syllabus, labs, readings, resources, assignments)
- Role badges (parent, teacher, admin)
- Brand colors (Google)
- Shadows, radii, overlays, gradients

#### 6.15.1 Logo & Branding Assets (Phase 1.5)

The platform uses ClassBridge logo files in multiple locations with theme-aware rendering via transparent backgrounds.

**Logo Types:**

| Logo Type | File | Usage | Dimensions | Theme Support |
|-----------|------|-------|-----------|---------------|
| Auth Logo | `classbridge-logo.png` | Login, Register, ForgotPassword, ResetPassword, AcceptInvite pages | max-width: 280px (220px mobile) | Transparent BG works for all themes |
| Header Icon | `logo-icon.png` | DashboardLayout header (all dashboards) | height: 80px (margin-cropped) | Transparent BG works for all themes |
| Landing Nav Logo | `classbridge-logo.png` | Landing page navigation bar | height: 100px (margin-cropped) | N/A |
| Landing Hero Logo | `classbridge-hero-logo.png` | Landing page hero section | height: 300px (margin-cropped) | N/A |
| Favicon | `favicon.png`, `favicon-192.png`, `favicon.ico`, `favicon.svg` | Browser tab, PWA icon, bookmarks | 16x16, 32x32, 48x48, 192x192 | N/A |

**Theme Handling:**
- CSS uses `content: url()` to swap images based on `[data-theme]` attribute
- Current implementation swaps between `-logo.png` and `-logo-dark.png` variants
- New logo files have transparent backgrounds, so same file works for all themes (light/dark/focus)

**Implementation Details:**
- Auth logo: `Auth.css:21-30` (`.auth-logo` class with dark mode swap)
- Header icon: `Dashboard.css:25-34` (`.header-logo` class with dark mode swap)
- Favicon: `frontend/index.html:5` (`<link rel="icon">`)

**Asset Optimization:**
- Auth logo (v6.1): 196KB - optimized for clarity and detail
- Header icon (v7.1): 150KB - optimized for web performance
- Multiple favicon formats for cross-browser/device support (PNG, ICO, SVG)
- Transparent backgrounds work for both light and dark themes
- All logo images have built-in transparent padding; CSS uses negative margins to visually crop whitespace and render the graphic larger (#427)

**File Locations:**
- Source: `frontend/public/*.{png,ico,svg}`
- Build output: `frontend/dist/*.{png,ico,svg}` (copied during build)

**Status:** Phase 1.5 — IMPLEMENTED (#308, #309, #427) ✅ (Feb 2026, commits 619e42b, d7bb5ce, cdaf63e–000e526)

### 6.15.2 Flat (Non-Gradient) Default Style (Phase 1)

Replace all gradient UI styling with solid accent colors across web and mobile. This is a direct response to user feedback that the gradient style (teal-to-orange diagonal gradients on buttons, tabs, backgrounds) feels too flashy and distracting.

**GitHub Issues:** #486 (parent), #487 (web CSS), #488 (mobile), #489 (gradient toggle)

#### Design Decision
- **Default style: Flat/Solid** — all buttons, tabs, backgrounds, and text accents use solid `var(--color-accent)` instead of `linear-gradient()`
- **Gradient available as opt-in** — users who prefer the old gradient look can re-enable via a style toggle (low priority, #489)
- **Mobile: Flat only** — no gradient style option on mobile

#### Scope (30+ gradient instances across 14 files)

**Web Frontend (13 CSS files):**

| File | Elements Affected |
|------|-------------------|
| `index.css` | Body background (radial wash), dot pattern |
| `Auth.css` | Auth page background, login/register button |
| `Dashboard.css` | Logo text, messages button, active sidebar link, generate/create buttons |
| `MessagesPage.css` | Page title text, new message button, sent message bubble, send button |
| `MyKidsPage.css` | Active child tab, mykids button, study count card, link-child buttons |
| `ParentDashboard.css` | Active child tab, study count card, link-child buttons |
| `CoursesPage.css` | Active child tab |
| `FlashcardsPage.css` | Flashcard front/back faces |
| `Calendar.css` | Primary action button in calendar popover |
| `NotificationBell.css` | Notification action button |
| `AdminDashboard.css` | Admin submit button |
| `TeacherCommsPage.css` | AI summary card |
| `AnalyticsPage.css` | AI insights button |

**Mobile App (1 file):**
- `LoginScreen.tsx` — Replace `expo-linear-gradient` button with solid `colors.primary`

#### Flat Style Design Guidelines
- **Buttons**: `background: var(--color-accent)`, `color: white`. Hover: `var(--color-accent-strong)`
- **Active tabs**: `background: var(--color-accent)`, `color: white`
- **Text accents**: `color: var(--color-accent)` (no `background-clip` gradient text)
- **Flashcards**: Front = `var(--color-accent)`, Back = `var(--color-accent-strong)`
- **Subtle backgrounds** (count cards): `var(--color-accent-light)` (rgba variant)
- **Page background**: Flat `var(--color-surface-bg)` — no radial gradient wash
- **Auth background**: Flat `var(--color-surface-bg)` or subtle single-color tint
- **Skeleton loader**: Keep gradient — it's a loading animation, not decorative

#### Optional Gradient Toggle (#489, low priority)
- `[data-style="gradient"]` CSS attribute restores all gradient declarations
- `ThemeContext.tsx` extended with `style: 'flat' | 'gradient'` (default: `'flat'`)
- Persisted to `localStorage` under `classbridge-style`
- Mobile stays flat-only (no toggle)

#### Status: Phase 1 — IMPLEMENTED (#487)

### 6.16 Layout Redesign (turbo.ai-inspired) — PARTIAL

A layout overhaul inspired by modern SaaS dashboards (turbo.ai), addressing prototype user feedback.

GitHub Issues: #198, #199, #200, #557

#### Changes
- [x] Persistent collapsible sidebar navigation (replacing hamburger slide-out) — IMPLEMENTED (#541, PR #545); further refined to always icon-only with bigger icons and hover tooltips (#557)
- [ ] Glassmorphism card design with gradient borders
- [x] Improved information density and visual hierarchy — IMPLEMENTED (#540, PR #545); further improved with Today's Focus header replacing status cards, primary/secondary quick action hierarchy (#557)
- [x] Simplified header (logo + search + notifications + avatar) — IMPLEMENTED
- [ ] Generous spacing and modern typography
- [x] Mobile: sidebar converts to hamburger overlay on <768px — IMPLEMENTED (#541)

#### Status: Phase 1 — Partially implemented (sidebar + hierarchy + Today's Focus done, visual polish remaining)

### 6.17 Global Search (Phase 1.5) - IMPLEMENTED

**Status: DEPRECATED — Superseded by §6.59.9 (#1630). Removal tracked in #1698.**

A unified search field in the DashboardLayout header that searches across the entire ClassBridge platform. Available to all roles (parent, student, teacher, admin).

**Searchable Entities:**

| Entity | Searchable Fields | Result Navigation |
|--------|-------------------|-------------------|
| Courses | name, description | `/courses/{id}` |
| Study Guides | title | `/study/guide/{id}`, `/study/quiz/{id}`, `/study/flashcards/{id}` |
| Tasks | title, description | `/tasks/{id}` |
| Course Content | title, description | `/study-guides/{id}` |

**Backend:**
- `GET /api/search?q=<query>&types=<csv>&limit=<n>` — unified search endpoint
- Case-insensitive `ilike()` matching (same pattern as admin user search)
- Results respect role-based access (parents see children's data, students see own, etc.)
- Returns results grouped by entity type with count per type
- Default: 5 results per type, minimum query length: 2 characters

**Data Model:** No new tables — queries existing Course, StudyGuide, Task, CourseContent tables.

**Frontend:**
- `GlobalSearch` component in DashboardLayout header (all roles)
- Debounced input (300ms), dropdown overlay with grouped results
- Type icons per category: courses (🎓), study guides (📖), tasks (📋), content (📄)
- Keyboard: Escape closes, Ctrl+K / Cmd+K to focus search
- Click result → navigate to detail page, click outside → close

**Superseded by Help Chatbot (§6.59.9):** Global search functionality has been merged into the AI Help Chatbot (#1355) instead of a standalone search bar. The chatbot serves as the unified search interface — handling both help/FAQ questions and platform data search in one conversational UI. See §6.59.9, #1630. (Original #1410 closed as superseded.)

**Implementation Steps:**
1. Create `app/schemas/search.py` (SearchResultItem, SearchResponse)
2. Create `app/api/routes/search.py` (GET /api/search)
3. Register router in `main.py`
4. Add `searchApi` to `frontend/src/api/client.ts`
5. Create `frontend/src/components/GlobalSearch.tsx` + `.css`
6. Integrate into `DashboardLayout.tsx` header

### 6.18 Mobile Support (Phase 1.5 + Phase 2+)

ClassBridge must be accessible and usable on all devices — phones, tablets, and desktops.

#### Phase 1.5: Mobile-Responsive Web (Current)
Make the existing web application fully responsive and touch-friendly.

**Status:** IN PROGRESS — March 2026 audit found 80+ issues. Most CSS files have breakpoints but many use non-standard values. See linked issues below.

**Standard Breakpoints (canonical — all CSS must use ONLY these):**
- Mobile: 480px
- Tablet: 768px
- Desktop: 1024px

**Requirements:**
- [ ] All pages render correctly at 320px–1440px viewport widths
- [x] Collapsible sidebar navigation on mobile (hamburger menu)
- [x] Viewport meta tag configured correctly
- [ ] All CSS files use ONLY standard breakpoints: 480px, 768px, 1024px (#2486)
- [ ] Minimum font size: 11px for all user-visible text at any viewport (#2482)
- [ ] All page titles (40px+) have mobile scaling media queries (#2482)
- [ ] Full-screen modals on small screens (#2472)
- [ ] Minimum 44px touch targets on all interactive elements (#2619)
- [ ] Horizontal scroll for wide tables with card-view for user-facing tables (#2614)
- [ ] Touch-friendly calendar interactions (tap instead of drag-drop)
- [ ] Swipe gestures for flashcards
- [ ] No horizontal page overflow at any screen size (#2613)
- [ ] Fixed-dimension components use responsive units (min(), clamp(), vw) (#2613)
- [ ] Touch alternatives for all hover-only interactions (#2612)
- [ ] Sidebar panels auto-collapse on mobile (#2617)
- [ ] Shared responsive CSS utility classes in design system (#2616)
- [ ] No functionality accessible only via :hover — touch alternatives required (#2612)

**Implementation Notes:**
- Use standard breakpoints: 480px (mobile), 768px (tablet), 1024px (desktop) — NOT 600px
- CSS-only solutions preferred over JavaScript for responsiveness
- Test with Chrome DevTools device emulation (iPhone SE, iPad, Galaxy S21)
- Test at 320px, 375px, 414px, 768px, 1024px, 1440px viewport widths

**GitHub Issues:** #152 (mobile responsive web), #2486, #2482, #2612, #2613, #2614, #2616, #2617, #2619

#### Phase 2+: Native Mobile Apps (Future)
Dedicated Android and iOS applications for enhanced mobile experience.

**Recommended Approach:** PWA first (Phase 2), then React Native (Phase 3) if needed.

**Future capabilities:**
- Native push notifications
- Offline access to study guides and flashcards
- Camera integration for scanning assignments/documents (#2615)
- App store presence for discoverability
- Home screen install via PWA

**GitHub Issues:** #192 (native mobile apps), #2615

### 6.18.1 Accessibility Standards (WCAG 2.1 AA)

ClassBridge targets WCAG 2.1 Level AA compliance for all user-facing pages. March 2026 audit identified 80+ accessibility issues across the frontend.

**Form Accessibility:**
- [ ] All inputs have associated labels (visible `<label>` with `htmlFor` or `aria-label`) (#2474)
- [ ] Validation errors use `aria-invalid` and `aria-describedby` (#2474)
- [ ] Dynamic status changes use `aria-live` regions (#2478)
- [ ] Register username availability announced to screen readers (#2474)

**Semantic HTML:**
- [ ] Interactive elements use `<button>`, `<a>`, or native form controls — no `div role="button"` (#2473)
- [ ] Data tables use `<table>`, `<thead>`, `<th scope>` for tabular data
- [ ] Modals have `role="dialog"` and `aria-label` (#2472)
- [ ] All dropdowns/listboxes have proper ARIA roles and labels (#2478)

**Color & Contrast:**
- [ ] All text meets 4.5:1 contrast ratio (AA) on its background (#2611)
- [ ] `--color-accent` reserved for large text only; `--color-accent-strong` for small text (#2611)
- [ ] Color is never the sole indicator of state
- [ ] All three themes (light, dark, focus) pass contrast checks (#2611)

**Motion & Animation:**
- [ ] All CSS animations respect `prefers-reduced-motion: reduce` (#2484)
- [ ] Loading spinners reduce to opacity-only animation (not removed entirely) (#2484)
- [ ] Decorative entrance animations fully suppressed when reduced motion preferred (#2484)

**Touch & Input:**
- [ ] All interactive elements have 44px minimum touch target on touch devices (#2619)
- [ ] Hover-only effects wrapped in `@media (hover: hover)` (#2612)
- [ ] Skip-to-main-content link functional (already implemented ✓)

**Testing & CI:**
- [ ] axe-core integrated in CI pipeline (#2148)
- [ ] Lighthouse accessibility score >= 90 on key pages (#2148)
- [ ] Manual screen reader testing on Login, Dashboard, Study Guide pages
- [ ] 200% browser zoom testing on key flows (#2618)

**Known Limitations (documented in #2618):**
- PWA offline: AI features and messaging require network
- Gesture support: Only CalendarView has swipe; other views are tap-only
- Keyboard shortcuts: Desktop-only, visible UI buttons serve as mobile alternatives

**GitHub Issues:** #2148, #2472, #2473, #2474, #2478, #2482, #2484, #2611, #2612, #2618, #2619

### 6.19 AI Email Communication Agent (Phase 5)
- Compose messages inside ClassBridge
- AI formats and sends email to teacher
- AI-powered reply suggestions
- Searchable email archive

### 6.20 UI Polish & Resilience (Phase 1) - IMPLEMENTED

Frontend UX improvements for reliability, feedback, and loading experience.

**GitHub Issues:** #147 (ErrorBoundary), #148 (Toast), #150 (Skeletons)

#### Toast Notification System
- Global `ToastProvider` wraps the app in `App.tsx`
- `useToast()` hook returns `toast(message, type)` for any component
- Three types: `success` (green check), `error` (red x), `info` (blue i)
- Auto-dismiss: 3s for success/info, 5s for errors
- Click to dismiss, max 5 visible, animated entrance
- Mobile responsive (full-width at 480px)

#### React ErrorBoundary
- Class component wraps all routes in `App.tsx`
- Catches unhandled render errors gracefully
- Shows "Something went wrong" card with Try Again / Reload Page buttons
- In dev mode, displays error message for debugging

#### Loading Skeletons
- Reusable `Skeleton`, `PageSkeleton`, `CardSkeleton`, `ListSkeleton`, `DetailSkeleton` components
- Uses CSS shimmer animation (global `.skeleton` class in `index.css`)
- Replaces "Loading..." text across 16 pages: CoursesPage, TeacherDashboard, CourseDetailPage, AdminDashboard, StudyGuidesPage, CourseMaterialDetailPage, TaskDetailPage, ParentDashboard, TeacherCommsPage, AdminAuditLog, TasksPage, StudentDashboard, MessagesPage (conversation selection), QuizPage, FlashcardsPage, MyKidsPage

#### Task Due Date Filters
- Tasks page (`/tasks`) supports `?due=overdue|today|week` URL parameter
- New "Due" filter dropdown: All, Overdue, Due Today, This Week
- Parent Dashboard status cards (Overdue, Due Today) now navigate to `/tasks?due=overdue` and `/tasks?due=today`
- Dashboard overdue/due-today counts computed client-side from task data using local timezone (matches TasksPage filter logic exactly — fixes count mismatch caused by mixing assignment counts and UTC vs local time)
- Dashboard overdue/due-today counts adjust when a specific child is selected
- Filter state syncs with URL for shareable/bookmarkable links

#### Assignee Filter
- Tasks page has an "Assignee" dropdown filter populated from assignable users
- Parents can filter tasks to see only a specific child's tasks
- Filter works client-side alongside existing status, priority, and due filters

### 6.21 Collapsible Calendar (Phase 1) - IMPLEMENTED

Allow parents to collapse/expand the calendar section on the Parent Dashboard for more control over their view.

**GitHub Issue:** #207

**Implementation:**
- Calendar section has a collapse/expand toggle button (chevron icon)
- When collapsed, shows a compact bar with item count and expand button
- When expanded, shows the full calendar (default state)
- Collapse state persists via localStorage across sessions
- Calendar defaults to **collapsed** on all screen sizes (changed in v3 — #544)

### 6.22 Parent UX Simplification (Phase 1.5) — IMPLEMENTED

Simplify the parent experience based on prototype user feedback. The core problem: ClassBridge is organized by feature (Courses, Materials, Tasks) rather than by parent workflow ("What's going on with my kid?").

GitHub Issues: #201, #202, #203, #204, #205, #206

#### 6.22.1 Single Dashboard API Endpoint (#201)
Replace 5+ waterfall API calls with one `GET /api/parent/dashboard` that returns children, overdue counts, due-today items, unread messages, and per-child highlights.

**Status:** IMPLEMENTED ✅

#### 6.22.2 Status-First Dashboard (#202)
Replace calendar-dominated dashboard with status summary cards (overdue count, due today, unread messages) and per-child status cards above the calendar.

**Status:** IMPLEMENTED ✅

#### 6.22.3 One-Click Study Generation (#203)
Smart "Study" button that checks for existing material, generates with defaults if needed, and navigates directly — no modal required for the common case.

**Status:** IMPLEMENTED ✅

#### 6.22.4 Filter Cascade Fix (#204)
Fix course materials page filter behavior: reset course filter when child changes, scope course dropdown to selected child, show result counts.

**Status:** IMPLEMENTED ✅

#### 6.22.5 Modal Nesting Reduction (#205)
Eliminate modal-in-modal patterns. Study generation from day detail should navigate to a page instead of stacking modals.

**Status:** IMPLEMENTED ✅

#### 6.22.6 Parent Navigation (#206, #529, #530)
Parent nav includes full navigation: Overview, Child Profiles, Courses, Course Materials, Tasks, Messages, Help. All non-dashboard pages show a back button (←) in the header. Originally planned to consolidate to 3 items, but user feedback required direct sidebar access to Courses and Course Materials.

**Status:** IMPLEMENTED ✅

### 6.23 Security Hardening (Phase 1) - IMPLEMENTED

Critical security vulnerabilities identified in the Feb 2026 risk audit and fixed:

#### 6.23.1 JWT Secret Key (#179)
- Removed hardcoded default `SECRET_KEY`; application crashes on startup in production if not set or uses a known weak value
- Development mode auto-generates a random 64-char key per process
- Production requires explicit `SECRET_KEY` via environment variable (stored in Google Secret Manager)

#### 6.23.2 Admin Self-Registration & Password Validation (#176)
- Blocked admin role from the public registration endpoint (only parent, student, teacher allowed)
- Added password strength validation: minimum 8 characters, must include uppercase, lowercase, digit, and special character
- Validation applied to both registration and invite acceptance flows

#### 6.23.3 CORS Hardening (#177)
- Replaced `allow_origins=["*"]` with explicit origin allowlist
- Development: `localhost:5173`, `localhost:8000`, configured `frontend_url`
- Production: only the configured `frontend_url` (Cloud Run service URL)
- Restricted allowed methods (GET, POST, PUT, PATCH, DELETE, OPTIONS) and headers (Authorization, Content-Type)

#### 6.23.4 Google OAuth Security (#178)
- Added cryptographic state parameter (CSRF protection) using `secrets.token_urlsafe(32)` with 10-minute TTL
- State tokens are consumed on callback (single-use)
- Removed Google access/refresh tokens from redirect URL parameters
- Google tokens stored server-side in temporary store during registration flow, resolved on user creation
- Error messages no longer leak internal exception details to the frontend

#### 6.23.5 RBAC Authorization Gaps (#181, #139)
- **Students route**: `list_students` restricted to ADMIN/TEACHER; teachers see only students in their courses; `get_student` scoped to admin/own/parent-child/teacher-course; `create_student` restricted to admin
- **Users route**: `get_user` restricted to own profile, admin, parent (linked children), teacher (course students)
- **Assignments route**: added `can_access_course()` checks on all CRUD; `create_assignment` restricted to course owner/teacher/admin; `list_assignments` scoped to accessible courses
- **Courses route**: `get_course` checks course access (enrollment/ownership/admin); `list_course_students` allows admin in addition to teacher
- **Course contents route**: `create`, `get`, and `list` (with course_id) verify course enrollment; update/delete allow admin in addition to creator
- **Study routes**: generation endpoints (study guide, quiz, flashcards) verify assignment course access before generating content
- Shared `can_access_course()` helper in `deps.py` checks admin/owner/public/teacher/enrolled/parent-child-enrolled

#### 6.23.6 Logging & Student Password Security (#182)
- Logging endpoint (`/api/logs/`) now requires authentication (Bearer token)
- Added input validation: max message length (2000 chars), max batch size (50 entries), valid level enum
- Frontend logger already sends auth token via Axios interceptor; unauthenticated errors silently skip server logging
- Parent-created student accounts use `UNUSABLE_PASSWORD_HASH` sentinel (`!INVITE_PENDING`) instead of empty string
- `verify_password()` explicitly rejects empty and sentinel hashes — no login possible without setting a real password via invite link

### 6.24 Multi-Role Support (Phase 1) - PARTIAL

Users can hold multiple roles simultaneously (e.g., a parent who is also a teacher, or an admin who is also a parent and student). The system uses an "Active Role" pattern where `role` is the current dashboard context and `roles` stores all held roles as a comma-separated string.

#### Phase A — IMPLEMENTED (#211)
- [x] **Backend: `roles` column** — `String(50)` comma-separated on User model with `has_role()`, `get_roles_list()`, `set_roles()` helpers
- [x] **Backend: Authorization** — `require_role()` and `can_access_course()` check ALL roles, not just active role
- [x] **Backend: Inline auth checks** — Updated 12 permission gates across 6 route files to use `has_role()`
- [x] **Backend: Registration** — New users get `roles` set to their registration role
- [x] **Backend: DB migration** — Auto-adds `roles` column and backfills from existing `role` at startup
- [x] **Backend: Switch-role endpoint** — `POST /api/users/me/switch-role` to change active dashboard
- [x] **Backend: UserResponse** — Includes `roles: list[str]` with field_validator for ORM compatibility
- [x] **Frontend: AuthContext** — `roles: string[]` on User, `switchRole()` function
- [x] **Frontend: ProtectedRoute** — Checks all roles for route access, not just active role
- [x] **Frontend: Role switcher** — Dropdown in DashboardLayout header (visible only with 2+ roles)

#### Phase B — IN PROGRESS
- [ ] **Admin role management UI** (#255) — Admin can add/remove roles for any user from the admin portal, with checkbox modal and auto-creation of profile records
- [x] **Auto-create profile records** (#256) — When adding teacher/student roles, auto-create Teacher/Student records if missing; preserve data on role removal (IMPLEMENTED - Feb 2026, commit 120e065)
- [x] **Multi-role registration** (#257) — Checkbox role selection during signup instead of single dropdown (IMPLEMENTED - Feb 2026, commit 120e065). **Note:** Role selection is being moved from registration to post-login onboarding (§6.43, #412-#414); multi-role selection will be supported in the onboarding flow instead
- [x] **Admin as multi-role** — Admin users can simultaneously hold parent, teacher, and/or student roles, accessing all corresponding dashboards and features via the role switcher. **CRITICAL:** Access control functions must evaluate ALL held roles, not blanket-deny based on `has_role(ADMIN)` — since `has_role()` checks the `roles` CSV column containing ALL roles. Pure admins are denied by matching no access rule, not by early return. (fix #2468, Mar 2026)
- [ ] Merged data views (combined parent+teacher data on single dashboard)

### 6.25 Course Materials Lifecycle Management (Phase 1) - IMPLEMENTED

Course materials and study guides use soft-delete (archive) with retention policies, last-viewed tracking, and automatic study guide archival when source content changes.

#### Requirements
1. **Edit/move/archive icons on course materials list** — Each item in the StudyGuidesPage list has pencil (edit ✏️), folder (move to course 📂), and trash (archive 🗑️) action icons. Move opens a course selector modal allowing reassignment to a different course (with search and create-new-course option)
2. **Edit + delete on course materials detail page** — Document tab actions (Edit Content, Upload/Replace Document, Download) are accessed via a **+ icon popover** inline with the Original Document tab row (#698, PR #699). Save/Cancel buttons during inline editing remain visible (not in popover). Uses shared `AddActionButton` component (32×32px variant in tab bar). Study guide tabs have "Archive" action.
3. **Back button on detail page** — Course Material Detail page includes a back button (←) in the DashboardLayout header (#696, PR #697)
4. **Regeneration prompt after content edit** — When course material `text_content` is modified and linked study guides are archived, a regeneration prompt appears with buttons for Study Guide, Quiz, and Flashcards
5. **Auto-archive linked study guides** — When a course material's `text_content` field changes, all linked non-archived study guides (`StudyGuide.course_content_id == id`) are automatically archived. A toast notification shows: "Content updated. N linked study material(s) archived."
6. **Soft delete (archive)** — DELETE endpoints for both course materials and study guides set `archived_at` timestamp instead of hard-deleting
7. **Archive list with restore and permanent delete** — StudyGuidesPage has "Show Archive" toggle that loads archived course materials and study guides. Each archived item has restore (↺) and permanent delete (🗑) buttons
8. **On-access auto-archive after 1 year** — When a course material is accessed via GET, if `created_at` is more than 1 year ago and not already archived, it is automatically archived
9. **On-access permanent delete after 7 years** — When a course material is accessed via GET, if `last_viewed_at` is more than 7 years ago, the item and linked study guides are permanently deleted
10. **Last-viewed tracking** — `last_viewed_at` is updated on every GET access to a course material
11. **Toast notifications** — Success messages for archive, restore, delete, and content-save operations
12. **Bulk archive** — Users can select multiple class materials and archive them in a single action. Available on both StudyGuidesPage and CourseDetailPage (`/course-materials`). A confirmation dialog shows the count of selected items before proceeding. Archive is soft-delete (`archived_at` timestamp), same as individual archive. Permission checks (ownership / role) apply per item; items the user lacks permission to archive are skipped with a warning toast (#1846, #1856)
13. **Cascade archive/restore/delete for master materials** — When a master material (`is_master == "true"`) is archived, restored, or permanently deleted, the operation cascades to all its sub-materials (`parent_content_id`). Archive and restore use batch SQL updates; permanent delete iterates subs to handle file cleanup and quota tracking (#1849)

#### Technical Implementation
- **Model changes**: `archived_at` column on `course_contents` and `study_guides` tables; `last_viewed_at` column on `course_contents`
- **Schema**: `CourseContentUpdateResponse` extends `CourseContentResponse` with `archived_guides_count: int`
- **Routes**: `PATCH /{id}/restore`, `DELETE /{id}/permanent` for both course contents and study guides; `include_archived` query param on list endpoints
- **Retention checks**: On-access only (no background job) — 1-year auto-archive, 7-year permanent delete
- **Frontend**: Archive toggle section, toast notifications, inline document editing, regeneration prompt on CourseMaterialDetailPage

#### Files Affected
- `app/models/course_content.py`, `app/models/study_guide.py` — new columns
- `app/schemas/course_content.py`, `app/schemas/study.py` — new response fields
- `app/api/routes/course_contents.py` — soft delete, restore, permanent delete, on-access checks
- `app/api/routes/study.py` — soft delete, restore, permanent delete, `include_archived` filter
- `main.py` — DB migration for new columns
- `frontend/src/api/client.ts` — new API methods and types
- `frontend/src/pages/StudyGuidesPage.tsx` — edit/delete icons, archive section
- `frontend/src/pages/CourseMaterialDetailPage.tsx` — document editing, regeneration prompt
- `frontend/src/pages/CourseDetailPage.tsx` — archive wording, bulk archive UI (#1856)
- CSS files for archived row styles, toast, and regeneration prompt

---

### 6.26 Password Reset Flow (Phase 1) - IMPLEMENTED

Users can reset forgotten passwords via email-based JWT token flow.

**Endpoints:**
- `POST /api/auth/forgot-password` — accepts email, sends reset link (always returns 200, no user enumeration)
- `POST /api/auth/reset-password` — accepts token + new password, validates strength, updates hash

**Frontend:**
- `/forgot-password` — email form with success confirmation
- `/reset-password?token=...` — new password form with confirmation
- "Forgot password?" link on login page

**Security:**
- JWT reset tokens with 1-hour expiry and `type: "password_reset"`
- Rate limited: 3/min for forgot-password, 5/min for reset-password
- Password strength validation (8+ chars, upper, lower, digit, special)
- Audit logging for reset requests and completions

**Reliability (#866):**
- 15-second request timeout on frontend reset call to prevent indefinite hangs
- Background jobs (`teacher_comm_sync`, `assignment_reminders`, `notification_reminders`) use per-item commits to avoid holding long DB row locks on User table during slow I/O (AI calls, email sends)
- Auto-redirect to login page 3 seconds after successful password reset

**Key files:**
- `app/core/security.py` — `create_password_reset_token()`, `decode_password_reset_token()`
- `app/api/routes/auth.py` — forgot-password, reset-password endpoints
- `app/templates/password_reset.html` — email template
- `frontend/src/pages/ForgotPasswordPage.tsx`, `ResetPasswordPage.tsx`

#### 6.26.1 Enhanced Password Management (Phase 1) - IMPLEMENTED

Extended password reset capabilities for all user types and parent-managed child accounts.

**Enhancements:**
- **OAuth/invite-only users:** `forgot-password` now sends reset emails to ALL users with an email address, including those who registered via Google OAuth or were created by a parent. Previously these users were silently skipped.
- **Parent-managed child password reset:** Parents can reset or set passwords for linked children from the My Kids page.
  - **Send reset email** — sends password reset link to child's email (if child has email)
  - **Set directly** — parent enters a password for the child (works even when child has no email)

**Endpoint:**
- `POST /api/parent/children/{student_id}/reset-password` — body: `{ "new_password": "optional" }`. If `new_password` provided, sets directly. If omitted, sends reset email to child.

**Frontend:**
- "Reset Password" button in My Kids per-child Teachers section header
- Modal with method toggle (Send Reset Email / Set Directly) when child has email; direct-only when child has no email
- Password + confirm fields with strength validation for direct set

**Security:**
- Rate limited: 5/min for parent child password reset
- Parent-child relationship verified via `parent_students` join table
- Password strength validation for direct-set method
- Audit logging for all password reset actions (method, target user, initiating parent)

**Key files:**
- `app/api/routes/parent.py` — `reset_child_password` endpoint
- `app/schemas/parent.py` — `ChildResetPasswordRequest` schema
- `frontend/src/pages/MyKidsPage.tsx` — Reset Password modal
- `frontend/src/api/parent.ts` — `resetChildPassword` API method

### 6.27 Design Consistency Initiative - IMPLEMENTED

Cross-page UI consistency pass ensuring all 24 pages follow identical layout, component, and styling patterns.

**GitHub Issues:** #1246, #1247, #1248, #1249, #1250, #1251, #1252, #1253, #1254

**Comprehensive Migration Note:** All pages now use DashboardLayout+PageNav, shared CSS patterns (section-card, list-row, empty-state, btn-* classes), standardized loading states. Orphaned CSS cleaned up across the codebase.

#### 6.27.1 Universal Page Shell
- [x] Every page wrapped in `<DashboardLayout>` with `<PageNav>` breadcrumbs
- [x] StudyGuidePage: add DashboardLayout + PageNav (#1246)
- [x] QuizPage: add DashboardLayout + PageNav (#1247)
- [x] FlashcardsPage: add DashboardLayout + PageNav (#1248)
- [x] TeacherCommsPage: replace custom header with DashboardLayout (#1249)
- [x] CoursesPage + CourseDetailPage: add PageNav breadcrumbs (#1250)

#### 6.27.2 Shared CSS Patterns (#1251, #1252)
- [x] `.btn-primary`, `.btn-secondary`, `.btn-danger`, `.btn-icon` in Dashboard.css
- [x] `.section-card`, `.section-card-header`, `.section-card-body` in Dashboard.css
- [x] `.list-row`, `.list-row-icon`, `.list-row-body`, `.list-row-action` in Dashboard.css
- [x] Standardized `.empty-state` pattern (icon + title + description + CTA)

#### 6.27.3 Page Migration (#1251, #1252, #1253)
- [x] All pages migrated to shared button classes
- [x] All pages migrated to shared section-card pattern
- [x] All pages migrated to shared list-row pattern
- [x] All pages use standard empty-state pattern
- [x] All pages use PageSkeleton/ListSkeleton for loading states

#### 6.27.4 CSS Cleanup (#1254)
- [x] Orphaned per-page CSS removed after migration
- [x] Total CSS line reduction documented

### 6.28 Upload Modal Redesign: Two-Step Wizard - IMPLEMENTED

Redesign the Upload Class Material modal (`CreateStudyMaterialModal`) from a single dense form into a progressive two-step wizard. The current modal overwhelms novice users by presenting file upload, text paste, AI tool checkboxes, title, course selector, material selector, focus prompts, and duplicate warnings all at once. The redesign prioritizes simplicity and usability across all roles (Parent, Student, Teacher, Admin).

**GitHub Issues:** (see Epic issue)

**Problem Statement:**
- Current modal has 8+ form fields visible simultaneously
- AI tool options appear above file upload (backwards flow — need content before generating)
- "Other" checkbox is ambiguous; button label morphs into 3+ variants
- Novice users don't know where to start

**Design: Two-Step Progressive Wizard**

#### 6.28.1 Step 1 — Add Your Material
- [x] File drop zone as hero element (large, prominent, first thing visible)
- [x] Drag-and-drop + click-to-browse (same file types: PDF, Word, Excel, PPT, Images, Text, ZIP)
- [x] Multi-file support (up to 10 files, 30 MB each) — same limits as current
- [x] "or paste text below" divider with textarea
- [x] Clipboard paste support (files + images) — same as current
- [x] Class selector dropdown (only if `courses` prop provided)
- [x] "Next" button advances to Step 2; "Just Upload" link skips AI tools entirely
- [x] Pasted image thumbnails with remove buttons

#### 6.28.2 Step 2 — Generate Study Tools (Optional)
- [x] Summary of uploaded content (filename + checkmark) for context
- [x] Visual card-based tool selection (3 cards: Study Guide, Practice Quiz, Flashcards)
- [x] Cards use icons + labels, tap to toggle, accent border + fill when selected
- [x] Title field (auto-filled from filename, editable)
- [x] "Focus on..." optional prompt field (replaces both focusPrompt and otherPrompt)
- [x] "Skip" button = upload without AI generation
- [x] "Upload & Create" button = upload + generate selected tools
- [x] Remove "Other" checkbox — focus prompt field handles custom requests naturally

#### 6.28.3 Wizard Shell & UX
- [x] Smooth slide animation between steps (left/right)
- [x] Step indicator (1 of 2 / 2 of 2) — subtle, not a heavy stepper
- [x] Back arrow on Step 2 returns to Step 1 with state preserved
- [x] Same component used for all roles (Parent, Student, Teacher, Admin)
- [x] Parent notification note shown inline when `showParentNote` is true
- [x] Duplicate check warning shown as alert after upload attempt (not inline in form)
- [x] Existing material selector moved out of modal (handled via material detail page)

#### 6.28.4 CSS & Responsive
- [x] New wizard modal CSS using existing design system variables
- [x] Card-based tool selector styles (hover, selected, disabled states)
- [x] Step transition animations (CSS or minimal JS)
- [x] Mobile-responsive: cards stack vertically on small screens
- [x] Consistent with 6.27 Design Consistency Initiative patterns

#### 6.28.5 Integration & Cleanup
- [x] Update ParentDashboard to use new wizard modal
- [x] Update StudentDashboard to use new wizard modal
- [x] Update TeacherDashboard to use new wizard modal
- [x] Update StudyGuidesPage to use new wizard modal
- [x] Update StudyPage to use new wizard modal
- [x] Update ReplaceDocumentModal for visual consistency (IMPLEMENTED — PR #1685)
- [x] Remove old CreateStudyMaterialModal.tsx after migration (IMPLEMENTED — PR #1685)
- [x] Remove orphaned CSS for old modal (IMPLEMENTED — PR #1685)

#### 6.28.6 Backend
- No backend changes required — same `/api/course-contents/upload` and `/api/course-contents/upload-multi` endpoints
- Same `StudyMaterialGenerateParams` interface; wizard maps to identical payload

### 6.28.7 Upload Wizard Phase 2: Simplified Upload & Decoupled Generation - IN PROGRESS

**Epic:** #2694 | **Phase 1:** #2695 | **Phase 2:** #2696 | **Phase 3:** #2697

Further simplification of the upload wizard to reduce cognitive load for novice users. Decouples file upload from AI study guide generation — users upload first, then choose what to generate from the Class Materials detail page.

**Problem Statement:**
- Despite the 2-step wizard (6.28), users still struggle to generate study guides
- The wizard combines upload + AI generation in one modal (8+ decisions)
- Full 4096-token study guides are generated even when users only skim the output

**Design: Upload-Only Wizard + Detail Page Generation**

#### Step 1 — Select Your Material (Simplified)
- [x] File drop zone as hero element (drag-drop, paste, multi-file) — same as 6.28.1
- [x] Text paste with image paste detection — preserved from 6.28.1
- [x] **Removed:** Course selector (moved to Step 2)
- [x] **Removed:** "Just Upload" / "Next" dual buttons — single "Next" button only

#### Step 2 — Student & Class (New)
- [x] Student selector (parent with multiple children) — mandatory
- [x] Class selector — mandatory (with "Create new class" option)
- [x] Title field (auto-filled from filename)
- [x] Master file selection for multi-file uploads
- [x] Upload summary bar ("3 files ready to upload")
- [x] **Removed:** Document type selector, study goal selector, AI tool cards, focus prompt
- [x] Single "Upload" button — no AI generation from wizard

#### Post-Upload Navigation
- [x] Navigate to `/course-materials/:id` (detail page for uploaded material)
- [x] No `autoGenerate` flag — user sees their document and chooses what to generate
- [ ] Default to guide tab with prominent empty state

#### Detail Page Empty State Generation Controls
- [ ] **StudyGuideTab:** Auto-detected document type selector, study goal dropdown, focus prompt input, "Generate Study Guide" CTA
- [ ] **QuizTab:** Focus prompt, difficulty selector (easy/medium/hard), "Generate Quiz" CTA
- [ ] **FlashcardsTab:** Focus prompt, "Generate Flashcards" CTA
- [ ] **MindMapTab:** Focus prompt, "Generate Mind Map" CTA
- [ ] All empty states: Clear messaging — "Your document is ready — choose how to study it"
- [ ] Document type auto-classification on page load (lazy, cached)

#### Progressive Study Guide Generation (Phase 2 — #2696)
- [x] Overview-first model: brief 3-5 sentence summary + suggestion chips (max_tokens=1200) (#2838, #2839)
- [x] AI appends `--- SUGGESTION_TOPICS ---` with 4-6 key topics (JSON array) (#2836, #2837)
- [x] Suggestion chips rendered below overview content: topic chips (blue) + "Full Study Guide" (amber, 4000 tokens) + "Ask Bot" (green) (#2852, #2856)
- [x] Strategy templates produce concise summaries for all document types (#2840, #2852)
- [x] Each chip triggers `generate_child_guide()` — creates sub-guide, dedup prevents duplicates (#2810, #2855)
- [x] **Navigate on chip click:** chip click navigates to sub-guide page `/study/guide/{id}` after generation (#2858)
- [x] "Full Study Guide" chip generates comprehensive detailed guide with 4000 max_tokens (#2859, #2860)
- [x] "Ask Bot" chip opens chatbot directly via `open-help-chat` event (#2854)
- [x] Shared constants for special chip labels `ASK_BOT_LABEL`, `FULL_GUIDE_LABEL` (#2857)
- [x] Sub-guides appear in `SubGuidesPanel`
- [x] Document-type-aware max_tokens for all generation paths (#2835)
- [x] **Toast feedback:** "Generating sub-guide..." toast on chip click, error toast on failure
- [x] **Chatbot save buttons:** toast feedback on success/error for Save as Study Guide / Save as Class Material (#2864)
- [x] **Sub-guide level chips:** sub-guide pages show "Full Study Guide" + "Ask Bot" chips (#2870, #2871)
- [x] **Streaming sub-guides:** SSE endpoint `generate-child-stream` with real-time token display (#2858, #2877, PR #2879)
- [x] **Navigate-then-stream:** chip click navigates to `/study/guide/generating` page, streams content there (#2882, #2885)
- [x] **Scroll to guide:** auto-scroll to content area when chip starts generating (#2811, #2876)
- [ ] **Cost model:** ~50% aggregate savings; break-even at 2-3 sub-guides

#### Problem Solver Guide Type (Phase 3 — #2697)
- [ ] New `problem_solver` guide type for math/science step-by-step solutions
- [ ] Dedicated prompt template emphasizing worked solutions, common mistakes, practice problems
- [ ] Renders in study guide tab as variant with type badge (no new tab)
- [ ] Scope: math, science, logic problems — not general tutoring

#### Upload Progress (Phase 4 — #2698)
- [ ] Toast/banner on dashboard: "Uploading..." → "Upload complete — View material"
- [ ] XHR-based progress bar for large files
- [ ] Cached document classification on `CourseContent` model
- [ ] Analytics: track sub-guides generated per overview

