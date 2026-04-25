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
import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { ArcMascot } from '../../components/arc/ArcMascot';
import { dciApi, type DciClassification, type DciStreakResponse } from '../../api/dci';
import './CheckIn.css';

const AUTO_DISMISS_MS = 8_000;

interface DoneLocationState {
  classifications?: DciClassification[];
  completed_seconds?: number;
}

// Inline streak-only badge: no XP coupling, day count + secondary "Longest N"
// label. Kept here (not as a new file) to avoid expanding the file footprint.
function DciStreakBadge({
  current,
  longest,
}: {
  current: number;
  longest: number;
}) {
  return (
    <div
      role="status"
      aria-label={`Current streak ${current} days, longest ${longest} days`}
      style={{
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2,
        padding: '8px 16px',
        borderRadius: 16,
        background: 'var(--color-accent-light, #fff7e6)',
        color: 'var(--color-accent-strong, #b45309)',
        fontWeight: 600,
      }}
    >
      <span style={{ fontSize: '1.6rem', lineHeight: 1 }}>{current}</span>
      <span style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        day{current === 1 ? '' : 's'} in a row
      </span>
      {longest > 0 && (
        <span
          style={{
            fontSize: '0.72rem',
            opacity: 0.75,
            fontWeight: 400,
          }}
        >
          Longest {longest}
        </span>
      )}
    </div>
  );
}

export function CheckInDonePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state ?? {}) as DoneLocationState;
  const { user } = useAuth();
  const kidId = user?.id ?? null;
  const dismissTimerRef = useRef<number | null>(null);

  const cancelDismiss = useCallback(() => {
    if (dismissTimerRef.current !== null) {
      window.clearTimeout(dismissTimerRef.current);
      dismissTimerRef.current = null;
    }
  }, []);

  // Auto-dismiss to /. Spec is explicit: kid should close, not engagement-farm.
  // The kid can interrupt by tapping anywhere on the screen — handled below
  // via onClick on <main>.
  useEffect(() => {
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
  }, [navigate]);

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
    <main className="dci-checkin" onClick={cancelDismiss}>
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
      </div>
    </main>
  );
}

export default CheckInDonePage;
