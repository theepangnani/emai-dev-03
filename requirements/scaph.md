## 14. Student Career & Academic Planning Hub (SCAPH)

**PRD:** CB-SCAPH-001 v3.0 | **Phase:** 3 | **Epic:** #2496
**Target:** April-September 2026 | **AI Engine:** Claude API (claude-sonnet-4)
**Source Document:** `ClassBridge_SCAPH_PRD_v3.docx`

---

### 14.1 Overview

SCAPH is ClassBridge's career planning module, empowering parents and students to explore career pathways, track interests, build resumes, and plan academic futures collaboratively. It extends the existing My Kids page with a Career Profile tab and adds Claude API as a second AI engine alongside OpenAI.

### 14.2 Architecture Decisions

| Decision | Detail |
|----------|--------|
| **Dual AI Engine** | OpenAI (study tools) + Claude API (career features) |
| **Student-Account-Optional** | All features work for name-only children |
| **Extends /my-kids** | Career Profile tab, not a new top-level page |
| **DB Migrations** | Startup ALTER TABLE (no Alembic), consistent with platform |
| **API Namespace** | `/api/v1/students/{id}/...` for all SCAPH endpoints |
| **Mobile Boundary** | Read-heavy features on mobile; complex workflows web-only |

### 14.3 Phase Plan

| Phase | Name | Duration | Features | Issues |
|-------|------|----------|----------|--------|
| **3A** | Career Foundation | 6 weeks (Apr-May) | F-01, F-07, F-08, F-18, F-19 + DB schema + Claude API | #2516-#2519, #2497-#2501 |
| **3B** | Collaboration & AI | 6 weeks (Jun-Jul) | F-02, F-09, F-10, F-13, F-16, F-17 | #2502-#2507 |
| **3C** | Advanced Tools | 6 weeks (Jul-Sep) | F-03-F-06, F-11, F-12, F-14, F-15 | #2508-#2515 |

### 14.4 Feature Modules

| # | Feature | Phase | GitHub Issue | Status |
|---|---------|-------|-------------|--------|
| F-01 | Academic History & Future Course Planner | 3A | #2498 | Not Started |
| F-02 | AI Career Pathway Recommender (Enhanced) | 3B | #2503 | Not Started |
| F-03 | Extracurricular Activity Recommender | 3C | #2508 | Not Started |
| F-04 | Opportunity Discovery (Try-Before-You-Commit) | 3C | #2509 | Not Started |
| F-05 | Certifications & Volunteer Hours Tracker | 3C | #2510 | Not Started |
| F-06 | AI-Generated Living Resume (Enhanced) | 3C | #2511 | Not Started |
| F-07 | Holistic Student Profile & Readiness Score | 3A | #2500 | Not Started |
| F-08 | Student Interest & Aspiration Discovery | 3A | #2499 | Not Started |
| F-09 | Collaborative Parent-Child Goal Setting | 3B | #2502 | Not Started |
| F-10 | Dream Evolution Timeline | 3B | #2504 | Not Started |
| F-11 | What-If Career Explorer | 3C | #2512 | Not Started |
| F-12 | Annual Review & Goal Reset Session | 3C | #2513 | Not Started |
| F-13 | Soft Skills & Character Profile | 3B | #2505 | Not Started |
| F-14 | Financial Pathway Awareness | 3C | #2514 | Not Started |
| F-15 | Parent Mentor Journal | 3C | #2515 | Not Started |
| F-16 | Career Milestone Calendar Layer | 3B | #2506 | Not Started |
| F-17 | Teacher Character Observation Request | 3B | #2507 | Not Started |
| F-18 | AI Credit Quota Classification | 3A | #2497 | Not Started |
| F-19 | Pivot Moment Celebration | 3A | #2501 | Not Started |

### 14.5 Foundation Issues

