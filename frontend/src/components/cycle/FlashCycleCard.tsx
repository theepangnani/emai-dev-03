/**
 * FlashCycleCard — single 3D-flippable card lifted from the demo cycle
 * (`components/demo/panels/flash/FlashCycleCard.tsx`) for Learning Cycle
 * reuse (CB-TUTOR-002 #4069). Demo original kept in place.
 */

import { useCallback, type KeyboardEvent } from 'react';

export interface FlashCycleCardProps {
  front: string;
  back: string;
  flipped: boolean;
  onFlip: () => void;
  /** 1-indexed position, e.g. "Card 2 of 3". */
  index: number;
  total: number;
}

export function FlashCycleCard({
  front,
  back,
  flipped,
  onFlip,
  index,
  total,
}: FlashCycleCardProps) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLDivElement>) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        if (!flipped) onFlip();
      }
    },
    [flipped, onFlip],
  );

  const handleClick = () => {
    if (!flipped) onFlip();
  };

  const cardClass = `cycle-flash-card${flipped ? ' cycle-flash-card--flipped' : ''}`;

  return (
    <div className="cycle-flash-card-wrap">
      <div className="cycle-flash-card-meta">
        Card {index} of {total}
      </div>
      <div
        className={cardClass}
        role="button"
        tabIndex={0}
        aria-pressed={flipped}
        aria-label={flipped ? 'Card answer revealed' : 'Reveal answer'}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
      >
        <div className="cycle-flash-card__inner">
          <div
            className="cycle-flash-card__face cycle-flash-card__face--front"
            aria-hidden={flipped}
          >
            <span className="cycle-flash-card__label">Question</span>
            <p className="cycle-flash-card__text">{front}</p>
            <span className="cycle-flash-card__hint">Tap to reveal</span>
          </div>
          <div
            className="cycle-flash-card__face cycle-flash-card__face--back"
            aria-hidden={!flipped}
          >
            <span className="cycle-flash-card__label cycle-flash-card__label--answer">
              Answer
            </span>
            <p
              className="cycle-flash-card__text cycle-flash-card__text--answer"
              aria-live="polite"
            >
              {back}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default FlashCycleCard;
