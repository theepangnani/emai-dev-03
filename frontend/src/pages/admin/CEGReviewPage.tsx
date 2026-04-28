/**
 * CB-CMCP-001 M0-B 0B-3b — Curriculum-admin review page (#4429).
 *
 * Route: /admin/ceg/review
 * RBAC: CURRICULUM_ADMIN only (gated by `<ProtectedRoute>` in App.tsx).
 * Feature flag: `cmcp.enabled` (frontend short-circuits when OFF; backend
 *               enforces independently via `require_curriculum_admin_with_flag`).
 *
 * Calls the four backend endpoints shipped by stripe 0B-3a (PR #4432):
 *   GET    /api/ceg/admin/review/pending
 *   POST   /api/ceg/admin/review/{id}/accept
 *   POST   /api/ceg/admin/review/{id}/reject
 *   PATCH  /api/ceg/admin/review/{id}
 *
 * Plan refs: §6 (UI/UX strategy), §6.4 (curriculum-code chip primitive),
 *            §7 M0-B 0B-3b (this stripe). No new design tokens introduced —
 *            inherits Bridge ivory + rust + Fraunces palette.
 */
import { useEffect, useMemo, useState } from 'react';
import { useFeatureFlagState } from '../../hooks/useFeatureToggle';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import {
  cegAdminReviewApi,
  type CEGEditExpectationPayload,
  type CEGPendingExpectation,
} from '../../api/cegAdminReview';
import './CEGReviewPage.css';

const EXPECTATION_TYPE_OVERALL = 'overall';
const EXPECTATION_TYPE_SPECIFIC = 'specific';

const MINISTRY_CODE_PATTERN = /^[A-Z]\d+(\.\d+)?$/;
const MIN_PARAPHRASE_LEN = 20;

const GRADE_OPTIONS = Array.from({ length: 12 }, (_, i) => i + 1);

interface EditFormState {
  description: string;
  ministry_code: string;
  strand_id: string;
  expectation_type: string;
  review_notes: string;
}

function CurriculumCodeChip({
  code,
  variant,
}: {
  code: string;
  variant: 'ministry' | 'cb';
}) {
  // Per plan §6.4: distinct icon + label, NOT just color (WCAG 1.4.1).
  const icon = variant === 'ministry' ? 'M' : 'CB';
  const ariaLabel =
    variant === 'ministry' ? `Ministry code: ${code}` : `ClassBridge code: ${code}`;
  return (
    <span
      className={`cb-curriculum-chip cb-curriculum-chip--${variant}`}
      aria-label={ariaLabel}
    >
      <span className="cb-curriculum-chip-icon" aria-hidden="true">
        {icon}
      </span>
      <span>{code}</span>
    </span>
  );
}

function StateChip({ state }: { state: string }) {
  const cls =
    state === 'accepted'
      ? 'ceg-state-chip--accepted'
      : state === 'rejected'
        ? 'ceg-state-chip--rejected'
        : 'ceg-state-chip--pending';
  return <span className={`ceg-state-chip ${cls}`}>{state}</span>;
}

