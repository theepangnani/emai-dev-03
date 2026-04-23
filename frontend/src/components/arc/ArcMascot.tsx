/**
 * ArcMascot — the ClassBridge Learning Companion.
 *
 * A friendly pebble-shaped character whose visual DNA is drawn from the
 * ClassBridge logo: the arc (bridge) becomes the smile, the three dots above
 * the logo become sparkles that float over Arc's head. Unique to ClassBridge —
 * not an animal, not a robot, but a warm abstract companion that works for
 * parents, students, and teachers alike.
 *
 * Moods: neutral | thinking | happy | celebrating | waving
 */
import { useId, useState, useEffect } from 'react';
import './ArcMascot.css';

export type ArcMood = 'neutral' | 'thinking' | 'happy' | 'celebrating' | 'waving';

export interface ArcMascotProps {
  size?: number;
  mood?: ArcMood;
  className?: string;
  /** Show soft glow halo behind Arc (for hero moments). */
  glow?: boolean;
  /** Subtle idle bobbing animation. Defaults to true. */
  animate?: boolean;
  /** Accessible label. Defaults to "ClassBridge companion". */
  label?: string;
}

export function ArcMascot({
  size = 72,
  mood = 'neutral',
  className = '',
  glow = false,
  animate = true,
  label = 'ClassBridge companion',
}: ArcMascotProps) {
  const uid = useId().replace(/:/g, '');
  const gradBody = `arc-body-${uid}`;
  const gradSparkle = `arc-sparkle-${uid}`;
  const gradGlow = `arc-glow-${uid}`;

  const [reduceMotion, setReduceMotion] = useState(
    () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
  );
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (e: MediaQueryListEvent) => setReduceMotion(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const moving = animate && !reduceMotion;
  const classes = [
    'arc-mascot',
    `arc-mascot--${mood}`,
    moving ? 'arc-mascot--animate' : '',
    glow ? 'arc-mascot--glow' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <svg
      className={classes}
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label={label}
    >
      <defs>
        {/* Body gradient — blends brand blue into a warmer teal */}
        <linearGradient id={gradBody} x1="20" y1="30" x2="100" y2="110" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="var(--color-accent, #4a90d9)" />
          <stop offset="100%" stopColor="var(--color-accent-strong, #2d6eb5)" />
        </linearGradient>
        {/* Sparkle gradient — warm accent */}
        <radialGradient id={gradSparkle} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="var(--color-accent-warm, #f4801f)" stopOpacity="1" />
          <stop offset="100%" stopColor="var(--color-accent-warm, #f4801f)" stopOpacity="0.6" />
        </radialGradient>
        {/* Halo glow gradient */}
        <radialGradient id={gradGlow} cx="50%" cy="55%" r="50%">
          <stop offset="0%" stopColor="var(--color-accent-warm, #f4801f)" stopOpacity="0.28" />
          <stop offset="70%" stopColor="var(--color-accent-warm, #f4801f)" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Halo */}
      {glow && <circle cx="60" cy="66" r="56" fill={`url(#${gradGlow})`} />}

      {/* Three floating sparkles above Arc — direct echo of ClassBridge logo's 3 dots */}
      <g className="arc-sparkles">
        <circle className="arc-sparkle arc-sparkle--left" cx="34" cy="22" r="3.2" fill={`url(#${gradSparkle})`} />
        <circle className="arc-sparkle arc-sparkle--center" cx="60" cy="14" r="3.8" fill={`url(#${gradSparkle})`} />
        <circle className="arc-sparkle arc-sparkle--right" cx="86" cy="22" r="3.2" fill={`url(#${gradSparkle})`} />
      </g>

      {/* Body — a soft rounded pebble. rx slightly larger than ry for a friendly stance. */}
      <g className="arc-body-group">
        <path
          className="arc-body"
          d="M60 36
             C 92 36, 104 56, 104 78
             C 104 98, 86 108, 60 108
             C 34 108, 16 98, 16 78
             C 16 56, 28 36, 60 36 Z"
          fill={`url(#${gradBody})`}
        />

        {/* Soft inner highlight — subtle dimension, not a hard cartoon shine */}
        <ellipse cx="42" cy="58" rx="18" ry="10" fill="#ffffff" opacity="0.14" />

        {/* Eyes */}
        <g className="arc-eyes">
          {/* Left eye */}
          <ellipse className="arc-eye arc-eye--left" cx="46" cy="70" rx="5.5" ry="7" fill="#ffffff" />
          <circle className="arc-pupil arc-pupil--left" cx="46" cy="71" r="2.6" fill="#1b1e2b" />
          <circle className="arc-shine arc-shine--left" cx="47.2" cy="69.2" r="1.1" fill="#ffffff" />

          {/* Right eye */}
          <ellipse className="arc-eye arc-eye--right" cx="74" cy="70" rx="5.5" ry="7" fill="#ffffff" />
          <circle className="arc-pupil arc-pupil--right" cx="74" cy="71" r="2.6" fill="#1b1e2b" />
          <circle className="arc-shine arc-shine--right" cx="75.2" cy="69.2" r="1.1" fill="#ffffff" />
        </g>

        {/* Cheek blushes (warm accent) */}
        <ellipse className="arc-cheek arc-cheek--left" cx="32" cy="85" rx="4" ry="2.5" fill="var(--color-accent-warm, #f4801f)" opacity="0.35" />
        <ellipse className="arc-cheek arc-cheek--right" cx="88" cy="85" rx="4" ry="2.5" fill="var(--color-accent-warm, #f4801f)" opacity="0.35" />

        {/* Mouth — the arc. Direct echo of the bridge in the ClassBridge logo. */}
        <path
          className="arc-mouth"
          d="M 48 90 Q 60 98 72 90"
          fill="none"
          stroke="var(--color-accent-warm, #f4801f)"
          strokeWidth="3"
          strokeLinecap="round"
        />

        {/* Thinking-mode dots (replace mouth) */}
        <g className="arc-thinking-dots">
          <circle cx="52" cy="92" r="1.8" fill="var(--color-accent-warm, #f4801f)" />
          <circle cx="60" cy="92" r="1.8" fill="var(--color-accent-warm, #f4801f)" />
          <circle cx="68" cy="92" r="1.8" fill="var(--color-accent-warm, #f4801f)" />
        </g>

        {/* Celebrating stars (appear on 'celebrating') */}
        <g className="arc-celebration">
          <path d="M 18 44 l 1.5 4 l 4 1 l -4 1 l -1.5 4 l -1.5 -4 l -4 -1 l 4 -1 z" fill="var(--color-accent-warm, #f4801f)" />
          <path d="M 102 50 l 1.2 3 l 3 1 l -3 1 l -1.2 3 l -1.2 -3 l -3 -1 l 3 -1 z" fill="var(--color-accent-warm, #f4801f)" />
          <path d="M 108 82 l 1 2.5 l 2.5 1 l -2.5 1 l -1 2.5 l -1 -2.5 l -2.5 -1 l 2.5 -1 z" fill="var(--color-accent, #4a90d9)" />
        </g>

        {/* Waving hand */}
        <g className="arc-hand" transform="translate(100 68)">
          <ellipse cx="0" cy="0" rx="6" ry="7" fill={`url(#${gradBody})`} />
          <path d="M -3 -2 Q 0 -6 3 -2" fill="none" stroke="var(--color-accent-warm, #f4801f)" strokeWidth="1.5" strokeLinecap="round" />
        </g>
      </g>
    </svg>
  );
}

export default ArcMascot;
