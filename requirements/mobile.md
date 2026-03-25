## 9. Mobile App Development

> **Status:** Parent-only MVP complete (16 screens). Phase 2 comprehensive plan created (2026-03-25).
> **Plan Document:** `docs/mobile-completion-plan.md`
> **Epic Issue:** #2287

---

### 9.1 Overview

**Technology Stack:** React Native + TypeScript with Expo (managed workflow)

**Platforms:** iOS 13+ and Android 8.0+

**Approach:** Parent-only "monitor & communicate" mobile app for the March 6, 2026 pilot. All complex workflows (registration, course management, study material generation, teacher linking) remain web-only. Mobile is read-heavy with limited write actions (reply to messages, mark tasks complete, mark notifications read).

**Key Design Decision:** No backend API changes needed for the mobile MVP. The existing `/api/*` endpoints return all data the mobile app needs. The mobile API client calls the same endpoints as the web frontend.

**GitHub Issues:** #364-#380 (pilot MVP + post-pilot enhancements)

### 9.2 Strategic Decision: React Native with Expo

**Selected Approach:** React Native with Expo SDK 54 (managed workflow)

**Rationale:**
1. **Maximum Code Reuse**: Web app already uses React — shared API types, business logic, patterns
2. **Single Team**: Same tooling (npm, TypeScript, VSCode), hot reload like web
3. **Fast Development**: 8 screens built in under a week using web API types as reference
4. **Expo Go Distribution**: No App Store submission needed for pilot — parents install Expo Go and scan QR code
5. **Native Performance**: Sufficient for educational platform (not gaming/AR)

### 9.3 Mobile Stack (Actual)

**Core:**
- React Native 0.81.5
- TypeScript 5.x
- Expo SDK 54

**Navigation:**
- React Navigation 7 (native stack + bottom tabs)

**State & Data Management (shared patterns with web):**
- TanStack React Query 5.x (same query keys and patterns as web)
- Axios (same interceptor pattern as web)
- AsyncStorage (localStorage equivalent for token storage)

**UI:**
- @expo/vector-icons (MaterialIcons)
- react-native-safe-area-context
- Custom theme system matching ClassBridge brand colors

**Deferred (Phase 3+):**
- React Native Firebase (push notifications)
- Expo Image Picker / Document Picker (file uploads)
- React Native MMKV (offline cache persistence)

### 9.4 Backend API Changes

**Key Decision: No backend changes needed for the March 6 pilot.** The existing `/api/*` endpoints return all data the mobile app needs. CORS is not a factor for React Native (native HTTP clients bypass browser CORS restrictions). The mobile API client calls the exact same endpoints as the web frontend.

**Deferred backend API work** (to be implemented post-pilot as needed):
- Issue #311: API Versioning (`/api/v1`) — Not needed when you control both clients
- Issue #312: Pagination on all list endpoints — Not needed for pilot scale
- Issue #313: Structured error responses — Nice-to-have for Phase 3
- Issues #314-#318: Firebase push notifications — Deferred to Phase 3 (late March)
- Issues #319-#320: File upload endpoints — Not needed for read-only parent mobile
- Issue #321: Health endpoint with version info — Deferred
- Issue #322: Integration tests for v1 API — Deferred (no v1 API yet)

### 9.5 Mobile App — What Was Built (Pilot MVP)

**Project:** `ClassBridgeMobile/` — Expo SDK 54 managed workflow

#### 9.5.1 Foundation (Issues #364-#366) ✅ COMPLETE

