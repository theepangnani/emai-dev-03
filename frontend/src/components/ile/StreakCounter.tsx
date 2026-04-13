/**
 * StreakCounter — Fire streak display with shake animation when broken.
 * CB-ILE-001 M1
 */
import { useState, useEffect } from 'react';
import './ile-components.css';

interface StreakCounterProps {
  count: number;
  broken: boolean;
}

export function StreakCounter({ count, broken }: StreakCounterProps) {
  const [shaking, setShaking] = useState(false);

  useEffect(() => {
    if (broken) {
      setShaking(true);
      const timer = setTimeout(() => setShaking(false), 600);
      return () => clearTimeout(timer);
    }
  }, [broken]);

  if (count <= 0 && !shaking) return null;

  return (
    <span className={`ile-streak${shaking ? ' ile-streak-shake' : ''}`} aria-label={`${count} correct streak`}>
      {'\uD83D\uDD25'} {count}
    </span>
  );
}
