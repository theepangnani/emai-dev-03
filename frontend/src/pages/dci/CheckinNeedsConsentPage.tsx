/**
 * CheckinNeedsConsentPage — kid-friendly fallback when /checkin is hit
 * without a saved consent row for the kid.
 *
 * #4266: the previous behaviour redirected the kid straight to
 * `/dci/consent`, which is `ProtectedRoute role=parent`. The kid bounced
 * twice — first to /dci/consent, then back to `/` (no role match) — with
 * no explanation. This page replaces that two-hop bounce with an in-app
 * message the kid can show their parent, plus a copy-link affordance.
 *
 * Spec note: parent-side consent grant is owned by /dci/consent — this
 * page is read-only on the kid side. It does NOT call any consent API.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArcMascot } from '../../components/arc/ArcMascot';
import './CheckinNeedsConsentPage.css';

const CONSENT_URL_PATH = '/dci/consent';

function buildConsentUrl(): string {
  if (typeof window === 'undefined') return CONSENT_URL_PATH;
  return `${window.location.origin}${CONSENT_URL_PATH}`;
}

export function CheckinNeedsConsentPage() {
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);
  const consentUrl = buildConsentUrl();

  async function handleCopy() {
    try {
      // Clipboard API is async + permission-gated; fall back to a
      // hidden-input selectAndCopy for older browsers.
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(consentUrl);
      } else {
        const ta = document.createElement('textarea');
        ta.value = consentUrl;
        ta.setAttribute('readonly', '');
        ta.style.position = 'absolute';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Silent — copy is a convenience; the URL is still on screen.
    }
  }

  return (
    <main className="dci-needs-consent">
      <div className="dci-needs-consent__shell">
        <div className="dci-needs-consent__mascot">
          <ArcMascot mood="thinking" size={96} glow />
        </div>
        <h1 className="dci-needs-consent__title">
          We need your parent&rsquo;s OK first
        </h1>
        <p className="dci-needs-consent__body">
          Daily Check-In is a quick 60-second way to share your day with your
          family. Before we turn it on, your parent has to enable it on their
          ClassBridge account.
        </p>
        <p className="dci-needs-consent__body">
          Show this page to your parent — or send them the link below.
        </p>

        <div className="dci-needs-consent__link-row">
          <code
            className="dci-needs-consent__link"
            data-testid="dci-needs-consent-url"
          >
            {consentUrl}
          </code>
          <button
            type="button"
            className="dci-needs-consent__copy"
            onClick={handleCopy}
            data-testid="dci-needs-consent-copy"
          >
            {copied ? 'Copied!' : 'Copy link'}
          </button>
        </div>

        <div className="dci-needs-consent__nav">
          <button
            type="button"
            className="dci-needs-consent__back"
            onClick={() => navigate('/dashboard')}
          >
            Back to dashboard
          </button>
        </div>
      </div>
    </main>
  );
}

export default CheckinNeedsConsentPage;
