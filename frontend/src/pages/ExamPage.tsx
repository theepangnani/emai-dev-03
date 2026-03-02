import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { mockExamsApi } from '../api/mockExams';
import type { MockExamAssignment, QuestionItem } from '../api/mockExams';
import { DashboardLayout } from '../components/DashboardLayout';
import './ExamPage.css';

const SESSION_KEY_PREFIX = 'exam_timer_';
const SESSION_ANSWERS_PREFIX = 'exam_answers_';

function formatTime(seconds: number): string {
  if (seconds <= 0) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function ExamPage() {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const navigate = useNavigate();
  const id = Number(assignmentId);

  const [assignment, setAssignment] = useState<MockExamAssignment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Exam state
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [timeLeft, setTimeLeft] = useState<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(Date.now());

  // Submit state
  const [showConfirm, setShowConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [result, setResult] = useState<MockExamAssignment | null>(null);

  // Load assignment
  useEffect(() => {
    if (!id) return;
    setLoading(true);
    mockExamsApi.getAssignment(id)
      .then(data => {
        if (data.status === 'completed') {
          setResult(data);
          setAssignment(data);
          setLoading(false);
          return;
        }
        setAssignment(data);

        // Restore answers from session storage
        const savedAnswers = sessionStorage.getItem(`${SESSION_ANSWERS_PREFIX}${id}`);
        const numQ = data.num_questions;
        if (savedAnswers) {
          try {
            const parsed = JSON.parse(savedAnswers);
            if (Array.isArray(parsed) && parsed.length === numQ) {
              setAnswers(parsed);
            } else {
              setAnswers(new Array(numQ).fill(null));
            }
          } catch {
            setAnswers(new Array(numQ).fill(null));
          }
        } else {
          setAnswers(new Array(numQ).fill(null));
        }

        // Timer: restore from session storage
        const timeLimitSec = (data.time_limit_minutes ?? 60) * 60;
        const savedTime = sessionStorage.getItem(`${SESSION_KEY_PREFIX}${id}`);
        if (savedTime) {
          const remaining = parseInt(savedTime, 10);
          if (!isNaN(remaining) && remaining > 0) {
            setTimeLeft(remaining);
          } else {
            setTimeLeft(timeLimitSec);
          }
        } else {
          setTimeLeft(timeLimitSec);
        }

        startTimeRef.current = Date.now();
        setLoading(false);
      })
      .catch(() => {
        setError('Failed to load exam. Please go back and try again.');
        setLoading(false);
      });
  }, [id]);

  // Timer tick
  useEffect(() => {
    if (timeLeft === null || result) return;
    if (timeLeft <= 0) {
      // Time's up — auto-submit
      handleAutoSubmit();
      return;
    }
    timerRef.current = setInterval(() => {
      setTimeLeft(prev => {
        if (prev === null) return null;
        const next = prev - 1;
        sessionStorage.setItem(`${SESSION_KEY_PREFIX}${id}`, String(next));
        return next;
      });
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeLeft !== null, !!result]);

  // Persist answers to session storage whenever they change
  useEffect(() => {
    if (answers.length > 0 && id) {
      sessionStorage.setItem(`${SESSION_ANSWERS_PREFIX}${id}`, JSON.stringify(answers));
    }
  }, [answers, id]);

  const handleAutoSubmit = useCallback(async () => {
    if (!assignment) return;
    const timeTaken = Math.round((Date.now() - startTimeRef.current) / 1000);
    const finalAnswers = answers.map(a => (a === null ? -1 : a));
    try {
      const res = await mockExamsApi.submit(id, {
        answers: finalAnswers,
        time_taken_seconds: timeTaken,
      });
      sessionStorage.removeItem(`${SESSION_KEY_PREFIX}${id}`);
      sessionStorage.removeItem(`${SESSION_ANSWERS_PREFIX}${id}`);
      setResult(res);
      setAssignment(res);
    } catch {
      // Silent — show error only if user-triggered
    }
  }, [assignment, answers, id]);

  const handleSelectAnswer = (optionIndex: number) => {
    setAnswers(prev => {
      const next = [...prev];
      next[currentQ] = optionIndex;
      return next;
    });
  };

  const handleSubmit = async () => {
    if (!assignment) return;
    setSubmitting(true);
    setSubmitError('');
    const timeTaken = Math.round((Date.now() - startTimeRef.current) / 1000);
    const finalAnswers = answers.map(a => (a === null ? -1 : a));
    try {
      const res = await mockExamsApi.submit(id, {
        answers: finalAnswers,
        time_taken_seconds: timeTaken,
      });
      sessionStorage.removeItem(`${SESSION_KEY_PREFIX}${id}`);
      sessionStorage.removeItem(`${SESSION_ANSWERS_PREFIX}${id}`);
      if (timerRef.current) clearInterval(timerRef.current);
      setResult(res);
      setAssignment(res);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Failed to submit. Please try again.';
      setSubmitError(msg);
    } finally {
      setSubmitting(false);
      setShowConfirm(false);
    }
  };

  const answeredCount = answers.filter(a => a !== null).length;
  const questions: QuestionItem[] = assignment?.questions ?? [];
  const currentQuestion = questions[currentQ];
  const isTimeLow = timeLeft !== null && timeLeft <= 120; // 2 min warning

  if (loading) {
    return (
      <DashboardLayout>
        <div className="exam-loading">Loading exam…</div>
      </DashboardLayout>
    );
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="exam-error-page">
          <p className="exam-error-msg">{error}</p>
          <button className="exam-back-btn" onClick={() => navigate('/dashboard')}>
            Back to Dashboard
          </button>
        </div>
      </DashboardLayout>
    );
  }

  // Result / review screen
  if (result) {
    const qs = result.questions ?? [];
    const submittedAnswers = result.answers ?? [];
    const correct = qs.filter((q, i) => submittedAnswers[i] === q.correct_index).length;
    const pct = result.score ?? 0;

    return (
      <DashboardLayout>
        <div className="exam-result-page">
          <div className="exam-result-header">
            <h1 className="exam-result-title">{result.exam_title}</h1>
            <div className={`exam-score-badge ${pct >= 70 ? 'pass' : 'fail'}`}>
              {pct.toFixed(0)}%
            </div>
            <p className="exam-result-meta">
              {correct}/{qs.length} correct
              {result.time_taken_seconds !== null && (
                <> &middot; {Math.floor((result.time_taken_seconds ?? 0) / 60)}m {(result.time_taken_seconds ?? 0) % 60}s</>
              )}
            </p>
          </div>

          <div className="exam-result-review">
            {qs.map((q, i) => {
              const chosen = submittedAnswers[i];
              const isCorrect = chosen === q.correct_index;
              return (
                <div key={i} className={`exam-result-q ${isCorrect ? 'correct' : 'wrong'}`}>
                  <div className="exam-result-q-header">
                    <span className="exam-result-q-num">Q{i + 1}</span>
                    <span className={`exam-result-q-status ${isCorrect ? 'correct' : 'wrong'}`}>
                      {isCorrect ? '✓ Correct' : '✗ Wrong'}
                    </span>
                  </div>
                  <p className="exam-result-q-text">{q.question}</p>
                  <div className="exam-result-options">
                    {q.options?.map((opt, oi) => (
                      <div
                        key={oi}
                        className={`exam-result-option ${
                          oi === q.correct_index ? 'correct-opt' : ''
                        } ${chosen === oi && oi !== q.correct_index ? 'wrong-opt' : ''}`}
                      >
                        <span className="exam-opt-label">{String.fromCharCode(65 + oi)}</span>
                        {opt}
                        {oi === q.correct_index && <span className="exam-opt-check"> ✓</span>}
                        {chosen === oi && oi !== q.correct_index && <span className="exam-opt-x"> ✗</span>}
                      </div>
                    ))}
                  </div>
                  {q.explanation && (
                    <div className="exam-result-explanation">
                      <strong>Explanation:</strong> {q.explanation}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="exam-result-actions">
            <button className="exam-back-btn" onClick={() => navigate('/dashboard')}>
              Back to Dashboard
            </button>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="exam-page">
        {/* Header with timer */}
        <div className="exam-header">
          <div className="exam-header-left">
            <h1 className="exam-title">{assignment?.exam_title}</h1>
            <span className="exam-course">{assignment?.course_name}</span>
          </div>
          <div className={`exam-timer ${isTimeLow ? 'low' : ''}`}>
            <span className="exam-timer-icon">&#9201;</span>
            {timeLeft !== null ? formatTime(timeLeft) : '--:--'}
          </div>
        </div>

        {/* Progress bar */}
        <div className="exam-progress-bar">
          <div
            className="exam-progress-fill"
            style={{ width: `${questions.length > 0 ? ((currentQ + 1) / questions.length) * 100 : 0}%` }}
          />
        </div>

        <div className="exam-body">
          {/* Question panel */}
          <div className="exam-question-panel">
            <div className="exam-q-meta">
              Question {currentQ + 1} of {questions.length}
            </div>
            {currentQuestion ? (
              <>
                <p className="exam-q-text">{currentQuestion.question}</p>
                <div className="exam-options">
                  {currentQuestion.options?.map((opt, oi) => (
                    <button
                      key={oi}
                      type="button"
                      className={`exam-option-btn ${answers[currentQ] === oi ? 'selected' : ''}`}
                      onClick={() => handleSelectAnswer(oi)}
                    >
                      <span className="exam-opt-label-btn">{String.fromCharCode(65 + oi)}</span>
                      <span className="exam-opt-text">{opt}</span>
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <p className="exam-empty">No question data.</p>
            )}

            {/* Navigation */}
            <div className="exam-nav-btns">
              <button
                className="exam-nav-btn"
                onClick={() => setCurrentQ(q => Math.max(0, q - 1))}
                disabled={currentQ === 0}
              >
                &#8592; Previous
              </button>
              {currentQ < questions.length - 1 ? (
                <button
                  className="exam-nav-btn exam-nav-next"
                  onClick={() => setCurrentQ(q => Math.min(questions.length - 1, q + 1))}
                >
                  Next &#8594;
                </button>
              ) : (
                <button
                  className="exam-submit-btn"
                  onClick={() => setShowConfirm(true)}
                >
                  Submit Exam
                </button>
              )}
            </div>
          </div>

          {/* Question navigator sidebar */}
          <div className="exam-sidebar">
            <div className="exam-sidebar-header">
              Questions ({answeredCount}/{questions.length} answered)
            </div>
            <div className="exam-q-grid">
              {questions.map((_, i) => (
                <button
                  key={i}
                  type="button"
                  className={`exam-q-dot ${currentQ === i ? 'active' : ''} ${answers[i] !== null ? 'answered' : ''}`}
                  onClick={() => setCurrentQ(i)}
                  title={`Question ${i + 1}${answers[i] !== null ? ' (answered)' : ' (unanswered)'}`}
                >
                  {i + 1}
                </button>
              ))}
            </div>
            <button
              className="exam-submit-sidebar-btn"
              onClick={() => setShowConfirm(true)}
            >
              Submit Exam
            </button>
          </div>
        </div>
      </div>

      {/* Confirm submit modal */}
      {showConfirm && (
        <div className="exam-confirm-overlay" role="dialog" aria-modal="true">
          <div className="exam-confirm-modal">
            <h2 className="exam-confirm-title">Submit Exam?</h2>
            <p className="exam-confirm-body">
              You have answered <strong>{answeredCount}</strong> of <strong>{questions.length}</strong> questions.
              {answeredCount < questions.length && (
                <> Unanswered questions will be marked wrong.</>
              )}
            </p>
            {submitError && <p className="exam-confirm-error">{submitError}</p>}
            <div className="exam-confirm-actions">
              <button
                className="exam-confirm-cancel"
                onClick={() => setShowConfirm(false)}
                disabled={submitting}
              >
                Go Back
              </button>
              <button
                className="exam-confirm-submit"
                onClick={handleSubmit}
                disabled={submitting}
              >
                {submitting ? 'Submitting…' : 'Submit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

export default ExamPage;