| Issue | Description | Phase |
|-------|-------------|-------|
| #2516 | DB Schema Migration (all SCAPH tables) | 3A — M1 |
| #2517 | Career Profile Tab (My Kids page extension) | 3A — M2 |
| #2518 | Claude API Integration Service | 3A — M1 |
| #2519 | Design System Compliance Audit | 3A — close |

### 14.6 Design Principles

1. **Progressive disclosure** — 3 summary cards at top, details on tap
2. **Warm & collaborative UX** — Wishlist feels conversational (iMessage-inspired), not transactional
3. **Quick capture** — Curiosity log is emoji + one sentence, not a form
4. **No negative language** — Pivots are celebrated, never "abandoned" (F-19)
5. **Mobile: read-heavy** — Complex workflows (RIASEC, What-If, Annual Review) are web-only
6. **Duolingo-inspired assessment** — RIASEC broken into 6 mini-sessions, progress bars, celebrations
7. **Spotify Wrapped-inspired timeline** — Year-in-Review as animated experience, PDF as takeaway

### 14.7 Privacy & Access Control

| Data | Parent | Student | Teacher | Notes |
|------|--------|---------|---------|-------|
| Course History | R/W | R | R (consent) | GC pre-populates |
| Career Pathways | R/W | R + react | R (consent) | Exploring hides gap warnings |
| Wishlist | R/W | R/W (acct) | No | Name-only = parent-only |
| Curiosity Log | R/W | R/W (Gr.7+) | No | Parent vs student distinguished |
| RIASEC Assessment | R | Write | No | Parent proxy for name-only |
| Dream Timeline | R/W annot. | R | No | Parent adds annotations |
| Letter to Future Self | No | Write | No | Encrypted; parent cannot read |
| Character Profile | R/W | R | R/W (consent) | Teacher entries need consent |
| Financial Outlook | R | R (Gr.9+) | No | Age-gated |
| Mentor Journal | R/W | No | No | Fully private; AI digest opt-in |
| AI Resume | R/W | R | No | Parent controls sections |
| Career Milestones | R/W | R | No | On shared calendar |

### 14.8 AI Credit Quota (Claude API)

| Feature | Free | Plus | Unlimited |
|---------|------|------|-----------|
| Career pathway generation | 2/mo | 10/mo | Unlimited |
| Goal drift alert | Included | Included | Included |
| Bridge career discovery | 1/mo | 5/mo | Unlimited |
| Interest cluster report | 1/qtr | 1/mo | Unlimited |
| What-If preview | 3/mo | 15/mo | Unlimited |
| Career conversation starters | Included | Included | Included |
| Resume generation | 1/mo | On update | On update |
| Personal statement | 1/mo | 3/mo | Unlimited |
| Character narrative | 1/qtr | 1/mo | Unlimited |
| Parent journal digest | Plus+ only | 1/qtr | Monthly |
| Scholarship matching | Top 5 | Top 10 | Top 20 + alerts |

### 14.9 Open Questions

| # | Question | Priority | Recommendation |
|---|----------|----------|----------------|
| 1 | Validate RIASEC instrument with psychologist? | P0 | Yes — U of T Career Centre or Ontario School Counsellors' Association |
| 2 | Require min data before pathway generation? | P0 | Yes — at least 1 curiosity log entry or parent-proxy RIASEC |
| 3 | Claude API cost ceiling per user/month? | P0 | Set monthly budget cap; Claude Sonnet ~$3/M input tokens |
| 4 | Career milestone calendar default on/off? | P1 | Default ON with toggle to hide |
| 5 | Letter encryption: GCS key or separate? | P0 | Separate key per letter |
| 6 | Financial data: build vs partner? | P1 | Hardcoded JSON MVP → ontario.ca API partnership later |
| 7 | Teachers see Readiness Score? | P0 | No — Character Profile only (with consent) |
| 8 | Multi-child comparison? | P2 | Deferred to v3.1 |
| 9 | French language support? | P1 | Architecture must support; content deferred to v3.1 |
