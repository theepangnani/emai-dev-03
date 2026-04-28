# CB-CMCP-001 — Cost Model

**Status:** Draft v1.0 (M0-D 0D-1)
**Owner:** Engineering (Theepan)
**Issue:** #4417
**Plan:** `docs/design/CB-CMCP-001-batch-implementation-plan.md` (locked decision D8=B; risk register §10 cost-overrun row)

---

## 1. Context

CB-CMCP-001 introduces curriculum-aligned long-form generation (Study Guides, Worksheets, Quizzes, Sample Tests, Assignments, Parent Companions) anchored on the Curriculum Expectations Graph (CEG) and the four authenticity amendments (A1 class-context blending, A2 Parent Companion, A3 Arc voice overlay, A4 surface delivery).

Locked decision **D8=B** ("estimate now") requires an explicit cost projection before the M0 → M1 acceptance gate. Without it, M1 (Generation Pipeline Alpha) ships into production token spend with no per-tier ceiling, no per-artifact spend cap, and no anchor against existing unit economics. A budget surprise mid-M1 — when ~6 generation paths are simultaneously hitting Claude/OpenAI — is materially more expensive to fix than a doc shipped now.

This document closes that gap. It is the cost-overrun mitigation referenced in plan §10. M1-E telemetry (spend dashboards) consumes the assumptions here and validates / corrects them with real data after the first 100 production generations.

**Anchors used:**
- **CB-ASGF-001 epic #3390:** $0.106/ASGF session, $0.013/Flash Tutor session, ~$1.28/student/month combined, **AI cost as % of B2C revenue ≈ 36%** (mitigation needed pre-M5c).
- **CB-DEMO-001 §6.135:** Haiku token-budget envelopes (500 / 600 / 1200 tokens per demo_type) — used here as a sanity check on small-form artifact costs.
- **Provider rate cards** retrieved from Anthropic + OpenAI public pricing pages (rates listed in §3 below; subject to provider-side change).

---

## 2. Provider rate card (baseline)

All figures USD per 1M tokens. Source: Anthropic + OpenAI public pricing pages, current as of **2026-04-27** (doc date). **These rates change** — re-validate at every M-gate.

| Model | Input | Output | Notes |
|---|---|---|---|
| Claude Sonnet 4 (`claude-sonnet-4`) | $3.00 / 1M | $15.00 / 1M | Long-form route per locked plan (Study Guide, Sample Test, Assignment, Parent Companion). |
| GPT-4o-mini (`gpt-4o-mini`) | $0.15 / 1M | $0.60 / 1M | Short-form route per locked plan (Quiz, Worksheet). |
| Claude Haiku 4.5 (`claude-haiku-4-5`) | $1.00 / 1M | $5.00 / 1M | Reference only (used by CB-DEMO-001); not in CMCP-001 routing. |
| `text-embedding-3-small` | $0.02 / 1M | n/a | CEG embedding refresh + class-context resolver. |

**Routing rule (locked plan §1A-1):** Long-form (>1,500 output tokens, structured prose) → Sonnet. Short-form (<800 output tokens, structured JSON list of items) → GPT-4o-mini. Parent Companion is long-form Sonnet despite shorter token count because the warm-coaching voice quality requires Sonnet-tier reasoning (cannot drop to Haiku without voice-audit failure per A3 amendment).

---

## 3. Per-content-type token cost

### 3.1 Per-artifact token assumptions

Token estimates assume the locked guardrail-engine prompt structure (plan §1A-1):
1. **System / persona prompt** — ~600 tokens (voice overlay + reviewer rubric + JSON schema instructions)
2. **CEG SE list** — 4–8 specific expectations, each with code + descriptor + sample indicators ≈ 80 tokens/SE → **400–650 tokens**
3. **Class-context envelope summary (A1)** — 14d announcement digest + 30d teacher-email digest + matched artifact-library snippets, capped at **800 tokens** by the resolver
4. **Voice overlay (A3)** — 250 tokens for student / parent / teacher variant
5. **User intent + grade/subject** — 100 tokens

**Input baseline per artifact:** ~2,200 tokens. Range ±30% depending on envelope fullness (long-tail teachers with rich digest history sit at ~2,800; brand-new classrooms with empty A1 envelope sit at ~1,500).

