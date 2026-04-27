# Multi-Parent Email Digest Sync — Design (Option B, deferred)

**Status:** design-review (not yet approved for build)
**Tracking issue:** #4330
**Owner:** TBD
**Filed:** 2026-04-27
**Successor of:** CB-PEDI-002 (`features-part7.md` §6.142)

---

## Problem

The CB-PEDI-002 unified-digest-v2 schema scopes everything per-parent:

| Table | Keying |
|---|---|
| `parent_child_profiles` | UNIQUE `(parent_id, student_id)` |
| `parent_child_school_emails` | FK to `child_profile_id` (per-parent) |
| `parent_digest_monitored_senders` | UNIQUE `(parent_id, email_address)` |
| `sender_child_assignments` | FK chain into per-parent rows |

But `parent_students` is many-to-many — a student can have multiple linked guardians. So when Parent A configures a kid, school emails, and senders, **Parent B logging in for the same kid sees a blank slate** and has to redo it. Worse, future edits never propagate either way.

Live evidence (2026-04-27): "Theepan" (parent A) had Thanushan + Haashini configured; "Idigital Spider" (parent B) saw both with "No school email configured yet."

## Goal

A second guardian linked to the same student inherits the first guardian's setup *by default*, sees subsequent edits in real time, and can opt out for any individual row or wholesale if they want their own private list. Privacy is bounded by the `parent_students` guardian set — sharing never crosses unrelated households.

User intent (verbatim, 2026-04-27): *"Your kids and monitor senders should be synched by default across the parents. Second parent shouldn't need to configure again. However, they choose to do it if they like."*

## Non-goals

- Real-time cross-tab UI push (WebSocket). Daily digest cadence is forgiving — React-Query revalidation on focus is enough.
- Three-plus-parent edge cases. Schema supports them; UX needs a follow-up usability pass.
- Migrating away from per-parent integration rows (`parent_gmail_integrations`). Each parent's Gmail OAuth stays per-parent.

---

## Architecture

### Layer 1 — shared student-scoped rows (the new canonical state)

```
student_school_emails(
  id, student_id (FK users.id), email_address, forwarding_seen_at?,
  created_by_parent_id (FK users.id, nullable on parent deletion),
  created_at
)
UNIQUE (student_id, LOWER(email_address))
```

```
student_monitored_senders(
  id, owner_set_signature (CHAR(64)), email_address, sender_name?, label?,
  applies_to_all (BOOLEAN), created_by_parent_id, created_at
)
UNIQUE (owner_set_signature, LOWER(email_address))
```

`owner_set_signature` is a deterministic hash (`sha256` of sorted `parent_id`s, hex) of the guardian set linked to a kid. Two unrelated guardian sets each having `no-reply@classroom.google.com` never collide. Recomputed when guardians are added/removed; senders re-keyed during the relationship-change transaction.

```
student_sender_assignments(
  id, student_sender_id (FK student_monitored_senders.id),
  student_id (FK users.id),
  created_at
)
UNIQUE (student_sender_id, student_id)
```

### Layer 2 — per-parent override layer

```
parent_digest_overrides(
  id, parent_id, scope, target_id, action,
  replacement_target_id?,  -- only for action=replace
  created_at
)
scope ∈ {"school_email", "sender", "sender_assignment"}
action ∈ {"hide", "replace"}
UNIQUE (parent_id, scope, target_id)
```

- `hide`: row is suppressed for this parent only. Other guardians still see it.
- `replace`: shared row is suppressed for this parent; `replacement_target_id` points to the parent's own private row in the existing `parent_*` tables (which continue to exist as the private layer).

### Reads — the effective view

For a given parent_id, materialize the digest view as:
```
shared_school_emails(student_id) ∪ private_school_emails(parent_id, student_id)
  − rows where parent has a HIDE override
shared_senders(owner_set_signature) ∪ private_senders(parent_id)
  − rows where parent has a HIDE override
```
Cached per-request in the worker; recomputed on each digest run.

### Writes

| User action | Default behavior | Modifier |
|---|---|---|
| Add school email to kid | Insert into `student_school_emails` | `[shared]` toggle defaulted on |
| Edit school email | Mutate the shared row | "Make private" → creates HIDE override + a private row in legacy `parent_child_school_emails` |
| Remove school email | If shared → HIDE override (so other guardians keep it); long-press / "Remove for everyone" → actual delete | Confirm dialog explains the difference |
| Add monitored sender | Insert into `student_monitored_senders` keyed by current signature | Same `[shared]` semantics |
| Edit/remove monitored sender | Same as school email |
| Toggle "Use my own list" (wholesale) | Per-kid override flag → all shared rows for that kid become hidden + private rows are read | Reversible via "Re-sync to shared" |

### Audit log

```
audit_digest_changes(
  id, parent_id, action ("create"|"update"|"delete"|"hide"|"replace"|"unhide"),
  scope ("school_email"|"sender"|"sender_assignment"),
  target_id, before_json, after_json, created_at
)
```

Two purposes: (1) "Who added this sender?" UI hint; (2) backstop for sharing-induced disputes.

---

## Backfill from existing parent-scoped data

For each student linked to two-plus parents:

