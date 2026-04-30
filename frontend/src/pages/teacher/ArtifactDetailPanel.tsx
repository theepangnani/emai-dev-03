/**
 * CB-CMCP-001 M3-A 3A-2 (#4582) — Teacher review queue: artifact detail.
 *
 * Renders one full artifact + its review metadata + Approve / Reject /
 * Regenerate / Edit controls.
 *
 * Coordination — out of scope for THIS stripe, slotted for siblings:
 *   - SE-tag editor (3A-3 / #4583): replaces the read-only `<SeTagSlot>`.
 *   - Regenerate UX modal (3A-4 / #4584): replaces the simple confirm here.
 *
 * Markdown rendering: dev-03 doesn't have a shared Markdown renderer in
 * the shared components surface. Per task scope ("minimal but usable"),
 * we render Markdown as preformatted text with whitespace preserved —
 * the teacher can read the raw body, which is enough to make a Approve /
 * Reject call. Visual prettifying can ride a fast-follow.
 */
import { useEffect, useState } from 'react';
import type { ReviewArtifactDetail } from '../../api/cmcpReview';

interface ArtifactDetailPanelProps {
  artifact: ReviewArtifactDetail | null;
  isLoading: boolean;
  error: Error | null;
  // Action state
  isEditing: boolean;
  isApproving: boolean;
  isRejecting: boolean;
  isRegenerating: boolean;
  editError: string | null;
  approveError: string | null;
  regenerateError: string | null;
  // Action callbacks
  onSaveEdit: (content: string) => void;
  onApprove: () => void;
  onRequestReject: () => void;
  onRegenerate: () => void;
}

/**
 * Placeholder slot for the SE-tag editor (3A-3 / #4583). 3A-3 should
 * replace the body of this component without touching the parent.
 * Until then, render the existing SE codes read-only so the teacher can
 * see what's targeted.
 */
function SeTagSlot({ codes }: { codes: string[] }) {
  if (codes.length === 0) {
    return (
      <p className="cmcp-review-detail-empty">
        No SE codes targeted yet.
      </p>
    );
  }
  return (
    <ul className="cmcp-review-se-list" data-testid="cmcp-review-se-tag-slot">
      {codes.map((code) => (
        <li key={code} className="cmcp-review-se-chip">
          {code}
        </li>
      ))}
    </ul>
  );
}

function MetadataRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="cmcp-review-detail-row">
      <span className="cmcp-review-detail-label">{label}</span>
      <span className="cmcp-review-detail-value">{children}</span>
    </div>
  );
}

function formatDateTime(value: string | null): string {
  if (!value) return '—';
  try {
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return value;
    return dt.toLocaleString();
  } catch {
    return value;
  }
}

