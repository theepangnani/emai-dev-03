export interface DemoStreakFlameProps {
  streak: number;
}

/**
 * Gamification primitive — streak flame (CB-DEMO-001 foundation).
 *
 * Scaffold only: the flame goes active when streak ≥ 2 (two consecutive
 * got-its in Flash Tutor). Wave 2 streams will add the pulse animation and
 * the burst on milestone streaks.
 */
export function DemoStreakFlame({ streak }: DemoStreakFlameProps) {
  const active = streak >= 2;
  return (
    <span
      className={`demo-streak-flame${active ? ' demo-streak-flame--active' : ''}`}
      aria-label={
        active
          ? `Streak: ${streak} in a row`
          : streak > 0
            ? `Streak: ${streak}`
            : 'No streak yet'
      }
      title={`Streak: ${streak}`}
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M12 3c2 3 5 5 5 9a5 5 0 0 1-10 0c0-2 1-3 2-5 1 2 3 3 3 6" />
      </svg>
      <span className="demo-streak-flame__count">{streak}</span>
    </span>
  );
}

export default DemoStreakFlame;
