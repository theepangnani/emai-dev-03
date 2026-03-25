import { useState, useEffect, useCallback } from 'react';
import { dailyQuizApi } from '../api/dailyQuiz';
import type { DailyQuizResponse, DailyQuizQuestion } from '../api/dailyQuiz';
import './QuizOfTheDay.css';

export function QuizOfTheDay() {
  const [quiz, setQuiz] = useState<DailyQuizResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Quiz-taking state
  const [started, setStarted] = useState(false);
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [score, setScore] = useState(0);

  // Submit state
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [xpAwarded, setXpAwarded] = useState<number | null>(null);
  const [showCelebration, setShowCelebration] = useState(false);

  const fetchQuiz = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await dailyQuizApi.getQuiz();
      setQuiz(data);
      if (data.completed_at) {
        setSubmitted(true);
      }
    } catch {
      setError('Could not load Quiz of the Day');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQuiz();
  }, [fetchQuiz]);

  const handleAnswer = (answer: string) => {
    if (showResult) return;
    setSelectedAnswer(answer);
  };

  const handleSubmitAnswer = () => {
    if (!selectedAnswer || !quiz) return;
    const question = quiz.questions[currentQuestion];
    const isCorrect = selectedAnswer === question.correct_answer;
    if (isCorrect) setScore(prev => prev + 1);
    setAnswers(prev => ({ ...prev, [currentQuestion]: selectedAnswer }));
    setShowResult(true);
  };

  const handleNext = () => {
    if (!quiz) return;
    if (currentQuestion < quiz.questions.length - 1) {
      setCurrentQuestion(prev => prev + 1);
      setSelectedAnswer(null);
      setShowResult(false);
    }
  };

  const isQuizComplete = quiz ? currentQuestion === quiz.questions.length - 1 && showResult : false;

  // Submit when quiz is complete
  useEffect(() => {
    if (!isQuizComplete || submitted || submitting) return;
    setSubmitting(true);
    const finalAnswers = { ...answers };
    // Include the last answer
    if (quiz && selectedAnswer) {
      finalAnswers[currentQuestion] = selectedAnswer;
    }
    dailyQuizApi.submit(finalAnswers).then((result) => {
      setXpAwarded(result.xp_awarded);
      setSubmitted(true);
      setShowCelebration(true);
      setTimeout(() => setShowCelebration(false), 3000);
    }).catch(() => {
      // Score was already tracked locally
      setSubmitted(true);
    }).finally(() => {
      setSubmitting(false);
    });
  }, [isQuizComplete, submitted, submitting, answers, quiz, selectedAnswer, currentQuestion]);

  // Loading state
  if (loading) {
    return (
      <div className="qotd-card">
        <div className="qotd-card-header">
          <span className="qotd-icon" aria-hidden="true">&#9889;</span>
          <h3 className="qotd-title">Quiz of the Day</h3>
        </div>
        <div className="qotd-card-body">
          <div className="skeleton" style={{ width: '60%', height: 16 }} />
          <div className="skeleton" style={{ width: '40%', height: 14, marginTop: 8 }} />
        </div>
      </div>
    );
  }

  // Error state
  if (error || !quiz) {
    return (
      <div className="qotd-card">
        <div className="qotd-card-header">
          <span className="qotd-icon" aria-hidden="true">&#9889;</span>
          <h3 className="qotd-title">Quiz of the Day</h3>
        </div>
        <div className="qotd-card-body">
          <p className="qotd-error">{error || 'Quiz unavailable'}</p>
          <button className="qotd-retry-btn" onClick={fetchQuiz}>Try Again</button>
        </div>
      </div>
    );
  }

  // Already completed (page load)
  if (quiz.completed_at && !started) {
    return (
      <div className="qotd-card qotd-card--completed">
        <div className="qotd-card-header">
          <span className="qotd-icon" aria-hidden="true">&#9889;</span>
          <h3 className="qotd-title">Quiz of the Day</h3>
          <span className="qotd-badge">Completed</span>
        </div>
        <div className="qotd-card-body">
          <div className="qotd-score-display">
            <span className="qotd-score-value">{quiz.score}</span>
            <span className="qotd-score-sep">/</span>
            <span className="qotd-score-total">{quiz.total_questions}</span>
          </div>
          <p className="qotd-score-pct">{quiz.percentage}% correct</p>
        </div>
      </div>
    );
  }

  // Not started yet — show card
  if (!started) {
    return (
      <div className="qotd-card">
        <div className="qotd-card-header">
          <span className="qotd-icon" aria-hidden="true">&#9889;</span>
          <h3 className="qotd-title">Quiz of the Day</h3>
        </div>
        <div className="qotd-card-body">
          <p className="qotd-info">{quiz.total_questions} questions &middot; ~2 min</p>
          <button className="qotd-start-btn" onClick={() => setStarted(true)}>
            Start Quiz
          </button>
        </div>
      </div>
    );
  }

  // Active quiz
  const question: DailyQuizQuestion = quiz.questions[currentQuestion];

  // Quiz complete — show results
  if (isQuizComplete) {
    const finalScore = score;
    const pct = Math.round((finalScore / quiz.questions.length) * 100);
    return (
      <div className="qotd-card qotd-card--results">
        {showCelebration && <div className="qotd-celebration" aria-hidden="true" />}
        <div className="qotd-card-header">
          <span className="qotd-icon" aria-hidden="true">&#9889;</span>
          <h3 className="qotd-title">Quiz Complete!</h3>
        </div>
        <div className="qotd-card-body qotd-results-body">
          <div className="qotd-score-display qotd-score-display--large">
            <span className="qotd-score-value">{finalScore}</span>
            <span className="qotd-score-sep">/</span>
            <span className="qotd-score-total">{quiz.questions.length}</span>
          </div>
          <p className="qotd-score-pct">{pct}% correct</p>
          <p className="qotd-encouragement">
            {pct === 100
              ? 'Perfect score! Outstanding!'
              : pct >= 80
              ? 'Great job!'
              : pct >= 60
              ? 'Good effort! Keep practicing.'
              : 'Keep learning — every attempt helps!'}
          </p>
          {xpAwarded != null && xpAwarded > 0 && (
            <p className="qotd-xp">+{xpAwarded} XP earned</p>
          )}
          {submitting && <p className="qotd-saving">Saving...</p>}
        </div>
      </div>
    );
  }

  // In-progress question
  return (
    <div className="qotd-card qotd-card--active">
      <div className="qotd-card-header">
        <span className="qotd-icon" aria-hidden="true">&#9889;</span>
        <h3 className="qotd-title">Quiz of the Day</h3>
        <span className="qotd-progress">
          {currentQuestion + 1}/{quiz.questions.length}
        </span>
      </div>
      <div className="qotd-progress-bar">
        {quiz.questions.map((_: DailyQuizQuestion, i: number) => (
          <div
            key={i}
            className={`qotd-progress-seg${
              i < currentQuestion
                ? answers[i] === quiz.questions[i].correct_answer
                  ? ' correct'
                  : ' incorrect'
                : i === currentQuestion && showResult
                ? selectedAnswer === question.correct_answer
                  ? ' correct'
                  : ' incorrect'
                : i === currentQuestion
                ? ' current'
                : ''
            }`}
          />
        ))}
      </div>
      <div className="qotd-card-body">
        <p className="qotd-question">{question.question}</p>
        <div className="qotd-options">
          {Object.entries(question.options).map(([letter, text]) => (
            <button
              key={letter}
              className={`qotd-option${selectedAnswer === letter ? ' selected' : ''}${
                showResult
                  ? letter === question.correct_answer
                    ? ' correct'
                    : selectedAnswer === letter
                    ? ' incorrect'
                    : ''
                  : ''
              }`}
              onClick={() => handleAnswer(letter)}
              disabled={showResult}
            >
              <span className="qotd-option-letter">{letter}</span>
              <span className="qotd-option-text">{text}</span>
            </button>
          ))}
        </div>
        {showResult && (
          <div className={`qotd-feedback ${selectedAnswer === question.correct_answer ? 'correct' : 'incorrect'}`}>
            <p className="qotd-feedback-status">
              {selectedAnswer === question.correct_answer ? 'Correct!' : 'Incorrect'}
            </p>
            <p className="qotd-feedback-explanation">{question.explanation}</p>
          </div>
        )}
        <div className="qotd-actions">
          {!showResult ? (
            <button
              className="qotd-submit-btn"
              onClick={handleSubmitAnswer}
              disabled={!selectedAnswer}
            >
              Submit
            </button>
          ) : (
            <button className="qotd-next-btn" onClick={handleNext}>
              {currentQuestion < quiz.questions.length - 1 ? 'Next' : 'See Results'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
