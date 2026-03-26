# ClassBridge Mobile App — Comprehensive Completion Plan

> **Date:** 2026-03-25
> **Mode:** SCOPE EXPANSION — Build the cathedral
> **Branch:** `feature/mobile-app-complete-plan`
> **Base:** `master`

---

## Executive Summary

The ClassBridge mobile app (Expo SDK 54, React Native) has a **parent-only MVP** with 14 screens. This plan maps every feature gap between mobile and web, organizes them into phased GitHub issues, and provides explicit recommendations on what should **NOT** be built for mobile.

**Current State:** 14 screens, parent role only, read-heavy with limited writes
**Target State:** Full parent experience + student mobile + teacher mobile, with push notifications, offline support, and App Store/Play Store distribution
**Not In Scope:** Admin mobile, study guide generation, complex OAuth flows, file uploads

---

## 1. System Audit Findings

### 1.1 Current Mobile App Inventory (14 Screens)

| # | Screen | Role | Status |
|---|--------|------|--------|
| 1 | LoginScreen | Shared | ✅ Complete |
| 2 | ParentDashboardScreen | Parent | ✅ Complete |
| 3 | MyKidsScreen | Parent | ✅ Complete |
| 4 | ChildOverviewScreen | Parent | ✅ Complete |
| 5 | CoursesScreen | Parent | ✅ Complete |
| 6 | ClassMaterialsScreen | Parent | ✅ Complete |
| 7 | TasksScreen | Parent | ✅ Complete |
| 8 | CalendarScreen | Parent | ✅ Complete |
| 9 | QuizHistoryScreen | Parent | ✅ Complete |
| 10 | AddChildScreen | Parent | ✅ Complete |
| 11 | MessagesListScreen | Shared | ✅ Complete |
| 12 | ChatScreen | Shared | ✅ Complete |
| 13 | NotificationsScreen | Shared | ✅ Complete |
| 14 | ProfileScreen | Shared | ✅ Complete |
| 15 | HelpScreen | Shared | ✅ Complete |
| 16 | PlaceholderScreen | Utility | ✅ Complete |

### 1.2 Existing GitHub Issues (Mobile-labeled)

