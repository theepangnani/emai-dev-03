/**
 * TutorAvatar — Friendly owl mascot for Flash Tutor.
 * Uses inline SVG with design system colors.
 * CB-ILE-001
 */

interface TutorAvatarProps {
  size?: number;
  mood?: 'neutral' | 'happy' | 'thinking' | 'celebrating';
  className?: string;
}

export function TutorAvatar({ size = 48, mood = 'neutral', className }: TutorAvatarProps) {
  const prefersReducedMotion = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const eyeL = mood === 'thinking' ? { rx: 3.5, ry: 2 } : { rx: 4, ry: 4.5 };
  const pupilOffset = mood === 'thinking' ? -1 : 0;

  const mouth = (() => {
    switch (mood) {
      case 'happy':
      case 'celebrating':
        return <path d="M42 58 Q48 65 54 58" fill="none" stroke="var(--color-accent-warm, #f4801f)" strokeWidth="2.5" strokeLinecap="round" />;
      case 'thinking':
        return <circle cx="50" cy="59" r="2" fill="var(--color-accent-warm, #f4801f)" />;
      default:
        return <path d="M44 58 Q48 62 52 58" fill="none" stroke="var(--color-accent-warm, #f4801f)" strokeWidth="2" strokeLinecap="round" />;
    }
  })();

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 96 96"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      {/* Body */}
      <ellipse cx="48" cy="56" rx="30" ry="32" fill="var(--color-accent-light, rgba(74, 144, 217, 0.12))" stroke="var(--color-accent, #4a90d9)" strokeWidth="2" />

      {/* Belly */}
      <ellipse cx="48" cy="64" rx="18" ry="18" fill="var(--color-surface, #fff)" opacity="0.6" />

      {/* Ear tufts */}
      <path d="M24 30 L18 12 L32 24" fill="var(--color-accent, #4a90d9)" opacity="0.7" />
      <path d="M72 30 L78 12 L64 24" fill="var(--color-accent, #4a90d9)" opacity="0.7" />

      {/* Mortarboard cap */}
      <polygon points="48,6 76,18 48,26 20,18" fill="var(--color-accent-warm, #f4801f)" />
      <rect x="46" y="6" width="4" height="4" rx="2" fill="var(--color-accent-warm, #f4801f)" />
      <line x1="76" y1="18" x2="78" y2="28" stroke="var(--color-accent-warm, #f4801f)" strokeWidth="2" />
      <circle cx="78" cy="30" r="3" fill="var(--color-accent-warm, #f4801f)" />

      {/* Eyes — white */}
      <ellipse cx="38" cy="46" rx={eyeL.rx + 3} ry={eyeL.ry + 2} fill="var(--color-surface, #fff)" />
      <ellipse cx="58" cy="46" rx={7} ry={6.5} fill="var(--color-surface, #fff)" />

      {/* Pupils */}
      <ellipse cx={38 + pupilOffset} cy={46} rx={eyeL.rx} ry={eyeL.ry} fill="var(--color-accent-strong, #2d6eb5)" />
      <ellipse cx={58} cy={46} rx={4} ry={4.5} fill="var(--color-accent-strong, #2d6eb5)" />

      {/* Eye highlights */}
      <circle cx={36 + pupilOffset} cy={43} r="1.5" fill="white" />
      <circle cx={56} cy={43} r="1.5" fill="white" />

      {/* Beak */}
      <path d="M44 52 L48 56 L52 52" fill="var(--color-accent-warm, #f4801f)" />

      {/* Mouth */}
      {mouth}

      {/* Celebrating stars */}
      {mood === 'celebrating' && (
        <>
          <circle cx="14" cy="36" r="2.5" fill="var(--color-accent-warm, #f4801f)" opacity="0.8">
            <animate attributeName="opacity" values="0.4;1;0.4" dur="1.5s" repeatCount={prefersReducedMotion ? "1" : "indefinite"} />
          </circle>
          <circle cx="82" cy="32" r="2" fill="var(--color-accent, #4a90d9)" opacity="0.8">
            <animate attributeName="opacity" values="0.6;1;0.6" dur="1.2s" repeatCount={prefersReducedMotion ? "1" : "indefinite"} />
          </circle>
          <circle cx="78" cy="44" r="1.5" fill="var(--color-accent-warm, #f4801f)" opacity="0.7">
            <animate attributeName="opacity" values="0.3;0.9;0.3" dur="1.8s" repeatCount={prefersReducedMotion ? "1" : "indefinite"} />
          </circle>
        </>
      )}
    </svg>
  );
}
