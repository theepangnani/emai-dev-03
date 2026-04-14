/**
 * AhaMomentCelebration — Full-screen confetti celebration for breakthrough moments.
 * CB-ILE-001 M3 (#3215)
 *
 * Shows CSS-only confetti animation with a "Breakthrough!" message.
 * Auto-dismisses after 3 seconds.
 */
import { useState, useEffect, useMemo } from 'react';
import './AhaMomentCelebration.css';

interface AhaMomentCelebrationProps {
  topic: string;
  onDismiss?: () => void;
}

/** Pre-compute confetti positions so render is pure. */
function generateConfettiStyles() {
  return Array.from({ length: 30 }, (_, i) => ({
    left: `${Math.random() * 100}%`,
    animationDelay: `${Math.random() * 0.5}s`,
    animationDuration: `${1.5 + Math.random() * 1.5}s`,
    colorClass: i % 6,
  }));
}

export function AhaMomentCelebration({ topic, onDismiss }: AhaMomentCelebrationProps) {
  const [visible, setVisible] = useState(true);
  const confettiPieces = useMemo(() => generateConfettiStyles(), []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      onDismiss?.();
    }, 3000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  if (!visible) return null;

  return (
    <div className="aha-overlay" role="status" aria-live="assertive">
      {/* CSS-only confetti pieces */}
      <div className="aha-confetti-container" aria-hidden="true">
        {confettiPieces.map((piece, i) => (
          <span
            key={i}
            className={`aha-confetti-piece aha-confetti-${piece.colorClass}`}
            style={{
              left: piece.left,
              animationDelay: piece.animationDelay,
              animationDuration: piece.animationDuration,
            }}
          />
        ))}
      </div>

      <div className="aha-content">
        <div className="aha-icon">&#127881;</div>
        <h2 className="aha-title">Breakthrough!</h2>
        <p className="aha-message">
          Amazing progress in <strong>{topic}</strong>!
        </p>
      </div>
    </div>
  );
}
