# ClassBridge — Project Plan

**Date:** 2026-03-28
**Author:** Theepan Gnanasabapathy
**Version:** 1.1
**Product Name:** ClassBridge (EMAI)

---

## 1. Project Overview

ClassBridge is a unified, AI-powered education management platform that connects parents, students, teachers, and administrators in one role-based application. It integrates with Google Classroom, provides AI-driven study tools (study guides, quizzes, flashcards, mind maps), simplifies parent-teacher communication, and enables parents to actively support their children's education.

The platform is designed as a **parent-first** system, meaning parents can manage their children's education independently without requiring school board integration or Google Classroom access.

**Live URL:** https://www.classbridge.ca
**Repository:** emai-dev-03
**Phase 2 Repository:** class-bridge-phase-2

---

## 2. Vision & Objectives

### Vision
To become the trusted digital bridge between families and schools, empowering every student to succeed with the right support at the right time.

### Mission
ClassBridge empowers parents to actively participate in their children's education by providing intelligent tools, clear insights, and affordable access to trusted educators — all in one connected platform.

### Business Goals

| Goal | Target |
|------|--------|
| Scalable SaaS on GCP | 100k+ users, 99.9% uptime |
| Ontario School Board Partnerships | TDSB, PDSB, YRDSB, HDSB, OCDSB |
| Recurring Revenue | Subscriptions + marketplace services |
| VASP/DTAP Compliance | Ontario school board procurement approval |

---

## 3. Timeline & Milestones

### 3.1 Completed Milestones

| Milestone | Target Date | Actual Date | Status |
|-----------|------------|-------------|--------|
| MVP Backend + Frontend | Q4 2025 | February 2026 | Complete |
| Soft Launch | March 6, 2026 | March 6, 2026 | Complete |
| Mobile MVP (Expo SDK 54) | March 2026 | March 2026 | Complete |
| Pre-Launch Survey System | March 2026 | March 2026 | Complete |
| Digital Wallet & Credit System | March 2026 | March 2026 | Complete |
| XP / Gamification System | March 2026 | March 2026 | Complete |
| Help Knowledge Base + AI Chatbot | March 2026 | March 2026 | Complete |
| Bot Protection (all public forms) | March 2026 | March 2026 | Complete |
| Performance Optimization (14 issues) | March 2026 | March 2026 | Complete |
| CSV Import System | March 2026 | March 27, 2026 | Complete |
| Teacher Thanks / Appreciation | March 2026 | March 27, 2026 | Complete |
| Weekly Family Report Card | March 2026 | March 27, 2026 | Complete |

### 3.2 Upcoming Milestones

| Milestone | Target Date | Status | Dependencies |
|-----------|------------|--------|-------------|
| Full Launch | April 14, 2026 | On Track | Responsive CSS, final QA |
| Mobile Responsive Completion | April 2026 | In Progress | ~55 CSS files need breakpoints |
| VASP/DTAP Phase 1 | Q2 2026 | Planned | MFA, data residency, PIA |
| AI Cost Tracking & Premium Tiers | Q2 2026 | Planned | Token tracking, admin dashboard |
| Cloud Storage Integration | Q2 2026 | Planned | Google Drive, OneDrive APIs |
| **SCAPH Phase 3A — Career Foundation** | **Apr-May 2026** | **Planned** | **Claude API, DB schema, Career Profile tab** |
| **SCAPH Phase 3B — Collaboration & AI** | **Jun-Jul 2026** | **Planned** | **Wishlist, AI pathways, character profile** |
| **SCAPH Phase 3C — Advanced Tools** | **Jul-Sep 2026** | **Planned** | **Resume, What-If, Annual Review** |
| D2L Brightspace Integration | Q3 2026 | Planned | LMS abstraction layer |
| Tutor Marketplace | 2027 | Planned | Payment integration |

---

## 4. Phase Breakdown

### 4.1 Phase 1 (MVP) — COMPLETE

**Launch Date:** March 6, 2026 (soft launch)

