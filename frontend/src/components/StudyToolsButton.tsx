import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { studyApi } from '../api/client';
import { useConfirm } from './ConfirmModal';
import './StudyToolsButton.css';

interface StudyToolsButtonProps {
  assignmentId: number;
  assignmentTitle: string;
}

export function StudyToolsButton({ assignmentId }: StudyToolsButtonProps) {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { confirm, confirmModal } = useConfirm();

  const handleGenerateGuide = async () => {
    const ok = await confirm({
      title: 'Generate Study Guide',
      message: 'Generate a study guide from this assignment? This will use AI credits.',
      confirmLabel: 'Generate',
    });
    if (!ok) return;
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
    const ok = await confirm({
      title: 'Generate Practice Quiz',
      message: 'Generate a practice quiz from this assignment? This will use AI credits.',
      confirmLabel: 'Generate',
    });
    if (!ok) return;
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
    const ok = await confirm({
      title: 'Generate Flashcards',
      message: 'Generate flashcards from this assignment? This will use AI credits.',
      confirmLabel: 'Generate',
    });
    if (!ok) return;
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
      {confirmModal}
    </div>
  );
}