| Content type | Output tokens (typical) | Output tokens (P95) | Engine route | Rationale |
|---|---|---|---|---|
| Study Guide (long-form) | 4,500 | 6,500 | Sonnet | 6–8 sections, worked examples, slide-style narrative |
| Sample Test (long-form, multi-question) | 4,000 | 5,800 | Sonnet | 10–15 mixed-format questions w/ rubric |
| Assignment (long-form, project) | 3,500 | 5,000 | Sonnet | Multi-step task w/ checkpoints + scaffolds |
| Parent Companion (5-section) | 1,800 | 2,400 | Sonnet | Short but voice-critical; 5 sections per locked DD §6.1 |
| Quiz (short-form, structured) | 1,200 | 1,800 | GPT-4o-mini | 8–12 MCQ/short-answer items + answer key + per-item hints |
| Worksheet (short-form, structured) | 900 | 1,400 | GPT-4o-mini | 6–10 practice items + answer key |

### 3.2 Cost per artifact (typical)

Formula: `(input_tokens × input_rate) + (output_tokens × output_rate)`, all per 1M.

| Content type | Input cost | Output cost | **Cost / artifact (typical)** | **Cost / artifact (P95)** |
|---|---|---|---|---|
| Study Guide | 2,200 × $3 / 1M = $0.0066 | 4,500 × $15 / 1M = $0.0675 | **$0.0741** | **$0.1041** |
| Sample Test | $0.0066 | 4,000 × $15 / 1M = $0.0600 | **$0.0666** | **$0.0936** |
| Assignment | $0.0066 | 3,500 × $15 / 1M = $0.0525 | **$0.0591** | **$0.0816** |
| Parent Companion | $0.0066 | 1,800 × $15 / 1M = $0.0270 | **$0.0336** | **$0.0426** |
| Quiz | 2,200 × $0.15 / 1M = $0.00033 | 1,200 × $0.60 / 1M = $0.00072 | **$0.00105** | **$0.00141** |
| Worksheet | $0.00033 | 900 × $0.60 / 1M = $0.00054 | **$0.00087** | **$0.00117** |

**Observations:**
- Sonnet long-form artifacts are **~70× more expensive** per call than GPT-4o-mini short-form. This validates the locked routing rule.
- Study Guide P95 (**$0.1041**) **exceeds** the originally-considered $0.10 cap — the recommended cap (§8) is therefore **$0.12** to provide ~15% headroom above Study Guide P95. M1-E dashboard alerts at $0.10 typical → $0.12 hard cap.
- Parent Companion ($0.034) is cheaper than Study Guide because output is shorter and structured. A2 derivative cost is ~45% of the parent artifact — well within the locked plan's "≤60s, no extra surface" envelope.
- Quiz + Worksheet costs are **negligible** at <$0.002 each — they could be regenerated freely (e.g., new variant per student) with no material spend impact.

### 3.3 Sanity check vs CB-ASGF-001 anchor

CB-ASGF-001 = $0.106 per session. ASGF wraps **slide generation + concept extraction + intent classification + Flash Tutor quiz handoff** in a single user-visible flow. CB-CMCP-001 single-artifact Study Guide P95 = $0.1041 — within 2% of the ASGF anchor, which suggests the input + output token assumptions are well-calibrated. If real-world telemetry (M1-E) shows CMCP-001 spend ≥1.5× the ASGF anchor, prompt-bloat is the most likely cause; investigate envelope-resolver output size first.

---

## 4. Volume tier projections

Three tiers, taken from plan §9 acceptance gates and §1 (M4 pilot scope).

### 4.1 Tier A — Pilot (~500 artifacts total, M4 YRDSB pilot scope)

Single-board pilot. ~5 schools × ~15 teachers × ~7 artifacts each over the pilot window.

**Mix assumption:** 25% Study Guide, 20% Sample Test, 15% Assignment, 20% Parent Companion (derivatives), 10% Quiz, 10% Worksheet.

| Type | Count | $/artifact (typical) | Subtotal |
|---|---|---|---|
| Study Guide | 125 | $0.0741 | $9.26 |
| Sample Test | 100 | $0.0666 | $6.66 |
| Assignment | 75 | $0.0591 | $4.43 |
| Parent Companion | 100 | $0.0336 | $3.36 |
| Quiz | 50 | $0.00105 | $0.05 |
| Worksheet | 50 | $0.00087 | $0.04 |
| **Subtotal — generation only** | **500** | — | **$23.81** |

