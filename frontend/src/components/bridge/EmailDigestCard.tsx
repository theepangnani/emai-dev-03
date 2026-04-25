/**
 * CB-BRIDGE-HF Stream B (#4128) — Thin Email Digest summary card.
 *
 * The unified `/email-digest` page (per #4102 / #4103) is the correct home
 * for per-kid email digest management (Send Now, Sync Now, Digest History,
 * school email visibility). This card is now a thin summary whose primary
 * action navigates to that hub. When no integration exists, the action
 * routes to the existing setup wizard instead.
 */
interface EmailDigestCardProps {
  hasIntegration: boolean;
  onSetup: () => void;
  onOpenDigest: () => void;
  childName: string;
}

export function EmailDigestCard({ hasIntegration, onSetup, onOpenDigest, childName }: EmailDigestCardProps) {
  return (
    <article className="bridge-card bridge-card--digest">
      <header className="bridge-card-head">
        <div className="bridge-card-title-wrap">
          <span className="bridge-digest-meta">
            {hasIntegration ? (
              <>
                <span className="bridge-digest-live-dot" aria-hidden="true" />
                DAILY · 7:30 AM
              </>
            ) : (
              'SETUP NEEDED'
            )}
          </span>
          <h3>Email Digest</h3>
          <p className="bridge-card-desc">
            What lands in your inbox each morning — tuned for {childName}.
          </p>
        </div>
      </header>

      {hasIntegration ? (
        <div className="bridge-empty-hint">
          Daily digest for {childName} — open the digest hub to manage delivery, school email, and recent sends.
        </div>
      ) : (
        <div className="bridge-empty-hint">
          Not set up yet for {childName}. Set up to get classroom updates, teacher emails, and weekly progress in one inbox-friendly summary.
        </div>
      )}

      <footer className="bridge-card-foot">
        {hasIntegration ? (
          <button type="button" className="bridge-head-action" onClick={onOpenDigest}>
            Open digest →
          </button>
        ) : (
          <button type="button" className="bridge-head-action" onClick={onSetup}>
            Set up →
          </button>
        )}
      </footer>
    </article>
  );
}
