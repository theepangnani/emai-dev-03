# ClassBridge Compliance Claims Audit

**Context:** Compliance badges shown on the CB-DEMO-001 Proof Wall (`frontend/public/content/proof-wall/compliance-badges.json`) must each be backed by a defensible claim, justification, and artefact. If a badge cannot be justified, mark it "pending" and remove it before launch.

**Launch gate:** Any badge still marked "pending" on May 13, 2026 must be removed from the Proof Wall before the A/B test starts.

**Dependency:** Each badge's `href` in `compliance-badges.json` points to an anchor on `/compliance` (e.g., `/compliance#hosting`). That page must exist before Proof Wall ships or clicks will 404 — tracked in issue #3618 (blocker for FE4 #3610).

**Scope:** Public-facing marketing claims only. Internal DPIA and board-procurement responses live under `docs/DTAP_VASP_Compliance_Report_ClassBridge.docx`.

---

## Badges on the Proof Wall

### 1. `canada-hosted` — "Hosted in Canada (GCP Toronto)"

- **Claim:** All ClassBridge application servers and the primary PostgreSQL database run in Google Cloud's `northamerica-northeast2` region (Toronto).
- **Justification:** Cloud Run service `classbridge` and Cloud SQL instance are both deployed to `northamerica-northeast2`. Verifiable via `gcloud` console.
- **Artefact:** `gcloud run services describe classbridge --region=northamerica-northeast2` output; Cloud SQL instance region setting.
- **Caveat:** Cloud storage buckets and backups must remain in-region. Any expansion to US regions requires updating this claim.
- **Status:** Supportable.

### 2. `mfippa` — "MFIPPA-aligned"

- **Claim:** ClassBridge's handling of student and parent personal information is aligned with Ontario's Municipal Freedom of Information and Protection of Privacy Act as applied to school boards.
- **Justification:** Data minimization, access controls (RBAC), audit logging, and data-residency choices map to MFIPPA principles. Formal alignment checklist is tracked in `docs/DTAP_VASP_Compliance_Report_ClassBridge.docx`.
- **Artefact:** DTAP/VASP compliance report; internal privacy impact assessment (in progress).
- **Caveat:** "Aligned" is the honest word here. We are not certified, and MFIPPA certification is not a public regulator-issued program. Do not upgrade this language to "MFIPPA-certified".
- **Status:** Supportable with current language ("MFIPPA-aligned"). Do not strengthen.

### 3. `pipeda` — "PIPEDA-compliant"

- **Claim:** ClassBridge's collection, use, and disclosure of personal information follows the ten fair-information principles of Canada's Personal Information Protection and Electronic Documents Act.
- **Justification:** Privacy policy, consent flows, access/correction endpoints, breach-notification process, and data-retention schedule are implemented. Internal DPIA maps features to PIPEDA principles.
- **Artefact:** Privacy policy (`/privacy` page); DPIA section in `docs/DTAP_VASP_Compliance_Report_ClassBridge.docx`; breach-notification runbook in `docs/INCIDENT_RESPONSE.md`.
- **Caveat:** PIPEDA compliance is self-attested under Canadian law; there is no government certification. Keep language factual.
- **Status:** Supportable.

### 4. `canadian-stack` — "Canadian-hosted stack"

- **Claim:** Core infrastructure vendors (compute, database, storage, email) are operated from Canadian regions where configurable, and ClassBridge itself is a Canadian company.
- **Justification:** GCP Toronto for app + DB (see #1); SendGrid sub-processor agreement in place; Twilio Canadian long-code +1 647-800-8533; ClassBridge Inc. incorporated in Ontario.
- **Artefact:** Vendor list with sub-processor regions (to be published alongside the privacy policy at `/compliance#stack`).
- **Caveat:** Some sub-processors (e.g. OpenAI/Anthropic for AI inference, SendGrid global relays) are not Canadian. This badge says "Canadian-hosted stack", not "100% Canadian sub-processors". Keep language precise.
- **Status:** Supportable with current language.

---

## Explicitly removed badges (for launch)

### `oecm` — "OECM procurement pathway"

- **Removed per mentor delta #7 (CB-DEMO-001 PRD v1.1 scope deltas).**
- **Reason:** We are not on the OECM VOR at time of launch. Replaced by `canadian-stack` until OECM is real and verifiable.
- **Re-add criteria:** OECM award letter or signed VOR agreement on file, plus public listing on `oecm.ca`.

---

## Review process

- Any change to `frontend/public/content/proof-wall/compliance-badges.json` must be accompanied by an update to this file.
- Legal review required before adding a new badge.
- Badges must degrade gracefully: if an artefact becomes stale or a vendor changes region, the corresponding badge is removed from the JSON within 7 days.
