import { useState, type JSX, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import DOMPurify from 'dompurify';
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
}

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

export function DigestHistoryPanel({
  limit = 5,
  heading = 'Digest History',
  collapsible = false,
  defaultCollapsed = false,
  className,
}: DigestHistoryPanelProps): JSX.Element {
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);
  const [collapsed, setCollapsed] = useState<boolean>(collapsible && defaultCollapsed);

  const { data: logs = [], isLoading } = useQuery<DigestDeliveryLog[]>({
    queryKey: ['email-digest', 'logs', 'panel', limit],
    queryFn: () => getLogs({ limit }).then((r) => r.data),
  });

  const wrapperClass = ['dhp-panel', className].filter(Boolean).join(' ');
  const showList = !collapsible || !collapsed;

  let headingNode: ReactNode = null;
  if (heading !== null) {
    if (collapsible) {
      headingNode = (
        <button
          type="button"
          className="dhp-heading dhp-heading--button"
          onClick={() => setCollapsed((c) => !c)}
          aria-expanded={!collapsed}
        >
          <span className="dhp-heading-text">{heading}</span>
          <svg
            className={`dhp-chevron ${!collapsed ? 'dhp-chevron--open' : ''}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
      );
    } else {
      headingNode = <h2 className="dhp-heading">{heading}</h2>;
    }
  }

  return (
    <div className={wrapperClass}>
      {headingNode}
      {showList && (
        <>
          {isLoading && <div className="dhp-loading">Loading history…</div>}
          {!isLoading && logs.length === 0 && (
            <div className="dhp-empty">No digests delivered yet.</div>
          )}
          {!isLoading && logs.length > 0 && (
            <div className="dhp-log-list">
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
                      <svg
                        className={`dhp-chevron ${isOpen ? 'dhp-chevron--open' : ''}`}
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        aria-hidden="true"
                      >
                        <polyline points="6 9 12 15 18 9" />
                      </svg>
                    </button>
                    {isOpen && (
                      <div className="dhp-log-content">
                        {log.digest_content ? (
                          <div
                            className="dhp-digest-text"
                            dangerouslySetInnerHTML={{
                              __html: DOMPurify.sanitize(log.digest_content),
                            }}
                          />
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
