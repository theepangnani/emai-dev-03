import { useState, useCallback } from 'react';
import { googleApi } from '../api/client';
import './GoogleClassroomPrompt.css';

const DISMISS_KEY_PREFIX = 'gc-prompt-dismissed-';
const DISMISS_DURATION_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

interface GoogleClassroomPromptProps {
  childName: string;
  childStudentId: number;
  onAddManually?: () => void;
}

function isDismissed(childStudentId: number): boolean {
  try {
    const ts = localStorage.getItem(`${DISMISS_KEY_PREFIX}${childStudentId}`);
    if (!ts) return false;
    return Date.now() - Number(ts) < DISMISS_DURATION_MS;
  } catch {
    return false;
  }
}

function dismissForChild(childStudentId: number): void {
  try {
    localStorage.setItem(`${DISMISS_KEY_PREFIX}${childStudentId}`, String(Date.now()));
  } catch { /* ignore */ }
}

export function GoogleClassroomPrompt({
  childName,
  childStudentId,
  onAddManually,
}: GoogleClassroomPromptProps) {
  const [dismissed, setDismissed] = useState(() => isDismissed(childStudentId));
  const [connecting, setConnecting] = useState(false);

  const handleConnect = useCallback(async () => {
    setConnecting(true);
    try {
      const data = await googleApi.getConnectUrl();
      if (data.url || data.auth_url) {
        window.location.href = data.url || data.auth_url;
      }
    } catch {
      // Fall back to direct navigation
      window.location.href = '/api/google/connect';
    } finally {
      setConnecting(false);
    }
  }, []);

  const handleDismiss = useCallback(() => {
    dismissForChild(childStudentId);
    setDismissed(true);
  }, [childStudentId]);

  if (dismissed) return null;

  const firstName = childName.split(' ')[0];

  return (
    <div className="gc-prompt" role="region" aria-label="Connect Google Classroom">
      <div className="gc-prompt-icon" aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 48 48" fill="none">
          <rect width="48" height="48" rx="8" fill="#1a73e8" fillOpacity="0.1" />
          <path d="M24 14c-5.52 0-10 4.48-10 10s4.48 10 10 10 10-4.48 10-10-4.48-10-10-10zm-1 15v-4h-4v-2h4v-4h2v4h4v2h-4v4h-2z" fill="#1a73e8" />
        </svg>
      </div>
      <div className="gc-prompt-content">
        <p className="gc-prompt-text">
          Connect {firstName}'s school to see classes, assignments, and due dates.
        </p>
        <div className="gc-prompt-actions">
          <button
            className="gc-prompt-btn gc-prompt-btn-primary"
            onClick={handleConnect}
            disabled={connecting}
          >
            {connecting ? 'Connecting...' : 'Connect Google Classroom'}
          </button>
          {onAddManually && (
            <button
              className="gc-prompt-btn gc-prompt-btn-secondary"
              onClick={onAddManually}
            >
              Add Manually
            </button>
          )}
        </div>
      </div>
      <button
        className="gc-prompt-dismiss"
        onClick={handleDismiss}
        aria-label="Skip for now"
        title="Skip for now — hides for 7 days"
      >
        &times;
      </button>
    </div>
  );
}