- 24 open mobile-labeled issues (#311-#380, #425, #963, #1870)
- Key gaps: push notifications (#314-#317), student screens (#379), teacher screens (#380), CI/CD (#352), store submissions (#343-#346)
- Device testing still pending (#375)

### 1.3 Design System Drift

The mobile theme (`ClassBridgeMobile/src/theme/index.ts`) is **missing** several web design tokens:

| Token | Web (index.css) | Mobile (theme/index.ts) | Gap |
|-------|----------------|------------------------|-----|
| Semantic colors | danger, warning, success, info + light variants | Only error, warning, secondary | Missing danger, info, success-light |
| Priority colors | high/medium/low + light variants | Not in theme | **MISSING** |
| Role badge colors | parent (#b1571e), teacher (#2e7d32), admin (#a85f13) | Not in theme | **MISSING** |
| Content badge colors | syllabus, labs, readings, resources, assignments | Not in theme | **MISSING** |
| Purple accent | #7c3aed + light/bg variants | Not in theme | **MISSING** |
| Overlay colors | overlay, overlay-light | Not in theme | **MISSING** |
| Shadow scale | xs through xl (7 levels) | Not in theme | **MISSING** |
| Status backgrounds | success-bg, warning-bg, info-bg + borders | Not in theme | **MISSING** |
| Fonts | Space Grotesk (display) + Source Sans 3 (body) | System default | **MISSING** |

### 1.4 Logo/Branding Assets

**Available logos (OneDrive/Selected):**
- ClassBridge.logo.v6.1.png — current web header logo
- ClassBridge.logo.v7.1.png — alternate version
- ClassBridge.logo.v3.transparent.png — transparent background
- ClassBridge.logo.v3.dark.png — dark mode variant
- CB_Chat_bubble-2.png — chat/messaging icon

**Currently in mobile assets:**
- classbridge-logo.png — v6.1 (correct, matches web)
- logo-icon.png — v7.1
- icon.png, adaptive-icon.png, splash-icon.png — **generic Expo defaults, NOT ClassBridge branded**

**Gap:** App icon, adaptive icon, and splash screen are Expo defaults — not ClassBridge branded.

---

## 2. Feature Gap Analysis: Mobile vs Web

### 2.1 Parent Features — GAPS

```
  FEATURE                          WEB    MOBILE   PRIORITY
  ─────────────────────────────────────────────────────────
  Dashboard                        ✅      ✅       —
  Child management (view)          ✅      ✅       —
  Child add/link                   ✅      ✅       —
  Courses view                     ✅      ✅       —
  Class materials view             ✅      ✅       —
  Tasks (view + create + toggle)   ✅      ✅       —
  Calendar                         ✅      ✅       —
  Messages (view + reply)          ✅      ✅       —
  Notifications                    ✅      ✅       —
  Quiz history                     ✅      ✅       —
  Profile                          ✅      ✅       —
  Help/FAQ                         ✅      ✅       —
  ─────────────────────────────────────────────────────────
  Daily briefing view              ✅      ❌       P1
  Grade trends/analytics           ✅      ❌       P1
  Study guide viewer (read-only)   ✅      ❌       P1
  Flashcard viewer (read-only)     ✅      ❌       P2
  Quiz viewer (read-only results)  ✅      ❌       P2
  AI briefing notes                ✅      ❌       P2
  Activity history                 ✅      ❌       P2
  Conversation starters            ✅      ❌       P2
  Notification preferences         ✅      ❌       P2
  Report card viewer               ✅      ❌       P3
  Google OAuth login               ✅      ❌       P2
  Dark mode / Focus mode           ✅      ❌       P3
  Bug reporting                    ✅      ❌       P3
  Print/PDF export                 ✅      ❌       P3 (web-only rec.)
  Search                           ✅      ❌       P3
```

### 2.2 Student Features — ALL MISSING

```
  FEATURE                          WEB    MOBILE   PRIORITY
  ─────────────────────────────────────────────────────────
  Student dashboard                ✅      ❌       P1
  Course list + enrollment         ✅      ❌       P1
  Assignment list + details        ✅      ❌       P1
  Study guide viewer               ✅      ❌       P1
  Quiz taking                      ✅      ❌       P1
  Flashcard viewer                 ✅      ❌       P2
  XP / streak / badges             ✅      ❌       P1
  Study sessions tracking          ✅      ❌       P2
  Study requests (view + respond)  ✅      ❌       P2
  Grade summary                    ✅      ❌       P2
  Notes (read-only)                ✅      ❌       P3
  Readiness assessments            ✅      ❌       P3
  Study sharing                    ✅      ❌       P3
  ─────────────────────────────────────────────────────────
  Study guide GENERATION           ✅      ❌       NOT NEEDED
  File upload for materials        ✅      ❌       NOT NEEDED
  Course creation                  ✅      ❌       NOT NEEDED
```

### 2.3 Teacher Features — ALL MISSING

```
  FEATURE                          WEB    MOBILE   PRIORITY
  ─────────────────────────────────────────────────────────
  Teacher dashboard                ✅      ❌       P1
  Course list (teaching)           ✅      ❌       P1
  Student list per course          ✅      ❌       P1
  Assignment list + details        ✅      ❌       P1
  Grade viewer                     ✅      ❌       P2
  Quick message to parent          ✅      ❌       P1
  Invite management                ✅      ❌       P2
  Google Classroom status          ✅      ❌       P2
  ─────────────────────────────────────────────────────────
  Course creation                  ✅      ❌       NOT NEEDED
  Assignment creation/editing      ✅      ❌       NOT NEEDED
  Full Google Classroom sync       ✅      ❌       NOT NEEDED
  Course content management        ✅      ❌       NOT NEEDED
  Teacher email monitoring setup   ✅      ❌       NOT NEEDED
```

### 2.4 Infrastructure Gaps

```
  CAPABILITY                       STATUS        PRIORITY
  ─────────────────────────────────────────────────────────
  Push notifications (FCM)         Not started   P0
  Offline data caching             Not started   P1
  CI/CD pipeline (EAS Build)       Not started   P1
  App Store submission             Not started   P1
  Google Play submission           Not started   P1
  Beta testing (TestFlight)        Not started   P1
  Device testing                   Pending       P0
  Deep linking                     Not started   P2
  Biometric auth (Face ID/Touch)   Not started   P2
  App update prompts (OTA)         Not started   P2
  Analytics (Firebase/PostHog)     Not started   P2
  Crash reporting (Sentry)         Not started   P1
  API versioning                   Not started   P3
```

---

## 3. Recommendations: Features NOT Needed on Mobile

### 3.1 Admin Features — NONE on Mobile

**Recommendation:** Do not build any admin screens for mobile.

**Why:**
- Admin tasks (user management, AI usage limits, waitlist, FAQ management, feature toggles, broadcasts, surveys, holidays, XP awards) are low-frequency, keyboard-heavy operations
- Admin users are power users who work from desktops
- ClassBridge has 1-3 admins vs potentially thousands of parents/students
- Every admin screen would need complex tables, filters, bulk actions — terrible UX on mobile
- Zero user demand signal

**Affected web features (all skip mobile):**
- User management, storage overview
- AI usage management
- Waitlist management
- FAQ management
- Survey management
- Broadcast messages
- Feature toggles
- Holiday management
- Audit logs
- XP award management

### 3.2 Study Guide Generation — Web Only

**Recommendation:** Do not build AI study guide generation on mobile. Build read-only viewer instead.

**Why:**
- Generation requires file upload (PDF, DOCX, PPTX — up to 30MB)
- Multi-step wizard (select file → extract text → choose options → generate → stream response)
- Streaming generation takes 30-90 seconds with real-time markdown rendering
- File picking on mobile is friction-heavy and error-prone
- The output (study guides) should be viewable on mobile — that's the high-value mobile use case
- Students generate on desktop at home, review on phone during commute/breaks

### 3.3 Complex OAuth Flows — Web Only

**Recommendation:** Do not implement Google Classroom OAuth setup on mobile.

**Why:**
- Google OAuth consent screen → redirect → callback is complex on mobile
- Multi-account Google management is a power-user workflow
- Teacher email monitoring requires Gmail OAuth — desktop workflow
- Mobile can show Google connection **status** without managing the connection
- OAuth tokens are shared across web/mobile via the same user account

### 3.4 Course/Assignment Creation — Web Only

**Recommendation:** Do not build course creation, assignment creation, or content management on mobile.

**Why:**
- These are keyboard-intensive, form-heavy workflows
- Requires file attachments, rich text, date pickers, student selectors
- Teachers create content at their desks, not on phones
- Students and parents never create courses
- Mobile should be read/monitor/respond, not create/manage

### 3.5 Data Export — Web Only

**Recommendation:** Keep GDPR data export as web-only.

**Why:**
- One-time operation, not a daily workflow
- Generates large ZIP files
- Browser download handling is more reliable than mobile file system

### 3.6 Print/PDF Export — Web Only

**Recommendation:** Do not implement print/PDF on mobile.

**Why:**
- Mobile printing is niche and unreliable
- PDF generation should happen server-side if ever needed on mobile
- Users who need to print will use the web app

### 3.7 Full Calendar Management — Keep Read-Only

**Recommendation:** Keep calendar as read-only on mobile. Do not build ICS import or event creation.

**Why:**
- Calendar import (ICS feeds) is a setup-once operation
- Event creation is keyboard-heavy
- Mobile calendar is for quick "what's coming up" checks
- Matches the "monitor on phone, manage on desktop" pattern

### 3.8 Registration & Onboarding — Web Only

**Recommendation:** Do not build registration on mobile. Link to web from login screen.

**Why:**
- Registration is a one-time event
- Involves email verification, role selection, onboarding wizard
- Parent registration often includes child linking (multi-step)
- "Download app → register" is a poor conversion funnel anyway
- Standard pattern: register on web, then install app

### 3.9 Account Deletion — Web Only

**Recommendation:** Keep account deletion as web-only.

**Why:**
- GDPR/legal compliance feature, not a daily workflow
- 30-day grace period with email confirmations
- One-time operation
- App Store guidelines require a way to delete — can deep-link to web

### 3.10 Wallet/Credits Management — Web Only for Now

**Recommendation:** Show balance on mobile, manage on web.

**Why:**
- Payment flows (Stripe checkout) require web redirects
- Package selection and auto-refill are power-user settings
- Students can see "X credits remaining" in mobile profile
- Actual purchase happens on desktop

---

## 4. Phased Implementation Plan

### Phase 2A: Brand Polish + Parent Completion (April 2026)

| # | Task | Est. | Issues |
|---|------|------|--------|
| 1 | Branded app icon, adaptive icon, splash screen | 0.5d | NEW |
| 2 | Align mobile theme with full web design system | 1d | NEW |
| 3 | Add custom fonts (Space Grotesk + Source Sans 3) | 0.5d | NEW |
| 4 | Dark mode + Focus mode | 1d | NEW |
| 5 | Daily briefing screen (parent) | 1d | NEW |
| 6 | Grade trends/analytics screen (parent) | 1d | NEW |
| 7 | Study guide viewer (read-only, parent) | 1.5d | NEW |
| 8 | Flashcard viewer (read-only, parent) | 1d | NEW |
| 9 | Activity history screen (parent) | 0.5d | NEW |
| 10 | Notification preferences screen | 0.5d | NEW |
| 11 | Google OAuth login | 1d | NEW |
| 12 | Conversation starters in daily briefing | 0.5d | NEW |

**Subtotal: ~10 days**

### Phase 2B: Push Notifications + Infrastructure (April 2026)

| # | Task | Est. | Issues |
|---|------|------|--------|
| 1 | Firebase Admin SDK (backend) | 1d | #314 |
| 2 | DeviceToken model + endpoints | 1d | #315 |
| 3 | Push notification service | 1d | #316 |
| 4 | Integrate with key events | 2d | #317 |
| 5 | Firebase in mobile app | 1d | #334 |
| 6 | Deep linking for notifications | 1d | #335 |
| 7 | Crash reporting (Sentry/Expo) | 0.5d | NEW |
| 8 | Analytics integration | 0.5d | NEW |
| 9 | CI/CD pipeline (EAS Build) | 1d | #352 |

**Subtotal: ~9 days**

### Phase 2C: Student Mobile (May 2026)

| # | Task | Est. | Issues |
|---|------|------|--------|
| 1 | Student dashboard screen | 1.5d | #379 (expand) |
| 2 | Course list + enrollment screen | 1d | NEW |
| 3 | Assignment list + detail screen | 1.5d | #328, #329 |
| 4 | Study guide viewer (student) | 1d | Shared w/ parent |
| 5 | Quiz taking screen | 2d | NEW |
| 6 | Flashcard study mode screen | 1.5d | NEW |
| 7 | XP / streak / badges screen | 1d | NEW |
| 8 | Study requests (view + respond) | 0.5d | NEW |
| 9 | Grade summary screen | 0.5d | NEW |
| 10 | Study session tracking | 0.5d | NEW |
| 11 | Student navigation restructure | 1d | NEW |

**Subtotal: ~12 days**

### Phase 2D: Teacher Mobile (May-June 2026)

| # | Task | Est. | Issues |
|---|------|------|--------|
| 1 | Teacher dashboard screen | 1.5d | #380 (expand) |
| 2 | Course list (teaching) screen | 1d | NEW |
| 3 | Student list per course | 1d | NEW |
| 4 | Assignment list + details | 1d | NEW |
| 5 | Quick grade viewer | 1d | NEW |
| 6 | Invite management screen | 0.5d | NEW |
| 7 | Google Classroom status view | 0.5d | NEW |
| 8 | Teacher navigation restructure | 1d | NEW |

**Subtotal: ~7.5 days**

### Phase 2E: Store Submission + Offline (June 2026)

| # | Task | Est. | Issues |
|---|------|------|--------|
| 1 | React Query offline caching | 1d | #378 |
| 2 | Beta testing (TestFlight) | 1d | #342 |
| 3 | Beta testing (Google Play Internal) | 1d | #343 |
| 4 | App Store submission | 2d | #344 |
| 5 | Google Play submission | 2d | #345 |
| 6 | Device testing (full matrix) | 1d | #375 |
| 7 | OTA update mechanism (expo-updates) | 0.5d | NEW |

**Subtotal: ~8.5 days**

---

## 5. Architecture: Role-Based Navigation

```
  RootStackNavigator
  ├── AuthStack (not authenticated)
  │   └── LoginScreen
  │
  └── RoleRouter (authenticated — switches on user.role)
      │
      ├── ParentTabNavigator ──────────────────────────────
      │   ├── Home (Stack)
      │   │   ├── Dashboard
      │   │   ├── ChildOverview
      │   │   ├── DailyBriefing
      │   │   └── GradeTrends
      │   ├── My Kids (Stack)
      │   │   ├── MyKids
      │   │   ├── ChildOverview
      │   │   ├── Courses
      │   │   ├── ClassMaterials
      │   │   ├── StudyGuideViewer
      │   │   ├── FlashcardViewer
      │   │   ├── QuizHistory
      │   │   └── AddChild (Modal)
      │   ├── Tasks (Stack)
      │   ├── Messages (Stack)
      │   │   ├── ConversationsList
      │   │   └── Chat
      │   └── Help (Stack)
      │
      ├── StudentTabNavigator ─────────────────────────────
      │   ├── Home (Stack)
      │   │   ├── Dashboard
      │   │   ├── XP & Badges
      │   │   └── StudyRequests
      │   ├── Courses (Stack)
      │   │   ├── CourseList
      │   │   ├── CourseDetail
      │   │   ├── AssignmentDetail
      │   │   ├── StudyGuideViewer
      │   │   └── FlashcardViewer
      │   ├── Study (Stack)
      │   │   ├── QuizTaking
      │   │   ├── FlashcardStudy
      │   │   └── GradeSummary
      │   ├── Messages (Stack)
      │   └── Profile (Stack)
      │
      └── TeacherTabNavigator ─────────────────────────────
          ├── Home (Stack)
          │   ├── Dashboard
          │   └── InviteManagement
          ├── Classes (Stack)
          │   ├── CourseList
          │   ├── StudentList
          │   ├── AssignmentList
          │   └── GradeViewer
          ├── Messages (Stack)
          └── Profile (Stack)
```

---

## 6. Design System Alignment

### 6.1 Mobile Theme Expansion Required

The mobile theme must be expanded to match the web's full design token set:

```typescript
// NEW tokens needed in ClassBridgeMobile/src/theme/index.ts

// Semantic colors (missing)
danger: '#d64545',
dangerLight: 'rgba(214, 69, 69, 0.1)',
success: '#2e7d32',
successLight: 'rgba(46, 125, 50, 0.12)',
successBg: '#e8f5e9',
info: '#1565c0',
infoBg: '#e3f2fd',
warningBg: '#fff3e0',

// Priority colors (missing)
priorityHigh: '#ef5350',
priorityHighLight: 'rgba(239, 83, 80, 0.12)',
priorityMedium: '#ff9800',
priorityMediumLight: 'rgba(255, 152, 0, 0.12)',
priorityLow: '#66bb6a',
priorityLowLight: 'rgba(102, 187, 106, 0.12)',

// Role badge colors (missing)
roleParent: '#b1571e',
roleTeacher: '#2e7d32',
roleAdmin: '#a85f13',

// Purple accent (missing — needed for quiz/study screens)
purple: '#7c3aed',
purpleStrong: '#6d28d9',
purpleLight: '#f5f3ff',
purpleBg: '#ede9fe',

// Content badge colors (missing)
badgeSyllabus: '#9c27b0',
badgeLabs: '#f57c00',
badgeReadings: '#1976d2',
badgeResources: '#388e3c',
badgeAssignments: '#d32f2f',

// Overlay
overlay: 'rgba(0, 0, 0, 0.5)',
overlayLight: 'rgba(0, 0, 0, 0.3)',
```

### 6.2 Font Installation

Install `expo-font` and load:
- **Space Grotesk** (display/headers): weights 500, 600, 700
- **Source Sans 3** (body): weights 400, 500, 600, 700

### 6.3 App Icon & Splash Branding

Replace Expo defaults:
- `icon.png` → ClassBridge logo on white, 1024x1024
- `adaptive-icon.png` → ClassBridge logo for Android adaptive icon (foreground layer)
- `splash-icon.png` → ClassBridge full logo, centered on #eef1f5 background

Source assets available at `C:\Users\tgnan\OneDrive\Theepan\Business\EMAI\LOGO\Selected\`

---

## 7. NOT in Scope (Explicit Deferrals)

| Feature | Reason |
|---------|--------|
| Admin mobile screens | Low frequency, 1-3 users, keyboard-heavy |
| Study guide generation | File upload heavy, streaming UX, desktop workflow |
| Google Classroom OAuth setup | Complex redirect flow, one-time setup |
| Course/assignment creation | Form-heavy, teacher desktop workflow |
| Teacher email monitoring setup | Gmail OAuth, power-user feature |
| Data export (GDPR) | One-time operation, large file download |
| Print/PDF export | Niche mobile use case, unreliable |
| Registration/onboarding | One-time event, link to web |
| Account deletion | One-time, can deep-link to web |
| Wallet management (purchase) | Stripe checkout requires web |
| ICS calendar import | Setup-once operation |
| Full offline sync | P3+, React Query cache is sufficient |
| Shared study materials management | Low-frequency, complex permissions |
| Knowledge graph | Phase 3 web feature, not ready |
| MCP protocol integration | Phase 2 web feature, API-only |

---

## 8. What Already Exists (Reusable)

| Component | Location | Reusable For |
|-----------|----------|-------------|
| API client with JWT refresh | `ClassBridgeMobile/src/api/client.ts` | All new screens |
| Auth context | `ClassBridgeMobile/src/context/AuthContext.tsx` | All roles (needs role routing) |
| Theme system | `ClassBridgeMobile/src/theme/index.ts` | Expand, don't replace |
| Navigation framework | `ClassBridgeMobile/src/navigation/AppNavigator.tsx` | Restructure for multi-role |
| LoadingSpinner, EmptyState | `ClassBridgeMobile/src/components/` | All screens |
| ChildCard | `ClassBridgeMobile/src/components/ChildCard.tsx` | Parent screens |
| HeaderIcons | `ClassBridgeMobile/src/components/HeaderIcons.tsx` | All roles |
| Messages screens | `ClassBridgeMobile/src/screens/messages/` | Shared across roles |
| Notifications screen | `ClassBridgeMobile/src/screens/notifications/` | Shared across roles |
| Profile screen | `ClassBridgeMobile/src/screens/profile/` | Shared (add role display) |
| Help screen | `ClassBridgeMobile/src/screens/parent/HelpScreen.tsx` | Shared across roles |
| Test infrastructure | `ClassBridgeMobile/__tests__/` | All new screen tests |
| Web API types | `frontend/src/api/*.ts` | Reference for mobile API types |

---

## 9. Dream State Delta

```
  CURRENT STATE                  THIS PLAN                    12-MONTH IDEAL
  ──────────────────────────────────────────────────────────────────────────
  Parent-only MVP         →→→    Full 3-role mobile app  →→→  Native-quality
  14 screens                     ~40 screens                  experience with
  Read-heavy                     Read + key writes            offline-first,
  No push notifications          Full push + deep links       push, biometric,
  Expo Go only                   App Store + Play Store       and AI assistant
  Generic Expo branding          Full ClassBridge brand       on every screen
  No student/teacher             Student + teacher views
  No offline                     Query cache offline
```

**This plan gets us ~70% to the 12-month ideal.** Remaining 30% is offline-first sync, biometric auth, in-app AI assistant, and advanced gamification (leaderboards, challenges).

---

*Last updated: 2026-03-25 — Mobile Completion Plan (EXPANSION mode)*
