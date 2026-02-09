import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { studyApi } from '../api/client';
import './StudyToolsButton.css';

interface StudyToolsButtonProps {
  assignmentId: number;
  assignmentTitle: string;
}

export function StudyToolsButton({ assignmentId }: StudyToolsButtonProps) {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerateGuide = async () => {
    if (!window.confirm('Generate a study guide? This will use AI credits.')) return;
    setIsLoading('guide');
    setError(null);
    try {
      const guide = await studyApi.generateGuide({ assignment_id: assignmentId });
      navigate(`/study/guide/${guide.id}`);
    } catch (err) {
      setError('Failed to generate study guide');
      console.error(err);
    } finally {
      setIsLoading(null);
    }
  };

  const handleGenerateQuiz = async () => {
    if (!window.confirm('Generate a practice quiz? This will use AI credits.')) return;
    setIsLoading('quiz');
    setError(null);
    try {
      const quiz = await studyApi.generateQuiz({ assignment_id: assignmentId, num_questions: 5 });
      navigate(`/study/quiz/${quiz.id}`);
    } catch (err) {
      setError('Failed to generate quiz');
      console.error(err);
    } finally {
      setIsLoading(null);
    }
  };

  const handleGenerateFlashcards = async () => {
    if (!window.confirm('Generate flashcards? This will use AI credits.')) return;
    setIsLoading('flashcards');
    setError(null);
    try {
      const cards = await studyApi.generateFlashcards({ assignment_id: assignmentId, num_cards: 10 });
      navigate(`/study/flashcards/${cards.id}`);
    } catch (err) {
      setError('Failed to generate flashcards');
      console.error(err);
    } finally {
      setIsLoading(null);
    }
  };

  return (
    <div className="study-tools">
      <div className="study-tools-buttons">
        <button
          className="study-btn study-btn-guide"
          onClick={handleGenerateGuide}
          disabled={isLoading !== null}
          title="Generate Study Guide"
        >
          {isLoading === 'guide' ? '...' : 'Study Guide'}
        </button>
        <button
          className="study-btn study-btn-quiz"
          onClick={handleGenerateQuiz}
          disabled={isLoading !== null}
          title="Generate Practice Quiz"
        >
          {isLoading === 'quiz' ? '...' : 'Quiz'}
        </button>
        <button
          className="study-btn study-btn-cards"
          onClick={handleGenerateFlashcards}
          disabled={isLoading !== null}
          title="Generate Flashcards"
        >
          {isLoading === 'flashcards' ? '...' : 'Flashcards'}
        </button>
      </div>
      {error && <p className="study-error">{error}</p>}
    </div>
  );
}
