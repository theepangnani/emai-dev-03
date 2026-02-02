import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { studyApi } from '../api/client';
import type { StudyGuide, QuizQuestion } from '../api/client';
import './QuizPage.css';

export function QuizPage() {
  const { id } = useParams<{ id: string }>();
  const [guide, setGuide] = useState<StudyGuide | null>(null);
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [score, setScore] = useState(0);
  const [answers, setAnswers] = useState<{ [key: number]: string }>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchQuiz = async () => {
      if (!id) return;
      try {
        const data = await studyApi.getGuide(parseInt(id));
        setGuide(data);
        const parsedQuestions = JSON.parse(data.content) as QuizQuestion[];
        setQuestions(parsedQuestions);
      } catch (err) {
        setError('Failed to load quiz');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchQuiz();
  }, [id]);

  const handleAnswer = (answer: string) => {
    setSelectedAnswer(answer);
  };

  const handleSubmit = () => {
    if (!selectedAnswer) return;

    const isCorrect = selectedAnswer === questions[currentQuestion].correct_answer;
    if (isCorrect) {
      setScore(score + 1);
    }

    setAnswers({ ...answers, [currentQuestion]: selectedAnswer });
    setShowResult(true);
  };

  const handleNext = () => {
    if (currentQuestion < questions.length - 1) {
      setCurrentQuestion(currentQuestion + 1);
      setSelectedAnswer(null);
      setShowResult(false);
    }
  };

  const isQuizComplete = currentQuestion === questions.length - 1 && showResult;

  if (loading) {
    return (
      <div className="quiz-page">
        <div className="loading">Loading quiz...</div>
      </div>
    );
  }

  if (error || !guide || questions.length === 0) {
    return (
      <div className="quiz-page">
        <div className="error">{error || 'Quiz not found'}</div>
        <Link to="/dashboard" className="back-link">Back to Dashboard</Link>
      </div>
    );
  }

  const question = questions[currentQuestion];

  return (
    <div className="quiz-page">
      <div className="quiz-header">
        <Link to="/dashboard" className="back-link">&larr; Back to Dashboard</Link>
        <h1>{guide.title}</h1>
        <div className="progress">
          Question {currentQuestion + 1} of {questions.length}
        </div>
      </div>

      {!isQuizComplete ? (
        <div className="quiz-content">
          <div className="question-card">
            <h2 className="question-text">{question.question}</h2>

            <div className="options">
              {Object.entries(question.options).map(([letter, text]) => (
                <button
                  key={letter}
                  className={`option ${selectedAnswer === letter ? 'selected' : ''} ${
                    showResult
                      ? letter === question.correct_answer
                        ? 'correct'
                        : selectedAnswer === letter
                        ? 'incorrect'
                        : ''
                      : ''
                  }`}
                  onClick={() => !showResult && handleAnswer(letter)}
                  disabled={showResult}
                >
                  <span className="option-letter">{letter}</span>
                  <span className="option-text">{text}</span>
                </button>
              ))}
            </div>

            {showResult && (
              <div className={`result ${selectedAnswer === question.correct_answer ? 'correct' : 'incorrect'}`}>
                <p className="result-status">
                  {selectedAnswer === question.correct_answer ? 'Correct!' : 'Incorrect'}
                </p>
                <p className="explanation">{question.explanation}</p>
              </div>
            )}

            <div className="actions">
              {!showResult ? (
                <button
                  className="submit-btn"
                  onClick={handleSubmit}
                  disabled={!selectedAnswer}
                >
                  Submit Answer
                </button>
              ) : (
                <button className="next-btn" onClick={handleNext}>
                  {currentQuestion < questions.length - 1 ? 'Next Question' : 'See Results'}
                </button>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="quiz-results">
          <div className="results-card">
            <h2>Quiz Complete!</h2>
            <div className="score">
              <span className="score-value">{score}</span>
              <span className="score-total">/ {questions.length}</span>
            </div>
            <p className="score-percent">
              {Math.round((score / questions.length) * 100)}% correct
            </p>
            <div className="results-actions">
              <button
                className="retry-btn"
                onClick={() => {
                  setCurrentQuestion(0);
                  setSelectedAnswer(null);
                  setShowResult(false);
                  setScore(0);
                  setAnswers({});
                }}
              >
                Try Again
              </button>
              <Link to="/dashboard" className="done-btn">
                Done
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
