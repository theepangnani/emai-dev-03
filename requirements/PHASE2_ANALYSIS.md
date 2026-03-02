# Phase 2 Roadmap Analysis & Cherry-Pick Assessment

**Date:** March 1, 2026
**Deadline:** March 6, 2026 (Mobile Pilot Launch)
**Current branch:** `feature/phase-2` (22 commits, 91 files ahead of master)

---

## 1. What's on `feature/phase-2` (Not in Production)

| # | Feature | Commit | Files | Risk Level |
|---|---------|--------|-------|------------|
| 1 | Progressive account lockout (#796) | `5ca6e50` | 7 | HIGH — changes login flow, touches `auth.py` |
| 2 | httpOnly cookie auth (#788) | `fc8440e` | 5 | HIGH — changes auth mechanism, `auth.py` + `deps.py` + `client.ts` |
| 3 | Cookie consent & MFIPPA (#797, #783) | `28557e3` | 20 | HIGH — touches models, auth, App.tsx, ProtectedRoute |
| 4 | Deep linking & session persistence (#885, #886) | `16c8408` | 11 | MODERATE — touches 6+ existing pages/hooks |
| 5 | Bulk folder import wizard (#877, #883) | `c413f2d` | 10 | MODERATE — new components + modifies `CourseDetailPage` |
| 6 | AI task extraction (#878) | `efde2c2` | 11 | MODERATE — new service + modifies `CourseDetailPage` |
| 7 | Task templates & comments (#880, #881) | `c046f9c` | 12 | MODERATE — changes Task model, `main.py`, `tasks.py` |
| 8 | MCP foundation (#904, #905) | `bb412a2` | 6 | LOW — fully isolated new module |
| 9 | Student registration with username (#546) | `9bd7d8b` | 2 | LOW — frontend-only (Register.tsx, Auth.css) |
| 10 | Classroom type classification (#550) | `fd0914a` | 8 | LOW — self-contained, own migration |
| 11 | Notification ACK/suppress (#548) | `d71720a` | 5 | LOW — additive changes to existing notification system |
| 12 | Link request creation (#547) | `d763825` | 5 | LOW — additive to existing link_requests route |
| 13 | Student email identity (#941) | `b2dd8ae` | 10 | LOW — new model, own migration, new page |
| 14 | Gradient style overrides (#489) | `3cd6148` | 1 | NONE — single CSS file |

### Hotspot Files (touched by 3+ features)
- **`app/api/routes/auth.py`** — lockout + cookies + consent all modify this
- **`frontend/src/api/client.ts`** — 7 commits touch the Axios interceptor
- **`main.py`** — 4 commits add routers/startup logic
- **`app/models/user.py`** — lockout fields + consent fields

---

## 2. Cherry-Pick Candidates for Master (March 6 Safe)

### SAFE — Cherry-pick these now

These are isolated, additive features with no cross-cutting auth/model changes. They won't break the mobile app (which uses Bearer token auth on the same `/api/*` endpoints).

| Feature | Why Safe | Value for March 6 |
|---------|----------|-------------------|
| **Student registration with username (#546)** | Frontend-only, 2 files (Register.tsx + Auth.css) | Students can sign up without email — critical for pilot schools |
| **Gradient style overrides (#489)** | 1 CSS file, purely visual | Polish |
| **Notification ACK/suppress (#548)** | 5 files, additive to existing notifications | Parents can dismiss/mute noisy notifications |
| **Classroom type classification (#550)** | Self-contained with own migration, 8 files | Teachers see school vs private course labels |
| **Link request creation (#547)** | 5 files, additive to existing route | Students can initiate parent linking |
| **Student email identity (#941)** | New model/migration/page, fully isolated | Students can add school email to their account |

### MODERATE — Could cherry-pick with care

| Feature | Risk | Mitigation |
|---------|------|-----------|
| **MCP foundation (#904)** | Isolated new module, but adds to `main.py` and `requirements.txt` | Could work, but no user-facing value for March 6 — skip |
| **Deep linking (#885, #886)** | Touches 6+ existing pages | Nice for bookmarking, but not critical for pilot |

### DO NOT cherry-pick for March 6

| Feature | Why Not |
|---------|---------|
| **httpOnly cookies (#788)** | Changes auth mechanism. Mobile app uses Bearer tokens via AsyncStorage. While it has Bearer fallback, any auth change 5 days before pilot is reckless. |
| **Progressive account lockout (#796)** | Modifies login flow in `auth.py`. Could lock out pilot users if misconfigured. |
| **Cookie consent & MFIPPA (#797, #783)** | 20 files, touches auth, models, App.tsx, ProtectedRoute. Adds ConsentGateway that could block users. Too invasive. |
| **Bulk folder import (#877)** | Modifies `CourseDetailPage` and `client.ts`. Not needed for parent-only mobile pilot. |
| **AI task extraction (#878)** | Modifies `CourseDetailPage` and `client.ts`. Power feature, not pilot-critical. |
| **Task templates & comments (#880)** | Changes Task model and `main.py`. Model migration risk. |

---

## 3. Adjusted Roadmap — Quick Wins & High Value

### Tier 1: Cherry-Pick to Master NOW (March 1-2)
**Goal:** Ship safe, high-value features to production before March 6 pilot.

1. **Student registration with username (#546)** — CRITICAL for pilot
   - Students at partner school need to sign up without personal email
   - Frontend-only change, zero backend risk

2. **Notification ACK/suppress (#548)** — HIGH VALUE
   - Parents drowning in notifications can dismiss them
   - Clean, additive backend + frontend

3. **Link request creation (#547)** — HIGH VALUE
   - Students can initiate parent linking (bidirectional flow)
   - Completes the parent-student workflow for pilot

4. **Classroom type classification (#550)** — MEDIUM VALUE
   - Visual polish: school vs private course badges
   - Self-contained with own migration

5. **Student email identity (#941)** — MEDIUM VALUE
   - School email + personal email on same account
   - Self-contained, own migration

6. **Gradient overrides (#489)** — LOW VALUE (polish)
   - Single CSS file, zero risk

### Tier 2: Post-Pilot Phase 2 Merge (March 7-14)
**Goal:** Merge full `feature/phase-2` branch after pilot is stable.

1. **httpOnly cookies (#788)** — Security upgrade
2. **Progressive account lockout (#796)** — Security hardening
3. **Cookie consent & MFIPPA (#797, #783)** — Privacy compliance
4. **Deep linking (#885, #886)** — UX improvement
5. **Bulk folder import (#877)** — Power feature
6. **AI task extraction (#878)** — Power feature
7. **Task templates & comments (#880)** — Power feature
8. **MCP foundation (#904)** — Infrastructure

### Tier 3: New Phase 2 Development (March 14+)
**Prioritized by value/effort ratio:**

| Priority | Feature | Value | Effort | Why |
|----------|---------|-------|--------|-----|
| **P0** | Post-login onboarding (#413, #414) | HIGH | Small | New users are confused without role selection guidance |
| **P0** | Re-enable Analytics & FAQ nav (#962) | HIGH | Tiny | Already built, just hidden — flip a switch |
| **P1** | Admin email template management (#513) | MEDIUM | Medium | Admin self-service, reduces dev requests |
| **P1** | BYOK AI API Key (#578) | HIGH | Small | Immediate cost savings, simple CRUD + encrypted storage |
| **P1** | Advanced notifications (#966) | MEDIUM | Medium | Notification preferences, digest emails |
| **P2** | Report Card Upload & AI Analysis (#663) | HIGH | Large | Flagship parent feature — "wow factor" |
| **P2** | Student Progress Analysis (#960) | HIGH | Large | Consolidated from #575, #581, #663 |
| **P2** | Course Materials Storage (GCS) (#572) | HIGH | Medium | Infrastructure prerequisite for several features |
| **P2** | Study Guide Repository & Reuse (#573) | HIGH | Medium | 67% AI cost savings — needs #572 first |
| **P3** | AI Mock Exam Generator (#667) | MEDIUM | Large | Teacher engagement feature |
| **P3** | Parent-assigned quizzes (#664) | MEDIUM | Medium | Parent engagement |
| **P3** | Teacher grade entry (#665) | MEDIUM | Large | Spreadsheet-style bulk grading |
| **P3** | TeachAssist integration | HIGH | Large | External system integration |
| **P3** | Notes & project tracking | LOW | Medium | Nice-to-have |

### Tier 4: Phase 2+ AI Intelligence Platform (April+)
1. Course Materials Storage (#572) — if not done in Tier 3
2. Study Guide Repository & Reuse (#573)
3. Ontario Curriculum Management (#571)
4. Exam Preparation Engine (#576)
5. Parent AI Insights (#581)

---

## 4. March 6 Pilot Checklist

### Web App (master branch)
- [ ] Cherry-pick Tier 1 features (6 commits)
- [ ] Run full test suite after cherry-picks
- [ ] Verify TypeScript compiles clean
- [ ] Deploy to production
- [ ] Smoke test: student registration, notification dismiss, link request

### Mobile App
- [ ] Device testing (iOS + Android via Expo Go)
- [ ] Verify auth flow works (Bearer tokens unchanged)
- [ ] Test all 8 parent screens
- [ ] Pilot launch prep

---

## 5. Dependency Graph

```
httpOnly Cookies (#788)
  └── Cookie Consent (#797) depends on cookie auth mechanism

Account Lockout (#796)
  └── standalone (but shares auth.py with cookies)

Course Materials Storage (#572)
  └── Study Guide Reuse (#573) needs file storage
  └── Report Card Upload (#663) needs file storage
  └── Sample Exam Upload (#577) needs file storage

Quiz Results History (#574) ✅ DONE
  └── Student Progress Analysis (#575) needs quiz data
  └── Exam Prep Engine (#576) needs quiz data
  └── Parent AI Insights (#581) needs quiz + progress data

Ontario Curriculum (#571)
  └── Exam Prep Engine (#576) needs curriculum alignment
  └── Course Planning (Phase 3) needs curriculum data
```

---

## 6. Recommendation

**For March 6:** Cherry-pick the 6 safe features from Tier 1 to master. This gives
pilot users student registration, notification management, and parent linking — all
critical for the school pilot. Zero auth changes = zero risk to mobile app.

**After March 6:** Merge full `feature/phase-2` to master as a single release. The
auth changes (cookies, lockout, consent) are better deployed together after the pilot
is stable and you can monitor for issues.

**Phase 2 new dev:** Start with P0 items (onboarding, re-enable nav links) since they're
quick wins, then move to BYOK and GCS storage as infrastructure plays before the big
features (report cards, exam engine).
