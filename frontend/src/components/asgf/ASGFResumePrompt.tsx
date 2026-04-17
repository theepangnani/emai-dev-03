/**
 * ASGFResumePrompt -- Banner shown when the user has an active unfinished
 * ASGF session that can be resumed (within 24 hours of creation).
 *
 * Issue: #3409
 */
import { useEffect, useState } from 'react';

import { asgfApi, type ActiveSessionItem } from '../../api/asgf';

import './ASGFResumePrompt.css';

interface Props {
  /** Called when the user clicks "Resume" with the session to resume. */
  onResume: (session: ActiveSessionItem) => void;
  /** Called when the user clicks "Start Fresh" to dismiss the prompt. */
  onDismiss?: () => void;
}

export default function ASGFResumePrompt({ onResume, onDismiss }: Props) {
  const [session, setSession] = useState<ActiveSessionItem | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    asgfApi
      .getActiveSessions()
      .then((res) => {
        if (!cancelled && res.sessions.length > 0) {
          setSession(res.sessions[0]);
        }
      })
      .catch(() => {
        /* silent -- no resume prompt if fetch fails */
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading || dismissed || !session) return null;

  const truncatedQuestion =
    session.question.length > 80
      ? session.question.slice(0, 77) + '...'
      : session.question;

  const subject = session.subject ? ` in ${session.subject}` : '';

  return (
    <div className="asgf-resume-prompt" role="status">
      <span className="asgf-resume-prompt__icon" aria-hidden="true">
        &#128218;
      </span>
      <div className="asgf-resume-prompt__body">
        <p className="asgf-resume-prompt__text">
          You have an unfinished study session{subject}:{' '}
          <strong>{truncatedQuestion}</strong>
        </p>
        <p className="asgf-resume-prompt__meta">
          {session.slide_count} slides &middot; Resume or start fresh?
        </p>
      </div>
      <div className="asgf-resume-prompt__actions">
        <button
          className="asgf-resume-prompt__btn asgf-resume-prompt__btn--resume"
          onClick={() => onResume(session)}
        >
          Resume
        </button>
        <button
          className="asgf-resume-prompt__btn asgf-resume-prompt__btn--fresh"
          onClick={() => {
            setDismissed(true);
            onDismiss?.();
          }}
        >
          Start Fresh
        </button>
      </div>
    </div>
  );
}
