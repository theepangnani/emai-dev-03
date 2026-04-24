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
  const prevXpRef = useRef(xp);

  useEffect(() => {
    const prev = prevXpRef.current;
    const diff = xp - prev;
    if (diff === 0) return;
    prevXpRef.current = xp;

    if (Math.abs(diff) > 50 || diff < 0) {
      // Big jump or rollback — just snap
      setDisplayXp(xp);
      if (diff > 0) {
        setPulsing(true);
        const t = setTimeout(() => setPulsing(false), 900);
        return () => clearTimeout(t);
      }
      return;
    }

    // Tick up
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
    <div className={`xp-streak-badge ${className}`.trim()} aria-live="polite">
      <div className={`xp-streak-badge__xp ${pulsing ? 'xp-streak-badge__xp--pulse' : ''}`}>
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
        <div className="xp-streak-badge__streak" title={`${streak}-day streak`}>
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
    </div>
  );
}

export default XpStreakBadge;
