/**
 * Flash Tutor Session — CB-ILE-001
 *
 * Active quiz session with Learning Mode hints/explanations
 * and Testing Mode simple progression.
 */
import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ileApi } from '../api/ile';
import type { ILECurrentQuestion, ILEAnswerFeedback, ILESessionResults, ILESession } from '../api/ile';
import { DashboardLayout } from '../components/DashboardLayout';
import { HintBubble } from '../components/ile/HintBubble';
import { ExplanationBubble } from '../components/ile/ExplanationBubble';
import { XpPopBadge } from '../components/ile/XpPopBadge';
import { StreakCounter } from '../components/ile/StreakCounter';
import './FlashTutorSessionPage.css';

type Phase = 'question' | 'feedback' | 'results' | 'loading' | 'error';

export function FlashTutorSessionPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const sessionId = parseInt(id || '0');

  const [phase, setPhase] = useState<Phase>('loading');
  const [session, setSession] = useState<ILESession | null>(null);
  const [currentQ, setCurrentQ] = useState<ILECurrentQuestion | null>(null);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<ILEAnswerFeedback | null>(null);
  const [results, setResults] = useState<ILESessionResults | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streak, setStreak] = useState(0);
  const [streakBroken, setStreakBroken] = useState(false);
  const [sessionXp, setSessionXp] = useState(0);
  const [startTime, setStartTime] = useState<number>(0);

  const loadQuestion = useCallback(async () => {
    try {
      setPhase('loading');
      const [sess, q] = await Promise.all([
        ileApi.getSession(sessionId),
        ileApi.getCurrentQuestion(sessionId),
      ]);
      setSession(sess);
      setCurrentQ(q);
      setSelectedAnswer(null);
      setFeedback(null);
      setStartTime(Date.now());
      setPhase('question');
    } catch {
      // Session might be completed
      try {
        const sess = await ileApi.getSession(sessionId);
        if (sess.status === 'completed') {
          const res = await ileApi.getSessionResults(sessionId);
          setResults(res);
          setPhase('results');
          return;
        }
      } catch { /* ignore — fallthrough to error state */ }
      setError('Failed to load question');
      setPhase('error');
    }
  }, [sessionId]);

  // Load session and first question
  useEffect(() => {
    if (!sessionId) return;
    loadQuestion();
  }, [sessionId, loadQuestion]);

  const handleSelectAnswer = (answer: string) => {
    if (submitting || phase !== 'question') return;
    // In Learning Mode, don't allow re-selecting disabled options
    if (currentQ?.disabled_options.includes(answer)) return;
    setSelectedAnswer(answer);
  };

  const handleSubmit = async () => {
    if (!selectedAnswer || submitting || !currentQ) return;
    setSubmitting(true);

    try {
      const timeTaken = Date.now() - startTime;
      const fb = await ileApi.submitAnswer(sessionId, selectedAnswer, timeTaken);
      setFeedback(fb);
      setSessionXp(prev => prev + fb.xp_earned);

      setStreakBroken(false);
      if (fb.is_correct && fb.attempt_number === 1) {
        setStreak(prev => prev + 1);
      } else if (fb.streak_broken) {
        setStreakBroken(true);
        setStreak(0);
      }

      if (session?.mode === 'testing') {
        // Testing Mode: auto-advance
        if (fb.session_complete) {
          await handleComplete();
        } else {
          await loadQuestion();
        }
      } else {
        // Learning Mode: show feedback
        setPhase('feedback');
      }
    } catch {
      setError('Failed to submit answer');
    } finally {
      setSubmitting(false);
    }
  };

  const handleNext = async () => {
    if (feedback?.session_complete) {
      await handleComplete();
    } else {
      if (feedback?.question_complete) {
        await loadQuestion();
      } else {
        // Wrong answer in learning mode — stay on same question, add disabled option
        if (currentQ && selectedAnswer) {
          setCurrentQ({
            ...currentQ,
            disabled_options: [...currentQ.disabled_options, selectedAnswer],
            attempt_number: (feedback?.attempt_number ?? currentQ.attempt_number) + 1,
          });
        }
        setSelectedAnswer(null);
        setFeedback(null);
        setStartTime(Date.now());
        setPhase('question');
      }
    }
  };

  const handleComplete = async () => {
    try {
      const res = await ileApi.completeSession(sessionId);
      setResults(res);
      setPhase('results');
    } catch {
      // Already completed — fetch results
      try {
        const res = await ileApi.getSessionResults(sessionId);
        setResults(res);
        setPhase('results');
      } catch {
        setError('Failed to load results');
        setPhase('error');
      }
    }
  };

  const handleAbandon = async () => {
    try {
      await ileApi.abandonSession(sessionId);
      navigate('/flash-tutor');
    } catch {
      navigate('/flash-tutor');
    }
  };

  // --- Render ---

  if (phase === 'loading') {
    return (
      <DashboardLayout showBackButton headerSlot={() => null}>
        <div className="fts-page">
          <div className="fts-loading">
            <div className="fts-spinner" />
            <p>Loading question...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (phase === 'error') {
    return (
      <DashboardLayout showBackButton headerSlot={() => null}>
        <div className="fts-page">
          <div className="fts-error-card">
            <p>{error || 'Something went wrong'}</p>
            <button className="fts-btn fts-btn-secondary" onClick={() => navigate('/flash-tutor')}>
              Back to Flash Tutor
            </button>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (phase === 'results' && results) {
    return (
      <DashboardLayout showBackButton headerSlot={() => null}>
        <div className="fts-page">
          <div className="fts-results">
            <div className="fts-results-header">
              <h1>Session Complete!</h1>
              <div className="fts-score-circle">
                <span className="fts-score-pct">{results.percentage}%</span>
                <span className="fts-score-fraction">{results.score}/{results.total_questions}</span>
              </div>
              <div className="fts-results-meta">
                <span className="fts-tag">{results.mode === 'learning' ? '📖 Learning' : '📝 Testing'}</span>
                <span className="fts-tag">{results.subject} — {results.topic}</span>
              </div>
              <div className="fts-xp-earned">+{results.total_xp} XP</div>
            </div>

            <div className="fts-results-breakdown">
              <h2>Question Breakdown</h2>
              {results.questions.map(q => (
                <div key={q.index} className={`fts-result-row ${q.is_correct ? 'correct' : 'incorrect'}`}>
                  <span className="fts-result-icon">{q.is_correct ? '✓' : '✗'}</span>
                  <span className="fts-result-q">{q.question}</span>
                  <span className="fts-result-attempts">
                    {q.attempts > 1 ? `${q.attempts} attempts` : '1st try'}
                  </span>
                  <span className="fts-result-xp">+{q.xp_earned} XP</span>
                </div>
              ))}
            </div>

            <div className="fts-results-actions">
              <button className="fts-btn fts-btn-primary" onClick={() => navigate('/flash-tutor')}>
                New Session
              </button>
              <button className="fts-btn fts-btn-secondary" onClick={() => navigate('/dashboard')}>
                Back to Dashboard
              </button>
            </div>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  // Question / Feedback phase
  if (!currentQ) return null;

  const q = currentQ.question;
  const progressPct = ((currentQ.question_index) / currentQ.total_questions) * 100;

  return (
    <DashboardLayout showBackButton headerSlot={() => null}>
      <div className="fts-page">
        {/* Header bar */}
        <div className="fts-session-header">
          <div className="fts-progress-bar">
            <div className="fts-progress-fill" style={{ width: `${progressPct}%` }} />
          </div>
          <div className="fts-header-info">
            <span className="fts-q-counter">
              {currentQ.question_index + 1} / {currentQ.total_questions}
            </span>
            <span className="fts-mode-tag">
              {session?.mode === 'learning' ? '📖 Learning' : '📝 Testing'}
            </span>
            <StreakCounter count={streak} broken={streakBroken} />
            <span className="fts-xp-counter">⭐ {sessionXp} XP</span>
            <button className="fts-abandon-btn" onClick={handleAbandon} title="Exit session">
              ✕
            </button>
          </div>
        </div>

        {/* Question card */}
        <div className="fts-question-card">
          <div className="fts-difficulty-tag">{q.difficulty}</div>
          <p className="fts-question-text">{q.question}</p>

          {currentQ.attempt_number > 1 && session?.mode === 'learning' && (
            <div className="fts-attempt-label">
              Attempt {currentQ.attempt_number} — try again
            </div>
          )}

          {/* MCQ Options */}
          {q.options && (
            <div className="fts-options">
              {(Object.entries(q.options) as [string, string][]).map(([key, text]) => {
                const isDisabled = currentQ.disabled_options.includes(key);
                const isSelected = selectedAnswer === key;
                const isCorrectReveal = phase === 'feedback' && feedback?.correct_answer === key;
                const isWrongReveal = phase === 'feedback' && feedback && !feedback.is_correct && isSelected;

                let className = 'fts-option';
                if (isDisabled) className += ' disabled';
                if (isSelected && phase === 'question') className += ' selected';
                if (isCorrectReveal && feedback?.question_complete) className += ' correct';
                if (isWrongReveal) className += ' wrong';

                return (
                  <button
                    key={key}
                    className={className}
                    onClick={() => handleSelectAnswer(key)}
                    disabled={isDisabled || phase === 'feedback'}
                  >
                    <span className="fts-option-key">{key}</span>
                    <span className="fts-option-text">{text}</span>
                    {isDisabled && <span className="fts-option-x">✗</span>}
                    {isCorrectReveal && feedback?.question_complete && <span className="fts-option-check">✓</span>}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Feedback bubbles (Learning Mode) */}
        {phase === 'feedback' && feedback && (
          <div className="fts-feedback">
            {feedback.hint && !feedback.question_complete && (
              <HintBubble hint={feedback.hint} attemptNumber={feedback.attempt_number} />
            )}

            {feedback.explanation && feedback.question_complete && (
              <ExplanationBubble
                explanation={feedback.explanation}
                isCorrect={feedback.is_correct}
                isAutoRevealed={!feedback.is_correct}
              />
            )}

            {feedback.xp_earned > 0 && (
              <XpPopBadge xp={feedback.xp_earned} isFirstTry={feedback.attempt_number === 1} />
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="fts-actions">
          {phase === 'question' && (
            <button
              className="fts-btn fts-btn-primary"
              onClick={handleSubmit}
              disabled={!selectedAnswer || submitting}
            >
              {submitting ? 'Submitting...' : 'Submit Answer'}
            </button>
          )}

          {phase === 'feedback' && (
            <button className="fts-btn fts-btn-primary" onClick={handleNext}>
              {feedback?.session_complete
                ? 'See Results'
                : feedback?.question_complete
                  ? 'Next Question →'
                  : 'Try Again'}
            </button>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
