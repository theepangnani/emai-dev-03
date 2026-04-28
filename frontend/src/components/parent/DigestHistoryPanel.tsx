import { useEffect, useId, useState, type JSX, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  getLogs,
  type DigestDeliveryLog,
} from '../../api/parentEmailDigest';
import './DigestHistoryPanel.css';

export interface DigestHistoryPanelProps {
  /** Maximum number of recent entries to fetch + display. Default: 5 */
  limit?: number;
  /** Heading text. Pass `null` to hide. Default: "Digest History" */
  heading?: ReactNode;
  /** When true, the heading becomes a button that toggles the list. Default: false */
  collapsible?: boolean;
  /** Initial collapsed state when collapsible. Default: false (expanded) */
  defaultCollapsed?: boolean;
  /** Optional className for the outer wrapper */
  className?: string;
  /** Custom copy for the empty state. Defaults to "No digests delivered yet." */
  emptyState?: ReactNode;
  /** Optional one-line subhint rendered below the heading. Useful when embedded under a child filter to clarify scope. */
  description?: ReactNode;
}

type DOMPurifyType = typeof import('dompurify').default;

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function StatusBadge({ status }: { status: string }) {
  const cls = status === 'delivered' ? 'dhp-status--delivered' : 'dhp-status--failed';
  return <span className={`dhp-status ${cls}`}>{status}</span>;
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      className={`dhp-chevron ${open ? 'dhp-chevron--open' : ''}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

export function DigestHistoryPanel({
  limit = 5,
  heading = 'Digest History',
  collapsible = false,
  defaultCollapsed = false,
  className,
  emptyState = 'No digests delivered yet.',
  description,
}: DigestHistoryPanelProps): JSX.Element {
  const listId = useId();
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);
  // `defaultCollapsed` is read once at mount; runtime prop changes are intentionally
  // ignored. If a future caller needs to control collapse state externally, expose
  // `collapsed` + `onToggle` props instead of mutating the initializer.
  const [collapsed, setCollapsed] = useState<boolean>(collapsible && defaultCollapsed);
  const [purify, setPurify] = useState<DOMPurifyType | null>(null);

  const { data: logs = [], isLoading } = useQuery<DigestDeliveryLog[]>({
    queryKey: ['email-digest', 'logs', 'panel', limit],
    queryFn: () => getLogs({ limit }).then((r) => r.data),
    staleTime: 60_000, // S-1: 1-min cache to debounce navigation refetches
  });

  // S-7: if the currently expanded row is no longer in the list after a refetch,
  // reset so we don't render an orphaned expanded state.
  useEffect(() => {
    if (expandedLogId !== null && !logs.some((l) => l.id === expandedLogId)) {
      setExpandedLogId(null);
    }
  }, [logs, expandedLogId]);

  // S-12: lazy-load DOMPurify only when a row gets expanded.
  useEffect(() => {
    if (expandedLogId !== null && !purify) {
      import('dompurify')
        .then((m) => setPurify(() => m.default))
        .catch(() => {});
    }
  }, [expandedLogId, purify]);

  const wrapperClass = ['dhp-panel', className].filter(Boolean).join(' ');
  const showList = !collapsible || !collapsed;

  let headingNode: ReactNode = null;
  if (heading !== null) {
    if (collapsible) {
      headingNode = (
        <h2 className="dhp-heading dhp-heading--collapsible">
          <button
            type="button"
            className="dhp-heading--button"
            onClick={() => setCollapsed((c) => !c)}
            aria-expanded={!collapsed}
            aria-controls={listId}
          >
            <span className="dhp-heading-text">{heading}</span>
            <Chevron open={!collapsed} />
          </button>
        </h2>
      );
    } else {
      headingNode = <h2 className="dhp-heading">{heading}</h2>;
    }
  }

  return (
    <div className={wrapperClass}>
      {headingNode}
      {description && <p className="dhp-description">{description}</p>}
      {showList && (
        <>
          {isLoading && (
            <div id={listId} className="dhp-loading">
              Loading history...
            </div>
          )}
          {!isLoading && logs.length === 0 && (
            <div id={listId} className="dhp-empty">
              {emptyState}
            </div>
          )}
          {!isLoading && logs.length > 0 && (
            <div id={listId} className="dhp-log-list">
              {logs.map((log) => {
                const isOpen = expandedLogId === log.id;
                return (
                  <div key={log.id} className="dhp-log-card">
                    <button
                      type="button"
                      className="dhp-log-header"
                      onClick={() => setExpandedLogId(isOpen ? null : log.id)}
                      aria-expanded={isOpen}
                    >
                      <div className="dhp-log-meta">
                        <span className="dhp-log-date">{formatDate(log.delivered_at)}</span>
                        <span className="dhp-log-count">
                          {log.email_count} {log.email_count === 1 ? 'email' : 'emails'}
                        </span>
                        <StatusBadge status={log.status} />
                      </div>
                      <Chevron open={isOpen} />
                    </button>
                    {isOpen && (
                      <div className="dhp-log-content">
                        {log.digest_content ? (
                          purify ? (
                            <div
                              className="dhp-digest-text"
                              dangerouslySetInnerHTML={{
                                __html: purify.sanitize(log.digest_content),
                              }}
                            />
                          ) : (
                            <div className="dhp-digest-text">Loading content...</div>
                          )
                        ) : (
                          <p className="dhp-no-content">No digest content available.</p>
                        )}
                        {log.channels_used && (
                          <div className="dhp-log-channels">
                            Delivered via: {log.channels_used}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
