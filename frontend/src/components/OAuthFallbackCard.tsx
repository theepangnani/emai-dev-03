import './OAuthFallbackCard.css';

interface OAuthFallbackCardProps {
  errorMessage?: string;
  onNavigateToImport: () => void;
}

export default function OAuthFallbackCard({
  errorMessage,
  onNavigateToImport,
}: OAuthFallbackCardProps) {
  return (
    <div className="oauth-fallback" role="alert" aria-labelledby="oauth-fallback-title">
      {/* ── Error header ──────────────────────────────────────── */}
      <div className="oauth-fallback-header">
        <div className="oauth-fallback-icon" aria-hidden="true">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M16 3L2 29h28L16 3z"
              fill="var(--color-warning-light)"
              stroke="var(--color-warning)"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <path
              d="M16 13v7"
              stroke="var(--color-warning-text)"
              strokeWidth="2"
              strokeLinecap="round"
            />
            <circle cx="16" cy="24" r="1.2" fill="var(--color-warning-text)" />
          </svg>
        </div>
        <div className="oauth-fallback-header-text">
          <h3 className="oauth-fallback-title" id="oauth-fallback-title">
            School Account Connection Blocked
          </h3>
          <p className="oauth-fallback-subtitle">
            Your school board has restricted third-party app access to Google
            Classroom. This is a common security policy.
          </p>
        </div>
      </div>

      {/* ── Original error (if provided) ──────────────────────── */}
      {errorMessage && (
        <div className="oauth-fallback-error">
          <span className="oauth-fallback-error-label">Error detail:</span>{' '}
          {errorMessage}
        </div>
      )}

      {/* ── What this means ───────────────────────────────────── */}
      <div className="oauth-fallback-explainer">
        <p className="oauth-fallback-explainer-heading">What this means:</p>
        <ul className="oauth-fallback-explainer-list">
          <li>ClassBridge cannot directly sync with your school's Google Classroom.</li>
          <li>
            But don't worry — we have several alternative ways to import your
            data!
          </li>
        </ul>
      </div>

      {/* ── Alternative methods ────────────────────────────────── */}
      <ul className="oauth-fallback-methods" aria-label="Alternative import methods">
        <li className="oauth-fallback-method">
          <svg className="oauth-fallback-method-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="1.5" />
            <path d="M8 12h8M12 8v8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <div>
            <span className="oauth-fallback-method-name">Copy &amp; Paste</span>
            <span className="oauth-fallback-method-desc">
              Fastest: copy text from Classroom and paste it
            </span>
          </div>
        </li>

        <li className="oauth-fallback-method">
          <svg className="oauth-fallback-method-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="3" y="4" width="18" height="14" rx="2" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="9" cy="10" r="2" stroke="currentColor" strokeWidth="1.2" />
            <path d="M3 16l5-4 3 2 4-3 6 5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <span className="oauth-fallback-method-name">Screenshots</span>
            <span className="oauth-fallback-method-desc">
              Take photos of your Classroom pages
            </span>
          </div>
        </li>

        <li className="oauth-fallback-method">
          <svg className="oauth-fallback-method-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" strokeWidth="1.5" />
            <path d="M3 7l9 6 9-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <span className="oauth-fallback-method-name">Email Forward</span>
            <span className="oauth-fallback-method-desc">
              Auto-forward notification emails
            </span>
          </div>
        </li>

        <li className="oauth-fallback-method">
          <svg className="oauth-fallback-method-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.5" />
            <path d="M3 9h18M8 4V2M16 4V2M7 13h2M11 13h2M15 13h2M7 17h2M11 17h2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <div>
            <span className="oauth-fallback-method-name">Calendar Import</span>
            <span className="oauth-fallback-method-desc">
              Export calendar for due dates
            </span>
          </div>
        </li>

        <li className="oauth-fallback-method">
          <svg className="oauth-fallback-method-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M4 4h16v16H4z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M4 9h16M9 4v16" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
          <div>
            <span className="oauth-fallback-method-name">CSV</span>
            <span className="oauth-fallback-method-desc">
              Fill in a spreadsheet template
            </span>
          </div>
        </li>
      </ul>

      {/* ── CTA ───────────────────────────────────────────────── */}
      <div className="oauth-fallback-footer">
        <button
          className="oauth-fallback-cta"
          onClick={onNavigateToImport}
          type="button"
        >
          View Import Methods
        </button>
        <p className="oauth-fallback-footer-hint">
          Or ask your school's IT administrator to allow ClassBridge
        </p>
      </div>
    </div>
  );
}