export function ArtifactDetailPanel({
  artifact,
  isLoading,
  error,
  isEditing,
  isApproving,
  isRejecting,
  isRegenerating,
  editError,
  approveError,
  regenerateError,
  onSaveEdit,
  onApprove,
  onRequestReject,
  onRegenerate,
}: ArtifactDetailPanelProps) {
  // Inline editor state. The textarea seeds from `artifact.content`
  // every time the loaded artifact changes id (or content) so switching
  // rows pulls in the latest content; an in-progress edit on artifact A
  // is therefore lost when the user clicks artifact B — that's the
  // intended UX (no per-artifact draft persistence in 3A-2).
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');

  useEffect(() => {
    if (artifact) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: re-seed editor state when the loaded artifact id/content changes (external query result drives editor state; in-progress edit on prior artifact intentionally discarded)
      setDraft(artifact.content);
      setEditing(false);
    }
  }, [artifact?.id, artifact?.content, artifact]);

  if (isLoading) {
    return (
      <aside
        className="cmcp-review-detail"
        data-testid="cmcp-review-detail"
        aria-label="Artifact detail"
      >
        <p className="cmcp-review-state-msg">Loading artifact…</p>
      </aside>
    );
  }

  if (error) {
    return (
      <aside
        className="cmcp-review-detail"
        data-testid="cmcp-review-detail"
        aria-label="Artifact detail"
      >
        <div className="cmcp-review-error" role="alert">
          {error.message || 'Failed to load artifact.'}
        </div>
      </aside>
    );
  }

  if (!artifact) {
    return (
      <aside
        className="cmcp-review-detail cmcp-review-detail--empty"
        data-testid="cmcp-review-detail"
        aria-label="Artifact detail"
      >
        <div className="cmcp-review-state-msg" role="status">
          <h3>Select an artifact</h3>
          <p>Pick a row from the queue to review its content.</p>
        </div>
      </aside>
    );
  }

  const isMutable =
    artifact.state === 'PENDING_REVIEW' ||
    artifact.state === 'REJECTED' ||
    artifact.state === 'DRAFT';

  const isPending = artifact.state === 'PENDING_REVIEW';

  const draftDirty = editing && draft !== artifact.content;

  return (
    <aside
      className="cmcp-review-detail"
      data-testid="cmcp-review-detail"
      aria-label="Artifact detail"
    >
      <header className="cmcp-review-detail-header">
        <div>
          <div className="cmcp-review-detail-kicker">Artifact #{artifact.id}</div>
          <h2 className="cmcp-review-detail-title">{artifact.title}</h2>
        </div>
        <span
          className={`cmcp-review-state-chip cmcp-review-state-chip--${artifact.state.toLowerCase()}`}
        >
          {artifact.state}
        </span>
      </header>

      <section
        className="cmcp-review-detail-meta"
        aria-label="Artifact metadata"
      >
        <MetadataRow label="Type">{artifact.guide_type}</MetadataRow>
        <MetadataRow label="Persona">
          {artifact.requested_persona ?? '—'}
        </MetadataRow>
        <MetadataRow label="Course">
          {artifact.course_id !== null ? `#${artifact.course_id}` : '—'}
        </MetadataRow>
        <MetadataRow label="Board">{artifact.board_id ?? '—'}</MetadataRow>
        <MetadataRow label="Alignment score">
          {artifact.alignment_score === null
            ? '—'
            : artifact.alignment_score.toFixed(2)}
        </MetadataRow>
        <MetadataRow label="CEG version">
          {artifact.ceg_version === null ? '—' : `v${artifact.ceg_version}`}
        </MetadataRow>
        <MetadataRow label="Created">
          {formatDateTime(artifact.created_at)}
        </MetadataRow>
        {artifact.reviewed_at && (
          <MetadataRow label="Reviewed">
            {formatDateTime(artifact.reviewed_at)}
            {artifact.reviewed_by_user_id !== null && (
              <span className="cmcp-review-detail-reviewer">
                {' '}
                by user #{artifact.reviewed_by_user_id}
              </span>
            )}
          </MetadataRow>
        )}
        {artifact.rejection_reason && (
          <div className="cmcp-review-rejection" role="note">
            <span className="cmcp-review-detail-label">Rejection reason</span>
            <p className="cmcp-review-detail-rejection-body">
              {artifact.rejection_reason}
            </p>
          </div>
        )}
      </section>

      <section
        className="cmcp-review-detail-section"
        aria-label="Targeted SE codes"
      >
        <h3 className="cmcp-review-detail-section-title">SE codes</h3>
        {/* TODO(3A-3 / #4583): replace SeTagSlot with the SE-tag editor. */}
        <SeTagSlot codes={artifact.se_codes} />
      </section>

      <section
        className="cmcp-review-detail-section"
        aria-label="Artifact content"
      >
        <div className="cmcp-review-detail-content-header">
          <h3 className="cmcp-review-detail-section-title">Content</h3>
          {isMutable && !editing && (
            <button
              type="button"
              className="cmcp-review-action-btn cmcp-review-action-btn--ghost"
              onClick={() => setEditing(true)}
              data-testid="cmcp-review-edit-btn"
            >
              Edit content
            </button>
          )}
        </div>

        {editing ? (
          <div className="cmcp-review-edit-area">
            <label className="cmcp-review-visually-hidden" htmlFor="cmcp-review-edit-textarea">
              Artifact content
            </label>
            <textarea
              id="cmcp-review-edit-textarea"
              className="cmcp-review-edit-textarea"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={18}
              spellCheck
              data-testid="cmcp-review-edit-textarea"
              disabled={isEditing}
            />
            {editError && (
              <p className="cmcp-review-error" role="alert">
                {editError}
              </p>
            )}
            <div className="cmcp-review-edit-actions">
              <button
                type="button"
                className="cmcp-review-action-btn cmcp-review-action-btn--ghost"
                onClick={() => {
                  setDraft(artifact.content);
                  setEditing(false);
                }}
                disabled={isEditing}
              >
                Cancel
              </button>
              <button
                type="button"
                className="cmcp-review-action-btn cmcp-review-action-btn--primary"
                onClick={() => onSaveEdit(draft)}
                disabled={isEditing || !draftDirty || draft.trim().length === 0}
                data-testid="cmcp-review-save-edit-btn"
              >
                {isEditing ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </div>
        ) : (
          <pre className="cmcp-review-content-view" data-testid="cmcp-review-content-view">
            {artifact.content}
          </pre>
        )}
      </section>

      {artifact.edit_history.length > 0 && (
        <section
          className="cmcp-review-detail-section"
          aria-label="Edit history"
        >
          <h3 className="cmcp-review-detail-section-title">
            Edit history ({artifact.edit_history.length})
          </h3>
          <ul className="cmcp-review-history-list">
            {artifact.edit_history.map((entry, idx) => (
              <li
                key={`${entry.editor_id}-${entry.edit_at}-${idx}`}
                className="cmcp-review-history-item"
              >
                <div className="cmcp-review-history-meta">
                  <span>Editor #{entry.editor_id}</span>
                  <span className="cmcp-review-history-meta-sep">·</span>
                  <span>{formatDateTime(entry.edit_at)}</span>
                </div>
                <div className="cmcp-review-history-snippets">
                  <span className="cmcp-review-history-before">
                    {entry.before_snippet}
                  </span>
                  <span className="cmcp-review-history-arrow" aria-hidden="true">
                    →
                  </span>
                  <span className="cmcp-review-history-after">
                    {entry.after_snippet}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section
        className="cmcp-review-detail-actions"
        aria-label="Review actions"
      >
        {(approveError || regenerateError) && (
          <div className="cmcp-review-error" role="alert">
            {approveError ?? regenerateError}
          </div>
        )}
        <div className="cmcp-review-actions-row">
          <button
            type="button"
            className="cmcp-review-action-btn cmcp-review-action-btn--primary"
            onClick={onApprove}
            disabled={!isPending || isApproving || isRejecting || isRegenerating}
            data-testid="cmcp-review-approve-btn"
          >
            {isApproving ? 'Approving…' : 'Approve'}
          </button>
          <button
            type="button"
            className="cmcp-review-action-btn cmcp-review-action-btn--danger"
            onClick={onRequestReject}
            disabled={!isPending || isApproving || isRejecting || isRegenerating}
            data-testid="cmcp-review-reject-btn"
          >
            {isRejecting ? 'Rejecting…' : 'Reject'}
          </button>
          <button
            type="button"
            className="cmcp-review-action-btn cmcp-review-action-btn--ghost"
            onClick={onRegenerate}
            disabled={!isMutable || isApproving || isRejecting || isRegenerating}
            data-testid="cmcp-review-regenerate-btn"
          >
            {isRegenerating ? 'Regenerating…' : 'Regenerate'}
          </button>
        </div>
        {!isPending && (
          <p className="cmcp-review-action-hint" role="note">
            {artifact.state === 'APPROVED'
              ? 'This artifact is already approved.'
              : artifact.state === 'REJECTED'
                ? 'This artifact was rejected. Edit + regenerate to send back into the queue.'
                : `Action gating: state is ${artifact.state}.`}
          </p>
        )}
      </section>
    </aside>
  );
}
