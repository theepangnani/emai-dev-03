interface StreakCounterProps {
  days: number;
  compact?: boolean;
}

function getStreakTier(days: number): string {
  if (days < 1) return 'cold';
  if (days < 7) return 'cold';
  if (days < 14) return 'warm';
  if (days < 30) return 'hot';
  if (days < 60) return 'blazing';
  return 'legendary';
}

export function StreakCounter({ days, compact }: StreakCounterProps) {
  if (days < 1) return null;

  const tier = getStreakTier(days);

  if (compact) {
    return (
      <span className={`xp-child-streak xp-streak--tier-${tier}`}>
        <span className="xp-streak-flame">{'\uD83D\uDD25'}</span>
        {days}
      </span>
    );
  }

  return (
    <div className={`xp-streak xp-streak--tier-${tier}`}>
      <span className="xp-streak-flame">{'\uD83D\uDD25'}</span>
      <span className="xp-streak-count">
        {days} day{days !== 1 ? 's' : ''}
      </span>
    </div>
  );
}
