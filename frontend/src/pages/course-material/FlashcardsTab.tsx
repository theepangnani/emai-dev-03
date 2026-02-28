import { useState, useEffect, useRef } from 'react';
import type { StudyGuide } from '../../api/client';
import type { TaskItem } from '../../api/tasks';
import { printElement, downloadAsPdf } from '../../utils/exportUtils';
import { LinkedTasksBanner } from './LinkedTasksBanner';

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
  linkedTasks?: TaskItem[];
}

function FocusIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M8 1v2M8 13v2M1 8h2M13 8h2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

function EmptyFlashcardIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="2" y="5" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <rect x="8" y="9" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M11 13h8M11 16h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
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
  linkedTasks = [],
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
        <div className="cm-focus-prompt-inner">
          <span className="cm-focus-prompt-icon"><FocusIcon /></span>
          <input
            type="text"
            value={focusPrompt}
            onChange={(e) => onFocusPromptChange(e.target.value)}
            placeholder="Focus on a specific topic (e.g., photosynthesis, the Calvin cycle)"
            disabled={generating !== null}
          />
        </div>
      </div>
      {flashcardSet && displayCards.length > 0 ? (
        <div className="cm-tab-card">
          <div className="cm-guide-actions">
            <button className="cm-action-btn" onClick={handlePrint} title="Print">{'\u{1F5A8}\uFE0F'} Print</button>
            <button className="cm-action-btn" onClick={handleDownloadPdf} disabled={exporting} title="Download PDF">{'\u{1F4E5}'} {exporting ? 'Exporting...' : 'PDF'}</button>
            <button className="cm-action-btn" onClick={handleReset}>{'\u{1F504}'} Reset</button>
            <button className="cm-action-btn" onClick={handleShuffle}>{'\u{1F500}'} Shuffle</button>
            <button className="cm-action-btn" onClick={onGenerate} disabled={generating !== null}>{'\u2728'} Regenerate</button>
            <button className="cm-action-btn danger" onClick={() => onDelete(flashcardSet)}>{'\u{1F5D1}\uFE0F'} Delete</button>
          </div>
          <LinkedTasksBanner tasks={linkedTasks} />
          {generating === 'flashcards' && (
            <div className="cm-regen-status">
              <div className="cm-inline-spinner" />
              <span>Regenerating flashcards...</span>
            </div>
          )}
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
          <div className="cm-tab-card-body">
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
            <p className="cm-hint" style={{ textAlign: 'center' }}>Click card to flip. Use arrow keys to navigate.</p>
          </div>
        </div>
      ) : generating === 'flashcards' ? (
        <div className="cm-inline-generating">
          <div className="cm-inline-spinner" />
          <p>Generating flashcards... This may take a moment.</p>
        </div>
      ) : (
        <div className="cm-empty-tab">
          <div className="cm-empty-tab-icon"><EmptyFlashcardIcon /></div>
          <h3>No flashcards yet</h3>
          <p>Generate flashcards to review key concepts from this material with an interactive card deck.</p>
          <button
            className="cm-empty-generate-btn"
            onClick={onGenerate}
            disabled={generating !== null || !hasSourceContent}
          >
            {'\u2728'} Generate Flashcards
          </button>
          {!hasSourceContent && (
            <p className="cm-hint">Add content or upload a document first to generate flashcards.</p>
          )}
        </div>
      )}
    </div>
  );
}
