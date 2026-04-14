/**
 * StreakCounter — Fire streak display with tier-based styling and shake animation.
 * Tiers: warm (1-2), hot (3-4), blazing (5+)
 * CB-ILE-001 M1
 */
import { useState, useEffect } from 'react';
import './ile-components.css';

interface StreakCounterProps {
  count: number;
  broken: boolean;
}

function getTier(count: number): string {
  if (count >= 5) return 'ile-streak--tier-blazing';
  if (count >= 3) return 'ile-streak--tier-hot';
  return 'ile-streak--tier-warm';
}

export function StreakCounter({ count, broken }: StreakCounterProps) {
  const [shaking, setShaking] = useState(false);

  useEffect(() => {
    if (broken) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: triggers shake animation
      setShaking(true);
      const timer = setTimeout(() => setShaking(false), 600);
      return () => clearTimeout(timer);
    }
  }, [broken]);

  if (count <= 0 && !shaking) return null;

  const tier = getTier(count);

  return (
    <span className={`ile-streak ${tier}${shaking ? ' ile-streak-shake' : ''}`} aria-label={`${count} correct streak`}>
      {'\uD83D\uDD25'} {count}
    </span>
  );
}