Plus embedding refresh (one-time at pilot start, ~$0.40 per §5) + GCP infra (per §6 below, ~$120/mo in pilot) → **~$144 total for pilot window** (call it $200 to absorb retries + voice-audit re-runs).

**Per-artifact average:** ~$0.05 (well under $0.12 cap; see §8).

### 4.2 Tier B — Single-board (~5,000 artifacts/month, mid-pilot ramp)

Single board scaled across ~50 teachers actively producing 100 artifacts/month each.

**Same mix; 10× volume:**

| Type | Count/mo | $/artifact (typical) | Subtotal/mo |
|---|---|---|---|
| Study Guide | 1,250 | $0.0741 | $92.63 |
| Sample Test | 1,000 | $0.0666 | $66.60 |
| Assignment | 750 | $0.0591 | $44.33 |
| Parent Companion | 1,000 | $0.0336 | $33.60 |
| Quiz | 500 | $0.00105 | $0.53 |
| Worksheet | 500 | $0.00087 | $0.44 |
| **Subtotal — generation only** | **5,000** | — | **$238.13 / month** |

Plus embedding refresh ($5/mo buffer — see §5) + GCP infra ($340/mo, see §6) → **~$583 / month**.

Annualized: **~$7,000 / yr** for a single-board pilot at sustained mid-pilot volume.

### 4.3 Tier C — Multi-board (~50,000 artifacts/month, Year 1 target)

3–5 boards, ~500 active teachers, 100 artifacts/month each.

**Same mix; 100× pilot volume:**

| Type | Count/mo | $/artifact (typical) | Subtotal/mo |
|---|---|---|---|
| Study Guide | 12,500 | $0.0741 | $926.25 |
| Sample Test | 10,000 | $0.0666 | $666.00 |
| Assignment | 7,500 | $0.0591 | $443.25 |
| Parent Companion | 10,000 | $0.0336 | $336.00 |
| Quiz | 5,000 | $0.00105 | $5.25 |
| Worksheet | 5,000 | $0.00087 | $4.35 |
| **Subtotal — generation only** | **50,000** | — | **$2,381.10 / month** |

Plus embedding refresh ($15/mo buffer — see §5) + GCP infra ($1,150/mo, see §6) → **~$3,546 / month**.

Annualized: **~$42,500 / yr** at Year 1 target volume.

### 4.4 Tier summary

| Tier | Artifacts/mo | Generation $/mo | Embed buffer $/mo[^1] | GCP $/mo | **Total $/mo** | $/artifact blended |
|---|---|---|---|---|---|---|
| A — Pilot | 500 (window) | $24 | $0.40 | $120 | **~$144** | $0.29 (front-loaded fixed cost) |
| B — Single-board | 5,000 | $238 | $5 | $340 | **~$583** | $0.117 |
| C — Multi-board | 50,000 | $2,381 | $15 | $1,150 | **~$3,546** | $0.071 |

[^1]: Embedding **actual** spend rounds to ~$0.20/yr at all tiers (see §5). The "embed buffer" column is a conservative budget placeholder for unforeseen re-embed work (e.g., mid-year Ministry curriculum revision affecting >25% of expectations); it is **not** a recurring AI spend line. The **Total $/mo** column **includes** the buffer for budget-conservative planning — true forecast spend is ~$5-15/mo lower per tier. Drop these lines from year-2+ budget once telemetry confirms refresh cadence.

**Per-artifact blended cost decreases with scale** — fixed GCP infra amortizes across more generations. The pilot tier looks expensive per-artifact but the absolute spend is trivial; the multi-board tier is where unit economics start to matter.

---

## 5. Embedding refresh cost

Per locked plan §M0-B-4: `text-embedding-3-small` over the CEG, ~2,000 expectations (Gr 1–8 Math, Lang, Sci, Soc Studies — Phase 1 seed scope).

**Per-expectation token estimate:** ~250 tokens (SE descriptor + sample indicators + Ministry code + grade + strand metadata).

