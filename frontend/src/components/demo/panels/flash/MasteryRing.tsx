/**
 * MasteryRing — SVG progress ring for the Flash Tutor short learning cycle
 * (#3786).
 *
 * Fills per completed card: at 3/3 the stroke colour swaps from
 * `var(--color-accent)` (cyan/blue) to `var(--color-accent-warm)` (amber)
 * to signal mastery. Track uses `var(--color-surface-alt)`. No new colours.
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
  // ARIA 1.2 requires valuemax > valuemin — don't render a zero-range
  // progressbar. Callers typically gate on parse-success before reaching
  // here, but the component protects itself as a defensive contract.
  if (total <= 0) return null;

  const clampedCompleted = Math.max(0, Math.min(total, completed));
  const pct = clampedCompleted / total;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct);
  const isMastered = clampedCompleted >= total;

  const ringClass = `demo-flash-mastery-ring${
    isMastered ? ' demo-flash-mastery-ring--mastered' : ''
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
          className="demo-flash-mastery-ring__track"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          fill="none"
        />
        <circle
          className="demo-flash-mastery-ring__fill"
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
      <span className="demo-flash-mastery-ring__label" aria-hidden="true">
        {clampedCompleted}/{total}
      </span>
    </div>
  );
}

export default MasteryRing;
