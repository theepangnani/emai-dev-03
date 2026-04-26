import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, Link, useNavigate, useLocation } from 'react-router-dom';
import { studyApi } from '../api/client';
import type { StudyGuide, Flashcard } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { MaterialContextMenu } from '../components/MaterialContextMenu';
import { EditStudyGuideModal } from '../components/EditStudyGuideModal';
import { PageNav } from '../components/PageNav';
import { useRegisterNotesFAB } from '../context/FABContext';
import { NotesPanel } from '../components/NotesPanel';
import './FlashcardsPage.css';

type CardDifficulty = 'mastered' | 'learning';

export function FlashcardsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [guide, setGuide] = useState<StudyGuide | null>(null);
  const [allCards, setAllCards] = useState<Flashcard[]>([]);
  const [cards, setCards] = useState<Flashcard[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const toggleNotes = useCallback(() => setNotesOpen(v => !v), []);
  useRegisterNotesFAB(guide?.course_content_id ? { courseContentId: guide.course_content_id, isOpen: notesOpen, onToggle: toggleNotes } : null);

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
        let parsedCards: Flashcard[];
        try {
          parsedCards = JSON.parse(data.content) as Flashcard[];
        } catch {
          setError('Flashcard content is corrupted. Please try regenerating these flashcards.');
          return;
        }
        if (!Array.isArray(parsedCards) || parsedCards.length === 0) {
          setError('Flashcard content is corrupted. Please try regenerating these flashcards.');
          return;
        }
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

  // Redirect to course-materials tab when flashcards have a parent material (#1969)
  // Skip redirect if opened from class materials tab (fromMaterial state)
  const location = useLocation();
  const fromMaterial = (location.state as { fromMaterial?: boolean })?.fromMaterial;
  useEffect(() => {
    if (guide && guide.course_content_id && !fromMaterial) {
      navigate(`/course-materials/${guide.course_content_id}?tab=flashcards`, { replace: true });
    }
  }, [guide, navigate, fromMaterial]);

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
      <DashboardLayout headerSlot={() => null}>
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
      </DashboardLayout>
    );
  }

  if (error || !guide || cards.length === 0) {
    return (
      <DashboardLayout headerSlot={() => null}>
        <div className="flashcards-page">
          <PageNav items={[
            { label: 'Home', to: '/dashboard' },
            { label: 'Class Materials', to: '/course-materials' },
            ...(guide?.course_content_id
              ? [{ label: guide.title.replace(/^Flashcards:\s*/i, ''), to: `/course-materials/${guide.course_content_id}?tab=flashcards` }]
              : []),
            { label: 'Flashcards' },
          ]} />
          <div className="error">{error || 'Flashcards not found'}</div>
        </div>
      </DashboardLayout>
    );
  }

  if (showSummary) {
    const pct = summary.total > 0 ? Math.round((summary.mastered / summary.total) * 100) : 0;
    return (
      <DashboardLayout headerSlot={() => null}>
      <div className="flashcards-page">
        <div className="flashcards-header">
          <PageNav items={[
            { label: 'Home', to: '/dashboard' },
            { label: 'Class Materials', to: '/course-materials' },
            ...(guide?.course_content_id
              ? [{ label: guide.title.replace(/^Flashcards:\s*/i, ''), to: `/course-materials/${guide.course_content_id}?tab=flashcards` }]
              : []),
            { label: 'Flashcards' },
          ]} />
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
      </DashboardLayout>
    );
  }

  const card = cards[currentIndex];
  const currentDifficulty = cardProgress.get(card.front);

  return (
    <DashboardLayout headerSlot={() => null}>
    <div className="flashcards-page">
      <div className="flashcards-header">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Class Materials', to: '/course-materials' },
          ...(guide?.course_content_id
            ? [{ label: guide.title.replace(/^Flashcards:\s*/i, ''), to: `/course-materials/${guide.course_content_id}?tab=flashcards` }]
            : []),
          { label: 'Flashcards' },
        ]} />
        <h1>
          {guide.title}
          {reviewMode && <span className="review-mode-badge">Review Mode</span>}
          {guide.version > 1 && <span style={{ background: 'var(--color-info-bg)', color: 'var(--color-info)', padding: '1px 6px', borderRadius: '8px', fontSize: '0.75rem', marginLeft: '0.5rem', verticalAlign: 'middle' }}>v{guide.version}</span>}
        </h1>
        <div className="flashcards-header-actions">
          <MaterialContextMenu items={[
            { label: 'Create Task', icon: <svg width="16" height="16" viewBox="0 0 20 20" fill="none"><rect x="3" y="2" width="14" height="16" rx="2" stroke="currentColor" strokeWidth="1.6"/><path d="M7 7h6M7 10.5h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/><circle cx="14.5" cy="14.5" r="4.5" fill="var(--color-accent-strong, #2a9fa8)"/><path d="M14.5 12.5v4M12.5 14.5h4" stroke="#fff" strokeWidth="1.4" strokeLinecap="round"/></svg>, onClick: () => setShowTaskModal(true) },
            { label: 'Edit Class Material', icon: <svg width="16" height="16" viewBox="0 0 20 20" fill="none"><path d="M13.586 3.586a2 2 0 112.828 2.828l-9.5 9.5L3 17l1.086-3.914 9.5-9.5z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>, onClick: () => setShowEditModal(true) },
          ]} />
          {/* Notes FAB at bottom-right */}
        </div>
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
      {showEditModal && (
        <EditStudyGuideModal
          guide={guide}
          onClose={() => setShowEditModal(false)}
          onSaved={(updated) => { setGuide(updated); setShowEditModal(false); }}
        />
      )}
      {guide.course_content_id && (
        <>
          <NotesPanel courseContentId={guide.course_content_id} isOpen={notesOpen} onClose={() => setNotesOpen(false)} />
        </>
      )}
    </div>
    </DashboardLayout>
  );
}