**One-time backfill cost:**
- 2,000 SEs × 250 tokens = **500,000 tokens**
- 500,000 × $0.02 / 1M = **$0.01**

Yes — one cent for the entire CEG backfill. Embeddings are extremely cheap relative to generation; they are not a meaningful cost line.

**Periodic refresh trigger:** Ministry curriculum revisions (per locked D9=B severity classifier, only `scope_substantive` revisions trigger re-embed).

**Refresh cadence assumption:** ~2 Ministry revisions/year affecting ~10% of expectations on average → 200 SEs × 250 tokens × 2 = 100,000 tokens / year = **$0.002 / yr**.

**Class-context envelope embeddings (M1-B) — separate budget line:** the class-context resolver may embed teacher-email digests + announcement summaries to do similarity search against artifact library matches. Estimate: 50 active teachers × 4 envelopes/wk × 1,000 tokens × 52 wk = ~10M tokens/yr = **$0.20/yr**. Still negligible.

**Conclusion:** Embedding cost is **lost in rounding** at all three volume tiers. The $0.40/$5/$15 monthly embedding lines in §4 are budget placeholders for unforeseen re-embed work, not a real recurring spend.

---

## 6. GCP infrastructure cost (3 tiers)

Estimates assume locked plan §M2-A architecture: Cloud Run for CGP (Curriculum Generation Pipeline) + MCP server (per D1=C, end-user MCP only at M2; board MCP deferred), Cloud SQL HA for Postgres (CEG + content_artifacts), Cloud Storage for source PDFs + generated artifact JSON, Cloud Monitoring for SLO dashboards (locked plan §1E-2).

### Tier A — Pilot (~500 artifacts over pilot window, ~30 days)

| Service | Usage | $/mo |
|---|---|---|
| Cloud Run — CGP service | ~500 generations × 25s P95 × 2 vCPU + 4GB → ~7 vCPU-hours; ~1M req-secs | $20 |
| Cloud Run — MCP server | <100 req/day; mostly idle | $5 |
| Cloud SQL — `db-custom-2-7680` HA | Always-on (HA already required for prod) | $80 |
| Cloud Storage — source PDFs (Ministry + teacher) | ~5GB | $0.10 |
| Cloud Storage — generated artifacts | ~500 × ~50KB = 25MB | <$0.01 |
| Cloud Monitoring + Logging | Default tier | $10 |
| Egress | Negligible (artifacts stay in-region) | $5 |
| **Total** | — | **~$120 / month** |

### Tier B — Single-board (5,000 artifacts/month)

| Service | Usage | $/mo |
|---|---|---|
| Cloud Run — CGP service | ~5,000 × 25s × 2 vCPU = ~70 vCPU-hours; min-instances=1 to cut cold-start | $80 |
| Cloud Run — MCP server | ~500 req/day; min-instances=1 | $40 |
| Cloud SQL — same HA tier | Same | $80 |
| Cloud Storage | ~50GB source + ~250MB artifacts | $1 |
| Cloud Monitoring + Logging | More log volume | $30 |
| Egress | LTI link-out + parent app fetches | $15 |
| Cloud Run — embeddings worker | Periodic, low | $5 |
| Buffer for autoscale spikes | — | $89 |
| **Total** | — | **~$340 / month** |

### Tier C — Multi-board (50,000 artifacts/month)

| Service | Usage | $/mo |
|---|---|---|
| Cloud Run — CGP service | ~50,000 × 25s × 2 vCPU = ~700 vCPU-hours; autoscale to ~20 max instances | $400 |
| Cloud Run — MCP server | ~5,000 req/day across boards (per D1=C end-user MCP, plus pilot board service-account traffic) | $200 |
| Cloud SQL — bump to `db-custom-4-15360` HA | Higher connection / IOPS load | $260 |
| Cloud Storage | ~500GB source + ~2.5GB artifacts | $10 |
| Cloud Monitoring + Logging | Dashboards + 5min SLO alerts | $80 |
| Egress | LTI + Parent Companion fetches across 3-5 boards | $100 |
| Cloud Run — embeddings worker | Same | $5 |
| Buffer for autoscale spikes / failovers | — | $95 |
| **Total** | — | **~$1,150 / month** |

