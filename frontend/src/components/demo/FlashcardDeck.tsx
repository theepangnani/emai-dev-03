/**
 * FlashcardDeck — Renders Haiku flash-tutor JSON output as flippable cards.
 *
 * Parses the raw streamed text from the backend flash-tutor prompt
 * (see prompts/demo/flash-tutor.md) into a deck of {front, back} cards
 * with keyboard navigation and flip-on-click.
 *
 * Not integrated yet — see #3759 / #3762.
 */

import { useEffect, useMemo, useState, type KeyboardEvent } from 'react';
import { DemoMascot } from './DemoMascot';

export interface FlashcardDeckProps {
  rawText: string;
  isStreaming?: boolean;
  className?: string;
}

interface Flashcard {
  front: string;
  back: string;
}

const FOOTER = 'This is a ClassBridge demo preview.';

/** Strip optional markdown code fences and trailing demo footer. */
function cleanRawText(raw: string): string {
  let text = raw.trim();

  // Strip surrounding ```json ... ``` or ``` ... ``` fences.
  const fenceMatch = text.match(/^```(?:json)?\s*\n?([\s\S]*?)\n?```\s*$/i);
  if (fenceMatch) {
    text = fenceMatch[1].trim();
  }

  // Strip trailing footer line.
  if (text.endsWith(FOOTER)) {
    text = text.slice(0, -FOOTER.length).trim();
  }

  return text;
}

/** Parse the cleaned raw text into an array of valid Flashcard entries. */
function parseFlashcards(raw: string): Flashcard[] | null {
  const cleaned = cleanRawText(raw);
  if (!cleaned) return null;

  try {
    let parsed: unknown = JSON.parse(cleaned);
    if (!Array.isArray(parsed) && parsed && Array.isArray((parsed as { cards?: unknown }).cards)) {
      parsed = (parsed as { cards: unknown[] }).cards;
    }
    if (!Array.isArray(parsed)) return null;

    const cards: Flashcard[] = [];
    for (const entry of parsed) {
      if (
        entry &&
        typeof entry === 'object' &&
        typeof (entry as Flashcard).front === 'string' &&
        typeof (entry as Flashcard).back === 'string' &&
        (entry as Flashcard).front.trim() &&
        (entry as Flashcard).back.trim()
      ) {
        cards.push({
          front: (entry as Flashcard).front,
          back: (entry as Flashcard).back,
        });
      }
    }
    return cards;
  } catch {
    return null;
  }
}

export function FlashcardDeck({ rawText, isStreaming, className }: FlashcardDeckProps) {
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);

  const cards = useMemo(() => (isStreaming ? null : parseFlashcards(rawText)), [rawText, isStreaming]);

  const cardsLength = cards?.length ?? 0;
  useEffect(() => {
    if (index >= cardsLength) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional reset when deck shrinks mid-session
      setIndex(0);
      setFlipped(false);
    }
  }, [cardsLength, index]);

  const rootClass = ['demo-flashcard-deck', className ?? ''].filter(Boolean).join(' ');

  if (isStreaming) {
    return (
      <div className={rootClass}>
        <div className="demo-flashcard-placeholder" aria-live="polite">
          <DemoMascot size={44} mood="streaming" />
          <span className="demo-flashcard-placeholder__text">Building your flashcards&hellip;</span>
        </div>
      </div>
    );
  }

  if (!cards || cards.length === 0) {
    return (
      <div className={rootClass}>
        <pre className="demo-flashcard-fallback">{rawText}</pre>
      </div>
    );
  }

  const safeIndex = Math.min(index, cards.length - 1);
  const current = cards[safeIndex];
  const atStart = safeIndex <= 0;
  const atEnd = safeIndex >= cards.length - 1;

  const goPrev = () => {
    if (atStart) return;
    setIndex((i) => Math.max(0, i - 1));
    setFlipped(false);
  };

  const goNext = () => {
    if (atEnd) return;
    setIndex((i) => Math.min(cards.length - 1, i + 1));
    setFlipped(false);
  };

  const toggleFlip = () => setFlipped((f) => !f);

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    // preventDefault on Arrow keys prevents page scroll and flip-button default handling.
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      goPrev();
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      goNext();
    } else if (e.key === ' ' || e.key === 'Enter') {
      const target = e.target as HTMLElement;
      if (target.tagName === 'BUTTON') return;
      e.preventDefault();
      toggleFlip();
    }
  };

  return (
    <div
      className={rootClass}
      role="region"
      aria-label="Flashcards"
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      <button
        type="button"
        className="demo-flashcard-card"
        aria-expanded={flipped}
        aria-label={flipped ? 'Show card front' : 'Show card back'}
        onClick={toggleFlip}
      >
        <span className="demo-flashcard-side-label">{flipped ? 'Back' : 'Front'}</span>
        <span className="demo-flashcard-text" aria-live="polite">{flipped ? current.back : current.front}</span>
      </button>

      <div className="demo-flashcard-controls">
        <button
          type="button"
          className="demo-flashcard-nav"
          onClick={goPrev}
          disabled={atStart}
          aria-label="Previous card"
        >
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path
              d="M12 4L6 10L12 16"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        <span className="demo-flashcard-counter" role="status">
          {safeIndex + 1} / {cards.length}
        </span>
        <button
          type="button"
          className="demo-flashcard-nav"
          onClick={goNext}
          disabled={atEnd}
          aria-label="Next card"
        >
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path
              d="M8 4L14 10L8 16"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}

export default FlashcardDeck;
