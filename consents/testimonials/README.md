# Testimonials Consent Process

**Feature:** CB-DEMO-001 — Proof Wall testimonials (`frontend/public/content/proof-wall/testimonials.json`).

**Rule:** No testimonial is published on classbridge.ca without a signed consent artefact stored in this directory. Placeholder entries in `testimonials.json` with `"status": "pending_consent"` are allowed during build but MUST NOT be swapped for real quotes until consent is on file.

---

## 1. How consent is collected

1. We draft the exact quote we want to publish, along with the attributed role and city (e.g. "parent, Markham").
2. We send the person a plain-language consent request by email (template below). No marketing-speak, no legalese.
3. The person replies "I consent" (or returns a signed PDF) with:
   - The exact quote they approve.
   - Role + city they are willing to be attributed by.
   - Confirmation that they are over 18 and consenting on their own behalf. For student quotes, a parent or guardian consents on the student's behalf.
4. We file the reply (see Storage below).
5. Only then do we replace the placeholder in `testimonials.json`.

### Email template

```
Subject: Permission to use your words on ClassBridge

Hi [Name],

You mentioned [summary of the feedback] — would you be willing to let us share a
short version on classbridge.ca? Here's exactly what we'd publish:

  "[EXACT QUOTE]"
  — [role], [city]

If you're okay with this, just reply "I consent" and we'll take that as
permission. If you'd rather we change the wording, the role, or the city —
or decline entirely — that's completely fine. You can withdraw permission at
any time by replying to this thread.

Thanks,
ClassBridge
```

---

## 2. Where consent artefacts are stored

- **Path:** `consents/testimonials/<id>.{eml,pdf}` where `<id>` matches the `id` field in `testimonials.json` (e.g. `t1.eml`).
- **Format:** Either the raw email reply (saved as `.eml`) or a signed PDF.
- **Checked-in or private?** Consent artefacts contain personal information and MUST NOT be committed to the public repo. Store them in the private ClassBridge Google Drive folder `ClassBridge / Legal / Testimonials Consent /` and reference them here by filename only.
- **Index:** Maintain `consents/testimonials/INDEX.md` (private, not committed) listing `id → artefact filename → date → reviewer initials`.

---

## 3. Retention policy

- **Active:** Keep consent artefacts for as long as the quote is published on classbridge.ca.
- **Post-removal:** Keep for 1 year after the quote is removed, to defend against any disputed publication claim.
- **Then:** Securely delete the artefact. Update `INDEX.md` with a deletion note.

---

## 4. Revocation process

If a person asks to withdraw consent:

1. Within 24 hours: change the matching entry in `testimonials.json` to `"status": "pending_consent"` and replace the quote with `"[TBD — awaiting consent]"`. Ship the change.
2. Record the revocation in `INDEX.md` with the date and reason (if given).
3. Keep the original consent artefact for the 1-year retention window; do not delete it immediately, because we may need to prove the quote was previously authorized.
4. Confirm back to the person that the quote has been removed.

---

## 5. Launch gate (May 13, 2026)

Any testimonial that is still `pending_consent` on launch day stays as a placeholder — it does NOT ship with a real quote. The Proof Wall is designed to look legitimate with placeholders; do not fabricate quotes to fill the wall.
