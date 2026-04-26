/**
 * CheckInDonePage — Screen 3 of the kid /checkin flow.
 *
 * Success ring + ArcMascot mood=`celebrating` + inline streak badge (no XP)
 * + "Tonight your parents will see…" preview list + explicit close.
 * Auto-dismisses after 8s per the design lock § 7 (no engagement farming —
 * VPC). The kid can tap to cancel the auto-dismiss.
 *
 * Spec: docs/design/CB-DCI-001-daily-checkin.md § 7.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { ArcMascot } from '../../components/arc/ArcMascot';
import { DciStreakBadge } from '../../components/dci/DciStreakBadge';
import { dciApi, type DciClassification, type DciStreakResponse } from '../../api/dci';
import './CheckIn.css';

const AUTO_DISMISS_MS = 8_000;

interface DoneLocationState {
  classifications?: DciClassification[];
  completed_seconds?: number;
}

export function CheckInDonePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state ?? {}) as DoneLocationState;
  const { user } = useAuth();
  const kidId = user?.id ?? null;
  const dismissTimerRef = useRef<number | null>(null);
  const [stayOpen, setStayOpen] = useState(false);

  const cancelDismiss = useCallback(() => {
    if (dismissTimerRef.current !== null) {
      window.clearTimeout(dismissTimerRef.current);
      dismissTimerRef.current = null;
    }
    setStayOpen(true);
  }, []);

  // Auto-dismiss to /. Spec is explicit: kid should close, not engagement-farm.
  // The kid interrupts via the explicit "Stay open" button (issue #4196) —
  // accidental scroll-taps on streak badge / preview list no longer cancel.
  useEffect(() => {
    if (stayOpen) return;
    dismissTimerRef.current = window.setTimeout(
      () => navigate('/'),
      AUTO_DISMISS_MS,
    );
    return () => {
      if (dismissTimerRef.current !== null) {
        window.clearTimeout(dismissTimerRef.current);
        dismissTimerRef.current = null;
      }
    };
  }, [navigate, stayOpen]);

  const streakQuery = useQuery<DciStreakResponse | null>({
    queryKey: ['dci', 'streak', kidId, 'after-checkin'],
    queryFn: () =>
      kidId !== null ? dciApi.getStreak(kidId) : Promise.resolve(null),
    enabled: kidId !== null,
    retry: false,
  });

  const previewBullets = useMemo(() => {
    return (state.classifications ?? []).map((c, i) => {
      const subject = c.subject ?? 'Something new';
      const topic = c.topic ? ` — ${c.topic}` : '';
      const deadline = c.deadline_iso ? ` (due ${c.deadline_iso})` : '';
      return { key: `${c.artifact_type}-${i}`, text: `${subject}${topic}${deadline}` };
    });
  }, [state.classifications]);

  const streak = streakQuery.data;

  return (
    <main className="dci-checkin">
      <div className="dci-checkin__shell dci-checkin__done">
        <div className="dci-checkin__success-ring" aria-hidden="true">
          ✓
        </div>
        <ArcMascot mood="celebrating" size={96} glow />
        {streak && (
          <DciStreakBadge
            current={streak.current_streak}
            longest={streak.longest_streak}
          />
        )}
        {previewBullets.length > 0 && (
          <>
            <p className="dci-checkin__preview-heading">
              Tonight your parents will see:
            </p>
            <ul className="dci-checkin__preview-list">
              {previewBullets.map((b) => (
                <li key={b.key}>{b.text}</li>
              ))}
            </ul>
          </>
        )}
        <p className="dci-checkin__close-msg">
          Close the app. Have a snack. You're good.
        </p>
        {!stayOpen && (
          <button
            type="button"
            className="dci-checkin__stay-open"
            onClick={cancelDismiss}
          >
            Stay open
          </button>
        )}
      </div>
    </main>
  );
}

export default CheckInDonePage;
