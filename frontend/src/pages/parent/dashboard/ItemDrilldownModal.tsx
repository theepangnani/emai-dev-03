import { useCallback, useEffect, useState, type JSX } from 'react';
import { useFocusTrap } from '../../../hooks/useFocusTrap';
import './ItemDrilldownModal.css';

/**
 * Stripe E4 (CB-EDIGEST-002 §F3) — drilldown modal.
 *
 * Displays the source email + extracted task + Mark done / Snooze actions
 * for a single dashboard item. The component is a pure overlay — the parent
 * supplies async callbacks for Mark done / Snooze, and we only handle the UX
 * (loading + error + close).
 *
 * Local contract — E6 will reconcile with the canonical types in
 * `frontend/src/api/parentEmailDigest.ts` once the backend item shape lands.
 */
export interface DrilldownItem {
  id: string;
  title: string;
  due_date: string | null;
  course_or_context: string | null;
  source_email_id: string;
  source_email_subject?: string;
  source_email_body?: string;
  source_email_from?: string;
  source_email_received?: string;
}

export interface ItemDrilldownModalProps {
  open: boolean;
  item: DrilldownItem | null;
  onClose: () => void;
  onMarkDone: (item_id: string) => Promise<void>;
  onSnooze: (item_id: string, days: number) => Promise<void>;
}

type DOMPurifyType = typeof import('dompurify').default;

function formatDueDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatReceivedDate(iso: string | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

type PendingAction = null | 'mark-done' | 'snooze-1' | 'snooze-7';

export function ItemDrilldownModal({
  open,
  item,
  onClose,
  onMarkDone,
  onSnooze,
}: ItemDrilldownModalProps): JSX.Element {
  const trapRef = useFocusTrap<HTMLDivElement>(open && item !== null, onClose);
  const [pending, setPending] = useState<PendingAction>(null);
  const [error, setError] = useState<string | null>(null);
  const [purify, setPurify] = useState<DOMPurifyType | null>(null);
  const [purifyError, setPurifyError] = useState(false);

  // Reset pending + error when item changes or modal closes — avoids stuck
  // spinner / stale error if parent swaps items between opens.
  useEffect(() => {
    if (!open || !item) {
      setPending(null);
      setError(null);
    }
  }, [open, item]);

  // Lazy-load DOMPurify only when we have an email body to render. Mirrors the
  // existing pattern in `DigestHistoryPanel` so we share the chunk.
  const hasBody = !!item?.source_email_body;
  useEffect(() => {
    if (open && item && hasBody && !purify && !purifyError) {
      import('dompurify')
        .then((m) => setPurify(() => m.default))
        .catch(() => setPurifyError(true));
    }
  }, [open, item, hasBody, purify, purifyError]);

  const runAction = useCallback(
    async (kind: PendingAction, fn: () => Promise<void>) => {
      if (pending) return;
      setError(null);
      setPending(kind);
      try {
        await fn();
      } catch (err) {
        const msg =
          err instanceof Error && err.message
            ? err.message
            : 'Something went wrong. Please try again.';
        setError(msg);
      } finally {
        setPending(null);
      }
    },
    [pending],
  );

  const handleMarkDone = useCallback(() => {
    if (!item) return;
    void runAction('mark-done', () => onMarkDone(item.id));
  }, [item, onMarkDone, runAction]);

  const handleSnooze1 = useCallback(() => {
    if (!item) return;
    void runAction('snooze-1', () => onSnooze(item.id, 1));
  }, [item, onSnooze, runAction]);

  const handleSnooze7 = useCallback(() => {
    if (!item) return;
    void runAction('snooze-7', () => onSnooze(item.id, 7));
  }, [item, onSnooze, runAction]);

  const handleBackdropClick = useCallback(() => {
    if (pending) return;
    onClose();
  }, [pending, onClose]);

  // Don't render anything when closed or no item provided.
  if (!open || !item) {
    return <></>;
  }

  const dueLabel = formatDueDate(item.due_date);
  const receivedLabel = formatReceivedDate(item.source_email_received);
  const isBusy = pending !== null;

  return (
    <div className="modal-overlay idm-overlay" onClick={handleBackdropClick}>
      <div
        ref={trapRef}
        className="modal idm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="idm-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="idm-header">
          <div className="idm-header-text">
            <h2 id="idm-title" className="idm-title">
              {item.title}
            </h2>
            {dueLabel && (
              <span className="idm-due-pill" data-testid="idm-due-pill">
                Due {dueLabel}
              </span>
            )}
          </div>
          <button
            type="button"
            className="idm-close"
            onClick={onClose}
            aria-label="Close"
            disabled={isBusy}
          >
            &times;
          </button>
        </header>

        <div className="idm-body">
          <section className="idm-section idm-section--task" aria-label="Task details">
            <h3 className="idm-section-title">Task</h3>
            <dl className="idm-meta">
              <div className="idm-meta-row">
                <dt>Title</dt>
                <dd>{item.title}</dd>
              </div>
              {dueLabel && (
                <div className="idm-meta-row">
                  <dt>Due</dt>
                  <dd>{dueLabel}</dd>
                </div>
              )}
              {item.course_or_context && (
                <div className="idm-meta-row">
                  <dt>Course</dt>
                  <dd>{item.course_or_context}</dd>
                </div>
              )}
            </dl>
          </section>

          <section className="idm-section idm-section--email" aria-label="Source email">
            <h3 className="idm-section-title">Source email</h3>
            <dl className="idm-meta">
              {item.source_email_from && (
                <div className="idm-meta-row">
                  <dt>From</dt>
                  <dd>{item.source_email_from}</dd>
                </div>
              )}
              {item.source_email_subject && (
                <div className="idm-meta-row">
                  <dt>Subject</dt>
                  <dd>{item.source_email_subject}</dd>
                </div>
              )}
              {receivedLabel && (
                <div className="idm-meta-row">
                  <dt>Received</dt>
                  <dd>{receivedLabel}</dd>
                </div>
              )}
            </dl>
            {hasBody ? (
              purify ? (
                <div
                  className="idm-email-body"
                  data-testid="idm-email-body"
                  // Purify-sanitized HTML — body tags only, no scripts/handlers.
                  dangerouslySetInnerHTML={{
                    __html: purify.sanitize(item.source_email_body ?? ''),
                  }}
                />
              ) : purifyError ? (
                <p className="idm-email-error">
                  Could not load email content. Please refresh.
                </p>
              ) : (
                <div className="idm-email-body idm-email-body--loading">
                  Loading email content...
                </div>
              )
            ) : (
              <p className="idm-email-empty">No email body available.</p>
            )}
          </section>

          {error && (
            <div role="alert" className="idm-error" data-testid="idm-error">
              {error}
            </div>
          )}

          <div className="idm-actions" role="group" aria-label="Actions">
            <button
              type="button"
              className="idm-btn idm-btn--primary"
              onClick={handleMarkDone}
              disabled={isBusy}
              data-testid="idm-mark-done"
            >
              {pending === 'mark-done' ? 'Marking...' : 'Mark done'}
            </button>
            <button
              type="button"
              className="idm-btn idm-btn--secondary"
              onClick={handleSnooze1}
              disabled={isBusy}
              data-testid="idm-snooze-1"
            >
              {pending === 'snooze-1' ? 'Snoozing...' : 'Snooze 1 day'}
            </button>
            <button
              type="button"
              className="idm-btn idm-btn--secondary"
              onClick={handleSnooze7}
              disabled={isBusy}
              data-testid="idm-snooze-7"
            >
              {pending === 'snooze-7' ? 'Snoozing...' : 'Snooze until next week'}
            </button>
            <button
              type="button"
              className="idm-btn idm-btn--tertiary"
              onClick={onClose}
              disabled={isBusy}
              data-testid="idm-close-action"
            >
              Close
            </button>
          </div>

          {/* Phase 2 hook — Arc Q&A slot. Markup-only; deferred behavior per PRD §F3. */}
          <div data-testid="phase2-arc-qa-slot" hidden />
        </div>
      </div>
    </div>
  );
}