**API Client (#364)** — Ported from `frontend/src/api/client.ts`
- `src/api/client.ts` — Axios instance with AsyncStorage token management
- Token refresh interceptor (same logic as web, using AsyncStorage instead of localStorage)
- Form-urlencoded login (backend uses `OAuth2PasswordRequestForm`)
- `src/api/parent.ts` — ParentDashboardData, ChildHighlight, ChildOverview types
- `src/api/messages.ts` — ConversationSummary, ConversationDetail, MessageResponse types
- `src/api/notifications.ts` — NotificationResponse type + list/read/count functions
- `src/api/tasks.ts` — TaskItem type + list/toggleComplete functions

**Auth & Login (#365)**
- `src/context/AuthContext.tsx` — Token in AsyncStorage, auto-load user on app start, login/logout
- `src/screens/auth/LoginScreen.tsx` — Email/password form, validation, error display

**Navigation (#366)**
- `src/navigation/AppNavigator.tsx` — Auth-gated navigation:
  - Not authenticated → LoginScreen
  - Authenticated → Bottom tab navigator (Home, Calendar, Messages, Notifications, Profile)
  - HomeStack: Dashboard → ChildOverview (nested stack)
  - MsgStack: ConversationsList → Chat (nested stack)

#### 9.5.2 Core Screens (Issues #367-#373) ✅ COMPLETE

| Screen | Issue | API Endpoint | Key Features |
|--------|-------|-------------|--------------|
| ParentDashboardScreen | #367 | `GET /api/parent/dashboard` | Greeting, 3 status cards (overdue/due today/messages), child cards with avatars and status badges |
| ChildOverviewScreen | #368 | `GET /api/parent/children/{id}/overview` + `GET /api/tasks/` | Courses list, assignments sorted by due date, tasks with complete toggle |
| CalendarScreen | #369 | Dashboard `all_assignments` + tasks API | Custom month grid, color-coded date dots, tap date → day items list |
| MessagesListScreen | #370 | `GET /api/messages/conversations` | Conversation cards, unread badges, time formatting, tap → Chat |
| ChatScreen | #371 | `GET /api/messages/conversations/{id}` + `POST .../messages` | Chat bubbles (sent/received), date separators, send message, auto-mark-read |
| NotificationsScreen | #372 | `GET /api/notifications/` | Type-specific icons, mark as read, mark all read, relative timestamps |
| ProfileScreen | #373 | `GET /api/auth/me` | User info, unread counts, Google status, logout, web app reminder |

#### 9.5.3 UI Polish (#374) ✅ COMPLETE

- SafeArea handling via `useSafeAreaInsets` on headerless screens
- Native headers on Calendar, Notifications, Profile tabs
- Tab bar badges with 30-second polling (Messages: unread count, Notifications: unread count)
- Pull-to-refresh (`RefreshControl`) on all list/scroll screens
- Empty states with icons and messages
- Loading spinners with messages

#### 9.5.4 Remaining Pilot Work

- [x] **Device testing prep (#375):** ESLint 9 flat config migration, unused import cleanup, dependency compatibility fix (`react-native-screens`), `useMemo` dependency fix in ChatScreen — TypeScript and ESLint pass clean, Metro Bundler starts successfully
- [ ] **Device testing (#375):** Test on physical iOS device via Expo Go, test on physical Android device
- [x] **Pilot onboarding docs (#362):** Welcome email template (`docs/pilot/welcome-email.md`), quick-start guide with Expo Go instructions, known limitations, and feedback mechanism (`docs/pilot/quick-start-guide.md`)
- [ ] **Pilot launch checklist (#376):** Verify mobile connects to production API, prepare Expo Go instructions

#### 9.5.5 Mobile Unit & Component Testing (#490-#494)

**Framework:** Jest + React Native Testing Library (same pattern as web frontend's 319 tests)

| Screen | Issue | Tests | Status |
|--------|-------|-------|--------|
| Test framework setup (Jest + RNTL config, mocks) | #490 | — | [ ] |
| LoginScreen | #491 | Logo, inputs, validation, auth flow, error states | [ ] |
| ParentDashboardScreen | #492 | Greeting, status cards, child cards, navigation | [ ] |
| ChildOverviewScreen | #492 | Stats, assignments, tasks, completion toggle | [ ] |
| CalendarScreen | #492 | Grid, date selection, month nav, item dots | [ ] |
| MessagesListScreen | #493 | Conversations, unread styling, time formatting | [ ] |
| ChatScreen | #493 | Message bubbles, send flow, date separators | [ ] |
| NotificationsScreen | #494 | Icons, unread styling, mark read, time formatting | [ ] |
| ProfileScreen | #494 | Avatar, stats, Google status, sign out alert | [ ] |
| PlaceholderScreen | #494 | Smoke test | [ ] |

### 9.6 Mobile Boundary (What's Mobile vs Web-Only)

**MOBILE (parent read/reply only):**
- View dashboard: children status cards (overdue, due today, courses)
- View child detail: courses, assignments, upcoming deadlines
- View calendar: assignments & tasks by date (read-only)
- View/reply messages: parent-teacher conversations
- View notifications: mark as read
- Mark tasks complete: single tap toggle
- View profile & logout

**WEB ONLY (complex workflows):**
- Registration & account setup
- Create/link/edit children (invites, Google discovery)
- Create courses, assign to children, Google sync
- Link teachers (invite flow, email notifications)
- Generate study materials (AI, file upload)
- Create tasks with full detail & resource linking
- Teacher email monitoring (Gmail OAuth)
- All admin functions
- All student & teacher functions

### 9.7 Post-Pilot Phases

#### Phase 3: Post-Pilot Enhancement (Mar 7-31)

| Task | Issue | Est. |
|------|-------|------|
| Firebase Admin SDK setup | #314 | 1 day |
| DeviceToken model + endpoints | #315 | 1 day |
| Push notification service | #316 | 1 day |
| Integrate with key events | #317 | 2 days |
| Firebase in mobile app + deep linking | #334-#335 | 2 days |
| Notification polling (30s foreground) | #377 | 1 day |
| React Query offline caching | #378 | 1 day |
| API versioning (/api/v1) | #311 | 2 days |
| Structured error responses | #313 | 1 day |

#### Phase 4: Full Mobile + Scale (April 2026)

| Task | Issue |
|------|-------|
| Student mobile screens (dashboard, assignments, study viewer) | #379 |
| Teacher mobile screens (messages, notifications, quick grade) | #380 |
| Camera/file upload for course content | #333 |
| Profile picture upload | #319 |
| Offline mode with data sync | #337 |
| App Store + Google Play public launch | #343-#346 |
| Pagination on all endpoints | #312 |
| Mobile CI/CD pipeline | #352 |

### 9.8 Project Structure

```
ClassBridgeMobile/
  src/
    api/
      client.ts          # Axios instance + AsyncStorage token management
      parent.ts          # Parent dashboard/children types + functions
      messages.ts        # Conversations, messages types + functions
      notifications.ts   # Notification types + functions
      tasks.ts           # Task types + functions
    context/
      AuthContext.tsx     # Auth state provider (AsyncStorage)
    navigation/
      AppNavigator.tsx    # Root stack + bottom tabs + nested stacks
    screens/
      auth/
        LoginScreen.tsx
      parent/
        ParentDashboardScreen.tsx
        ChildOverviewScreen.tsx
        CalendarScreen.tsx
      messages/
        MessagesListScreen.tsx
        ChatScreen.tsx
      notifications/
        NotificationsScreen.tsx
      profile/
        ProfileScreen.tsx
    components/
      LoadingSpinner.tsx
      EmptyState.tsx
    theme/
      index.ts           # Colors, spacing, fontSize, borderRadius
  __tests__/             # Jest + React Native Testing Library tests
    setup.ts             # Test setup (mocks for navigation, auth, React Query)
    screens/             # Screen-level component tests
  app.json               # Expo configuration
  jest.config.js         # Jest configuration
  package.json
  tsconfig.json
```

### 9.9 Success Criteria (Pilot)

**Pilot MVP (March 6):**
- [x] All 8 screens built and type-checked
- [ ] App loads on physical iOS device via Expo Go
- [ ] App loads on physical Android device via Expo Go
- [ ] Parent can log in and see dashboard with children
- [ ] Parent can tap child → see courses/assignments
- [ ] Parent can read and reply to messages
- [ ] Parent can view and mark notifications as read
- [ ] No crashes during pilot use

**Post-Pilot Targets:**
- Push notifications working for all event types
- Student + teacher mobile screens
- App Store + Google Play submission
- < 1% crash rate, 4.0+ star rating

### 9.10 Phase 2: Complete Mobile App (April-June 2026)

> **Comprehensive plan created 2026-03-25.** See `docs/mobile-completion-plan.md` for full details.
> **Epic:** #2287 | **Recommendations:** #2314

#### 9.10.1 Phase 2A: Brand Polish + Parent Completion (~10 days)

| Task | Issue | Est. |
|------|-------|------|
| Branded app icon, adaptive icon, splash screen | #2288 | 0.5d |
| Align mobile theme with full web design system | #2289 | 1d |
| Add custom fonts (Space Grotesk + Source Sans 3) | #2290 | 0.5d |
| Dark mode + Focus mode | #2291 | 1d |
| Daily briefing screen (parent) | #2292 | 1d |
| Grade trends/analytics screen (parent) | #2293 | 1d |
| Study guide viewer (read-only) | #2294 | 1.5d |
| Flashcard viewer (read-only) | #2295 | 1d |
| Activity history screen (parent) | #2296 | 0.5d |
| Notification preferences screen | #2297 | 0.5d |
| Google OAuth login | #2298 | 1d |

#### 9.10.2 Phase 2B: Push Notifications + Infrastructure (~9 days)

| Task | Issue | Est. |
|------|-------|------|
| Firebase Admin SDK (backend) | #314 | 1d |
| DeviceToken model + endpoints | #315 | 1d |
| Push notification service | #316 | 1d |
| Integrate with key events | #317 | 2d |
| Firebase in mobile app | #334 | 1d |
| Deep linking for notifications | #335 | 1d |
| Crash reporting (Sentry/Expo) | #2310 | 0.5d |
| Analytics integration | #2311 | 0.5d |
| CI/CD pipeline (EAS Build) | #352 | 1d |

#### 9.10.3 Phase 2C: Student Mobile (~12 days)

| Task | Issue | Est. |
|------|-------|------|
| Role-based navigation router | #2299 | 1d |
| Student dashboard screen | #2300 | 1.5d |
| Student course list + enrollment | #2301 | 1d |
| Quiz taking screen | #2302 | 2d |
| XP / streak / badges screen | #2303 | 1d |
| Student assignment list + detail | #2304 | 1.5d |
| Flashcard study mode | #2305 | 1.5d |
| Student grade summary | #2306 | 0.5d |

#### 9.10.4 Phase 2D: Teacher Mobile (~7.5 days)

| Task | Issue | Est. |
|------|-------|------|
| Teacher dashboard screen | #2307 | 1.5d |
| Teacher course & student list | #2308 | 1d |
| Teacher assignment list & grade viewer | #2309 | 1d |
| (Messages/notifications shared from parent) | — | 0d |

#### 9.10.5 Phase 2E: Store Submission + Offline (~8.5 days)

| Task | Issue | Est. |
|------|-------|------|
| React Query offline caching | #378 | 1d |
| OTA update mechanism (expo-updates) | #2312 | 0.5d |
| Biometric authentication | #2313 | 1d |
| Beta testing (TestFlight) | #342 | 1d |
| Beta testing (Google Play Internal) | #343 | 1d |
| App Store submission | #344 | 2d |
| Google Play submission | #345 | 2d |

### 9.11 Features Explicitly NOT Building for Mobile

> **Recommendation Issue:** #2314

The following remain **web-only** based on analysis of user value vs. development cost:

| Feature | Reason |
|---------|--------|
| All admin screens | Low frequency, 1-3 users, keyboard-heavy |
| Study guide generation | File upload + streaming, desktop workflow |
| Google Classroom OAuth setup | Complex redirect, one-time setup |
| Course/assignment creation | Form-heavy, teacher desktop workflow |
| Teacher email monitoring setup | Gmail OAuth, power-user feature |
| Data export (GDPR) | One-time, large file download |
| Print/PDF export | Niche mobile use case |
| Registration/onboarding | One-time event, link to web |
| Account deletion | One-time, deep-link to web |
| Wallet purchase flow | Stripe checkout requires web |
| ICS calendar import | Setup-once operation |

### 9.12 Updated Project Structure (Phase 2 Target)

```
ClassBridgeMobile/
  src/
    api/
      client.ts              # Axios + AsyncStorage token management
      auth.ts                # Login, logout, getMe, Google OAuth
      parent.ts              # Parent dashboard/children
      courses.ts             # Courses (all roles)
      courseContents.ts       # Study guides, quizzes, flashcards
      messages.ts            # Conversations, messages
      notifications.ts       # Notifications
      tasks.ts               # Tasks
      assignments.ts         # Assignments (student + teacher)
      grades.ts              # Grades & analytics
      xp.ts                  # XP, streak, badges (student)
      briefing.ts            # Daily briefing (parent)
      quizResults.ts         # Quiz results
    context/
      AuthContext.tsx         # Auth state provider
      ThemeContext.tsx        # Light/dark/focus theme
    navigation/
      AppNavigator.tsx        # Root stack + role router
      ParentTabNavigator.tsx  # Parent bottom tabs
      StudentTabNavigator.tsx # Student bottom tabs
      TeacherTabNavigator.tsx # Teacher bottom tabs
    screens/
      auth/
        LoginScreen.tsx
      parent/
        ParentDashboardScreen.tsx
        ChildOverviewScreen.tsx
        MyKidsScreen.tsx
        CoursesScreen.tsx
        ClassMaterialsScreen.tsx
        TasksScreen.tsx
        CalendarScreen.tsx
        QuizHistoryScreen.tsx
        AddChildScreen.tsx
        HelpScreen.tsx
        DailyBriefingScreen.tsx      # NEW
        GradeTrendsScreen.tsx         # NEW
        ActivityHistoryScreen.tsx     # NEW
      student/
        StudentDashboardScreen.tsx    # NEW
        CourseListScreen.tsx          # NEW
        AssignmentListScreen.tsx      # NEW
        AssignmentDetailScreen.tsx    # NEW
        QuizTakingScreen.tsx          # NEW
        XpBadgesScreen.tsx            # NEW
        GradeSummaryScreen.tsx        # NEW
      teacher/
        TeacherDashboardScreen.tsx    # NEW
        TeachingCoursesScreen.tsx     # NEW
        StudentListScreen.tsx         # NEW
        TeacherAssignmentsScreen.tsx  # NEW
        GradeViewerScreen.tsx         # NEW
      shared/
        StudyGuideViewerScreen.tsx    # NEW (parent + student)
        FlashcardViewerScreen.tsx     # NEW (parent + student)
        FlashcardStudyScreen.tsx      # NEW (student interactive)
        NotificationPrefsScreen.tsx   # NEW
      messages/
        MessagesListScreen.tsx
        ChatScreen.tsx
      notifications/
        NotificationsScreen.tsx
      profile/
        ProfileScreen.tsx
      common/
        PlaceholderScreen.tsx
    components/
      ChildCard.tsx
      EmptyState.tsx
      LoadingSpinner.tsx
      HeaderIcons.tsx
    theme/
      index.ts               # Full design system (colors, fonts, shadows)
      dark.ts                # Dark theme overrides
      focus.ts               # Focus theme overrides
    types/
      user.ts
  __tests__/
  assets/
    icon.png                 # ClassBridge branded
    adaptive-icon.png        # ClassBridge branded
    splash-icon.png          # ClassBridge branded
    classbridge-logo.png
    logo-icon.png
  app.json
  eas.json
  package.json
```

### 9.13 Success Criteria (Phase 2)

- [ ] All 3 roles (parent, student, teacher) functional on mobile
- [ ] ClassBridge branding throughout (icons, splash, fonts, theme)
- [ ] Push notifications delivered for key events
- [ ] Dark mode + Focus mode working
- [ ] Crash reporting capturing errors
- [ ] App Store + Google Play published
- [ ] < 1% crash rate
- [ ] Offline data caching for "last seen" data

---