All core features implemented and deployed:

| Feature Area | Features | Status |
|-------------|----------|--------|
| **Authentication** | JWT, OAuth2, Google sign-in, password reset, email verification, invite system | Complete |
| **Google Classroom** | On-demand sync, assignments, student discovery, multi-account teachers, Gmail monitoring | Complete |
| **AI Study Tools** | Study guides, quizzes, flashcards, mind maps, content extraction (PDF/Word/PPTX/OCR) | Complete |
| **Task Manager** | CRUD, calendar (Month/Week/3-Day/Day), drag-and-drop, entity linking, reminders | Complete |
| **Communication** | Messaging, email notifications, teacher announcements, notification bell | Complete |
| **Parent Features** | Dashboard, child management, course management, teacher linking, AI tools suite | Complete |
| **Student Features** | Dashboard, study tools, XP/gamification, badges, streaks, daily quiz, study sessions | Complete |
| **Teacher Features** | Dashboard, course management, assignment CRUD, parent invites, email monitoring, thanks | Complete |
| **Admin Features** | User management, audit logs, broadcasts, FAQ management, inspiration messages, waitlist | Complete |
| **Security** | JWT refresh, CORS, RBAC, rate limiting, bot protection, security headers | Complete |
| **Analytics** | Grade tracking, trend charts, AI insights, quiz history, weekly reports | Complete |
| **Engagement** | XP/gamification, wallet/credits, daily quiz, streaks, badges, surveys | Complete |
| **Knowledge Base** | FAQ system, help articles, RAG-powered AI chatbot | Complete |
| **Data Privacy** | Account deletion, data export, audit logging, consent management | Complete |

### 4.2 Phase 1.5 (Calendar Extension, Mobile & School Integration)

