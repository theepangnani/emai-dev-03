/**
 * XpStreakBadge — subtle gamification chip that pins to the Ask/Flash Tutor
 * hero. Shows current XP with a tick-up animation when it changes, and a
 * streak flame if the user has 2+ consecutive days of learning.
 *
 * Pure presentational — data is supplied by the parent (no API calls here).
 */
import { useEffect, useRef, useState } from 'react';
import './XpStreakBadge.css';

export interface XpStreakBadgeProps {
  xp: number;
  /** Current daily streak (days). Hidden below 2. */
  streak?: number;
  /** Badge level unlocked ("Apprentice", "Scholar", etc.). Optional. */
  levelLabel?: string;
  className?: string;
}

export function XpStreakBadge({ xp, streak = 0, levelLabel, className = '' }: XpStreakBadgeProps) {
  const [displayXp, setDisplayXp] = useState(xp);
  const [pulsing, setPulsing] = useState(false);
  const [announcement, setAnnouncement] = useState<string>(
    `${xp.toLocaleString()} XP${streak >= 2 ? `, ${streak} day streak` : ''}`,
  );
  const prevXpRef = useRef(xp);

  // Commit the sr-only announcement only when xp or streak actually change, so
  // unrelated parent re-renders don't re-fire the aria-live region.
  useEffect(() => {
    setAnnouncement(
      `${xp.toLocaleString()} XP${streak >= 2 ? `, ${streak} day streak` : ''}`,
    );
  }, [xp, streak]);

  // Only `xp` triggers the tick animation. Streak updates are announced via
  // the effect above; no separate effect needed. Intentional.
  useEffect(() => {
    const prev = prevXpRef.current;
    const diff = xp - prev;
    if (diff === 0) return;
    prevXpRef.current = xp;

    const reduce =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    // Reduced motion — snap, skip pulse.
    if (reduce) {
      setDisplayXp(xp);
      return;
    }

    // Big jump or rollback — snap, pulse only on positive jumps.
    if (Math.abs(diff) > 50 || diff < 0) {
      setDisplayXp(xp);
      if (diff > 0) {
        setPulsing(true);
        const t = setTimeout(() => setPulsing(false), 900);
        return () => clearTimeout(t);
      }
      return;
    }

    // Normal tick-up animation.
    setPulsing(true);
    const steps = Math.min(20, Math.abs(diff));
    const stepMs = 30;
    const increment = diff / steps;
    let current = prev;
    let i = 0;
    const id = window.setInterval(() => {
      i++;
      current += increment;
      if (i >= steps) {
        setDisplayXp(xp);
        window.clearInterval(id);
      } else {
        setDisplayXp(Math.round(current));
      }
    }, stepMs);
    const pulseOff = setTimeout(() => setPulsing(false), 900);
    return () => {
      window.clearInterval(id);
      clearTimeout(pulseOff);
    };
  }, [xp]);

  return (
    <div className={`xp-streak-badge ${className}`.trim()}>
      <div
        className={`xp-streak-badge__xp ${pulsing ? 'xp-streak-badge__xp--pulse' : ''}`}
        aria-hidden="true"
      >
        <svg className="xp-streak-badge__star" width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 2l2.6 6.9 7.4.6-5.6 4.8 1.8 7.2L12 17.8 5.8 21.5l1.8-7.2L2 9.5l7.4-.6z"
            fill="currentColor"
          />
        </svg>
        <span className="xp-streak-badge__xp-value">{displayXp.toLocaleString()}</span>
        <span className="xp-streak-badge__xp-label">XP</span>
      </div>

      {streak >= 2 && (
        <div
          className="xp-streak-badge__streak"
          aria-label={`${streak} day streak`}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M12 2C10 6 6 8 6 13c0 3.9 3.1 7 6 7s6-3.1 6-7c0-3.2-1.6-5.8-3-8 .6 2.6-.6 5-2 5-1 0-1-1.5-1-3 0-2 1-4-0-5z"
              fill="currentColor"
            />
          </svg>
          <span>{streak}</span>
        </div>
      )}

      {levelLabel && <span className="xp-streak-badge__level">{levelLabel}</span>}

      {/* Hidden sr-only announcement — fires once per committed xp/streak value
       *  instead of on every tick-up frame. */}
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {announcement}
      </span>
    </div>
  );
}

export default XpStreakBadge;
