# ClassBridge — Project Status Report

**Date:** 2026-04-08
**Author:** Theepan Gnanasabapathy
**Version:** 1.2
**Status:** Active Development
**Report Period:** March 29 – April 8, 2026

---

## 1. Executive Summary

ClassBridge (EMAI) is an AI-powered education platform connecting parents, students, teachers, and administrators. The platform has been live at **classbridge.ca** since the March 6, 2026 soft launch. The full launch is targeted for **April 14, 2026**. The mobile MVP (Expo SDK 54) is complete. Development continues on Phase 2 WOW features, VASP/DTAP compliance for Ontario school board approval, and platform hardening.

This period's focus was on **codebase security & quality hardening** (22 issues resolved), **progressive study guide generation refinements** (Ask a Question, streaming sub-guides, suggestion chips), **study guide UX enhancements** (TOC, collapsible sections, inline resource links), **Parent Email Digest M1** (Gmail OAuth + setup wizard), **CI/CD optimization** for GitHub Actions free tier, and **activity feed fixes**. The platform remains stable with production deployed continuously.

---

## 2. Project Health Dashboard

| Area | Status | Notes |
|------|--------|-------|
| **Overall** | Green | On track for April 14 launch |
| **Backend** | Green | 63 route modules, 500+ endpoints, all tests passing |
| **Frontend** | Green | 100+ pages, 140+ components, build clean |
| **Mobile** | Green | MVP complete (Expo SDK 54), 8 screens |
| **Testing** | Green | 1,004+ backend tests, 258+ frontend tests, 14 integration tests added |
| **Documentation** | Green | All docs updated April 8, 2026 |
| **Security** | Green | Full codebase security review deployed (22 issues, PR #2816) |
| **CI/CD** | Green | GitHub Actions optimized for free tier (PR #2847) |
| **VASP/DTAP Compliance** | Amber | 29 issues tracked, in progress |
| **Performance** | Green | N+1 queries fixed, DB connection pool tuned, activity feed optimized |

---

## 3. Codebase Metrics

### 3.1 Backend

| Metric | Count |
|--------|-------|
| Route Modules | 63 |
| API Endpoints | 500+ |
| SQLAlchemy Models | 47 |
| Pydantic Schemas | 50+ |
| Service Modules | 54+ |
| Background Jobs | 12 (APScheduler) |
| Test Files | 100+ |

### 3.2 Frontend

| Metric | Count |
|--------|-------|
| Page Components | 100+ |
| Reusable Components | 140+ |
| API Client Modules | 47+ |
| Custom Hooks | 11 |
| Context Providers | 3 |
| CSS Files with Responsive Breakpoints | 75 |

### 3.3 Infrastructure

| Component | Technology |
|-----------|-----------|
| Backend Framework | FastAPI (Python 3.13+) |
| Frontend Framework | React 19, TypeScript, Vite |
| Database (Dev) | SQLite |
| Database (Prod) | PostgreSQL (Cloud SQL) |
| Hosting | GCP Cloud Run |
| Email | SendGrid |
| AI (Study) | OpenAI (gpt-4o-mini) |
| AI (Career) | Claude API (claude-sonnet-4) — Phase 3 SCAPH |
| Mobile | Expo SDK 54, React Native 0.81.5 |

---

## 4. GitHub Issue Tracker Summary

| Metric | Count |
|--------|-------|
| **Total Issues Created** | 2,937+ |
| **Open Issues** | ~30 |
| **Closed Issues** | ~2,907 |
| **Close Rate** | 99.0% |

### Issue Categories (Open)

| Category | Count | Priority |
|----------|-------|----------|
| Production Bugs (credit leakage, 422, logging) | 5 | Critical |
| CB-PEDI-001 Email Digest M2 | 7 | High |
| SCAPH Phase 3 (career planning) | 18 | Medium |
| Code Quality / Refactoring | 8 | Low |
| Accessibility / Mobile | 6 | Medium |
| Remaining Enhancements | ~15 | Varies |

---

## 5. Features Completed This Period

### 5.1 Codebase Security & Quality Hardening (PR #2816, deployed April 1)
Full codebase review resolving 22 issues:
- **Security (12 issues):** OAuth token encryption (Fernet), refresh token blacklisting, password reset single-use (JTI), user enumeration prevention, rate limit gaps, configurable security params, email verify TTL reduction
- **Correctness (4 issues):** Parent course visibility fix, safe JSON.parse on Quiz/Flashcards, AnalyticsPage stale closures, frontend token/NaN handling
- **Performance (2 issues):** Pagination on courses/broadcast/search, N+1 in message fan-out
- **DB Consistency (4 issues):** Enum→String migration (4 columns), model consistency (DateTime TZ, FK indexes, cascades), boolean defaults standardized
- **Integration tests:** 14 new tests for auth flows, course visibility, parent-child linking (#2805)

### 5.2 Progressive Study Guide Generation Refinements (March 29 – April 5)
- Concise overview prompt — rewrote strategy templates for 3-5 sentence summary + suggestion chips
- Suggestion chips create proper sub-guides with streaming (navigate-then-stream pattern)
- Full Study Guide chip uses 4000 tokens for detailed content
- Ask Bot chip directly opens chatbot
- Toast feedback for chatbot save actions
- Streaming endpoint parent_guide_id support for sub-guide hierarchy
- Auto-scroll to content on chip click

### 5.3 Ask a Question Feature (§6.128, #2861)
- Parent types free-form education question → streaming full study guide generated
- New `parent_question` document_type in strategy pattern
- Ontario curriculum awareness (OSSLT, EQAO, grade-level expectations)
- 4000 max_tokens, safety guardrails, AI cost ~$0.02-0.04/question
- Multiple streaming/navigation fixes (#2880-#2893)

### 5.4 Study Guide Enhancements (PR #2906, April 6-8)
- **Section Navigation (§6.129):** Auto-generated TOC from markdown headings, collapsible sections, smooth scroll, localStorage persistence
- **Inline Resource Links (§6.130):** ResourceLinksSection component with YouTube embeds, topic grouping on study guide pages
- **Continue Streaming Fix (#2896):** Fixed spinner-only bug, actual streaming content now displays
- **Sub-guides only:** TOC/collapsible only render on sub-guide pages, not overviews (PR #2915)

### 5.5 Parent Email Digest M1 (§6.127, CB-PEDI-001, PR #2780)
- ParentGmailIntegration database models (3 new tables)
- Gmail OAuth flow for parent personal accounts
- CRUD API routes for integrations, settings, pause/resume
- PARENT_EMAIL_DIGEST notification type (backend + frontend)
- 4-step email digest setup wizard on My Kids page

### 5.6 CI/CD Optimization (PR #2847)
- GitHub Actions optimized for free tier: path filters, concurrency groups, job consolidation
- Security scanning moved to daily schedule (off PR triggers)
- Debounce to reduce wasted minutes from rapid pushes

### 5.7 Activity Feed Fixes (PR #2916)
- Child filter fix — activity feed showed wrong child's tasks
- Cache invalidation after upload/study guide generation
- N+1 query fix in message sender lookup
- Regression test added

### 5.8 Batch Bug Fixes (March 29-31)
- Study tools grouped into dropdown to prevent tab overflow
- YouTube URL validation, created time, image fallback fixes
- Accessibility and dark mode improvements
- Duplicate sub-guide prevention + chip navigation reliability
- Student course visibility fix (only own/enrolled courses)
- DB connection pool reduced to prevent PostgreSQL slot exhaustion

### 5.9 Accessibility & Design System (PR #2780)
- Navigation ARIA patterns, missing labels, heading hierarchy
- Focus-visible states on buttons
- Hardcoded colors → CSS variables, spacing tokens, border-radius standardization
- Font type scale (rem)

### 5.10 September 2026 Retention Bundle — All 5 Batches Complete (March 12-22)
Entire retention bundle delivered 5 months ahead of schedule:
- **Batch 0:** Schema foundation — is_master migration, source_type column, holiday_dates table (#2025, #2010, #2024)
- **Batch 1:** XP core engine — XP model, earning service, streak engine, API routes (#2000-#2003)
- **Batch 2:** XP dashboard & visibility — streak counter, level bar, badges shelf, XP history page, parent visibility, digest crons (#2006-#2008, #2022-#2023)
- **Batch 3:** Badges & brownie points — badge trigger service, brownie points, anti-gaming rules (#2004, #2005, #2009)
- **Batch 4:** Assessment countdown, On Track signal, parent study request, multilingual summaries, Pomodoro, study timeline, end-of-term report card (#2011-#2021)

### 5.11 Study Guide Strategy Pattern (March 12-14, §6.106)
- Document type auto-detection classifier service
- Study guide prompt strategy service (exam_prep, homework, lecture_notes, etc.)
- Ontario curriculum mapping service
- Parent summary generation service
- DocumentTypeSelector and StudyGoalSelector components
- Frontend and backend tests

### 5.12 Material Hierarchy & Multi-Document Management (March 10-15, §6.98-§6.100)
- Material hierarchy fields on CourseContent (parent/child relationships)
- Linked materials panel, text selection context menu
- Multi-document management — add files, reorder, delete sub-materials (#993)
- Sub-study guide generation from text selection (#1594)
- Study guide tree API and breadcrumb navigation

### 5.13 Performance Optimization (March 9, §6.104)
- Comprehensive performance optimization across 14 issues (#1954-#1967)

### 5.14 Digital Wallet & Credit System (March 10-12, §6.60)
- Wallet models, schemas, service layer, API routes with Stripe checkout
- CreditTopUpModal with Stripe Elements
- Monthly credit refresh job, credit bridge into AI usage
- WalletPage, PackageSelector, TransactionHistory components

### 5.15 Chatbot Enhancements (March 9-22)
- Hybrid keyword + embedding intent classifier (#1711)
- Global search integration into help chatbot (#1630)
- Chatbot batch 4: streaming SSE, result limits, chat commands
- Study Q&A chatbot — context-aware Q&A on study guide pages (§6.114)
- Chatbot search parity: assignments, children entities

### 5.16 School Report Card System (March 23-26, §6.121)
- Complete system: upload, OCR extraction, AI analysis, routing, components, tests
- Career path analysis, report date extraction, concurrent loading states

### 5.17 Document Privacy & IP Protection (March 23, §6.119)
- Trust-circle access control for materials
- Material access audit logging
- Frontend privacy indicators and access log tab

### 5.18 Course Material Metadata & Popovers (March 25, §6.123)
- Clickable metadata popovers in all course material tabs

### 5.19 Pre-Launch Survey System (March 11-15, §6.102)
- Survey models, public API, admin analytics with Recharts
- Role-specific question sets, emoji likert scale
- Bot protection on all public forms
- Admin notification on survey completion

### 5.20 Streaming Study Guide Generation (March 9-10, §6.115)
- SSE streaming endpoint for study guide generation
- Anthropic streaming API integration
- useStudyGuideStream hook and SSE parser
- StreamingMarkdown renderer component

### 5.21 Other Notable Features (March 9-28)
- User journey guide + proactive journey hints (§6.125, §6.126)
- Video links enhancement — AI suggestions, YouTube live search (§6.57.2, §6.57.3)
- Bug report with screenshot + GitHub issue creation
- PWA offline mode — install as app + offline study access
- Google Calendar ICS import for assignment dates (§6.78)
- Show/hide password toggle
- CASL-compliant email opt-in and one-click unsubscribe
- Collapsible document text container
- Mobile responsiveness for 55+ CSS files
- GCS file storage migration complete (file_data/image_data columns dropped)
- Simplified upload & progressive generation Phase 1 (#2705) and Phase 2 (#2696)
- Weekly family report card email
- CSV template import
- Various batch defect fixes across 40+ issues

---

## 6. Features In Progress

| Feature | Epic/Issue | Status | Target |
|---------|-----------|--------|--------|
| Production Bugs (credit leakage, 422, logging) | #2921-#2935 | **In Progress** | **Immediate** |
| Parent Email Digest M2 (Core Engine) | #2648-#2653 | Planned | May 2026 |
| Gmail OAuth Verification (CASA Tier 2) | #2800 | Planned | Jul-Sep 2026 |
| **SCAPH Phase 3A — Career Foundation** | **#2496** | **Planned** | **Apr-May 2026** |
| **SCAPH Phase 3B — Collaboration & AI** | **#2496** | **Planned** | **Jun-Jul 2026** |
| **SCAPH Phase 3C — Advanced Tools** | **#2496** | **Planned** | **Jul-Sep 2026** |
| Cloud Storage Integration | #1865-#1877 | Planned | Q2 2026 |
| LMS Abstraction / D2L | 5 issues | Planned | Q3 2026 |

---

## 7. Deployment Status

| Item | Details |
|------|---------|
| **Production URL** | https://www.classbridge.ca |
| **Platform** | GCP Cloud Run (auto-deploy on merge to master) |
| **GCP Project** | emai-dev-01 |
| **Database** | PostgreSQL via Cloud SQL |
| **File Storage** | Google Cloud Storage (GCS) |
| **Email Provider** | SendGrid (production), Gmail SMTP (fallback) |
| **Domain** | classbridge.ca |
| **SSL** | Active (managed by GCP) |
| **Uptime Target** | 99.9% |
| **Incidents This Period** | 0 |

---

## 8. Testing Status

### 8.1 Backend Tests

| Category | Approximate Count |
|----------|------------------|
| Authentication | 50+ |
| Courses & Assignments | 40+ |
| Study Tools (guides, quiz, flashcards) | 80+ |
| Messaging & Notifications | 60+ |
| Parent Features | 50+ |
| Admin & Audit | 40+ |
| Gamification (XP, Wallet, Badges) | 50+ |
| AI Services | 40+ |
| File Processing | 30+ |
| Security & Protection | 30+ |
| Integration (Google Classroom) | 40+ |
| Data Integrity | 30+ |
| **Total Backend** | **1,004+** |

### 8.2 Frontend Tests

| Category | Approximate Count |
|----------|------------------|
| Component Tests | 150+ |
| Route/Page Tests | 60+ |
| Hook Tests | 20+ |
| Integration Tests | 28+ |
| **Total Frontend** | **258+** |

---

## 9. Key Risks & Blockers

| Risk | Probability | Impact | Status | Mitigation |
|------|------------|--------|--------|------------|
| VASP/DTAP compliance delays | Medium | High | Active | 29 issues tracked; PIA, MFA, SSO, data residency planned |
| Google API rate limits | Medium | High | Mitigated | Caching, batch requests, exponential backoff implemented |
| OpenAI API costs at scale | High | Medium | Mitigated | BYOK planned, study guide reuse, credit wallet system |
| Mobile responsive CSS gaps | Medium | Medium | In Progress | 75/130 CSS files have breakpoints; high-priority pages identified |
| User adoption pre-launch | Medium | High | Active | Survey system live, waitlist flow, pilot with target families |
| Data privacy compliance | Medium | High | Active | GDPR data export/deletion implemented; MFIPPA/PIPEDA in progress |

---

## 10. Upcoming Milestones

| Milestone | Target Date | Status |
|-----------|------------|--------|
| Full Launch | April 14, 2026 | On Track |
| Mobile Responsive Completion (high-priority pages) | April 2026 | In Progress |
| VASP/DTAP Phase 1 (MFA, data residency) | Q2 2026 | Planned |
| AI Cost Tracking & Premium Tiers | Q2 2026 | Planned |
| **SCAPH Phase 3A — Career Foundation** | **Apr-May 2026** | **Planned** |
| **SCAPH Phase 3B — Collaboration & AI** | **Jun-Jul 2026** | **Planned** |
| **SCAPH Phase 3C — Advanced Tools** | **Jul-Sep 2026** | **Planned** |
| D2L Brightspace Integration | Q3 2026 | Planned |
| Phase 4 (Tutor Marketplace) | 2027 | Planned |

---

## 11. Team & Stakeholders

| Role | Person |
|------|--------|
| Founder / Developer | Theepan Gnanasabapathy |
| Product Owner | Sarah |
| Platform | ClassBridge (EMAI) |
| Repository | emai-dev-03 |
| Phase 2 Repository | class-bridge-phase-2 |

---

*Report generated April 8, 2026. Next report due April 14, 2026 (full launch).*