1. Compute the canonical guardian set; derive `owner_set_signature`.
2. **Pick the earliest-configured parent** (min `parent_child_profiles.created_at`) as the "donor" for the shared rows.
3. Insert donor's `parent_child_school_emails` rows into `student_school_emails` (dedup on lowered address).
4. Insert donor's `parent_digest_monitored_senders` (matching `owner_set_signature`) into `student_monitored_senders`; copy `sender_child_assignments` into `student_sender_assignments`.
5. For each non-donor parent's rows that **don't match** the donor's set: insert as a `replace` override pointing to the parent's existing private row (preserving any typed divergence).
6. Log every step in `audit_digest_changes` with `action=create` and `parent_id=<system-backfill-marker>`.

Backfill is **non-destructive**: no parent's existing rows are deleted. The legacy `parent_*` tables continue to function as the private layer.

For students linked to exactly one parent: no shared rows created; behavior identical to today.

---

## API surface (delta from CB-PEDI-002)

### New endpoints

| Verb | Path | Purpose |
|---|---|---|
| `GET` | `/api/parent/digest/effective-view` | Returns the merged read model (existing reads compute it server-side) |
| `POST` | `/api/parent/digest/overrides` | Create HIDE or REPLACE override |
| `DELETE` | `/api/parent/digest/overrides/{id}` | Remove an override (re-syncs to shared) |
| `POST` | `/api/parent/digest/share-modes/{student_id}` | Bulk toggle: all-shared / all-private for one kid |
| `GET` | `/api/parent/digest/audit/{student_id}?since=...` | Recent shared-row changes for a kid |

### Modified endpoints

- All existing `POST/PATCH/DELETE` on `parent_child_school_emails`, `parent_digest_monitored_senders`, `sender_child_assignments` gain a `shared` query/body flag (default `true`). When `shared=true`, mutations target the shared layer.

---

## Privacy & access control

- **Bounded sharing:** writes/reads are gated by `parent_students` membership. Mutations include a `student_id` proof step (`require_guardian_of(student_id)` dependency).
- **Estranged co-parent opt-out:** the wholesale "Use my own list" toggle creates HIDE overrides for the entire shared set for that kid. UI surfaces this clearly: "Other guardians will not see your private settings, and you will not see theirs."
- **Guardian-set drift:** if a parent is removed from `parent_students`, their HIDE overrides remain (graceful no-op since they no longer have read access anyway). When a new guardian joins, the worker reseeds them with shared state — they see shared rows immediately on first load.
- **Sensitive data:** sharing extends parent-inbox-derived metadata (sender names, subject patterns inferred from monitored-sender labels) across guardians. Counsel review recommended before `on_for_all` ramp.

---

## UI affordances

- "Your kids" section: each kid row gains a small `[Shared with N guardians]` chip when the kid has more than one linked parent. Click → modal listing other guardians, last-edited audit, and a "Use my own list" wholesale toggle.
- Per-row "Make private" inline action on each school email + monitored sender. Confirm dialog explains the consequence.
- Per-row "Re-sync to shared" inline action for rows with a REPLACE override. Lists what's currently shared so the parent can preview the diff before re-syncing.
- "Recent changes" link in the kid row footer → audit log scoped to that kid (last 30 days).

---

## Rollout & feature flag

- New flag: `parent.digest_multiparent_sync_v1` (off / on_5 / on_25 / on_50 / on_100; OFF by default).
- Backfill runs on the first deploy with the flag at any `on_*` variant — idempotent, can re-run safely.
- During ramp, parents in the off bucket see the legacy parent-scoped behavior; in the on bucket, the merged view.
- Counsel review checkpoint required before `on_for_all`.

---

## Test surface (sketch)

- Backfill: idempotent, donor selection, divergence preservation, single-parent passthrough.
- Reads: effective view = shared ∪ private − hide; private replace shadows shared.
- Writes: default vs. private; HIDE preserves visibility for other guardians.
- Privacy: parent A cannot see/mutate parent B's private rows (cross-household leak test).
- Owner-set signature changes: senders re-key correctly when a guardian is added/removed mid-flight.
- Audit log: every shared-row mutation logged; never duplicates.

---

## Build stripe plan (when greenlit)

1. **S1 — schema + backfill** (one stream): new tables, audit log, idempotent backfill, signature helper.
2. **S2 — read pipeline** (one stream): effective-view query + worker plumbing + caching.
3. **S3 — write pipeline + override layer** (one stream): mutation endpoints, override CRUD, "Use my own list" toggle.
4. **S4 — UI** (one stream, depends on S2 + S3): chips, modals, inline actions, audit-log view.
5. **S5 — observability + audit** (one stream): metrics for shared-vs-private write distribution; audit retention policy.
6. **S6 — privacy review + counsel signoff** (gate, before `on_for_all`).

Each stripe = one isolated worktree, lint+build+pytest gate, two `/pr-review` rounds before integration. Same workflow as CB-PEDI-002.

---

## Open questions (for review)

1. Should "Remove for everyone" require all guardians' consent, or trust any guardian's judgment? (Cleaner UX = trust; safer = require consent. Default proposal: trust, with audit-log visibility.)
2. Do we need an in-app notification when another guardian mutates a shared row? (Daily-digest cadence may be enough; defer to telemetry.)
3. How do we handle a parent who *was* in the guardian set, made shared edits, and is later removed? Current proposal: their authored shared rows remain (others still need them); hide overrides remain; no automatic cleanup.
