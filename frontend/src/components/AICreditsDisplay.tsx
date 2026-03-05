import { useState } from 'react';
import { useAIUsage } from '../hooks/useAIUsage';
import { AILimitRequestModal } from './AILimitRequestModal';
import './AICreditsDisplay.css';

/**
 * Badge showing AI credit usage (e.g. "AI: 7/10").
 * Color-coded: green = plenty, yellow = warning, red = at limit.
 * Placed in the dashboard header area next to NotificationBell.
 */
export function AICreditsDisplay() {
  const { count, limit, remaining, atLimit, warningThreshold, isLoading } = useAIUsage();
  const [showRequestModal, setShowRequestModal] = useState(false);

  if (isLoading || limit === 0) return null;

  const usagePercent = limit > 0 ? (count / limit) * 100 : 0;
  const isWarning = remaining <= (limit - warningThreshold) === false && usagePercent >= 80;
  const statusClass = atLimit ? 'at-limit' : isWarning ? 'warning' : 'ok';

  return (
    <>
      <button
        className={`ai-credits-badge ai-credits-badge--${statusClass}`}
        onClick={() => atLimit && setShowRequestModal(true)}
        title={atLimit ? 'AI limit reached - click to request more' : `${remaining} AI credits remaining this ${count > 0 ? 'period' : 'month'}`}
        aria-label={`AI usage: ${count} of ${limit} credits used`}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
        </svg>
        <span className="ai-credits-text">AI: {count}/{limit}</span>
      </button>

      <AILimitRequestModal
        open={showRequestModal}
        onClose={() => setShowRequestModal(false)}
      />
    </>
  );
}

/**
 * Warning banner shown when usage >= 80%.
 * Dismissible, with a link to request more credits.
 */
export function AIWarningBanner() {
  const { remaining, limit, atLimit, isLoading } = useAIUsage();
  const [dismissed, setDismissed] = useState(false);
  const [showRequestModal, setShowRequestModal] = useState(false);

  if (isLoading || limit === 0 || dismissed) return null;

  const usagePercent = limit > 0 ? ((limit - remaining) / limit) * 100 : 0;
  if (usagePercent < 80 && !atLimit) return null;

  return (
    <>
      <div className={`ai-warning-banner${atLimit ? ' ai-warning-banner--limit' : ''}`}>
        <span className="ai-warning-banner-text">
          {atLimit
            ? 'You have reached your AI credit limit for this period.'
            : `You have ${remaining} AI credit${remaining !== 1 ? 's' : ''} remaining.`}
        </span>
        <button
          className="ai-warning-banner-action"
          onClick={() => setShowRequestModal(true)}
        >
          Request More
        </button>
        <button
          className="ai-warning-banner-dismiss"
          onClick={() => setDismissed(true)}
          aria-label="Dismiss"
        >
          &times;
        </button>
      </div>

      <AILimitRequestModal
        open={showRequestModal}
        onClose={() => setShowRequestModal(false)}
      />
    </>
  );
}
