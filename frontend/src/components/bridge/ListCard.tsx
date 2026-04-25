/**
 * CB-BRIDGE-004 — generic list card for the Bridge management grid (#4117).
 *
 * Used by Classes / Teachers / Materials. Email Digest has its own
 * specialised card (EmailDigestCard) — its anatomy diverges enough
 * (cadence pill, toggle list, distinct footer) that sharing a shell
 * here would warp it.
 */
import type { ReactNode } from 'react';

interface ListCardProps {
  kicker?: string;
  title: string;
  count?: number;
  description?: string;
  headAction?: { label: string; onClick: () => void };
  footMeta?: string;
  footAction?: { label: string; onClick: () => void };
  emptyState?: ReactNode;
  children: ReactNode;
}

export function ListCard({
  kicker,
  title,
  count,
  description,
  headAction,
  footMeta,
  footAction,
  emptyState,
  children,
}: ListCardProps) {
  return (
    <article className="bridge-card">
      <header className="bridge-card-head">
        <div className="bridge-card-title-wrap">
          {kicker && <span className="bridge-card-kicker">{kicker}</span>}
          <h3>
            {title}
            {count != null && <span className="bridge-card-count">{count}</span>}
          </h3>
          {description && <p className="bridge-card-desc">{description}</p>}
        </div>
        {headAction && (
          <button type="button" className="bridge-head-action" onClick={headAction.onClick}>
            {headAction.label}
          </button>
        )}
      </header>

      {emptyState ? (
        <div className="bridge-empty-hint">{emptyState}</div>
      ) : (
        <ul className="bridge-item-list" role="list">
          {children}
        </ul>
      )}

      {(footMeta || footAction) && (
        <footer className="bridge-card-foot">
          {footMeta && <span className="bridge-card-foot-meta">{footMeta}</span>}
          {footAction && (
            <button type="button" className="bridge-head-action" onClick={footAction.onClick}>
              {footAction.label}
            </button>
          )}
        </footer>
      )}
    </article>
  );
}
