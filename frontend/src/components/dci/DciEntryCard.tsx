import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useFeatureFlagState } from '../../hooks/useFeatureToggle';
import './DciEntryCard.css';

/**
 * CB-DCI-001 M0-12 — Soft-pitched parent entry tile (#4258).
 *
 * Adds a flag-gated card on the parent landing surface that links to the
 * M0 DCI routes (`/parent/today` and `/checkin`). Hidden entirely while
 * the `dci_v1_enabled` flag query is loading or the flag is OFF — the
 * feature should be invisible until intentionally enabled.
 *
 * Design lock § 7-8: copy is gentle, never pushy. The kid view link sits
 * as a secondary action with a small mobile-app handoff note (kid mobile
 * app is fast-follow; until then, parents share the URL).
 */
export function DciEntryCard() {
  const { enabled, isLoading } = useFeatureFlagState('dci_v1_enabled');
  const [copied, setCopied] = useState(false);

  if (isLoading || !enabled) return null;

  const handleCopyLink = async () => {
    const url = `${window.location.origin}/checkin`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard may be unavailable (insecure context, denied permission);
      // fail silently — the visible Kid view link still serves as fallback.
    }
  };

  return (
    <section
      className="dci-entry-card"
      aria-labelledby="dci-entry-card-title"
    >
      <header className="dci-entry-card__header">
        <p className="dci-entry-card__eyebrow">New &middot; Daily ritual</p>
        <h3 className="dci-entry-card__title" id="dci-entry-card-title">
          Daily Check-In
        </h3>
        <p className="dci-entry-card__subtitle">
          5-min evening conversation about your kid&rsquo;s day
        </p>
      </header>

      <div className="dci-entry-card__actions">
        <Link
          to="/parent/today"
          className="dci-entry-card__primary"
        >
          Open today&rsquo;s summary
        </Link>
        <Link
          to="/checkin"
          className="dci-entry-card__secondary"
        >
          Kid view
        </Link>
        <button
          type="button"
          className="dci-entry-card__copy"
          onClick={handleCopyLink}
        >
          Copy link
        </button>
        {/* Stable accessible name on the button; the live announcement is a
            sibling region so SRs reliably read it (button-name-change
            announcements are inconsistent across SR/browser combos). */}
        <span aria-live="polite" className="sr-only">
          {copied ? 'Link copied' : ''}
        </span>
      </div>

      <p className="dci-entry-card__note">
        Share this link with your kid (mobile app coming soon).
      </p>
    </section>
  );
}
