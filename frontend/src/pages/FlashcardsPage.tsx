import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { studyApi } from '../api/client';
import type { StudyGuide, Flashcard } from '../api/client';
import { CourseAssignSelect } from '../components/CourseAssignSelect';
import { CreateTaskModal } from '../components/CreateTaskModal';
import './FlashcardsPage.css';

type CardDifficulty = 'mastered' | 'learning';

export function FlashcardsPage() {
  const { id } = useParams<{ id: string }>();
  const [guide, setGuide] = useState<StudyGuide | null>(null);
  const [allCards, setAllCards] = useState<Flashcard[]>([]);
  const [cards, setCards] = useState<Flashcard[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showTaskModal, setShowTaskModal] = useState(false);

  // Mastery tracking: keyed by card front text (stable identifier)
  const [cardProgress, setCardProgress] = useState<Map<string, CardDifficulty>>(new Map());
  const [showSummary, setShowSummary] = useState(false);
  const [reviewMode, setReviewMode] = useState(false);

  // Refs for stable keyboard handler — avoids stale closures
  const currentIndexRef = useRef(currentIndex);
  const isFlippedRef = useRef(isFlipped);
  const cardsRef = useRef(cards);
  const showSummaryRef = useRef(showSummary);
  currentIndexRef.current = currentIndex;
  isFlippedRef.current = isFlipped;
  cardsRef.current = cards;
  showSummaryRef.current = showSummary;

  useEffect(() => {
    const fetchFlashcards = async () => {
      if (!id) return;
      try {
        const data = await studyApi.getGuide(parseInt(id));
        setGuide(data);
        const parsedCards = JSON.parse(data.content) as Flashcard[];
        setAllCards(parsedCards);
        setCards(parsedCards);
      } catch (err) {
        setError('Failed to load flashcards');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchFlashcards();
  }, [id]);

  const handleFlip = useCallback(() => {
    setIsFlipped(prev => !prev);
  }, []);

  const advanceCard = useCallback(() => {
    if (currentIndex < cards.length - 1) {
      setCurrentIndex(prev => prev + 1);
      setIsFlipped(false);
    } else {
      setShowSummary(true);
    }
  }, [currentIndex, cards.length]);

  const handlePrev = useCallback(() => {
    setCurrentIndex(prev => {
      if (prev > 0) return prev - 1;
      return prev;
    });
    setIsFlipped(false);
  }, []);

  const handleNext = useCallback(() => {
    if (currentIndex < cards.length - 1) {
      setCurrentIndex(prev => prev + 1);
      setIsFlipped(false);
    }
  }, [currentIndex, cards.length]);

  const handleMastery = useCallback((difficulty: CardDifficulty) => {
    const card = cards[currentIndex];
    setCardProgress(prev => {
      const next = new Map(prev);
      next.set(card.front, difficulty);
      return next;
    });
    advanceCard();
  }, [cards, currentIndex, advanceCard]);

  const handleShuffle = () => {
    const shuffled = [...cards].sort(() => Math.random() - 0.5);
    setCards(shuffled);
    setCurrentIndex(0);
    setIsFlipped(false);
  };

  // Keyboard shortcuts — uses refs to avoid stale closures (#153)
  useEffect(() => {
    const advance = () => {
      const idx = currentIndexRef.current;
      const len = cardsRef.current.length;
      if (idx < len - 1) {
        setCurrentIndex(idx + 1);
        setIsFlipped(false);
      } else {
        setShowSummary(true);
      }
    };

    const markAndAdvance = (difficulty: CardDifficulty) => {
      const card = cardsRef.current[currentIndexRef.current];
      setCardProgress(prev => {
        const next = new Map(prev);
        next.set(card.front, difficulty);
        return next;
      });
      advance();
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (showSummaryRef.current) return;
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        setIsFlipped(prev => !prev);
      } else if (e.key === 'ArrowLeft') {
        setCurrentIndex(prev => {
          if (prev > 0) return prev - 1;
          return prev;
        });
        setIsFlipped(false);
      } else if (e.key === 'ArrowRight') {
        if (isFlippedRef.current) {
          markAndAdvance('mastered');
        } else {
          const idx = currentIndexRef.current;
          if (idx < cardsRef.current.length - 1) {
            setCurrentIndex(idx + 1);
            setIsFlipped(false);
          }
        }
      } else if (e.key === '1' && isFlippedRef.current) {
        markAndAdvance('mastered');
      } else if (e.key === '2' && isFlippedRef.current) {
        markAndAdvance('learning');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const summary = useMemo(() => {
    let mastered = 0;
    let learning = 0;
    cards.forEach(c => {
      const status = cardProgress.get(c.front);
      if (status === 'mastered') mastered++;
      else if (status === 'learning') learning++;
    });
    return { mastered, learning, total: cards.length };
  }, [cards, cardProgress]);

  const handleReviewDifficult = () => {
    const difficult = allCards.filter(c => cardProgress.get(c.front) === 'learning');
    if (difficult.length === 0) return;
    setCards(difficult);
    setCurrentIndex(0);
    setIsFlipped(false);
    setShowSummary(false);
    setReviewMode(true);
  };

  const handleRestartAll = () => {
    setCards(allCards);
    setCurrentIndex(0);
    setIsFlipped(false);
    setShowSummary(false);
    setCardProgress(new Map());
    setReviewMode(false);
  };

  if (loading) {
    return (
      <div className="flashcards-page">
        <div className="flashcards-header">
          <div className="skeleton" style={{ width: 120, height: 16 }} />
          <div className="skeleton" style={{ width: '50%', height: 28, marginTop: 8 }} />
          <div className="skeleton" style={{ width: 140, height: 14, marginTop: 8 }} />
        </div>
        <div className="flashcard-container">
          <div className="skeleton" style={{ width: '100%', maxWidth: 500, height: 300, borderRadius: 16, margin: '0 auto' }} />
        </div>
        <div className="flashcard-controls" style={{ justifyContent: 'center' }}>
          <div className="skeleton" style={{ width: 100, height: 36, borderRadius: 8 }} />
          <div className="skeleton" style={{ width: 80, height: 36, borderRadius: 8 }} />
          <div className="skeleton" style={{ width: 100, height: 36, borderRadius: 8 }} />
        </div>
      </div>
    );
  }

  if (error || !guide || cards.length === 0) {
    return (
      <div className="flashcards-page">
        <div className="error">{error || 'Flashcards not found'}</div>
        <Link to="/dashboard" className="back-link">Back to Dashboard</Link>
      </div>
    );
  }

  if (showSummary) {
    const pct = summary.total > 0 ? Math.round((summary.mastered / summary.total) * 100) : 0;
    return (
      <div className="flashcards-page">
        <div className="flashcards-header">
          <Link to="/dashboard" className="back-link">&larr; Back to Dashboard</Link>
          <h1>{guide.title}</h1>
        </div>
        <div className="fc-summary">
          <div className="fc-summary-card">
            <h2>{reviewMode ? 'Review Complete!' : 'Session Complete!'}</h2>
            <div className="fc-summary-stats">
              <div className="fc-stat mastered">
                <span className="fc-stat-value">{summary.mastered}</span>
                <span className="fc-stat-label">Mastered</span>
              </div>
              <div className="fc-stat learning">
                <span className="fc-stat-value">{summary.learning}</span>
                <span className="fc-stat-label">Still Learning</span>
              </div>
            </div>
            <p className="fc-summary-pct">{pct}% mastered</p>
            <p className="fc-summary-encouragement">
              {pct === 100 ? 'You nailed every card!' :
               pct >= 70 ? 'Great progress! Keep it up!' :
               'Practice makes perfect — review the tricky ones!'}
            </p>
            <div className="fc-summary-actions">
              {summary.learning > 0 && (
                <button className="fc-review-btn" onClick={handleReviewDifficult}>
                  Review Difficult ({summary.learning})
                </button>
              )}
              <button className="fc-restart-btn" onClick={handleRestartAll}>
                Start Over
              </button>
              <Link to="/dashboard" className="fc-done-btn">Done</Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const card = cards[currentIndex];
  const currentDifficulty = cardProgress.get(card.front);

  return (
    <div className="flashcards-page">
      <div className="flashcards-header">
        <Link to="/dashboard" className="back-link">&larr; Back to Dashboard</Link>
        <h1>
          {guide.title}
          {reviewMode && <span className="review-mode-badge">Review Mode</span>}
          {guide.version > 1 && <span style={{ background: '#e3f2fd', color: '#1565c0', padding: '1px 6px', borderRadius: '8px', fontSize: '0.75rem', marginLeft: '0.5rem', verticalAlign: 'middle' }}>v{guide.version}</span>}
        </h1>
        <CourseAssignSelect
          guideId={guide.id}
          currentCourseId={guide.course_id}
          onCourseChanged={(courseId) => setGuide({ ...guide, course_id: courseId })}
        />
        <button className="control-btn" onClick={() => setShowTaskModal(true)} title="Create task">&#128203; + Task</button>
        <div className="progress">
          Card {currentIndex + 1} of {cards.length}
        </div>
      </div>

      <div className="flashcard-container">
        <div
          className={`flashcard ${isFlipped ? 'flipped' : ''}`}
          onClick={handleFlip}
        >
          <div className="flashcard-inner">
            <div className="flashcard-front">
              <p>{card.front}</p>
              <span className="flip-hint">Click to flip</span>
            </div>
            <div className="flashcard-back">
              <p>{card.back}</p>
              <span className="flip-hint">Click to flip back</span>
            </div>
          </div>
        </div>
      </div>

      {/* Mastery buttons (shown after flip) */}
      {isFlipped && (
        <div className="mastery-buttons">
          <button
            className={`mastery-btn got-it${currentDifficulty === 'mastered' ? ' active' : ''}`}
            onClick={() => handleMastery('mastered')}
          >
            Got it
          </button>
          <button
            className={`mastery-btn still-learning${currentDifficulty === 'learning' ? ' active' : ''}`}
            onClick={() => handleMastery('learning')}
          >
            Still Learning
          </button>
        </div>
      )}

      {!isFlipped && (
        <div className="flashcard-controls">
          <button
            className="control-btn"
            onClick={handlePrev}
            disabled={currentIndex === 0}
          >
            &larr; Previous
          </button>
          <button className="shuffle-btn" onClick={handleShuffle}>
            Shuffle
          </button>
          <button
            className="control-btn"
            onClick={handleNext}
            disabled={currentIndex === cards.length - 1}
          >
            Next &rarr;
          </button>
        </div>
      )}

      <div className="keyboard-hints">
        <span>Space/Enter: Flip</span>
        {isFlipped ? (
          <>
            <span>1: Got it</span>
            <span>2: Still Learning</span>
          </>
        ) : (
          <span>Arrow Keys: Navigate</span>
        )}
      </div>
      <CreateTaskModal
        open={showTaskModal}
        onClose={() => setShowTaskModal(false)}
        prefillTitle={`Review: ${guide.title}`}
        studyGuideId={guide.id}
        courseId={guide.course_id ?? undefined}
        linkedEntityLabel={`Flashcards: ${guide.title}`}
      />
    </div>
  );
}
