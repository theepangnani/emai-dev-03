/**
 * CB-EDIGEST-002 E5 (#4593) — EmptyStates component (PRD F5).
 *
 * Renders one of six dashboard "edge banner" states:
 *   calm | no_kids | paused | auth_expired | first_run | legacy_blob
 *
 * - The five non-blob states are simple title + sub + optional CTA cards
 *   styled with Bridge skin tokens.
 * - `legacy_blob` renders raw HTML inside a DOMPurify-sanitized container,
 *   matching the lazy-load pattern used in `DigestHistoryPanel` so we never
 *   pull DOMPurify into the bundle until a parent actually needs it.
 *
 * Sanitizer fallback: if DOMPurify fails to load (offline/blocked CDN), we
 * render a "could not load" notice instead of the raw HTML — never the raw
 * unsanitized blob.
 */
import { useEffect, useState, type JSX } from 'react';

type EmptyStateKind =
  | 'calm'
  | 'no_kids'
  | 'paused'
  | 'auth_expired'
  | 'first_run'
  | 'legacy_blob';

interface EmptyStatesProps {
  kind: EmptyStateKind;
  legacyBlob?: string;
  onRefresh?: () => void;
  onAddKids?: () => void;
  onResume?: () => void;
  onReconnectGmail?: () => void;
}

type DOMPurifyType = typeof import('dompurify').default;

function CheckIcon(): JSX.Element {
  return (
    <svg
      width="40"
      height="40"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" />
      <polyline points="9 12 12 15 16 10" />
    </svg>
  );
}

function AuthErrorIcon(): JSX.Element {
  return (
    <svg
      width="40"
      height="40"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 2L2 7l10 5 10-5-10-5z" />
      <path d="M2 17l10 5 10-5" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <circle cx="12" cy="16" r="0.5" />
    </svg>
  );
}

const cardStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  textAlign: 'center',
  padding: '40px 24px',
  background: 'var(--bridge-card, #ffffff)',
  border: '1px solid var(--bridge-hair, #e5ddd1)',
  borderRadius: '12px',
  fontFamily: '"DM Sans", system-ui, sans-serif',
  color: 'var(--bridge-ink, #1c1a16)',
};

const titleStyle: React.CSSProperties = {
  fontFamily: '"Fraunces", "Georgia", serif',
  fontSize: '22px',
  letterSpacing: '-0.01em',
  margin: '12px 0 6px',
  fontWeight: 400,
};

const subStyle: React.CSSProperties = {
  fontSize: '14px',
  color: 'var(--bridge-muted, #6b645b)',
  margin: 0,
  maxWidth: '360px',
};

function primaryButtonStyle(): React.CSSProperties {
  return {
    marginTop: '20px',
    padding: '10px 20px',
    fontFamily: '"DM Sans", system-ui, sans-serif',
    fontSize: '14px',
    fontWeight: 500,
    color: 'var(--color-paper, #fbf8f2)',
    background: 'var(--bridge-rust, #b04a2c)',
    border: '1px solid var(--bridge-rust, #b04a2c)',
    borderRadius: '8px',
    cursor: 'pointer',
  };
}

function ghostButtonStyle(): React.CSSProperties {
  return {
    marginTop: '20px',
    padding: '10px 20px',
    fontFamily: '"DM Sans", system-ui, sans-serif',
    fontSize: '14px',
    fontWeight: 500,
    color: 'var(--bridge-ink, #1c1a16)',
    background: 'var(--bridge-card, #ffffff)',
    border: '1px solid var(--bridge-hair, #e5ddd1)',
    borderRadius: '8px',
    cursor: 'pointer',
  };
}

function CalmState({ onRefresh }: { onRefresh?: () => void }): JSX.Element {
  return (
    <div className="edigest-empty edigest-empty--calm" style={cardStyle}>
      <div style={{ color: 'var(--bridge-active-ink, #23523f)' }}>
        <CheckIcon />
      </div>
      <h2 style={titleStyle}>Nothing urgent today</h2>
      <p style={subStyle}>
        We checked your kids&apos; school inboxes and didn&apos;t find anything that needs
        your attention right now.
      </p>
      {onRefresh && (
        <button type="button" style={ghostButtonStyle()} onClick={onRefresh}>
          Refresh
        </button>
      )}
    </div>
  );
}

