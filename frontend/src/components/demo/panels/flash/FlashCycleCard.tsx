/**
 * FlashCycleCard — single 3D-flippable card used inside the Flash Tutor
 * short learning cycle (#3786).
 *
 * Front shows the prompt + "Tap to reveal". Click / Enter / Space flips to
 * the back (rotateY(180deg), ~600ms). `aria-live="polite"` on the body so
 * screen readers announce the revealed answer. `prefers-reduced-motion`
 * is handled in CSS — the flip is replaced by a crossfade.
 */

import { useCallback, type KeyboardEvent } from 'react';

export interface FlashCycleCardProps {
  front: string;
  back: string;
  flipped: boolean;
  onFlip: () => void;
  /** 1-indexed position inside the deck, e.g. "Card 2 of 3". */
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

  const cardClass = `demo-flash-cycle-card${
    flipped ? ' demo-flash-cycle-card--flipped' : ''
  }`;

  return (
    <div className="demo-flash-cycle-card-wrap">
      <div className="demo-flash-cycle-card-meta" aria-live="polite">
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
        <div className="demo-flash-cycle-card__inner">
          <div
            className="demo-flash-cycle-card__face demo-flash-cycle-card__face--front"
            aria-hidden={flipped}
          >
            <span className="demo-flash-cycle-card__label">Question</span>
            <p className="demo-flash-cycle-card__text">{front}</p>
            <span className="demo-flash-cycle-card__hint">Tap to reveal</span>
          </div>
          <div
            className="demo-flash-cycle-card__face demo-flash-cycle-card__face--back"
            aria-hidden={!flipped}
          >
            <span className="demo-flash-cycle-card__label demo-flash-cycle-card__label--answer">
              Answer
            </span>
            <p
              className="demo-flash-cycle-card__text demo-flash-cycle-card__text--answer"
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
