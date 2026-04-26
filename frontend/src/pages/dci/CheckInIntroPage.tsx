/**
 * CheckInIntroPage — Screen 1 of the kid /checkin flow.
 * Greeting + 3 equal-priority CTAs. ArcMascot mood=`waving`.
 *
 * Adaptive tone: greeting drops the trailing `!` if the kid's last voice
 * sentiment was ≤ -0.3. Streak fetch is best-effort — if backend isn't
 * deployed yet we silently default to neutral (no `!` suppression).
 *
 * Spec: docs/design/CB-DCI-001-daily-checkin.md § 7.
 */
import { useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { ArcMascot } from '../../components/arc/ArcMascot';
import { dciApi, type DciStreakResponse } from '../../api/dci';
import { useDciConsent } from '../../hooks/useDciConsent';
import { emitDciKidEvent } from '../../components/dci/telemetry';
import type { CaptureMode } from '../../components/dci/CapturePicker';
import './CheckIn.css';

export function CheckInIntroPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const kidId = user?.id ?? null;
  const kidName = user?.full_name?.split(' ')[0] ?? 'friend';

  const streakQuery = useQuery<DciStreakResponse | null>({
    queryKey: ['dci', 'streak', kidId],
    queryFn: () =>
      kidId !== null ? dciApi.getStreak(kidId) : Promise.resolve(null),
    enabled: kidId !== null,
    retry: false,
    staleTime: 60_000,
  });

  // M0-13 (#4260): bounce to /dci/consent when consent is missing for this
  // kid (404 from the consent endpoint, or AI processing toggled off). Without
  // this, the next /api/dci/checkin POST would 403 with no in-app way to
  // grant consent. The parent-only consent route on the other side decides
  // how to actually surface the request.
  const consentQuery = useDciConsent(kidId);
  const consentMissing =
    kidId !== null &&
    !consentQuery.isLoading &&
    (consentQuery.isError || (consentQuery.data && !consentQuery.data.ai_ok));
  useEffect(() => {
    if (!consentMissing) return;
    const target = `/dci/consent?return_to=${encodeURIComponent('/checkin')}`;
    navigate(target, { replace: true });
  }, [consentMissing, navigate]);

  useEffect(() => {
    emitDciKidEvent('dci.kid.opened');
  }, []);

  const sentiment = streakQuery.data?.last_voice_sentiment ?? null;
  const greeting = useMemo(() => {
    const base = `Hi ${kidName}`;
    return sentiment !== null && sentiment <= -0.3 ? `${base}.` : `${base}!`;
  }, [kidName, sentiment]);

  const choose = (type: CaptureMode) => {
    emitDciKidEvent('dci.kid.input_chosen', { type });
    navigate(`/checkin/capture?mode=${type}`);
  };

  return (
    <main className="dci-checkin">
      <div className="dci-checkin__shell">
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <ArcMascot mood="waving" size={96} glow />
        </div>
        <h1 className="dci-checkin__greeting">{greeting}</h1>
        <p className="dci-checkin__sub">
          Quick 60-second check-in. How was school today?
        </p>

        <div className="dci-checkin__input-buttons">
          <button
            type="button"
            className="dci-checkin__input-cta"
            onClick={() => choose('photo')}
          >
            <span className="dci-checkin__input-cta-icon" aria-hidden="true">
              📸
            </span>
            <span>Snap a photo</span>
            <span className="dci-checkin__input-cta-hint">
              Handout · Board · Notebook
            </span>
          </button>
          <button
            type="button"
            className="dci-checkin__input-cta"
            onClick={() => choose('voice')}
          >
            <span className="dci-checkin__input-cta-icon" aria-hidden="true">
              🎙️
            </span>
            <span>Record voice</span>
            <span className="dci-checkin__input-cta-hint">
              "Today we learned…"
            </span>
          </button>
          <button
            type="button"
            className="dci-checkin__input-cta"
            onClick={() => choose('text')}
          >
            <span className="dci-checkin__input-cta-icon" aria-hidden="true">
              ✏️
            </span>
            <span>Type a line</span>
            <span className="dci-checkin__input-cta-hint">Quick &amp; easy</span>
          </button>
        </div>
      </div>
    </main>
  );
}

export default CheckInIntroPage;
