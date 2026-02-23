import { useState, useEffect, useRef } from 'react';
import type { StudyGuide } from '../../api/client';
import { printElement, downloadAsPdf } from '../../utils/exportUtils';

interface FlashcardItem {
  front: string;
  back: string;
}

interface FlashcardsTabProps {
  flashcardSet: StudyGuide | undefined;
  generating: string | null;
  focusPrompt: string;
  onFocusPromptChange: (value: string) => void;
  onGenerate: () => void;
  onDelete: (guide: StudyGuide) => void;
  hasSourceContent: boolean;
  isActiveTab: boolean;
}

export function FlashcardsTab({
  flashcardSet,
  generating,
  focusPrompt,
  onFocusPromptChange,
  onGenerate,
  onDelete,
  hasSourceContent,
  isActiveTab,
}: FlashcardsTabProps) {
  const [cardIndex, setCardIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [shuffledCards, setShuffledCards] = useState<FlashcardItem[]>([]);
  const [exporting, setExporting] = useState(false);
  const printRef = useRef<HTMLDivElement>(null);

  const parsedCards: FlashcardItem[] = flashcardSet ? (() => {
    try { return JSON.parse(flashcardSet.content); } catch { return []; }
  })() : [];

  // Keep shuffledCards in sync with parsedCards
  useEffect(() => {
    setShuffledCards(parsedCards);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flashcardSet?.id, flashcardSet?.content]);

  const displayCards = shuffledCards.length > 0 ? shuffledCards : parsedCards;

  const handleShuffle = () => {
    const arr = [...displayCards];
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    setShuffledCards(arr);
    setCardIndex(0);
    setIsFlipped(false);
  };

  const handleReset = () => {
    setShuffledCards(parsedCards);
    setCardIndex(0);
    setIsFlipped(false);
  };

  const handlePrint = () => {
    if (printRef.current) printElement(printRef.current, flashcardSet?.title || 'Flashcards');
  };

  const handleDownloadPdf = async () => {
    if (!printRef.current) return;
    setExporting(true);
    try {
      const filename = (flashcardSet?.title || 'Flashcards').replace(/[^a-zA-Z0-9 _-]/g, '');
      await downloadAsPdf(printRef.current, filename);
    } finally {
      setExporting(false);
    }
  };

  // Keyboard navigation (#732)
  useEffect(() => {
    if (!isActiveTab || displayCards.length === 0) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft' && cardIndex > 0) {
        setCardIndex(i => i - 1);
        setIsFlipped(false);
      } else if (e.key === 'ArrowRight' && cardIndex < displayCards.length - 1) {
        setCardIndex(i => i + 1);
        setIsFlipped(false);
      } else if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        setIsFlipped(f => !f);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isActiveTab, cardIndex, displayCards.length]);

  return (
    <div className="cm-flashcards-tab">
      <div className="cm-focus-prompt">
        <input
          type="text"
          value={focusPrompt}
          onChange={(e) => onFocusPromptChange(e.target.value)}
          placeholder="Focus on... (e.g., photosynthesis and the Calvin cycle)"
          disabled={generating !== null}
        />
      </div>
      {flashcardSet && displayCards.length > 0 ? (
        <>
          <div className="cm-guide-actions">
            <button className="cm-action-btn" onClick={handlePrint} title="Print">{'\u{1F5A8}\uFE0F'} Print</button>
            <button className="cm-action-btn" onClick={handleDownloadPdf} disabled={exporting} title="Download PDF">{'\u{1F4E5}'} {exporting ? 'Exporting...' : 'Download PDF'}</button>
            <button className="cm-action-btn" onClick={handleReset}>{'\u{1F504}'} Reset</button>
            <button className="cm-action-btn" onClick={handleShuffle}>{'\u{1F500}'} Shuffle</button>
            <button className="cm-action-btn" onClick={onGenerate} disabled={generating !== null}>{'\u2728'} Regenerate</button>
            <button className="cm-action-btn danger" onClick={() => onDelete(flashcardSet)}>{'\u{1F5D1}\uFE0F'} Delete</button>
          </div>
          {/* Hidden print-ready view with all flashcards */}
          <div ref={printRef} className="cm-print-view">
            <h1 className="print-title">{flashcardSet.title}</h1>
            <p className="print-subtitle">Flashcards &middot; {parsedCards.length} cards</p>
            {parsedCards.map((card, i) => (
              <div key={i} className="print-fc-item">
                <span className="print-fc-num">{i + 1}.</span>
                <span className="print-fc-front">{card.front}</span>
                <span className="print-fc-back">&mdash; {card.back}</span>
              </div>
            ))}
          </div>
          <div className="cm-flashcard-progress">
            Card {cardIndex + 1} of {displayCards.length}
          </div>
          <div
            className={`cm-flashcard${isFlipped ? ' flipped' : ''}`}
            onClick={() => setIsFlipped(f => !f)}
            tabIndex={0}
            role="button"
            aria-label={`Flashcard ${cardIndex + 1}. ${isFlipped ? 'Back' : 'Front'}: ${isFlipped ? displayCards[cardIndex]?.back : displayCards[cardIndex]?.front}`}
          >
            <div className="cm-flashcard-inner">
              <div className="cm-flashcard-front">
                <p>{displayCards[cardIndex]?.front}</p>
              </div>
              <div className="cm-flashcard-back">
                <p>{displayCards[cardIndex]?.back}</p>
              </div>
            </div>
          </div>
          <div className="cm-flashcard-controls">
            <button
              className="cm-action-btn"
              onClick={() => { setCardIndex(i => i - 1); setIsFlipped(false); }}
              disabled={cardIndex === 0}
            >
              Previous
            </button>
            <button
              className="cm-action-btn"
              onClick={() => { setCardIndex(i => i + 1); setIsFlipped(false); }}
              disabled={cardIndex >= displayCards.length - 1}
            >
              Next
            </button>
          </div>
          <p className="cm-hint">Click card to flip. Use arrow keys to navigate.</p>
        </>
      ) : generating === 'flashcards' ? (
        <div className="cm-inline-generating">
          <div className="cm-inline-spinner" />
          <p>Generating flashcards... This may take a moment.</p>
        </div>
      ) : (
        <div className="cm-empty-tab">
          <p>No flashcards generated yet.</p>
          <button
            className="generate-btn"
            onClick={onGenerate}
            disabled={generating !== null || !hasSourceContent}
          >
            Generate Flashcards
          </button>
          {!hasSourceContent && (
            <p className="cm-hint">Add content or upload a document first to generate flashcards.</p>
          )}
        </div>
      )}
    </div>
  );
}