| Feature | Status | Notes |
|---------|--------|-------|
| Mobile-responsive web | In Progress | 75/130 CSS files have breakpoints; ~55 files remaining (#1641) |
| Extend calendar to Student/Teacher | Complete | Implemented |
| Background Google Classroom sync | Complete | 15-minute periodic sync for teachers |
| Student email identity merging | Planned | Personal + school email |
| Google Calendar push integration | Planned | |
| Central document repository | Planned | |

### 4.3 Phase 2 (WOW Features — Parent Value & Engagement)

**Core Principle:** Parents First, Responsible AI — AI helps parents understand and engage; AI challenges students, never shortcuts their learning.

| Priority | Feature | Status | WOW Impact |
|----------|---------|--------|------------|
| 1 | Smart Daily Briefing (#1403) | Complete | Highest |
| 2 | Help My Kid — one-tap study generation (#1407) | Complete | Highest |
| 3 | Global Search + Smart Shortcuts (#1410) | Complete | Medium |
| 4 | Weekly Progress Pulse — email digest (#1413) | Complete | High |
| 5 | Parent-Child Study Link (#1414) | Complete | High |
| 6 | Dashboard Redesign — persona-based (#1415) | Complete | High |
| 7 | Responsible AI Parent Tools (#1421) | Complete | Highest |

### 4.4 Phase 2 (Intelligence & Data)

| Feature | Status | Notes |
|---------|--------|-------|
| Performance Analytics Dashboard | Complete | #469-#474 |
| Quiz Results History | Complete | #574, #621 |
| FAQ / Knowledge Base | Complete | #437-#444 |
| AI Usage Limits & Quota Management | Complete | #1121-#1130 |
| AI Token/Cost Tracking | Planned | #1650 — prompt_tokens, completion_tokens, estimated_cost_usd |
| AI Regeneration/Continuation Tracking | Planned | #1651 |
| Continuation as Premium Perk | Planned | #1645 — Free tier Upgrade CTA, Plus/Unlimited free continuation |
| Admin Cost-Summary Endpoint | Planned | #1650 |
| Mind Map Desktop Layout | Planned | #1653 — horizontal with center node |
| User-Provided AI API Key (BYOK) | Planned | #578 |
| User Cloud Storage Destination | Planned | §6.95, #1865-#1871 |
| Cloud File Import | Planned | §6.96, #1872-#1877 |
| Mobile App Pilot (8 screens) | Complete | March 2026 |

### 4.5 VASP/DTAP Compliance — Ontario School Board Approval

**29 issues tracked.** Required for school board procurement.

| Category | Requirements | Status |
|----------|-------------|--------|
| **Data Residency** | GCP Canada region, OpenAI data transfer agreements | Planned |
| **Privacy** | PIA, MFIPPA consent, PIPEDA compliance, cookie disclosure | Planned |
| **Security** | MFA/2FA, SSO/SAML, httpOnly cookies, WAF/DDoS, SAST/DAST | Planned |
| **Governance** | SOC 2 readiness, penetration testing, breach notification, DPA templates | Planned |
| **Accessibility** | WCAG 2.1 AA full remediation | In Progress |
| **Engagement** | K-12CVAT questionnaire completion, pilot partner school | Planned |

### 4.6 LMS Abstraction & D2L Brightspace Integration

**5 issues open.**

| Feature | Status |
|---------|--------|
| LMS adapter pattern with OneRoster canonical models | Complete |
| Google Classroom refactored into LMSProvider adapter | Complete |
| D2L Brightspace MVP (courses, assignments, grades sync) | Planned |

### 4.7 Phase 3 — Student Career & Academic Planning Hub (SCAPH)

**PRD:** CB-SCAPH-001 v3.0 | **Epic:** #2496 | **Target:** April–September 2026
**AI Engine:** Claude API (claude-sonnet-4) — second engine alongside OpenAI
**Full Specification:** [requirements/scaph.md](../requirements/scaph.md)

SCAPH empowers parents and students to explore career pathways, track interests, build resumes, and plan academic futures collaboratively. It extends the existing My Kids page with a Career Profile tab and adds Claude API as a second AI engine.

**Key Architecture Decisions:**
- Dual AI Engine: OpenAI (study tools) + Claude API (career features)
- Student-Account-Optional: all features work for name-only children
- Extends /my-kids: Career Profile tab, not a new top-level page
- API Namespace: `/api/v1/students/{id}/...`

#### Phase 3A — Career Foundation (April–May 2026)

| Feature | Issue | Description |
|---------|-------|-------------|
| DB Schema Migration | #2516 | 12 new tables + Task table extensions |
| Claude API Integration | #2518 | Second AI engine with zero-retention, PII anonymization |
| F-18: AI Credit Quota | #2497 | All SCAPH features classified into Free/Plus/Unlimited tiers |
| Career Profile Tab | #2517 | My Kids page extension with 3-card hub layout |
| F-01: Course Planner | #2498 | Academic history with Google Classroom auto-population |
| F-07: Readiness Score | #2500 | 5-dimension radial chart (nightly background job) |
| F-08: Interest Discovery | #2499 | RIASEC assessment + Curiosity Log + Career Cluster suggestions |
| F-19: Pivot Celebration | #2501 | Positive language enforcement on pathway changes |

#### Phase 3B — Collaboration & AI (June–July 2026)

| Feature | Issue | Description |
|---------|-------|-------------|
| F-09: Goal Setting | #2502 | Shared wishlist with proposal-and-reaction flow |
| F-10: Dream Timeline | #2504 | Visual career evolution timeline with Year-in-Review PDF |
| F-02: AI Pathways | #2503 | Claude-powered career recommendations, goal drift alerts |
| F-13: Character Profile | #2505 | Soft skills tracking with evidence entries |
| F-16: Career Calendar | #2506 | Career milestones on existing task calendar |
| F-17: Teacher Observations | #2507 | Structured character observation requests via messaging |

#### Phase 3C — Advanced Tools (July–September 2026)

| Feature | Issue | Description |
|---------|-------|-------------|
| F-03: Activity Recommender | #2508 | Pathway-aligned extracurricular activities |
| F-04: Opportunity Discovery | #2509 | Shadow days, interviews, Try-Before-You-Commit |
| F-05: Certifications Tracker | #2510 | Certifications + Ontario 40-hour volunteer tracking |
| F-06: Living Resume | #2511 | Claude-generated personal statement, PDF export |
| F-11: What-If Explorer | #2512 | Side-by-side career pathway comparison (web-only) |
| F-12: Annual Review | #2513 | 5-step wizard for yearly career review (web-only) |
| F-14: Financial Awareness | #2514 | Ontario salary averages, OSAP links, scholarship matching |
| F-15: Mentor Journal | #2515 | Encrypted parent journal with opt-in AI digest |
| Design System Audit | #2519 | WCAG 2.1 AA + design system compliance verification |

#### SCAPH Design Principles
1. **Progressive disclosure** — 3 summary cards at top, details on tap
2. **Warm & collaborative UX** — Wishlist feels conversational (iMessage-inspired)
3. **Quick capture** — Curiosity log is emoji + one sentence, not a form
4. **No negative language** — Pivots are celebrated, never "abandoned"
5. **Mobile: read-heavy** — Complex workflows (RIASEC, What-If, Annual Review) are web-only
6. **Duolingo-inspired assessment** — RIASEC in 6 mini-sessions with progress bars
7. **Spotify Wrapped-inspired timeline** — Year-in-Review as animated web experience

### 4.8 Phase 4 (Tutor Marketplace) — Planned 2027

- Private tutor profiles and search
- AI tutor matching
- Booking workflow
- Ratings & reviews
- Payment integration (Stripe)

### 4.9 Phase 5 (AI Email Agent) — Planned 2027+

- AI email sending on behalf of parents
- Reply ingestion and threading
- AI summaries of conversations
- Searchable email archive

---

## 5. Technical Architecture

### 5.1 Technology Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | FastAPI (Python 3.13+), SQLAlchemy 2.0, Pydantic 2.x |
| **Frontend** | React 19, TypeScript, Vite, React Router 7, TanStack React Query |
| **Database** | SQLite (dev), PostgreSQL (prod via Cloud SQL) |
| **AI (Study Tools)** | OpenAI API (gpt-4o-mini) |
| **AI (Career/SCAPH)** | Claude API (claude-sonnet-4) |
| **Authentication** | JWT (python-jose), OAuth2 Bearer, bcrypt |
| **Google APIs** | Classroom API, Gmail API, OAuth2 |
| **Email** | SendGrid (prod), Gmail SMTP (fallback) |
| **Scheduling** | APScheduler (12 background jobs) |
| **Deployment** | GCP Cloud Run (auto-deploy on merge to master) |
| **File Storage** | Google Cloud Storage (prod), local filesystem (dev) |
| **Mobile** | Expo SDK 54, React Native 0.81.5 |

### 5.2 Architecture Overview

```
Frontend (React 19 + Vite)
  ├── Pages (100+)
  ├── Components (140+)
  ├── API Clients (47+)
  ├── Hooks (11)
  └── Context Providers (3)

Backend (FastAPI)
  ├── Routes (63 modules, 500+ endpoints)
  ├── Models (47 SQLAlchemy)
  ├── Schemas (50+ Pydantic)
  ├── Services (54+)
  └── Jobs (12 APScheduler)

Infrastructure
  ├── GCP Cloud Run
  ├── Cloud SQL (PostgreSQL)
  ├── Google Cloud Storage
  ├── SendGrid
  ├── OpenAI API (study tools)
  └── Claude API (career planning — SCAPH)
```

---

## 6. Resource Plan

### 6.1 Team

| Role | Person | Allocation |
|------|--------|-----------|
| Founder / Lead Developer | Theepan Gnanasabapathy | Full-time |
| Product Owner | Sarah | Part-time |
| AI Development Assistant | Claude (Anthropic) | As needed |

### 6.2 Tools & Services

| Tool | Purpose | Cost |
|------|---------|------|
| GCP Cloud Run | Backend + Frontend hosting | Pay-per-use |
| Cloud SQL | PostgreSQL database | Monthly |
| Google Cloud Storage | File storage | Pay-per-use |
| SendGrid | Email delivery | Free tier + paid |
| OpenAI API | AI study tool generation (gpt-4o-mini) | ~$0.02/generation |
| Claude API | AI career planning (claude-sonnet-4) | ~$0.01-0.05/call |
| GitHub | Source control & issue tracking | Free |
| Expo | Mobile app builds | Free tier |

---

## 7. Risk Management

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Google API rate limits | Medium | High | Caching, batch requests, exponential backoff |
| User adoption challenges | Medium | High | UX focus, onboarding, pilot with families |
| OpenAI API costs at scale | High | Medium | BYOK feature, study guide reuse, credit wallet |
| Claude API costs (SCAPH) | Medium | Medium | Per-user monthly cap, tiered quota (F-18), zero-retention |
| VASP/DTAP compliance delays | High | High | 29 issues tracked; phased approach |
| Data privacy compliance | Medium | High | GDPR export/deletion implemented; MFIPPA in progress |
| SQLite to PostgreSQL issues | Medium | Medium | Cross-DB testing, migration scripts |
| Stale browser cache after deploy | Low | Low | Lazy chunk retry, cache-busting |

---

## 8. Success Metrics (KPIs)

| KPI | Measurement | Target |
|-----|-------------|--------|
| Parent Engagement Rate | % of parents logging in weekly | 60%+ |
| Student Grade Improvement | Average grade change after 1 semester | +5% |
| Daily Active Users | DAU across all roles | 500+ by Q3 2026 |
| Retention Rate (30-day) | Users returning after 30 days | 40%+ |
| Teacher Adoption Rate | % of invited teachers who accept | 50%+ |
| AI Tool Usage | Guides/quizzes/flashcards per user per week | 3+ |
| Message Response Time | Average parent-teacher reply time | < 24 hours |
| App Store Rating | Mobile app rating | 4.5+ stars |

---

## 9. Dependencies

### 9.1 External Services

| Dependency | Purpose | Risk Level |
|-----------|---------|-----------|
| Google Classroom API | Course/assignment sync | Medium (rate limits) |
| Gmail API | Teacher email monitoring | Low |
| OpenAI API | AI study tool generation | Medium (cost, availability) |
| Claude API | AI career planning (SCAPH) | Medium (cost, zero-retention required) |
| SendGrid | Email delivery | Low |
| GCP Cloud Run | Hosting | Low |
| Cloud SQL | Database | Low |
| Stripe | Payment processing (future) | Low |

### 9.2 Internal Dependencies

| Dependency | Blocks |
|-----------|--------|
| VASP/DTAP Compliance | School board partnerships |
| LMS Abstraction | D2L Brightspace integration |
| Payment Integration | Tutor marketplace |
| Mobile App v2 | Full mobile feature parity |

---

## 10. Budget Considerations

### 10.1 Current Monthly Costs (Estimated)

| Item | Estimated Cost |
|------|---------------|
| GCP Cloud Run | $50-100/month |
| Cloud SQL (PostgreSQL) | $30-50/month |
| Google Cloud Storage | $5-10/month |
| SendGrid | $0-20/month (free tier) |
| OpenAI API | $20-50/month (growing) |
| Claude API (SCAPH) | $10-30/month (estimated) |
| Domain (classbridge.ca) | $15/year |
| **Total** | **~$120-250/month** |

### 10.2 Scaling Projections

| Users | Estimated Monthly Cost |
|-------|----------------------|
| 100 (current) | $120-250 |
| 1,000 | $300-500 |
| 10,000 | $1,000-2,000 |
| 100,000 | $5,000-10,000 |

**Revenue Model:** Freemium (Free tier with limited AI credits) + Plus/Unlimited subscription tiers + future tutor marketplace commissions.

---

*Project plan last updated March 28, 2026. Next review: April 14, 2026 (full launch).*
