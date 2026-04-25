/**
 * CB-BRIDGE-004 — Email Digest management card (#4117).
 *
 * Decision (locked in plan): toggles are read-only summaries for now.
 * Editing routes to the existing EmailDigestSetupWizard so we do not
 * block on a per-channel PATCH endpoint.
 */
interface EmailDigestCardProps {
  hasIntegration: boolean;
  onSetup: () => void;
  childName: string;
}

const TOPICS = [
  { title: 'Classroom updates', meta: 'Announcements, new assignments, grades posted' },
  { title: 'Teacher emails', meta: 'Auto-summarised from linked teachers' },
  { title: 'Weekly progress', meta: 'XP earned, study streaks, weak spots' },
  { title: 'Dinner-table talk', meta: 'AI-picked conversation starters from the week' },
];

export function EmailDigestCard({ hasIntegration, onSetup, childName }: EmailDigestCardProps) {
  return (
    <article className="bridge-card bridge-card--digest">
      <header className="bridge-card-head">
        <div className="bridge-card-title-wrap">
          <span className="bridge-digest-meta">
            <span className="bridge-digest-live-dot" aria-hidden="true" />
            DAILY · 7:30 AM
          </span>
          <h3>Email Digest</h3>
          <p className="bridge-card-desc">
            What lands in your inbox each morning — tuned for {childName}.
          </p>
        </div>
        <button type="button" className="bridge-head-action" onClick={onSetup}>
          {hasIntegration ? 'Edit setup' : 'Set up'}
        </button>
      </header>

      {hasIntegration ? (
        <ul className="bridge-digest-list" role="list">
          {TOPICS.map(t => (
            <li key={t.title}>
              <div className="bridge-digest-row-text">
                <div className="bridge-digest-row-title">{t.title}</div>
                <div className="bridge-digest-row-meta">{t.meta}</div>
              </div>
              <span className="bridge-digest-status" aria-label="Enabled">
                ● On
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="bridge-empty-hint">
          Daily digest is not set up yet for {childName}. Set up to get classroom updates, teacher emails, and weekly progress in one inbox-friendly summary.
        </div>
      )}
    </article>
  );
}
