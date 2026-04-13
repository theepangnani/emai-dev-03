/**
 * XpPopBadge — Animated XP badge popup after answering.
 * CB-ILE-001 M1
 */
import { useState, useEffect } from 'react';
import './ile-components.css';

interface XpPopBadgeProps {
  xp: number;
  isFirstTry: boolean;
}

export function XpPopBadge({ xp, isFirstTry }: XpPopBadgeProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(false), 2000);
    return () => clearTimeout(timer);
  }, []);

  if (!visible) return null;

  return (
    <div className="ile-xp-pop">
      +{xp} XP{isFirstTry && ' \u2014 First try bonus!'}
    </div>
  );
}
