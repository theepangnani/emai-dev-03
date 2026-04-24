/**
 * MasteryRing — SVG progress ring for the Learning Cycle (CB-TUTOR-002 #4069).
 *
 * Lifted from `components/demo/panels/flash/MasteryRing.tsx`. Demo original
 * kept in place.
 *
 * Fills per completed chunk. At total/total the stroke swaps to
 * `var(--color-accent-warm)` to signal mastery.
 */

export interface MasteryRingProps {
  completed: number;
  total: number;
  size?: number;
  strokeWidth?: number;
}

export function MasteryRing({
  completed,
  total,
  size = 64,
  strokeWidth = 6,
}: MasteryRingProps) {
  if (total <= 0) return null;

  const clampedCompleted = Math.max(0, Math.min(total, completed));
  const pct = clampedCompleted / total;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct);
  const isMastered = clampedCompleted >= total;

  const ringClass = `cycle-mastery-ring${
    isMastered ? ' cycle-mastery-ring--mastered' : ''
  }`;

  return (
    <div
      className={ringClass}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={clampedCompleted}
      aria-label={`Mastery: ${clampedCompleted} of ${total}`}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        aria-hidden="true"
      >
        <circle
          className="cycle-mastery-ring__track"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          fill="none"
        />
        <circle
          className="cycle-mastery-ring__fill"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <span className="cycle-mastery-ring__label" aria-hidden="true">
        {clampedCompleted}/{total}
      </span>
    </div>
  );
}

export default MasteryRing;