**Note on Cloud SQL sizing:** the existing `classbridge` Cloud SQL instance already serves dev-03 and is HA — Tier A/B can reuse it without bumping the SKU. Tier C **does** need a SKU bump (db-custom-4-15360), called out as a Year 1 capex item in §8.

**Note on shared-infra accounting:** §6 prices Cloud SQL HA, Cloud Monitoring base tier, and a portion of Cloud Run cold-start at on-demand list price. Some of this is **already paid** by dev-03's existing classbridge service — the **incremental** GCP cost from CMCP-001 at Tier B is closer to **~$80-100/mo** (just CGP + MCP Cloud Run + storage delta + log volume), not the full $340/mo. The §4.4 blended $/artifact figures conservatively allocate the full GCP line; true marginal CMCP-001 cost is ~30-50% lower at Tier B and ~25-35% lower at Tier C. Use §4.4 totals for budget planning; use the marginal estimate for unit-economics conversations with finance.

---

## 7. AI cost as % of B2C revenue

### 7.1 Anchor: CB-ASGF-001 baseline

CB-ASGF-001 epic body §"Cost Model":
- Cost per ASGF session: **$0.106**
- Cost per Flash Tutor session: **$0.013**
- Combined cost per student/month: **~$1.28**
- AI cost as % of B2C revenue: **~36%** (mitigation needed pre-M5c)

The 36% number sets a **soft ceiling** for the CB-CMCP-001 rollout: any feature that pushes the combined AI-cost % above 36% is regression on already-strained unit economics. Per-feature AI spend must be additive but **bounded** so the combined % stays ≤36%.

### 7.2 CB-CMCP-001 projection — added AI cost per active student/month

Assumption: an active student in M4+ pilot consumes CMCP-001 artifacts via teacher-published Bridge cards / DCI nudges / PEDI digest (per A4 surface delivery).

**Class-size amortization assumption:** ~25 students per class (Ontario Gr 4-8 average; Gr 1-3 cap is 20). Per-student cost scales inversely with this number — smaller classes = higher per-student cost.

Average exposure:

- 4 Study Guides / month consumed (1/wk) — most are reused across students, so per-student amortized cost is the artifact cost ÷ ~25 students consuming it = $0.0741 / 25 = **$0.0030 / student**
- 4 Quizzes / month — short-form, near-zero cost — **$0.0001 / student**
- 2 Worksheets / month — **<$0.0001 / student**
- 1 Sample Test / month — $0.0666 / 25 = **$0.0027 / student**
- 4 Parent Companions / month (one per study guide for parent-side delivery) — $0.0336 amortized = **$0.0013 / student**

**Added AI cost per active student/month from CB-CMCP-001:** ~**$0.007** (sum of bullets above; rounded up to **~$0.01** in the §7.3 table for combined-cost reporting).

This is **deliberately small** because the locked plan amortizes generation across classrooms — a Study Guide generated once for a Grade 5 Math class is consumed by ~25 students at zero marginal AI cost.

### 7.3 Combined AI cost per student/month

| Source | $/student/mo |
|---|---|
| ASGF + Flash Tutor (existing CB-ASGF-001) | $1.28 |
| **CB-CMCP-001 added (this PRD)** | **+$0.01** |
| **Combined** | **~$1.29** |

The CMCP-001 additive cost is **<1% of the existing baseline**. The 36%-of-revenue ceiling is **not threatened** by CMCP-001 specifically.

**However:** if amortization assumption breaks (e.g., teachers regenerate per-student variants instead of reusing), per-student CMCP cost balloons by ~25× to **$0.18 / student / mo**, which would push combined AI cost to ~$1.46 and AI-cost-% from 36% → ~41%. The per-artifact spend cap (§8) plus the M1-E dashboards are the guardrails that prevent this.

---

## 8. Per-artifact spend cap recommendation

### 8.1 Recommended cap

**$0.12 hard cap per artifact generation.** Bail-out logic in the guardrail engine (M1-A-1) before the LLM call:

```
estimated_cost = (estimated_input_tokens × input_rate) + (max_output_tokens × output_rate)
if estimated_cost > $0.12:
    return AlignmentReport(
        state=BAILED_OUT_SPEND_CAP,
        reason="Estimated spend $X.XX exceeds $0.12 cap. Reduce envelope or split request.",
    )
```

