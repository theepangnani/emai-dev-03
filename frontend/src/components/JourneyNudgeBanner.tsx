import { useEffect, useRef, useState } from 'react';
import { useJourneyHint } from '../hooks/useJourneyHint';
import { useFABContext } from '../context/FABContext';
import './JourneyNudgeBanner.css';

interface JourneyNudgeBannerProps {
  pageName: string;
}

export function JourneyNudgeBanner({ pageName }: JourneyNudgeBannerProps) {
  const { hint, loading, dismiss } = useJourneyHint(pageName);
  const { openChatWithQuestion } = useFABContext();
  const [visible, setVisible] = useState(false);
  const mountTimeRef = useRef<number>(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Track mount time for auto-dismiss on quick navigation
  useEffect(() => {
    mountTimeRef.current = Date.now();
    return () => {
      // If unmounted within 2 seconds, treat as navigation-away dismiss
      if (Date.now() - mountTimeRef.current < 2000 && timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  // Trigger fade-in after hint loads
  useEffect(() => {
    if (!hint || hint.hint_key === 'welcome_modal') {
      return;
    }
    timerRef.current = setTimeout(() => setVisible(true), 50);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      setVisible(false);
    };
  }, [hint]);

  if (loading || !hint || !hint.hint_key || hint.hint_key === 'welcome_modal') {
    return null;
  }

  const handleAskBot = () => {
    openChatWithQuestion(hint.title);
    dismiss();
  };

  const handleLearnMore = () => {
    // Navigate handled by anchor tag
    dismiss();
  };

  return (
    <div
      className={`journey-nudge-banner ${visible ? 'journey-nudge-banner--visible' : ''}`}
      role="status"
      aria-live="polite"
    >
      <div className="journey-nudge-banner__content">
        <span className="journey-nudge-banner__icon" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 18h6" />
            <path d="M10 22h4" />
            <path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z" />
          </svg>
        </span>
        <span className="journey-nudge-banner__text">{hint.title}</span>
      </div>
      <div className="journey-nudge-banner__actions">
        <a
          href={`/help#journey-${hint.journey_id.toLowerCase()}`}
          className="journey-nudge-banner__link"
          onClick={handleLearnMore}
        >
          Learn more
        </a>
        <button
          type="button"
          className="journey-nudge-banner__bot-btn"
          onClick={handleAskBot}
        >
          Ask Bot
        </button>
        <button
          type="button"
          className="journey-nudge-banner__dismiss"
          onClick={dismiss}
          aria-label="Dismiss hint"
        >
          &times;
        </button>
      </div>
    </div>
  );
}