function NoKidsState({ onAddKids }: { onAddKids?: () => void }): JSX.Element {
  return (
    <div className="edigest-empty edigest-empty--no-kids" style={cardStyle}>
      <h2 style={titleStyle}>Add your kids to start</h2>
      <p style={subStyle}>
        Link a kid to begin monitoring their school inbox and seeing today&apos;s view.
      </p>
      {onAddKids && (
        <button type="button" style={primaryButtonStyle()} onClick={onAddKids}>
          Add a kid
        </button>
      )}
    </div>
  );
}

function PausedState({ onResume }: { onResume?: () => void }): JSX.Element {
  return (
    <div className="edigest-empty edigest-empty--paused" style={cardStyle}>
      <h2 style={titleStyle}>Digests paused</h2>
      <p style={subStyle}>Resume to see today&apos;s view.</p>
      {onResume && (
        <button type="button" style={primaryButtonStyle()} onClick={onResume}>
          Resume
        </button>
      )}
    </div>
  );
}

function AuthExpiredState({
  onReconnectGmail,
}: {
  onReconnectGmail?: () => void;
}): JSX.Element {
  return (
    <div className="edigest-empty edigest-empty--auth" style={cardStyle}>
      <div style={{ color: 'var(--bridge-rust, #b04a2c)' }}>
        <AuthErrorIcon />
      </div>
      <h2 style={titleStyle}>Reconnect Gmail</h2>
      <p style={subStyle}>
        Your Gmail connection has expired. Reconnect to keep digests flowing.
      </p>
      {onReconnectGmail && (
        <button type="button" style={primaryButtonStyle()} onClick={onReconnectGmail}>
          Reconnect
        </button>
      )}
    </div>
  );
}

function FirstRunState({ onRefresh }: { onRefresh?: () => void }): JSX.Element {
  return (
    <div className="edigest-empty edigest-empty--first-run" style={cardStyle}>
      <h2 style={titleStyle}>Your first digest is on the way</h2>
      <p style={subStyle}>
        We&apos;re scanning your kids&apos; inboxes for the first time. This usually takes
        a couple of minutes.
      </p>
      {onRefresh && (
        <button type="button" style={ghostButtonStyle()} onClick={onRefresh}>
          Refresh now
        </button>
      )}
    </div>
  );
}

function LegacyBlobState({ legacyBlob }: { legacyBlob?: string }): JSX.Element {
  const [purify, setPurify] = useState<DOMPurifyType | null>(null);
  const [purifyError, setPurifyError] = useState(false);

  useEffect(() => {
    if (!legacyBlob || purify || purifyError) return;
    let cancelled = false;
    import('dompurify')
      .then((m) => {
        if (!cancelled) setPurify(() => m.default);
      })
      .catch(() => {
        if (!cancelled) setPurifyError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [legacyBlob, purify, purifyError]);

  return (
    <section
      className="edigest-empty edigest-empty--legacy"
      style={{
        ...cardStyle,
        alignItems: 'stretch',
        textAlign: 'left',
        padding: '24px',
      }}
      aria-label="Today's digest"
    >
      <h2 style={{ ...titleStyle, marginTop: 0 }}>Today&apos;s digest</h2>
      {!legacyBlob ? (
        <p style={subStyle}>No digest content available.</p>
      ) : purify ? (
        <div
          className="edigest-empty__legacy-html"
          data-testid="legacy-blob-html"
          dangerouslySetInnerHTML={{ __html: purify.sanitize(legacyBlob) }}
        />
      ) : purifyError ? (
        <p style={subStyle}>Could not load digest content. Please refresh.</p>
      ) : (
        <p style={subStyle}>Loading content...</p>
      )}
    </section>
  );
}

export function EmptyStates({
  kind,
  legacyBlob,
  onRefresh,
  onAddKids,
  onResume,
  onReconnectGmail,
}: EmptyStatesProps): JSX.Element {
  switch (kind) {
    case 'calm':
      return <CalmState onRefresh={onRefresh} />;
    case 'no_kids':
      return <NoKidsState onAddKids={onAddKids} />;
    case 'paused':
      return <PausedState onResume={onResume} />;
    case 'auth_expired':
      return <AuthExpiredState onReconnectGmail={onReconnectGmail} />;
    case 'first_run':
      return <FirstRunState onRefresh={onRefresh} />;
    case 'legacy_blob':
      return <LegacyBlobState legacyBlob={legacyBlob} />;
  }
}

export type { EmptyStateKind, EmptyStatesProps };
