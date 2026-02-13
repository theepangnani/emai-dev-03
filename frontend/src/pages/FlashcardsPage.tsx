import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { studyApi } from '../api/client';
import type { StudyGuide, Flashcard } from '../api/client';
import { CourseAssignSelect } from '../components/CourseAssignSelect';
import { CreateTaskModal } from '../components/CreateTaskModal';
import './FlashcardsPage.css';

export function FlashcardsPage() {
  const { id } = useParams<{ id: string }>();
  const [guide, setGuide] = useState<StudyGuide | null>(null);
  const [cards, setCards] = useState<Flashcard[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showTaskModal, setShowTaskModal] = useState(false);

  useEffect(() => {
    const fetchFlashcards = async () => {
      if (!id) return;
      try {
        const data = await studyApi.getGuide(parseInt(id));
        setGuide(data);
        const parsedCards = JSON.parse(data.content) as Flashcard[];
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

  const handlePrev = useCallback(() => {
    setCurrentIndex(prev => {
      if (prev > 0) {
        setIsFlipped(false);
        return prev - 1;
      }
      return prev;
    });
  }, []);

  const handleNext = useCallback(() => {
    setCurrentIndex(prev => {
      if (prev < cards.length - 1) {
        setIsFlipped(false);
        return prev + 1;
      }
      return prev;
    });
  }, [cards.length]);

  const handleShuffle = () => {
    const shuffled = [...cards].sort(() => Math.random() - 0.5);
    setCards(shuffled);
    setCurrentIndex(0);
    setIsFlipped(false);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        handleFlip();
      } else if (e.key === 'ArrowLeft') {
        handlePrev();
      } else if (e.key === 'ArrowRight') {
        handleNext();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleFlip, handlePrev, handleNext]);

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

  const card = cards[currentIndex];

  return (
    <div className="flashcards-page">
      <div className="flashcards-header">
        <Link to="/dashboard" className="back-link">&larr; Back to Dashboard</Link>
        <h1>
          {guide.title}
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

      <div className="keyboard-hints">
        <span>Space/Enter: Flip</span>
        <span>Arrow Keys: Navigate</span>
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
