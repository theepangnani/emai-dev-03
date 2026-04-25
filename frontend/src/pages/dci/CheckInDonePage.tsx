/**
 * CheckInDonePage — Screen 3 of the kid /checkin flow.
 *
 * Success ring + ArcMascot mood=`celebrating` + XpStreakBadge + "Tonight
 * your parents will see…" preview list + explicit close. Auto-dismisses
 * after 8s per the design lock § 7 (no engagement farming — VPC).
 *
 * Spec: docs/design/CB-DCI-001-daily-checkin.md § 7.
 */
import { useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { ArcMascot } from '../../components/arc/ArcMascot';
import { XpStreakBadge } from '../../components/arc/XpStreakBadge';
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

  // Auto-dismiss to /. Spec is explicit: kid should close, not engagement-farm.
  useEffect(() => {
    const t = window.setTimeout(() => navigate('/'), AUTO_DISMISS_MS);
    return () => window.clearTimeout(t);
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
    <main className="dci-checkin">
      <div className="dci-checkin__shell dci-checkin__done">
        <div className="dci-checkin__success-ring" aria-hidden="true">
          ✓
        </div>
        <ArcMascot mood="celebrating" size={96} glow />
        {streak && (
          <XpStreakBadge
            xp={streak.current_streak}
            streak={streak.current_streak}
            levelLabel={
              streak.longest_streak > 0
                ? `Longest ${streak.longest_streak}`
                : undefined
            }
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