> **Note on `BAILED_OUT_SPEND_CAP` state:** This state is **not yet** in the locked DD §6.1 state machine. Adding it is a follow-up requirement for M1-A-3 (state machine implementation). Track as part of M1-A-3 stripe scope.

### 8.2 Rationale

- **$0.12 = Study Guide P95 ($0.1041) + ~15% headroom.** This is the most expensive artifact at the upper end of typical token usage; the cap leaves room for normal P95 generations to complete while flagging prompt bloat or runaway output. (An earlier draft proposed $0.10, but Study Guide P95 = $0.1041 sits above that — every typical-fullness Study Guide would have bailed out, breaking the most common path. The $0.12 cap fixes this.)
- **At Tier C volume (50k/mo), even a 5% bail-out rate saves ~$140/mo** — small in absolute terms but a meaningful early-warning signal that prompts are drifting.
- **Hard cap, not soft warning.** A soft warning + log entry is insufficient because the LLM call has already happened and the money is spent. The cap must be checked **before** the API call.

### 8.3 Cap enforcement points

1. **Pre-call estimator** in `app/services/cmcp/guardrail_engine.py` (M1-A-1) — uses `tiktoken` for OpenAI input estimate and Anthropic's published count-tokens API for Sonnet. Bail before issuing the LLM call.
2. **Per-day per-teacher quota** (recommended secondary cap): max 50 artifacts/day/teacher → ~$5/day max per teacher. Prevents a single buggy automation loop from running up Sonnet spend overnight.
3. **Per-month per-board ceiling** (M2 milestone): board-admin dashboard shows monthly spend; soft alert at 80% of board budget (set per partnership agreement); hard freeze at 100%. Defers full enforcement to M2 board MCP work.

### 8.4 Bail-out telemetry

`cmcp.spend_cap.bailout_count` metric stamped with `content_type` + `board_id` + `estimated_cost` (board_id has cardinality ≤5, no PII concerns; per-teacher detail lives in audit logs not metrics). M1-E dashboard shows weekly bail-out rate by content type. **Acceptance threshold:** bail-out rate ≤1% per content type at steady state. Above 1% indicates the cap is too tight for the prompt design and needs re-tuning (or the prompt is bloated and needs fixing — the dashboard makes the right call obvious).

---

## 9. Risks + mitigations

This section ties directly back to plan §10 risk register. The cost-overrun row reads:

> | Cost overrun mid-M1 | Medium | Medium | D8=B cost model; per-artifact spend cap as backstop |

Below is the **expanded** mitigation chain that backs that row.

| Risk | Likelihood | Impact | Mitigation chain (this doc) |
|---|---|---|---|
| Sonnet rate increase (provider-side) | Low | Medium | §2 rate card re-validated at every M-gate; M1-E dashboard alerts on $/artifact >1.5× baseline; routing fallback to Haiku for non-voice-critical artifacts evaluated at M3 |
| Prompt bloat (envelope grows over time) | Medium | Medium | §8 per-artifact $0.12 cap with bail-out telemetry; envelope-resolver size cap of 800 tokens (M1-B-2); weekly review of average input tokens vs §3.1 baseline |
| Per-student amortization breaks (teachers regen per-student variants) | Medium | Medium-High | §7.3 — would push AI cost % from 36% → ~41%. Mitigation: M1-E surfaces per-class regeneration count; product decision needed before allowing >2 regenerations per artifact |
| Volume forecast wrong (multi-board ramps faster than Year 1 target) | Low | Medium | Cloud SQL bump triggered at 30k/mo (75% of Tier C); Cloud Run autoscale max 20 already in place per plan §10 row 5 |
| Embedding refresh becomes more frequent than 2/yr | Low | Low | §5 — even 12 refreshes/yr stays under $0.05/yr; not a real risk |
| Parent Companion cost spike (voice overlay grows) | Low | Low | §3.2 — Sonnet route is already the most expensive path; cap at 2,400 P95 output tokens; locked A2 amendment forbids un-bounded expansion |
| GCP egress > forecast | Low | Low | LTI link-out + Parent Companion fetches stay in-region (us-central1); §6 Tier C egress line already includes 100 GB/mo headroom |

**Cross-link to plan §10:** if any of the above triggers, the corresponding row in plan §10 risk register should be updated with the actual incident + remediation. This doc is the source of truth for cost assumptions; plan §10 is the source of truth for risk-level + mitigation status.

