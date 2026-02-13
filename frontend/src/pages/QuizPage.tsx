import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { studyApi } from '../api/client';
import type { StudyGuide, QuizQuestion } from '../api/client';
import { CourseAssignSelect } from '../components/CourseAssignSelect';
import { CreateTaskModal } from '../components/CreateTaskModal';
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
  const [showTaskModal, setShowTaskModal] = useState(false);

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
        <div className="quiz-header">
          <div className="skeleton" style={{ width: 120, height: 16 }} />
          <div className="skeleton" style={{ width: '50%', height: 28, marginTop: 8 }} />
          <div className="skeleton" style={{ width: 140, height: 14, marginTop: 8 }} />
        </div>
        <div className="quiz-content">
          <div className="question-card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="skeleton" style={{ width: '80%', height: 22 }} />
            <div className="skeleton" style={{ width: '100%', height: 48, borderRadius: 8 }} />
            <div className="skeleton" style={{ width: '100%', height: 48, borderRadius: 8 }} />
            <div className="skeleton" style={{ width: '100%', height: 48, borderRadius: 8 }} />
            <div className="skeleton" style={{ width: '100%', height: 48, borderRadius: 8 }} />
          </div>
        </div>
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
        <h1>
          {guide.title}
          {guide.version > 1 && <span style={{ background: '#e3f2fd', color: '#1565c0', padding: '1px 6px', borderRadius: '8px', fontSize: '0.75rem', marginLeft: '0.5rem', verticalAlign: 'middle' }}>v{guide.version}</span>}
        </h1>
        <CourseAssignSelect
          guideId={guide.id}
          currentCourseId={guide.course_id}
          onCourseChanged={(courseId) => setGuide({ ...guide, course_id: courseId })}
        />
        <button className="submit-btn" onClick={() => setShowTaskModal(true)} title="Create task" style={{ padding: '6px 12px', fontSize: '13px' }}>&#128203; + Task</button>
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
      <CreateTaskModal
        open={showTaskModal}
        onClose={() => setShowTaskModal(false)}
        prefillTitle={`Review: ${guide.title}`}
        studyGuideId={guide.id}
        courseId={guide.course_id ?? undefined}
        linkedEntityLabel={`Quiz: ${guide.title}`}
      />
    </div>
  );
}
