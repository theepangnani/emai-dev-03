/**
 * CB-EDIGEST-002 E5 (#4593) — Dashboard header (PRD F4).
 *
 * Greeting + last-refreshed timestamp + Refresh control. Pure
 * presentational; the digest dashboard owns refresh state and passes
 * `onRefresh` / `isRefreshing` down. Uses Bridge skin tokens (consumed
 * via the parent `.bridge-page` scope) so this component contributes no
 * extra global CSS — all visual treatment is inline + tokenized.
 */
import type { JSX } from 'react';

interface DashboardHeaderProps {
  parentName: string;
  lastRefreshedAt: string | null;
  isRefreshing: boolean;
  onRefresh: () => void;
}

/**
 * Format an ISO timestamp as a coarse relative-time string.
 *
 * Granularity matches the PRD F4 examples ("2 minutes ago", "1 hour
 * ago", "yesterday"). Returns null on invalid / future input so callers
 * can fall back gracefully.
 */
function formatRelativeTime(iso: string | null): string | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  const diffMs = Date.now() - then;
  if (diffMs < 0) return 'just now';
  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes === 1) return '1 minute ago';
  if (minutes < 60) return `${minutes} minutes ago`;
  const hours = Math.floor(minutes / 60);
  if (hours === 1) return '1 hour ago';
  if (hours < 24) return `${hours} hours ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days} days ago`;
  const weeks = Math.floor(days / 7);
  if (weeks === 1) return '1 week ago';
  return `${weeks} weeks ago`;
}

function RefreshIcon(): JSX.Element {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
    </svg>
  );
}

function Spinner(): JSX.Element {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ animation: 'edigest-spin 1s linear infinite' }}
    >
      <path d="M21 12a9 9 0 11-6.22-8.56" />
    </svg>
  );
}

export function DashboardHeader({
  parentName,
  lastRefreshedAt,
  isRefreshing,
  onRefresh,
}: DashboardHeaderProps): JSX.Element {
  // Defensive: TS says `string` but real callers may pass `user?.full_name`
  // (undefined during loading) or null. Coerce so trim() never throws.
  const trimmedName = (parentName ?? '').trim();
  const greeting = trimmedName
    ? `Hi ${trimmedName}, here's today's view`
    : "Hi there, here's today's view";
  const relative = formatRelativeTime(lastRefreshedAt);

  return (
    <header className="edigest-dashboard-header">
      <style>{`@keyframes edigest-spin { to { transform: rotate(360deg); } }`}</style>
      <div className="edigest-dashboard-header__text">
        <h1
          className="edigest-dashboard-header__title"
          style={{
            fontFamily: '"Fraunces", "Georgia", serif',
            fontSize: '24px',
            lineHeight: 1.2,
            letterSpacing: '-0.01em',
            margin: 0,
            color: 'var(--bridge-ink, #1c1a16)',
          }}
        >
          {greeting}
        </h1>
        <p
          className="edigest-dashboard-header__updated"
          style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '12px',
            color: 'var(--bridge-muted, #6b645b)',
            margin: '6px 0 0',
            letterSpacing: '0.02em',
          }}
        >
          {relative ? `Last updated ${relative}` : 'Not refreshed yet'}
        </p>
      </div>
      <button
        type="button"
        onClick={onRefresh}
        disabled={isRefreshing}
        aria-busy={isRefreshing}
        aria-label={isRefreshing ? 'Refreshing digest' : 'Refresh digest'}
        className="edigest-dashboard-header__refresh"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          padding: '10px 16px',
          fontFamily: '"DM Sans", system-ui, sans-serif',
          fontSize: '14px',
          fontWeight: 500,
          color: 'var(--bridge-ink, #1c1a16)',
          background: 'var(--bridge-card, #ffffff)',
          border: '1px solid var(--bridge-hair, #e5ddd1)',
          borderRadius: '8px',
          cursor: isRefreshing ? 'not-allowed' : 'pointer',
          opacity: isRefreshing ? 0.7 : 1,
        }}
      >
        {isRefreshing ? <Spinner /> : <RefreshIcon />}
        <span>{isRefreshing ? 'Updating...' : 'Refresh'}</span>
      </button>
    </header>
  );
}

export type { DashboardHeaderProps };