export function CEGReviewPage() {
  const { enabled: cmcpEnabled, isLoading: flagLoading } =
    useFeatureFlagState('cmcp.enabled');

  const [items, setItems] = useState<CEGPendingExpectation[]>([]);
  const [accepted, setAccepted] = useState<CEGPendingExpectation[]>([]);
  const [rejected, setRejected] = useState<CEGPendingExpectation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyIds, setBusyIds] = useState<Set<number>>(new Set());

  const [gradeFilter, setGradeFilter] = useState<string>('');
  const [subjectFilter, setSubjectFilter] = useState<string>('');
  const [strandFilter, setStrandFilter] = useState<string>('');

  const [editTarget, setEditTarget] = useState<CEGPendingExpectation | null>(null);

  // Initial load
  useEffect(() => {
    if (!cmcpEnabled) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await cegAdminReviewApi.listPending();
        if (cancelled) return;
        setItems(data);
      } catch (e) {
        if (cancelled) return;
        const msg =
          e && typeof e === 'object' && 'message' in e
            ? String((e as { message: unknown }).message)
            : 'Failed to load pending expectations.';
        setError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [cmcpEnabled]);

  // Filter options derived from the current dataset (and accepted/rejected
  // for completeness, since filter chips should also work over historical
  // counts). We only filter the visible *pending* table — accept/reject
  // counts in the header always reflect totals.
  const subjectOptions = useMemo(() => {
    const ids = new Set(items.map((r) => r.subject_id));
    return Array.from(ids).sort((a, b) => a - b);
  }, [items]);

  const strandOptions = useMemo(() => {
    const ids = new Set(items.map((r) => r.strand_id));
    return Array.from(ids).sort((a, b) => a - b);
  }, [items]);

  const filteredItems = useMemo(() => {
    return items.filter((row) => {
      if (gradeFilter && String(row.grade) !== gradeFilter) return false;
      if (subjectFilter && String(row.subject_id) !== subjectFilter) return false;
      if (strandFilter && String(row.strand_id) !== strandFilter) return false;
      return true;
    });
  }, [items, gradeFilter, subjectFilter, strandFilter]);

  function markBusy(id: number, busy: boolean) {
    setBusyIds((prev) => {
      const next = new Set(prev);
      if (busy) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function removePending(id: number) {
    setItems((prev) => prev.filter((r) => r.id !== id));
  }

  async function handleAccept(row: CEGPendingExpectation) {
    markBusy(row.id, true);
    setError(null);
    // Optimistic: remove from pending list immediately, snapshot to roll back
    // if the request fails.
    const snapshot = items;
    removePending(row.id);
    try {
      const updated = await cegAdminReviewApi.accept(row.id);
      setAccepted((prev) => [updated, ...prev]);
    } catch (e) {
      // Roll back optimistic removal.
      setItems(snapshot);
      const msg =
        e && typeof e === 'object' && 'message' in e
          ? String((e as { message: unknown }).message)
          : 'Accept failed.';
      setError(msg);
    } finally {
      markBusy(row.id, false);
    }
  }

  async function handleReject(row: CEGPendingExpectation) {
    markBusy(row.id, true);
    setError(null);
    const snapshot = items;
    removePending(row.id);
    try {
      const updated = await cegAdminReviewApi.reject(row.id);
      setRejected((prev) => [updated, ...prev]);
    } catch (e) {
      setItems(snapshot);
      const msg =
        e && typeof e === 'object' && 'message' in e
          ? String((e as { message: unknown }).message)
          : 'Reject failed.';
      setError(msg);
    } finally {
      markBusy(row.id, false);
    }
  }

  async function handleEditSubmit(payload: CEGEditExpectationPayload) {
    if (!editTarget) return;
    const id = editTarget.id;
    markBusy(id, true);
    setError(null);
    try {
      const updated = await cegAdminReviewApi.edit(id, payload);
      setItems((prev) =>
        prev.map((r) => (r.id === id ? { ...r, ...updated } : r)),
      );
      setEditTarget(null);
    } catch (e) {
      const msg =
        e && typeof e === 'object' && 'message' in e
          ? String((e as { message: unknown }).message)
          : 'Edit failed.';
      setError(msg);
    } finally {
      markBusy(id, false);
    }
  }

  // ── Feature-flag OFF / hydrating ────────────────────────────────────
  if (flagLoading) {
    return (
      <div className="ceg-review-page" data-testid="ceg-review-page">
        <p className="ceg-review-state-msg">Loading…</p>
      </div>
    );
  }

  if (!cmcpEnabled) {
    return (
      <div className="ceg-review-page" data-testid="ceg-review-page">
        <div className="ceg-review-disabled" role="status">
          <h2>Curriculum review is currently disabled</h2>
          <p>Contact an admin to enable the CB-CMCP-001 feature flag.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="ceg-review-page" data-testid="ceg-review-page">
      <header className="ceg-review-header">
        <div>
          <div className="ceg-review-kicker">CB-CMCP-001 / Curriculum Review</div>
          <h1 className="ceg-review-title">CEG expectation review</h1>
        </div>
        <div className="ceg-review-counts" aria-label="Review counts">
          <div className="ceg-review-count">
            <span>Pending</span>
            <span className="ceg-review-count-value">{items.length}</span>
          </div>
          <div className="ceg-review-count">
            <span>Accepted</span>
            <span className="ceg-review-count-value">{accepted.length}</span>
          </div>
          <div className="ceg-review-count">
            <span>Rejected</span>
            <span className="ceg-review-count-value">{rejected.length}</span>
          </div>
        </div>
      </header>

      <div className="ceg-review-filters" role="region" aria-label="Filters">
        <div className="ceg-review-filter-group">
          <label
            htmlFor="ceg-filter-grade"
            className="ceg-review-filter-label"
          >
            Grade
          </label>
          <select
            id="ceg-filter-grade"
            className="ceg-review-filter-select"
            value={gradeFilter}
            onChange={(e) => setGradeFilter(e.target.value)}
          >
            <option value="">All grades</option>
            {GRADE_OPTIONS.map((g) => (
              <option key={g} value={String(g)}>
                Grade {g}
              </option>
            ))}
          </select>
        </div>
        <div className="ceg-review-filter-group">
          <label
            htmlFor="ceg-filter-subject"
            className="ceg-review-filter-label"
          >
            Subject
          </label>
          <select
            id="ceg-filter-subject"
            className="ceg-review-filter-select"
            value={subjectFilter}
            onChange={(e) => setSubjectFilter(e.target.value)}
          >
            <option value="">All subjects</option>
            {subjectOptions.map((id) => (
              <option key={id} value={String(id)}>
                Subject #{id}
              </option>
            ))}
          </select>
        </div>
        <div className="ceg-review-filter-group">
          <label
            htmlFor="ceg-filter-strand"
            className="ceg-review-filter-label"
          >
            Strand
          </label>
          <select
            id="ceg-filter-strand"
            className="ceg-review-filter-select"
            value={strandFilter}
            onChange={(e) => setStrandFilter(e.target.value)}
          >
            <option value="">All strands</option>
            {strandOptions.map((id) => (
              <option key={id} value={String(id)}>
                Strand #{id}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="ceg-review-error" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <p className="ceg-review-state-msg">Loading pending expectations…</p>
      ) : filteredItems.length === 0 ? (
        <div className="ceg-review-state-msg" role="status">
          <h3>No pending expectations</h3>
          <p>
            {items.length === 0
              ? 'The review queue is empty. New extractions will appear here for sign-off.'
              : 'No pending expectations match the current filters.'}
          </p>
        </div>
      ) : (
        <div className="ceg-review-table-wrap">
          <table className="ceg-review-table" aria-label="Pending expectations">
            <thead>
              <tr>
                <th scope="col">CB code</th>
                <th scope="col">Ministry code</th>
                <th scope="col">Type</th>
                <th scope="col">Strand</th>
                <th scope="col">Grade</th>
                <th scope="col">Subject</th>
                <th scope="col">State</th>
                <th scope="col">Paraphrase</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((row) => {
                const busy = busyIds.has(row.id);
                return (
                  <tr key={row.id} data-testid={`ceg-row-${row.id}`}>
                    <td>
                      {row.cb_code ? (
                        <CurriculumCodeChip code={row.cb_code} variant="cb" />
                      ) : (
                        <span aria-label="No ClassBridge code">—</span>
                      )}
                    </td>
                    <td>
                      <CurriculumCodeChip
                        code={row.ministry_code}
                        variant="ministry"
                      />
                    </td>
                    <td>
                      {row.expectation_type === EXPECTATION_TYPE_OVERALL
                        ? 'OE'
                        : 'SE'}
                    </td>
                    <td>#{row.strand_id}</td>
                    <td>{row.grade}</td>
                    <td>#{row.subject_id}</td>
                    <td>
                      <StateChip state={row.review_state} />
                    </td>
                    <td className="ceg-review-paraphrase">{row.description}</td>
                    <td>
                      <div className="ceg-review-actions">
                        <button
                          type="button"
                          className="ceg-action-btn ceg-action-btn--accept"
                          onClick={() => handleAccept(row)}
                          disabled={busy}
                          aria-label={`Accept expectation ${row.ministry_code}`}
                        >
                          Accept
                        </button>
                        <button
                          type="button"
                          className="ceg-action-btn ceg-action-btn--reject"
                          onClick={() => handleReject(row)}
                          disabled={busy}
                          aria-label={`Reject expectation ${row.ministry_code}`}
                        >
                          Reject
                        </button>
                        <button
                          type="button"
                          className="ceg-action-btn"
                          onClick={() => setEditTarget(row)}
                          disabled={busy}
                          aria-label={`Edit expectation ${row.ministry_code}`}
                        >
                          Edit
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {editTarget && (
        <EditModal
          target={editTarget}
          onCancel={() => setEditTarget(null)}
          onSubmit={handleEditSubmit}
        />
      )}
    </div>
  );
}

// ── Edit modal ────────────────────────────────────────────────────────

interface EditModalProps {
  target: CEGPendingExpectation;
  onCancel: () => void;
  onSubmit: (payload: CEGEditExpectationPayload) => Promise<void>;
}

function EditModal({ target, onCancel, onSubmit }: EditModalProps) {
  const trapRef = useFocusTrap(true, onCancel);
  const [form, setForm] = useState<EditFormState>({
    description: target.description,
    ministry_code: target.ministry_code,
    strand_id: String(target.strand_id),
    expectation_type: target.expectation_type,
    review_notes: target.review_notes ?? '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{
    description?: string;
    ministry_code?: string;
    strand_id?: string;
  }>({});

  function validate(): boolean {
    const next: typeof errors = {};
    if (!form.description || form.description.trim().length < MIN_PARAPHRASE_LEN) {
      next.description = `Paraphrase must be at least ${MIN_PARAPHRASE_LEN} characters.`;
    }
    if (!form.ministry_code || !MINISTRY_CODE_PATTERN.test(form.ministry_code)) {
      next.ministry_code =
        'Ministry code must match pattern like B2 or B2.1 (letter, digits, optional .digits).';
    }
    const strandNum = Number(form.strand_id);
    if (!form.strand_id || !Number.isInteger(strandNum) || strandNum <= 0) {
      next.strand_id = 'Strand must be a positive integer.';
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSave() {
    if (!validate()) return;
    setSubmitting(true);
    // Build the partial payload with ONLY changed fields. The backend
    // rejects empty bodies with 400, so by definition at least one field
    // must differ from the original — otherwise the form is a no-op and
    // we still send the description (the most-edited field) to keep UX
    // simple. But to honor "only touched fields", we diff explicitly.
    const payload: CEGEditExpectationPayload = {};
    if (form.description !== target.description) {
      payload.description = form.description.trim();
    }
    if (form.ministry_code !== target.ministry_code) {
      payload.ministry_code = form.ministry_code.trim();
    }
    const strandNum = Number(form.strand_id);
    if (strandNum !== target.strand_id) {
      payload.strand_id = strandNum;
    }
    if (form.expectation_type !== target.expectation_type) {
      payload.expectation_type = form.expectation_type;
    }
    const trimmedNotes = form.review_notes.trim();
    const originalNotes = (target.review_notes ?? '').trim();
    if (trimmedNotes !== originalNotes) {
      payload.review_notes = trimmedNotes;
    }
    if (Object.keys(payload).length === 0) {
      // Nothing changed — close without calling backend.
      setSubmitting(false);
      onCancel();
      return;
    }
    try {
      await onSubmit(payload);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="ceg-modal-overlay" role="presentation">
      <div
        ref={trapRef}
        className="ceg-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ceg-modal-title"
      >
        <h2 id="ceg-modal-title" className="ceg-modal-title">
          Edit expectation
        </h2>
        <p className="ceg-modal-subtitle">
          {target.cb_code ?? `#${target.id}`} · grade {target.grade}
        </p>

        <div className="ceg-modal-field">
          <label
            htmlFor="ceg-modal-description"
            className="ceg-modal-field-label"
          >
            Paraphrase
          </label>
          <textarea
            id="ceg-modal-description"
            className="ceg-modal-textarea"
            value={form.description}
            onChange={(e) =>
              setForm((f) => ({ ...f, description: e.target.value }))
            }
            aria-invalid={!!errors.description}
            aria-describedby={errors.description ? 'ceg-modal-description-err' : undefined}
          />
          {errors.description && (
            <span id="ceg-modal-description-err" className="ceg-modal-error">
              {errors.description}
            </span>
          )}
        </div>

        <div className="ceg-modal-field">
          <label
            htmlFor="ceg-modal-ministry"
            className="ceg-modal-field-label"
          >
            Ministry code
          </label>
          <input
            id="ceg-modal-ministry"
            type="text"
            className="ceg-modal-input"
            value={form.ministry_code}
            onChange={(e) =>
              setForm((f) => ({ ...f, ministry_code: e.target.value }))
            }
            aria-invalid={!!errors.ministry_code}
            aria-describedby={errors.ministry_code ? 'ceg-modal-ministry-err' : undefined}
          />
          {errors.ministry_code && (
            <span id="ceg-modal-ministry-err" className="ceg-modal-error">
              {errors.ministry_code}
            </span>
          )}
        </div>

        <div className="ceg-modal-field">
          <label
            htmlFor="ceg-modal-strand"
            className="ceg-modal-field-label"
          >
            Strand ID
          </label>
          <input
            id="ceg-modal-strand"
            type="number"
            min="1"
            step="1"
            className="ceg-modal-input"
            value={form.strand_id}
            onChange={(e) =>
              setForm((f) => ({ ...f, strand_id: e.target.value }))
            }
            aria-invalid={!!errors.strand_id}
            aria-describedby={errors.strand_id ? 'ceg-modal-strand-err' : undefined}
          />
          {errors.strand_id && (
            <span id="ceg-modal-strand-err" className="ceg-modal-error">
              {errors.strand_id}
            </span>
          )}
        </div>

        <div className="ceg-modal-field">
          <span className="ceg-modal-field-label">Expectation type</span>
          <div
            className="ceg-modal-radio-group"
            role="radiogroup"
            aria-label="Expectation type"
          >
            <label className="ceg-modal-radio-label">
              <input
                type="radio"
                name="ceg-expectation-type"
                value={EXPECTATION_TYPE_OVERALL}
                checked={form.expectation_type === EXPECTATION_TYPE_OVERALL}
                onChange={() =>
                  setForm((f) => ({
                    ...f,
                    expectation_type: EXPECTATION_TYPE_OVERALL,
                  }))
                }
              />
              Overall (OE)
            </label>
            <label className="ceg-modal-radio-label">
              <input
                type="radio"
                name="ceg-expectation-type"
                value={EXPECTATION_TYPE_SPECIFIC}
                checked={form.expectation_type === EXPECTATION_TYPE_SPECIFIC}
                onChange={() =>
                  setForm((f) => ({
                    ...f,
                    expectation_type: EXPECTATION_TYPE_SPECIFIC,
                  }))
                }
              />
              Specific (SE)
            </label>
          </div>
        </div>

        <div className="ceg-modal-field">
          <label
            htmlFor="ceg-modal-notes"
            className="ceg-modal-field-label"
          >
            Review notes (optional)
          </label>
          <textarea
            id="ceg-modal-notes"
            className="ceg-modal-textarea"
            value={form.review_notes}
            onChange={(e) =>
              setForm((f) => ({ ...f, review_notes: e.target.value }))
            }
          />
        </div>

        <div className="ceg-modal-actions">
          <button
            type="button"
            className="ceg-modal-btn ceg-modal-btn--cancel"
            onClick={onCancel}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="ceg-modal-btn ceg-modal-btn--save"
            onClick={handleSave}
            disabled={submitting}
          >
            {submitting ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
