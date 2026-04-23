### 6.60 Digital Wallet & Subscription System — Payments, Plans, Invoicing (Phase 2+)

**Epic:** #1384
**Issues:** #1385-#1392, #1851
**Dependencies:** AI Usage Limits (§6.54, #1116), Premium Accounts (#1007), Monetization Plan (#761)
**Source:** ClassBridge_DigitalWallet_Requirement.docx v1.0 (March 2026)

Build a complete monetization system: digital wallet with dual credit pools, subscription plans via admin-managed PackageTier config, one-time credit purchases, Interac e-Transfer (Phase 2), and invoice generation for billing clients.

#### Key Design Decisions

- **Dual credit pools:** Wallet tracks `package_credits` (reset monthly, don't roll over) and `purchased_credits` (roll over indefinitely) separately
- **Debit order:** Consume `purchased_credits` first, then `package_credits` — preserves renewable allocation. Configurable via settings flag in future.
- **PaymentIntent flow:** Server-side PaymentIntent + `<PaymentElement>` for credit top-ups (full UI control). Stripe Checkout used only for subscription plan changes.
- **PackageTier config table:** Admin-adjustable tier allocations without code deploy
- **Immutable ledger:** No records ever deleted from `wallet_transactions` — full audit trail
- **Idempotency guard:** Before crediting on webhook, check `reference_id` against existing transactions. If found, skip — Stripe may deliver webhooks more than once.

#### Subscription Tiers (via `package_tiers` table)

| Tier | Monthly Credits | Price (CAD) | Notes |
|------|----------------|-------------|-------|
| **Free** | TBD by product | $0 | Default for all new users |
| **Standard** | TBD by product | TBD | Monthly subscription |
| **Premium** | TBD by product | TBD | Priority access + higher allocation |

> Credit amounts and prices are stored in the `package_tiers` DB table — adjustable by admin without code deploy.

Free tier users can also purchase additional credits à la carte:
| Pack | Credits | Price |
|------|---------|-------|
| Starter | 50 | $2.00 |
| Standard | 200 | $5.00 |
| Bulk | 500 | $10.00 |

#### 6.60.1 Stripe Integration (#1385)

Payment processing foundation using Stripe with **PaymentIntent flow** for credit top-ups.

- Stripe Customer created on user registration (`stripe_customer_id` on users table)
- **PaymentIntent flow for credit purchases:** Backend creates PaymentIntent → returns `client_secret` → Frontend renders `<PaymentElement>` (supports card, Apple Pay, Google Pay) → Webhook confirms and credits
- **Stripe Checkout** for subscription plan upgrades (hosted redirect)
- Webhook endpoint `POST /api/payments/webhook` handles: `payment_intent.succeeded`, `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.*`
- **Webhook idempotency guard:** Query `wallet_transactions` for `reference_id = payment_intent_id` before crediting. Skip if found.
- Webhook signature verification for security
- Env vars: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`
- Frontend: Load `stripePromise` once at app root via `loadStripe()`. Never instantiate inside a render loop.

**Payment provider rationale:** Stripe recommended for Phase 1 — best DX, webhook reliability, native CAD support, Elements compatibility. Revisit Moneris only if monthly volume > ~$50K CAD.

#### 6.60.2 Subscription Plans (#1386)

Recurring billing via Stripe Checkout and Customer Portal, backed by an admin-managed **PackageTier config table**.

**`package_tiers` table (NEW):**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name | VARCHAR(20) UNIQUE | `free` / `standard` / `premium` |
| monthly_credits | DECIMAL | Credits allocated per month |
| price_cents | INTEGER | Monthly price in cents CAD (0 for free) |
| is_active | BOOLEAN DEFAULT TRUE | Soft-delete / disable tier |
| created_at | DATETIME | |
| updated_at | DATETIME | |

**Data model additions to `users` table:**
| Column | Type | Default | Notes |
|--------|------|---------|-------|
| subscription_tier | VARCHAR(20) | 'free' | free / standard / premium |
| subscription_stripe_id | VARCHAR(255) | NULL | Stripe subscription ID |
| subscription_status | VARCHAR(20) | 'active' | active / past_due / canceled / trialing |
| subscription_period_end | DATETIME | NULL | Current billing period end |
| credits_reset_at | DATETIME | NULL | Last monthly credit reset |

**API Endpoints:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/wallet/packages` | Authenticated | List available package tiers |
| POST | `/api/wallet/packages/enroll` | Authenticated | Enroll in or change package tier |
| POST | `/api/subscriptions/checkout` | Authenticated | Create Stripe Checkout session |
| POST | `/api/subscriptions/portal` | Authenticated | Open Stripe Customer Portal |
| GET | `/api/subscriptions/status` | Authenticated | Current plan + status |
| PATCH | `/api/subscriptions/change-plan` | Authenticated | Switch plans |

**Package Lifecycle:**
- **Upgrade:** Grants a pro-rated delta of credits immediately for the remainder of the billing cycle
- **Downgrade:** Takes effect at next billing cycle start. No credit clawback.
- All changes recorded as `WalletTransaction` with `transaction_type = 'package_credit'`

**Behaviors:**
- Monthly scheduled task (1st of month, 00:00 UTC): resets `package_credits` for all wallets to their tier allocation from `package_tiers` table
- Premium tier bypasses AI usage limit checks entirely
- 3-day grace period on failed payments before downgrade to Free

#### 6.60.3 Digital Wallet (#1387)

Per-user wallet with **dual credit pools** — package credits and purchased credits tracked separately.

**Credit Model:**
| Credit Type | Description |
|---|---|
| `package_credits` | Allocated monthly by active tier. Reset on 1st of each month. Do **not** roll over. |
| `purchased_credits` | Bought by user via payment. **Roll over indefinitely**. Consumed first on debit. |

**`wallets` table:**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_id | INTEGER FK UNIQUE | One wallet per user |
| package | VARCHAR(20) DEFAULT 'free' | Active tier: free / standard / premium |
| package_credits | DECIMAL DEFAULT 0 | From active package (reset monthly) |
| purchased_credits | DECIMAL DEFAULT 0 | From top-ups (roll over indefinitely) |
| auto_refill_enabled | BOOLEAN DEFAULT FALSE | |
| auto_refill_threshold_cents | INTEGER DEFAULT 0 | Trigger refill below this |
| auto_refill_amount_cents | INTEGER DEFAULT 500 | Amount to add ($5.00) |
| created_at | DATETIME | |
| updated_at | DATETIME | |

**Computed property:** `total_balance = package_credits + purchased_credits`

**`wallet_transactions` table (immutable ledger):**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| wallet_id | INTEGER FK | |
| transaction_type | VARCHAR(20) | `package_credit` / `purchase_credit` / `debit` / `refund` |
| amount | DECIMAL | Positive for credits, negative for debits |
| balance_after | DECIMAL | Snapshot of total_balance after transaction |
| reference_id | VARCHAR(255) NULL | Stripe PaymentIntent ID — **idempotency guard** |
| payment_method | VARCHAR(20) NULL | `stripe` / `interac` / `system` |
| note | TEXT NULL | e.g., "Monthly reset — free tier" |
| created_at | DATETIME | |

**Auto-create:** Wallet created automatically on user registration. Every user gets a Free wallet — zero friction.

**API Endpoints:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/wallet` | Authenticated | Balance (both pools), package, summary |
| GET | `/api/wallet/transactions` | Authenticated | Full history (paginated, immutable) |
| POST | `/api/wallet/deposit` | Authenticated | Add funds via Stripe PaymentIntent |
| PATCH | `/api/wallet/auto-refill` | Authenticated | Configure auto-refill |
| GET | `/api/admin/wallets` | Admin | List all wallets with balances |

#### 6.60.4 One-Time Credit Purchases (#1388)

Buy AI credits à la carte. Replaces "Request More Credits" admin flow for paid users.

- `POST /api/wallet/credits/checkout` — Create Stripe PaymentIntent for a credit bundle
- `POST /api/wallet/credits/confirm` — Confirm payment (client-side flow)
- `GET /api/credits/packs` — List available packs with prices
- ConfirmModal shows "Buy More Credits" for wallet/subscription users, "Request More Credits" for free-only
- Credits added to `purchased_credits` pool (roll over indefinitely)

#### 6.60.5 Subscription Frontend (#1389)

- **Pricing page** (`/pricing`) — 3-column plan comparison with "Current Plan" badge
- **Billing settings** (`/settings/billing`) — Plan, credits (both pools), wallet, transactions, invoices
- **Tier badge** in header next to username
- **Buy Credits modal** — Credit pack cards with `<PaymentElement>` (Stripe Elements)
- **Credit top-up modal** wrapped in `<Elements stripe={stripePromise} options={{ clientSecret }}>`

#### 6.60.6 Invoice Module (#1390)

Generate and send invoices to clients (school boards, parents).

**`invoices` table:**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| invoice_number | VARCHAR(20) UNIQUE | Auto-generated (CB-YYYY-NNNN) |
| user_id | INTEGER FK NULL | Associated user |
| client_name | VARCHAR(200) | Recipient |
| client_email | VARCHAR(200) | |
| status | VARCHAR(20) | draft / sent / paid / overdue / cancelled |
| subtotal_cents | INTEGER | |
| tax_rate | DECIMAL(5,2) DEFAULT 13.00 | HST (Ontario) |
| tax_cents | INTEGER | |
| total_cents | INTEGER | |
| due_date | DATE | |
| notes | TEXT NULL | |

**`invoice_items` table:**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| invoice_id | INTEGER FK | |
| description | VARCHAR(500) | |
| quantity | INTEGER | |
| unit_price_cents | INTEGER | |
| total_cents | INTEGER | |

**API Endpoints:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/admin/invoices` | Admin | Create invoice |
| GET | `/api/admin/invoices` | Admin | List all (filterable) |
| POST | `/api/admin/invoices/{id}/send` | Admin | Send via email |
| PATCH | `/api/admin/invoices/{id}/mark-paid` | Admin | Mark paid |
| GET | `/api/admin/invoices/{id}/pdf` | Admin | Download PDF |
| GET | `/api/invoices` | Authenticated | Own invoices |

**Features:** Auto-increment invoice numbers, line item editor, 13% HST, branded PDF generation, SendGrid email delivery, overdue detection cron job.

#### 6.60.7 Admin Subscription Management (#1391)

- Subscription user table with tier control
- Revenue dashboard: MRR, subscriber count, churn, growth charts
- Grant bonus credits, override tier limits
- Payment transaction history
- PackageTier management (add/edit/disable tiers)

#### 6.60.8 Interac e-Transfer — Manual-Assisted Flow (#1851)

Phase 2 payment method for the Canadian market. Interac e-Transfer's programmatic receive API is restricted to licensed financial institutions — no third-party processor (including Stripe) supports it.

**Flow:**
1. User selects "Interac e-Transfer" in top-up UI
2. System displays ClassBridge receiving email + unique reference code: `CB-{user_id}-{timestamp}`
3. User sends transfer from their bank using the reference code
4. Admin receives and accepts the transfer
5. Admin confirms via admin panel → system credits wallet as `purchase_credit` with `payment_method = interac`

**`interac_transfer_requests` table:**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_id | INTEGER FK | |
| wallet_id | INTEGER FK | |
| reference_code | VARCHAR(50) UNIQUE | `CB-{user_id}-{timestamp}` |
| amount_cents | INTEGER | Expected transfer amount |
| credits_to_add | DECIMAL | Credits to grant on confirmation |
| status | VARCHAR(20) | pending / confirmed / rejected / expired |
| admin_confirmed_by | INTEGER FK NULL | Admin who confirmed |
| confirmed_at | DATETIME NULL | |
| created_at | DATETIME | |

**API Endpoints:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/wallet/interac/request` | Authenticated | Submit request, get reference code |
| GET | `/api/admin/interac/pending` | Admin | List pending transfers |
| POST | `/api/admin/interac/{id}/confirm` | Admin | Confirm and credit wallet |
| POST | `/api/admin/interac/{id}/reject` | Admin | Reject transfer |

#### Sub-tasks

- [x] Stripe integration: PaymentIntent flow, SDK, webhooks, idempotency (#1385) — **IMPLEMENTED PR #1854**
- [x] Subscription plans: Stripe Checkout for recurring billing, pro-rated upgrades (#1386) — PackageTier table + enrollment done, Stripe recurring NOT done
- [x] Digital wallet: dual credit pools, debit order, immutable ledger (#1387) — **IMPLEMENTED PR #1854**
- [x] Credit purchases: integrate CreditTopUpModal into "Request More" flow (#1388, #1861) — checkout + modal done, ConfirmModal bridge NOT done
- [x] Subscription frontend: pricing page, billing settings, tier badge (#1389, #1862) — WalletPage done, pricing/billing/badge NOT done
- [ ] Invoice module: generate, send, track invoices (#1390)
- [ ] Admin subscription management + revenue dashboard (#1391, #1860)
- [x] Backend tests (#1392) — **IMPLEMENTED PR #1854** (13 tests)
- [ ] Interac e-Transfer: manual-assisted payment flow (#1851)
- [x] Fix UTF-8 arrow in transaction notes (#1859)

### 6.60.1 Product Strategy: Two Layers — Infrastructure vs Intelligence

**GitHub Issue:** #1430

ClassBridge features fall into two strategic layers:

| Layer | Purpose | Examples |
|-------|---------|---------|
| **Layer 1: Infrastructure** (existing) | Mirror & organize school data | Google Classroom sync, calendar, messaging, tasks, study guides |
| **Layer 2: Intelligence** (WOW features) | Tell parents what to DO with that data | Daily Briefing, Help My Kid, Weak Spot Reports, Readiness Checks |

**Layer 1 is table stakes** — it gets parents in the door, but they compare it 1:1 against Google Classroom and shrug. **Layer 2 is the moat** — no other tool does this. Google Classroom doesn't tell a parent "Your child failed 3 geometry questions this week — here's a practice set."

**The Car Analogy:** Layer 1 is the engine. Layer 2 is the steering wheel. Parents don't buy a car because it has an engine — every car has one. They buy it because of how it drives.

**Recommendations:**
1. Don't remove or de-emphasize existing features — they feed Layer 2
2. Reposition them in the UI as supporting tools, not the headline
3. Lead with proactive features on the dashboard — Daily Briefing front and center
4. Marketing shift: "View your child's assignments" → "Know exactly how to help your child tonight"

---

### 6.61 Smart Daily Briefing — Proactive Parent Intelligence (Phase 2) - IMPLEMENTED

A proactive daily summary that tells parents **what matters today** across all children — the #1 answer to "why should I open ClassBridge?"

**GitHub Epic:** #1403

**Design Philosophy:**
- **Zero AI cost** — pure SQL aggregation against tasks, assignments, study_guides
- **Urgency-first** — overdue → due today → due this week
- **Per-child breakdown** with merge view for multi-child families
- **Optional email delivery** — morning digest via SendGrid

**Backend:**
- `GET /api/briefing/daily` — aggregates today's priorities per child
- Returns: greeting, per-child overdue/due_today/due_this_week items, study activity signals, summary counts
- Student variant: same endpoint returns own data when role=STUDENT
- Role: PARENT or STUDENT

**Frontend:**
- `DailyBriefing` component replaces Today's Focus header on Parent Dashboard
- Compact card per child: urgency counts + top items with "Help Study" buttons (§6.62)
- "All caught up!" positive state with celebration styling
- Progressive disclosure: summary counts visible, expand for item details
- Mobile: stacks vertically, briefing first

**Email Digest (optional):**
- Daily email at 7 AM (EST default) via SendGrid cron
- `daily_briefing.html` template with per-child summary
- New fields: `users.daily_digest_enabled` (Boolean, default false)
- Unsubscribe link in footer

**Sub-tasks:**
- [x] Backend: daily briefing aggregation endpoint (#1404)
- [x] Frontend: briefing card on parent dashboard (#1405)
- [x] Email: optional daily morning digest (#1406)

### 6.62 Help My Kid — One-Tap Study Actions (Phase 2) - IMPLEMENTED

Parent sees an upcoming test → taps **"Help Study"** → ClassBridge generates a practice quiz and sends it to the child's dashboard with a notification.

**GitHub Epic:** #1407

**User Flow:**
1. Parent sees "Emma has Math test tomorrow" in Daily Briefing or anywhere in app
2. Parent taps "Help Study" button
3. Modal: "Generate study help for Emma's Math test?" — Quiz / Study Guide / Flashcards
4. Parent confirms → AI generates in background (existing pipeline)
5. Emma gets notification: "Mom sent you a practice quiz for tomorrow's Math test!"
6. Material appears on Emma's dashboard with "From Parent" badge

**Backend:**
- `POST /api/help-study` — generates study material for child, auto-notifies
- Request: `{ student_id, source_type, source_id, material_type, topic_hint }`
- Tags material with `generated_by_user_id` (parent) + `generated_for_user_id` (student)
- Creates notification for student
- New fields: `study_guides.generated_by_user_id`, `study_guides.generated_for_user_id` (FK, nullable)

**Frontend:**
- "Help Study" buttons on: Daily Briefing items, Task Detail, Course Material Detail, Calendar popover
- Generation modal with material type selector
- Non-blocking (background generation, existing pattern)

**AI Cost:** ~$0.02/call (existing gpt-4o-mini pipeline, governed by §6.54 usage limits)

**Source Material Linking (Derived Content):**

Generated materials maintain a **lineage chain** back to their source via a self-referential FK on `study_guides`:

```
study_guides table (existing — add 3 nullable FK columns):
  + source_study_guide_id  (FK → study_guides.id)  — "derived from" link
  + generated_by_user_id   (FK → users.id)          — who triggered generation
  + generated_for_user_id  (FK → users.id)          — who it's for (child)
```

**Why self-referential FK (not a new table):**
- No new entity type — a generated quiz is still a `study_guide` with `guide_type=quiz`
- Existing CRUD, permissions, and UI all work unchanged
- Source traceability: Original Document → Study Guide → Quiz → Word Problems (chain via `source_study_guide_id`)
- UI shows "Derived from: [Math Chapter 5 Study Guide]" as a clickable link on material detail page

**Constraints:**
- Max 2 levels deep (original → derived → sub-derived). Prevents infinite chains
- Soft-delete only on source materials. If hard-deleted, set children's `source_study_guide_id = NULL`
- Dedup: same content_hash + 60-second window (existing pattern) prevents duplicate derived materials

**UI:**
- Material detail page shows "Derived from: [source title]" breadcrumb link
- Source material detail page shows "Derived materials: [Quiz] [Flashcards] [Word Problems]" section
- "Generate More" dropdown on any material: Quiz / Flashcards / Word Problems / Summary — creates a new `study_guide` with `source_study_guide_id` pointing to current

**Sub-tasks:**
- [x] Backend: one-tap generation with auto-notify (#1408) (IMPLEMENTED)
- [x] Frontend: Help Study buttons + generation modal (#1409) (IMPLEMENTED)

**v3 Enhancements — Parent-Initiated Study Request (#2019):**
- [x] Parent selects subject, topic, and urgency level
- [x] Student receives notification: "Your parent suggested reviewing fractions before Friday. Tap to start."
- [x] Student can accept, defer, or flag as "already done"
- [x] Response visible to parent on Help My Kid dashboard

### 6.63 Weekly Progress Pulse — Email Digest (Phase 2)

Weekly email digest summarizing the past week and previewing the next. Sent Sunday evening.

**GitHub Epic:** #1413

**Email Content:**
- Per-child: completed assignments/tasks count, overdue items, quiz scores, next week preview
- "All caught up!" celebration for children with no overdue
- Direct links to ClassBridge for each item
- Unsubscribe link

**Backend:**
- Weekly digest aggregation service (queries tasks, assignments, quiz results per child)
- `weekly_progress_pulse.html` email template
- Cloud Scheduler / cron: Sunday 6 PM EST
- Parent preferences: opt-in/out

**AI Cost:** $0.00 — pure SQL + SendGrid

**Sub-tasks:**
- [x] Backend: weekly digest aggregation service (`app/services/weekly_digest_service.py`) (IMPLEMENTED)
- [x] Email template: weekly digest HTML rendering (IMPLEMENTED)
- [x] Cron/Cloud Scheduler trigger — APScheduler job for Sunday 7pm delivery (#2022)
- [x] Parent notification preferences — advanced per-category notification preferences (PR #1464)

**v3 Enhancements (StudyGuide Requirements v3 — Section 8, Feature #2):**
- [ ] Conversation starters per child: "Haashini studied cell division — ask her: what is the difference between mitosis and meiosis?"
- [ ] Frequency preference: weekly / bi-weekly; configurable delivery time (default Sunday 7pm)
- [x] CASL-compliant opt-in at registration
- [x] One-click unsubscribe link
- [ ] Multilingual support — translate digest into parent's preferred language (#2016)

### 6.63.1 Weekly Family Report Card Email with Gamification - IMPLEMENTED

**Status:** IMPLEMENTED (2026-03-25, PR #2369)
**GitHub Issue:** #2228 | **Related:** §6.63, §6.107 (XP/streaks)

Beautiful HTML email sent weekly with gamification data: streak flame, XP earned, quizzes completed, study time, and AI-generated encouragement. Designed to be shareable (parents forward to grandparents) for viral growth.

**Enhancements over §6.63 base digest:**
- [x] Gamification stats: XP earned, study streaks, level progress
- [x] Visual badges and achievement highlights
- [x] AI-generated encouragement messages per child
- [x] Shareable format optimized for forwarding

**Sub-tasks:**
- [x] Backend: family report card email service with gamification data aggregation
- [x] Email template: branded HTML with streak/XP visuals
- [x] Integration with weekly digest pipeline

### 6.63.2 Role-Based Deep Linking in Email Buttons - IMPLEMENTED

**Status:** IMPLEMENTED (2026-03-25, PR #2371)
**GitHub Issue:** #2237

Email notification buttons now deep-link to the correct page based on the recipient's role. Parents see links to My Kids/parent dashboard, students to their study tools, and teachers to course management.

**Sub-tasks:**
- [x] Backend: role-aware URL generation in email templates
- [x] All email notification types updated with role-based CTAs

### 6.64 Parent-Child Study Link — Feedback Loop (Phase 2) - IMPLEMENTED

When a parent generates study material (§6.62), a feedback loop tracks completion and reports back.

**GitHub Epic:** #1414

**Flow:**
1. Parent generates quiz → child notified
2. Child completes quiz → parent notified with score + struggle areas
3. Parent sees "Study Help I've Sent" with completion status

**Data Model:**
```sql
study_help_links:
  id, sender_user_id (parent), recipient_user_id (student),
  study_guide_id, source_type, source_id,
  status (sent/opened/completed), score (nullable),
  created_at, completed_at
```

**Frontend:**
- Parent: "Study Help I've Sent" section (items + scores)
- Student: "From Parent" badge on received materials
- Notifications both directions

**AI Cost:** $0.00 for tracking. Generation cost covered by §6.62.

### 6.65 Dashboard Redesign — Clean, Persona-Based Layouts (Phase 2) - IMPLEMENTED

Redesign all four dashboards to be clean, uncluttered, and persona-driven.

**GitHub Epic:** #1415

**Design Philosophy:**
- **One-screen rule**: Everything visible without scrolling on desktop (1080p)
- **3-section max**: Each dashboard has at most 3 primary sections
- **White space is a feature**: Generous padding, no visual noise
- **Role-specific language**: Parents see "your children", students see "your classes"
- **Action-first**: Lead with what the user can DO

**Per-Role Layouts:**

| Dashboard | Sections | Issue |
|-----------|----------|-------|
| Parent v5 | Daily Briefing + Child Snapshot + Quick Actions + Recent Activity (study guides & messages only) | #1416 |
| Student v4 | Coming Up + Recent Study + Quick Actions | #1417 |
| Teacher v2 | Student Alerts + My Classes + Quick Actions | #1418 |
| Admin v2 | Platform Health + Recent Activity + Quick Actions | #1419 |

**Sub-tasks:**
- [x] Parent Dashboard v5 (#1416)
- [x] Student Dashboard v4 (#1417)
- [x] Teacher Dashboard v2 (#1418)
- [x] Admin Dashboard v2 (#1419)
- [ ] DashboardLayout header cleanup
- [ ] CSS dead code removal (v1-v4 remnants)

### 6.66 Responsible AI Parent Tools — Parent-First Study Toolkit (Phase 2)

A suite of parent-first AI tools designed around the principle: *"Make the parent's life easier, make the student do the work."*

**GitHub Epic:** #1421

**Responsible AI Test — every tool must pass:**
- Does it require the student to DO something? ✅
- Does it help the PARENT understand and engage? ✅
- Could the student use it to avoid studying? ❌ → Don't build it

**Tools:**

| # | Tool | For Parent | For Student | AI Cost | Guide Type |
|---|------|-----------|-------------|---------|------------|
| 1 | **"Is My Kid Ready?" Assessment** | Readiness score + gap areas | Must answer 5 questions | ~$0.02 | `readiness` |
| 2 | **Parent Briefing Notes** | Plain-language topic summary + home help tips | Never sees it | ~$0.01 | `parent_briefing` |
| 3 | **Practice Problem Sets** | "I gave extra practice" | Must solve open-ended problems | ~$0.02 | `practice_problems` |
| 4 | **Weak Spot Report** | Trend analysis over time | Sees own progress | $0.00 | N/A (SQL) |
| 5 | **Conversation Starters** | Dinner table engagement prompts | N/A | ~$0.005 | N/A (cached) |

**Data Model:**
- Tools 1-3 reuse `study_guides` table with new `guide_type` values (`readiness`, `parent_briefing`, `practice_problems`)
- `source_study_guide_id` links back to source material (§6.62 lineage chain)
- Parent Briefing visibility: `generated_for_user_id = parent_id` + RBAC prevents student access
- Weak Spot Report: pure SQL aggregation of existing `quiz_results` table
- Conversation Starters: cached per course material, regenerate on new content

**Revised "Help Study" Menu (§6.62 update):**
- Primary actions: Quick Assessment, Practice Problems, Parent Briefing
- Secondary ("More options"): Quiz, Study Guide, Flashcards
- Parent Briefing only visible to parent role

**Sub-tasks:**
- [ ] "Is My Kid Ready?" readiness assessment (#1422)
- [x] Parent Briefing Notes (#1423, PR #1467)
- [ ] Practice Problem Sets (#1424)
- [ ] Weak Spot Report (#1425)
- [x] Conversation Starters (#1426, PR #1485) — moved to My Kids page, on-demand generation
- [x] Frontend: revised Help Study menu (#1427, PR #1480) — route fixes for blank pages
- [x] Tests (#1428, PR #1471)

### 6.67 Smart Data Import — Parent-Powered School Data (Phase 2)

School boards won't grant API access. Google Classroom OAuth requires individual setup. Manual upload creates friction. **Solution: empower parents to bring their own data in.**

**GitHub Epic:** #1431

**Key Insight:** Don't ask the school board for permission. Parents already have the data — report cards, emails, handouts, calendar feeds. Make it effortless to import.

**This is a Layer 1 → Layer 2 accelerator** (#1430): the easier data flows in, the smarter Daily Briefing (#1403) and Help My Kid (#1407) become.

#### 6.67.1 Photo Capture (#1432)

Parent photographs assignment sheet / report card → GPT-4o-mini vision extracts structured data (title, due date, subject, grade).

- Endpoint: `POST /api/import/photo` (multipart)
- AI cost: ~$0.02/photo
- Returns preview → parent confirms/edits → saved as assignment, task, or content
- Original photo stored as attachment
- Mobile-friendly camera integration

#### 6.67.2 Email Forwarding (#1433)

Parent forwards school email to `import@classbridge.ca` → system parses assignment details automatically.

- SendGrid Inbound Parse webhook → `POST /api/import/email-webhook`
- Match incoming email to parent by registered email address
- AI cost: ~$0.01/email for structured extraction
- Pending imports queue with 7-day expiry + review UI
- Optional: parent sets auto-forwarding rule for zero ongoing effort

#### 6.67.3 Calendar Import / ICS Feed (#1434)

Parent pastes school calendar URL → ClassBridge syncs events, due dates, school holidays.

- Endpoint: `POST /api/import/calendar` (URL input)
- Python `icalendar` library for parsing — **$0 AI cost**
- `calendar_feeds` table: user_id, url, last_synced, refresh_interval
- Daily auto-refresh, duplicate detection by UID
- Events appear in ClassBridge calendar + Daily Briefing

#### Deprioritized

- **Browser extension:** Higher dev cost, store approvals, maintenance burden
- **Direct school board integrations:** Long sales cycle, legal complexity, unlikely in Phase 2

**Sub-tasks:**
- [ ] Photo Capture: snap & import (#1432)
- [ ] Email Forwarding: parse school emails (#1433)
- [ ] Calendar Import: ICS feed sync (#1434)
- [x] CSV Template Import: bulk import via CSV (#2167) — see §6.67.4

#### 6.67.4 CSV Template Import — Bulk Data Upload (Phase 2) - IMPLEMENTED

**Status:** IMPLEMENTED (2026-03-28, PR #2584)
**GitHub Issue:** #2167 | **Review Fixes:** PR #2589 (#2585-#2588)

Parents, teachers, and admins can download CSV templates and upload populated files to bulk-import courses, students, and assignments. Reduces manual data entry friction for onboarding.

**Implementation:**
1. Template download endpoint returns pre-formatted CSV with correct headers per entity type (courses, students, assignments)
2. CSV upload with client-side preview and validation before server submission
3. Backend parses CSV, validates rows, creates entities in bulk with per-row error handling
4. RBAC restricted to parent, teacher, and admin roles (#2587)
5. 5 MB file size limit on uploads (#2588)
6. Students created via CSV receive hashed passwords (#2585)
7. Savepoint-based transaction handling — individual row failures don't roll back prior successful rows (#2586)

**Sub-tasks:**
- [x] Backend: CSV template download endpoint per entity type
- [x] Backend: CSV upload, parse, validate, and bulk import service
- [x] Backend: RBAC enforcement on import endpoints
- [x] Backend: Per-row savepoint transaction handling
- [x] Frontend: CSV import page with upload, preview, and validation UI
- [x] Tests: 10 backend tests for CSV import

**Key files:**
- `app/api/routes/csv_import.py` — Template download + upload endpoints
- `app/services/csv_import_service.py` — Parse, validate, bulk create logic
- `frontend/src/pages/CSVImportPage.tsx` — Upload UI with preview

#### 6.67.5 Bulk Class Import — Google Classroom + Screenshot (CB-ONBOARD-001)

**Status:** IMPLEMENTED (2026-04-23, CB-ONBOARD-001)
**GitHub Issue:** #3985 (tracking) | Closes #3986 | Partially addresses #2163 | Part of epic #2160

Any logged-in user can bulk-import their classes and teachers into ClassBridge via two pathways that converge on one shared review step. Unlocks <60-second onboarding for parents/students/teachers without a school-board data feed.

**Pathways:**
- **From Google Classroom** — one-click import for users who have connected Google (uses existing `classroom.courses.readonly` scope, no new scopes requested). `GET /api/courses/google-classroom/preview` normalizes courses + teachers and detects already-imported entries.
- **From screenshot** — upload a Google Classroom screenshot; Claude vision (`claude-sonnet-4-6`) parses classes + teachers into an editable table. Works when Google isn't connected.

**Unified review step:**
- Editable table — users can edit names, add teacher emails, remove rows, and confirm
- Courses already imported surface with "Already imported" badge and are skipped on bulk create
- `POST /api/courses/bulk` loops the existing `create_course` logic per row with SAVEPOINT rollback; partial success is returned

**Teacher handling:**
- Teachers without a matching User record are created as shadow teachers
- If a teacher email is provided, an invite is sent (SendGrid)

**Scope:** Classes + teachers only. Phase-2 scope (assignments, announcements, materials, `ImportSession` staging model, `ImportReviewWizard` page) remains tracked in epic #2160.

**Key files:**
- `app/api/routes/class_import.py` — `google-classroom/preview`, `parse-screenshot`, `bulk` endpoints
- `app/schemas/class_import.py` — Pydantic schemas for the three endpoints
- `app/services/class_import_service.py` — Google preview, screenshot parse, bulk create logic
- `frontend/src/components/ImportClassesModal.tsx` — Two-tab modal (Google / Screenshot)
- `frontend/src/components/ImportReviewTable.tsx` — Shared editable review table
- `frontend/src/api/classImport.ts` — Frontend API client

#### 6.67.6 Unified Class-Add Modal (planned — CB-ONBOARD-001 fast-follow)

**Status:** PLANNED (tracked in #3997)
**GitHub Issue:** #3997 (CB-ONBOARD-001 fast-follow)

Collapse the separate "Create class" and "Import classes" entry points on CoursesPage into a single "Add classes" modal with three tabs — *Manual (single)*, *From Google Classroom*, *From screenshot*.

**Motivation:** PR #3996 shipped `ImportClassesModal` alongside the existing `CreateClassModal`, which creates two buttons with overlapping intent. Unifying improves discoverability and removes redundant UI.

**Scope:**
- Add a Manual tab inside `ImportClassesModal` that mirrors the current `CreateClassModal` form (name, subject, description, teacher select, require-approval) and submits to the existing `POST /api/courses/` endpoint.
- Update `CoursesPage.tsx` to render a single "Add classes" button.
- Update `UploadMaterialWizard.tsx` to reuse the unified modal in a `mode="single"` variant that hides the other tabs and returns the created `courseId` to the wizard.
- Delete `CreateClassModal.tsx` and its test file.

**Out of scope:** backend changes, admin class-management page, bulk-import behaviour changes.

### 6.68 AI Integration Strategy — Decision Log

**GitHub Issue:** #1435

#### Perplexity Integration — REJECTED

| Factor | Assessment |
|--------|-----------|
| What Perplexity does | Web search + AI summarization for general knowledge |
| What ClassBridge needs | Analysis of **private student data** (grades, assignments, study history) |
| Data overlap | Zero — Perplexity has no access to student school data |
| Cost | ~$5/1000 queries vs GPT-4o-mini ~$0.15/1000 |
| Responsible AI | Students could use it to get answers without studying — **fails the test** |

**Decision:** ClassBridge's AI value is contextual (private student data + uploaded course content). A general web search engine adds cost, risk, and zero differentiation. If web enrichment is needed later (Phase 4+), a YouTube API search ($0) covers the primary use case.

### 6.69 "Learn Your Way" — Interest-Based Personalized Learning (Phase 2)

Inspired by [Google's Learn Your Way](https://learnyourway.withgoogle.com/) and requested by a Grade 10 pilot student. Transforms existing study tools into a personalized learning experience.

**GitHub Epic:** #1436

**Core Concept:** Instead of a single "Generate Study Guide" button, students choose HOW they want to learn:

| Format | Description | Status |
|--------|-------------|--------|
| Study Guide | Enriched text with inline questions | Already built |
| Quiz Me | Comprehension check questions | Already built |
| Flashcards | Key terms and definitions | Already built |
| "Explain Like I'm Into..." | Interest-based analogies (Pokemon, Basketball, Minecraft, etc.) | **New** |
| Mind Map | Visual knowledge structure (interactive nodes) | **New** |
| Audio Lessons | AI teacher + virtual student dialogue | Deferred (Phase 3+ — needs TTS) |

**Interest-Based Personalization:**
- Students set interests in profile (Pokemon, Basketball, Soccer, Minecraft, Music, Art, Gaming, Cooking, Space, Animals, or custom)
- AI prompts modified to use analogies from student's interests
- Example: Chemistry + Pokemon → "Hydrogen is Normal-type — everywhere, combines with anything. H + O fusion = Water (H₂O)"
- AI cost: $0 additional (same API call, modified prompt)

**Learning Science Principles (from Google's research):**
1. Inspire active learning
2. Manage cognitive load
3. Adapt to the learner
4. Stimulate curiosity
5. Deepen metacognition

**Responsible AI Test:** ✅
- Student must READ and ENGAGE with content
- Based on THEIR course material, not generic web answers
- Can't skip studying — it IS studying, in their language

**Data Model:**
- `users` table: add `interests TEXT DEFAULT NULL` (JSON array)
- `study_guides` table: existing `guide_type` extended with `mind_map` value
- Generation endpoints: add optional `interest: str` parameter

**Sub-tasks:**
- [x] Backend: interest-based prompt customization (#1437, PR #1469)
- [x] Frontend: "Learn Your Way" format selector UI (#1438, PR #1469)
- [x] Backend + Frontend: Mind Map generation and rendering (#1439, PR #1469)
- [x] Student profile: interests/hobbies setting (#1440, PR #1469)

### 6.69.5 Monetization Strategy

- Learn Your Way is a **premium feature** behind a paywall
- Free tier: Standard AI study guides (current functionality)
- Premium tier: Interest-based personalized content (Learn Your Way)
- Upgrade UX: Show a preview/teaser of personalized content, then prompt to upgrade
- Pricing model: TBD (per-credit or subscription)
- Suggested by pilot user feedback (Grade 10 student)

### 6.70 Advanced Per-Category Notification Preferences (Phase 2) - IMPLEMENTED

Fine-grained notification preferences allowing users to control notifications per category rather than a single global toggle.

**GitHub:** PR #1464

**Implementation:**
- Per-category toggles: assignments, tasks, messages, briefings, study_help, system
- Backend: `notification_preferences` table with per-user, per-category enabled/disabled settings
- `GET/PUT /api/notifications/settings` — retrieve and update per-category preferences
- Frontend: Settings page with individual toggle switches per notification category
- Backwards compatible: defaults all categories to enabled for existing users

**Sub-tasks:**
- [x] Backend: per-category notification preferences model and endpoints (PR #1464)
- [x] Frontend: notification preferences settings UI (PR #1464)

### 6.71 Premium Storage & Upload Limits (Phase 2) - IMPLEMENTED

Tiered storage and upload limits based on user subscription tier (free vs premium).

**GitHub:** PR #1470

**Implementation:**
- Free tier: limited study guide storage and file upload counts
- Premium tier: higher limits for storage and uploads
- Backend enforces limits at generation and upload endpoints
- Frontend displays usage vs limit with upgrade prompts when approaching limits
- Admin can override limits per user

**Sub-tasks:**
- [x] Backend: tiered storage/upload limit enforcement (PR #1470)
- [x] Frontend: usage display and upgrade prompts (PR #1470)

### 6.72 Sidebar Always-Expanded with Icons (Phase 2) - IMPLEMENTED

Sidebar navigation updated to always show expanded state with proper icons for all menu items. Collapse/toggle feature removed for simplicity.

**GitHub:** PR #1483 (fixes #1482)

**Implementation:**
- Added missing icons to all sidebar navigation items
- Removed sidebar collapse/expand toggle — sidebar is always fully expanded
- Consistent icon set across all roles (parent, student, teacher, admin)
- Fixes blank/missing icon states reported in #1482

### 6.73 Briefing & Conversation Starters Relocated to My Kids (Phase 2) - IMPLEMENTED

Daily briefing summary and conversation starters moved from the parent dashboard to the My Kids page, available on-demand per child rather than as a dashboard-level component.

**GitHub:** PR #1485 (fixes #1484)

**Implementation:**
- Daily briefing card moved from parent dashboard to My Kids page (per-child context)
- Conversation starters ("Dinner Table Talk") relocated to My Kids page alongside briefing
- On-demand generation: parents trigger briefing/starters when they want them, not auto-loaded
- Reduces dashboard clutter; parent dashboard focuses on urgency items only

### 6.74 Mind Map Generation & Rendering (Phase 2) - IMPLEMENTED

Interactive mind map visualization for course materials with expandable/collapsible nodes.

**GitHub:** PR #1469 (part of Learn Your Way, #1439)

**Implementation:**
- New `guide_type = 'mind_map'` in study_guides table
- AI generates hierarchical JSON structure from course content
- Frontend renders interactive node graph with expand/collapse
- Available via "Learn Your Way" format selector and Help Study menu

### 6.75 Notes Revision History (Phase 2) - IMPLEMENTED

365-day version retention for contextual notes with diff viewing.

**GitHub:** PR #1469 (#1139)

**Implementation:**
- `note_versions` table stores previous versions with timestamps
- `GET /api/notes/{id}/versions` — list version history
- `GET /api/notes/{id}/versions/{version_id}` — retrieve specific version
- Auto-creates version snapshot on each note save
- Frontend: version history panel with restore capability
- 365-day retention policy

### 6.76 Course Material Grouping by Category (Phase 2) - IMPLEMENTED

Course materials can be organized and filtered by category for easier navigation.

**GitHub:** PR #1469 (#992)

**Implementation:**
- Category field on course_contents with predefined categories
- Filter UI on CoursesPage and CourseDetailPage
- Category badges on material cards

### 6.77 Daily Morning Email Digest (Phase 2) - IMPLEMENTED

Automated daily email sent to parents summarizing their children's upcoming tasks and overdue items.

**GitHub:** PR #1469 (#1406)

**Implementation:**
- SendGrid email template `daily_briefing.html`
- `users.daily_digest_enabled` boolean field (opt-in)
- Morning cron aggregates per-child data and sends digest
- Unsubscribe link in footer

### 6.78 ICS Calendar Import (Phase 2) - IMPLEMENTED

Parents can import school calendar events via ICS URL for automatic sync.

**GitHub:** PR #1469 (#1434)

**Implementation:**
- `POST /api/import/calendar` — accepts ICS URL
- `calendar_feeds` table: user_id, url, last_synced
- Python icalendar library for parsing
- Events appear in ClassBridge calendar view
- Daily auto-refresh with duplicate detection

### 6.79 Tutorial Completion Tracking (Phase 2) - IMPLEMENTED

Track which tutorial/onboarding steps users have completed with backend persistence.

**GitHub:** PR #1469 (#1210)

**Implementation:**
- `tutorial_completions` table: user_id, tutorial_key, completed_at
- `GET/POST /api/tutorials/completions` endpoints
- Frontend checks completion state to show/hide tutorial prompts
- Persists across sessions and devices

### 6.80 Command Palette Search (Phase 2) - IMPLEMENTED

Upgraded global search to a command palette interface with Ctrl+K shortcut.

**GitHub:** PR #1469 (#1410, #1411, #1412)

**Implementation:**
- Ctrl+K / Cmd+K keyboard shortcut to open
- Searches across children, assignments, courses, study guides, tasks
- Recent searches and keyboard navigation
- Grouped results with type icons and preview text

### 6.81 Recent Activity Panel (Phase 2) - IMPLEMENTED

Real-time activity feed for parent dashboard showing recent study guide generations and messages.

**GitHub:** PR #1469 (#1225, #1226, #1227)

**Implementation:**
- `GET /api/activity/recent` — aggregates recent study guides and messages per child
- Filters: by child, by type (study_guides, messages only for parents)
- RecentActivityPanel component with collapsible sections
- Task click deep-links to /tasks/:id
- Simplified view: collapsed by default, expandable on demand
- Child filter properly excludes unrelated children's activity

### 6.82 LaTeX Math Rendering in Study Guides (Phase 2) - IMPLEMENTED

Study guides render LaTeX math expressions ($...$ inline and $$...$$ block).

**GitHub:** PR #1555 (#1552)

**Implementation:**
- Added remark-math + rehype-katex to ReactMarkdown pipeline
- AI prompt updated to explicitly use LaTeX notation for math content
- Supports both inline ($x^2$) and block ($$\int_0^1 f(x)dx$$) math
- KaTeX CSS loaded for proper rendering

### 6.83 Help/FAQ for Responsible AI Tools (Phase 2) - IMPLEMENTED

Help page sections explaining each Responsible AI parent tool with usage guidance.

**GitHub:** PR #1549 (#1548)

**Implementation:**
- FAQ entries for each AI tool: readiness assessment, parent briefing, practice problems
- Explains responsible AI principles and how each tool helps parents without enabling shortcuts
- Integrated into existing Help page article system

### 6.84 Chat FAB Icon and Study Guide UI Polish (Phase 2) - IMPLEMENTED

Iterative refinement of the Chat FAB sub-icon appearance and study guide UI elements.

**GitHub:** #1615 (PRs #1499, #1503, #1505, #1515, #1529–#1537)

**Implementation:**
- Study guide UI: title icon, wider container, focus prompt for regeneration
- Chat FAB: evolved from outline icon → filled icon → CB logo → rounded rectangle FAB
- Final state: v7.1 logo icon in rounded rectangle, 512px resolution, object-fit cover
- Header logo updated to v6.1 transparent background with proportional sizing
- Create Study Guide added to course material context menu

