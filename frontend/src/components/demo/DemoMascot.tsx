/**
 * DemoMascot — Friendly droid/spark helper character for CB-DEMO-001 surfaces.
 * Inline SVG with mood prop; CSS-only animations; respects prefers-reduced-motion.
 *
 * Not an owl — a rounded geometric helper bot with a warm spark antenna.
 * Mirrors the pattern from ile/TutorAvatar.tsx but uses a distinct character.
 */

import { useEffect, useState } from 'react';
import './DemoMascot.css';

export interface DemoMascotProps {
  size?: number;
  mood?: 'greeting' | 'thinking' | 'streaming' | 'complete';
  className?: string;
}

export function DemoMascot({ size = 48, mood = 'greeting', className }: DemoMascotProps) {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const classes = [
    'demo-mascot',
    `demo-mascot--${mood}`,
    prefersReducedMotion ? 'demo-mascot--reduced-motion' : '',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ');

  // Eye geometry per mood
  const eyeShape = (() => {
    switch (mood) {
      case 'thinking':
        return { rx: 3, ry: 1.2 };
      case 'streaming':
        return { rx: 2.8, ry: 2.8 };
      case 'complete':
        return { rx: 3.2, ry: 2.2 };
      default:
        return { rx: 2.8, ry: 3 };
    }
  })();

  const mouth = (() => {
    switch (mood) {
      case 'thinking':
        return <circle cx="48" cy="62" r="1.8" fill="var(--color-ink, #1b1e2b)" />;
      case 'complete':
        return (
          <path
            d="M40 60 Q48 68 56 60"
            fill="none"
            stroke="var(--color-ink, #1b1e2b)"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        );
      case 'streaming':
        return (
          <path
            d="M42 62 L54 62"
            fill="none"
            stroke="var(--color-ink, #1b1e2b)"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        );
      default:
        return (
          <path
            d="M42 60 Q48 64 54 60"
            fill="none"
            stroke="var(--color-ink, #1b1e2b)"
            strokeWidth="2"
            strokeLinecap="round"
          />
        );
    }
  })();

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 96 96"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={classes}
      aria-hidden="true"
      data-testid="demo-mascot"
    >
      <defs>
        <linearGradient id="demo-mascot-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-accent-light, rgba(74, 144, 217, 0.18))" />
          <stop offset="100%" stopColor="var(--color-accent, #4a90d9)" stopOpacity="0.35" />
        </linearGradient>
      </defs>

      {/* Antenna stem */}
      <line
        x1="48"
        y1="20"
        x2="48"
        y2="10"
        stroke="var(--color-accent-strong, #2d6eb5)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      {/* Antenna spark (warm accent) */}
      <circle
        className="demo-mascot__spark"
        cx="48"
        cy="8"
        r="3.5"
        fill="var(--color-accent-warm, #f4801f)"
      />

      {/* Rounded body (squircle) */}
      <rect
        className="demo-mascot__body"
        x="18"
        y="22"
        width="60"
        height="60"
        rx="22"
        ry="22"
        fill="url(#demo-mascot-body)"
        stroke="var(--color-accent-strong, #2d6eb5)"
        strokeWidth="2"
      />

      {/* Inner face plate */}
      <rect
        x="26"
        y="34"
        width="44"
        height="34"
        rx="14"
        ry="14"
        fill="var(--color-surface, #ffffff)"
        opacity="0.85"
      />

      {/* Left eye */}
      <ellipse
        className="demo-mascot__eye demo-mascot__eye--left"
        cx="40"
        cy="48"
        rx={eyeShape.rx}
        ry={eyeShape.ry}
        fill="var(--color-ink, #1b1e2b)"
      />
      {/* Right eye */}
      <ellipse
        className="demo-mascot__eye demo-mascot__eye--right"
        cx="56"
        cy="48"
        rx={eyeShape.rx}
        ry={eyeShape.ry}
        fill="var(--color-ink, #1b1e2b)"
      />

      {/* Mouth */}
      {mouth}

      {/* Side "ears" / speakers */}
      <rect x="12" y="44" width="6" height="16" rx="3" fill="var(--color-accent-strong, #2d6eb5)" opacity="0.7" />
      <rect x="78" y="44" width="6" height="16" rx="3" fill="var(--color-accent-strong, #2d6eb5)" opacity="0.7" />

      {/* Complete mood: sparkle */}
      {mood === 'complete' && (
        <g className="demo-mascot__sparkle">
          <path
            d="M78 24 L80 28 L84 30 L80 32 L78 36 L76 32 L72 30 L76 28 Z"
            fill="var(--color-accent-warm, #f4801f)"
          />
        </g>
      )}
    </svg>
  );
}

export default DemoMascot;