---

## 10. Open questions

The numbers above are **good enough to commit M0 → M1**. They are not load-tested. The following items will be answered by M1-E telemetry or by external lookups; flagged here so the doc is honest about its known unknowns.

1. **Real Ministry PDF token counts.** The 2,000-expectations / 250-tokens-per-SE estimate (§5) is from a sample of 50 SEs across Math + Lang. Full-Phase-1 backfill (all 4 strands) may shift the average up or down by up to 30%. Negligible cost impact, but flagged for the M0-B-5 audit.
2. **Class-context envelope real fullness distribution.** §3.1 assumes ~800 tokens cap with average ~500. Real distribution unknown until M1-B-2 ships and the resolver sees production teacher data. If average is materially higher (e.g., 1,200 tokens) all input-token figures need a +50% bump.
3. **Sonnet vs Haiku quality break-even for Parent Companion.** §3.2 keeps Parent Companion on Sonnet for voice-quality reasons. A2 voice audit (M1-C-3) is the gate. If audit passes for Haiku at 5× lower cost, the Parent Companion line drops from $0.034 → $0.007 per artifact. Re-validate after M1-C-3.
4. **Provider rate cards.** §2 reflects current published rates. Anthropic and OpenAI have both adjusted long-form pricing within recent months; commit to a re-validation at M1 → M2 gate and at M2 → M3 gate.
5. **Per-board service-account traffic for end-user MCP.** §6 Tier C MCP line ($200/mo) is a guess based on D1=C scoping (board MCP deferred, end-user MCP only). If D1 reverses post-M2, MCP line could 3-5× to $600-1000/mo. Tracked under plan §10 row 5 (MCP rate-limit risk).
6. **Cache-hit assumptions for Sonnet prompts.** Sonnet prompt caching can reduce input-token cost by up to 90% for stable system prompts + voice overlays. §3.2 figures **do not assume any caching** (worst-case cost). If M1-A wires caching correctly, real Tier C generation cost may drop from $2,381 → $1,400-1,800 / month. Deferred until M1 telemetry confirms cache-hit rates.
7. **OCT reviewer cost (M0-C-1).** This is a non-LLM cost not modeled here; tracked under plan §M0-C-1 ("hire / contract paid OCT-certified curriculum reviewer ~80h Phase 1"). Founder-owned line item, not engineering budget.
8. **Voice-overlay real token sizes.** §3.1 assumes 250 tokens for the active voice variant. Existing CB-TUTOR-001/002 voice files (`arc_voice_v1.txt`, `professional_v1.txt`, `parent_coach_v1.txt`) per locked plan §1C-1 may be larger (600-1000 tokens for richer voice prompts is common). Measure at M1-C-1 stripe; if average is materially higher, all input-cost figures need a +5-10% bump and Sonnet prompt-caching (Open Question #6) becomes more attractive.

---

## 11. Change log

| Date | Author | Change |
|---|---|---|
| 2026-04-27 | Engineering | Initial draft (M0-D 0D-1) — covers per-content-type cost, 3 volume tiers, embedding refresh, GCP infra, AI-% anchor, spend cap, risks, open questions |
| 2026-04-27 | Engineering (PR #4418 review pass 1) | Raised spend cap $0.10 → **$0.12** to give 15% headroom above Study Guide P95 ($0.1041); reconciled §4.4 embed-buffer column with §5 (footnote labels it as buffer, not real spend); class-size assumption (~25 students) called out explicitly in §7.2; §7.3 cross-reference clarified between $0.007 and $0.01 rounding; §6 shared-infra accounting note (incremental cost is ~30-50% lower than full table); Open Question #8 added (voice overlay real token sizes); §2 rate card pinned to 2026-04-27 |
| 2026-04-27 | Engineering (PR #4418 review pass 2) | §9 risk row: stale $0.10 cap reference fixed → $0.12; §4.2/§4.3 narrative "amortized" → "buffer (see §5)" to match §4.4 footnote framing; §4.4 footnote clarifies that Total $/mo column includes buffer for conservative planning; §8.4 telemetry label `teacher_id` → `board_id` (lower cardinality + no PII concerns) |

---

*End of document.*
