/**
 * ASGFQuizBridge — Slide-anchored quiz after ASGF mini-lesson.
 * CB-ASGF-001 M5c (#3400)
 *
 * Renders quiz questions with:
 *  - Hint bubble on wrong answer (referencing specific slide)
 *  - Explanation bubble on correct answer
 *  - XP display tiered by attempt: 30/15/8/3/0
 *  - Results summary at the end
 *
 * Supports three question formats (#4020):
 *  - multiple_choice (default): A/B/C/D buttons
 *  - true_false: two large True / False buttons
 *  - fill_blank / short_answer: text input + submit
 */
import { useState, useCallback, useEffect, useRef } from 'react';
import type { ASGFQuizQuestion } from '../../api/asgf';
import './ASGFQuizBridge.css';

/** XP awarded per attempt tier (display only — backend XP handled by ILE). */
const XP_TIERS = [30, 15, 8, 3, 0] as const;

function getXpForAttempt(attempt: number): number {
  if (attempt <= 0) return XP_TIERS[0];
  if (attempt >= XP_TIERS.length) return XP_TIERS[XP_TIERS.length - 1];
  return XP_TIERS[attempt - 1];
}

const OPTION_LETTERS = ['A', 'B', 'C', 'D'];

export interface ASGFQuizBridgeProps {
  questions: ASGFQuizQuestion[];
  sessionId: string;
  onComplete?: (results: QuizResults) => void;
}

export interface QuizResults {
  totalQuestions: number;
  correctFirstTry: number;
  totalAttempts: number;
  totalXp: number;
  /** Per-question breakdown */
  breakdown: {
    questionText: string;
    attempts: number;
    xp: number;
    correct: boolean;
  }[];
}

interface QuestionState {
  attempts: number;
  selectedIndex: number | null;
  isCorrect: boolean;
  showHint: boolean;
  wrongIndices: Set<number>;
  /** Last typed fill_blank answer (for display + matching). */
  typedAnswer: string;
}

export function ASGFQuizBridge({ questions, sessionId, onComplete }: ASGFQuizBridgeProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [questionStates, setQuestionStates] = useState<QuestionState[]>(
    () => questions.map(() => ({
      attempts: 0,
      selectedIndex: null,
      isCorrect: false,
      showHint: false,
      wrongIndices: new Set(),
      typedAnswer: '',
    })),
  );
  const [completed, setCompleted] = useState(false);
  const [fillBlankDraft, setFillBlankDraft] = useState('');
  const fillBlankInputRef = useRef<HTMLInputElement>(null);

  const question = questions[currentIndex];
  const state = questionStates[currentIndex];
  const format = question?.format ?? 'multiple_choice';

  // Reset typed-answer draft + focus fill-blank input on question change
  useEffect(() => {
    setFillBlankDraft(''); // eslint-disable-line react-hooks/set-state-in-effect -- intentional reset on question change
    if (format === 'fill_blank' || format === 'short_answer') {
      fillBlankInputRef.current?.focus();
    }
  }, [currentIndex, format]);

  const handleOptionClick = useCallback((optionIndex: number) => {
    if (!question || state.isCorrect) return;
    // Don't allow re-selecting a previously wrong option
    if (state.wrongIndices.has(optionIndex)) return;

    const isCorrect = optionIndex === question.correct_index;
    const newAttempts = state.attempts + 1;

    setQuestionStates((prev) => {
      const updated = [...prev];
      const newWrong = new Set(updated[currentIndex].wrongIndices);
      if (!isCorrect) {
        newWrong.add(optionIndex);
      }
      updated[currentIndex] = {
        ...updated[currentIndex],
        attempts: newAttempts,
        selectedIndex: optionIndex,
        isCorrect,
        showHint: !isCorrect,
        wrongIndices: newWrong,
      };
      return updated;
    });
  }, [question, state, currentIndex]);

  const handleFillBlankSubmit = useCallback(() => {
    if (!question || state.isCorrect) return;
    const trimmed = fillBlankDraft.trim();
    if (!trimmed) return;

    const canonical = question.options[question.correct_index] ?? '';
    const isCorrect = trimmed.toLowerCase() === canonical.trim().toLowerCase();
    const newAttempts = state.attempts + 1;

    setQuestionStates((prev) => {
      const updated = [...prev];
      updated[currentIndex] = {
        ...updated[currentIndex],
        attempts: newAttempts,
        selectedIndex: isCorrect ? question.correct_index : null,
        isCorrect,
        showHint: !isCorrect,
        typedAnswer: trimmed,
      };
      return updated;
    });
  }, [question, state, fillBlankDraft, currentIndex]);

  const handleNext = useCallback(() => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      // Calculate results
      const breakdown = questions.map((q, i) => {
        const qs = questionStates[i];
        return {
          questionText: q.question_text,
          attempts: qs.attempts,
          xp: getXpForAttempt(qs.attempts),
          correct: qs.isCorrect,
        };
      });

      const results: QuizResults = {
        totalQuestions: questions.length,
        correctFirstTry: breakdown.filter((b) => b.attempts === 1 && b.correct).length,
        totalAttempts: breakdown.reduce((sum, b) => sum + b.attempts, 0),
        totalXp: breakdown.reduce((sum, b) => sum + b.xp, 0),
        breakdown,
      };

      setCompleted(true);
      onComplete?.(results);
    }
  }, [currentIndex, questions, questionStates, onComplete]);

  // Results summary view
  if (completed) {
    const breakdown = questions.map((q, i) => {
      const qs = questionStates[i];
      return {
        questionText: q.question_text,
        attempts: qs.attempts,
        xp: getXpForAttempt(qs.attempts),
        correct: qs.isCorrect,
      };
    });
    const totalXp = breakdown.reduce((sum, b) => sum + b.xp, 0);
    const firstTryCount = breakdown.filter((b) => b.attempts === 1 && b.correct).length;

    return (
      <div className="asgf-quiz" data-session={sessionId}>
        <div className="asgf-quiz-results">
          <h3>Quiz Complete</h3>
          <div className="asgf-quiz-results-score">
            {firstTryCount}/{questions.length}
          </div>
          <p className="asgf-quiz-results-detail">
            correct on first try
          </p>
          <div className="asgf-quiz-results-xp">+{totalXp} XP</div>
          <div className="asgf-quiz-results-breakdown">
            {breakdown.map((item, i) => (
              <div className="asgf-quiz-results-item" key={i}>
                <span
                  className={`asgf-quiz-results-icon ${
                    item.correct
                      ? 'asgf-quiz-results-icon--correct'
                      : 'asgf-quiz-results-icon--wrong'
                  }`}
                  aria-hidden="true"
                >
                  {item.correct ? '✓' : '✗'}
                </span>
                <span>
                  Q{i + 1}: {item.attempts} attempt{item.attempts !== 1 ? 's' : ''} &mdash; +{item.xp} XP
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!question) return null;

  const xp = state.isCorrect ? getXpForAttempt(state.attempts) : null;

  const renderOptions = () => {
    if (format === 'true_false') {
      // Expect options to be ['True', 'False']. Fall back to first two entries.
      const tfOptions = question.options.length >= 2
        ? question.options.slice(0, 2)
        : ['True', 'False'];

      return (
        <div
          className="asgf-quiz-options question-tf-buttons"
          role="radiogroup"
          aria-label="True or False"
        >
          {tfOptions.map((option, i) => {
            let variant = '';
            if (state.isCorrect && i === question.correct_index) {
              variant = ' asgf-quiz-option--correct';
            } else if (state.wrongIndices.has(i)) {
              variant = ' asgf-quiz-option--wrong';
            } else if (!state.isCorrect && state.selectedIndex === i) {
              variant = ' asgf-quiz-option--selected';
            }

            return (
              <button
                key={i}
                className={`asgf-quiz-option asgf-quiz-option-tf${variant}`}
                onClick={() => handleOptionClick(i)}
                disabled={state.isCorrect || state.wrongIndices.has(i)}
                role="radio"
                aria-checked={state.selectedIndex === i}
                aria-label={option}
                type="button"
              >
                <span>{option}</span>
              </button>
            );
          })}
        </div>
      );
    }

    if (format === 'fill_blank' || format === 'short_answer') {
      const inputId = `asgf-quiz-fill-blank-${currentIndex}`;
      return (
        <div className="asgf-quiz-options question-fill-blank">
          <label htmlFor={inputId} className="asgf-quiz-fill-blank-label">
            Your answer
          </label>
          <input
            id={inputId}
            ref={fillBlankInputRef}
            type="text"
            className="asgf-quiz-fill-blank-input"
            placeholder="Type your answer..."
            value={fillBlankDraft}
            onChange={(e) => setFillBlankDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleFillBlankSubmit();
              }
            }}
            disabled={state.isCorrect}
            autoComplete="off"
            spellCheck={false}
            maxLength={500}
            aria-describedby={`${inputId}-hint`}
          />
          <span id={`${inputId}-hint`} className="asgf-quiz-visually-hidden">
            Type your answer and press Enter or click Submit
          </span>
          <button
            type="button"
            className="asgf-quiz-fill-blank-submit"
            onClick={handleFillBlankSubmit}
            disabled={state.isCorrect || !fillBlankDraft.trim()}
          >
            Submit Answer
          </button>
          {state.typedAnswer && (
            <div
              className={`asgf-quiz-typed-answer ${state.isCorrect ? 'correct' : 'wrong'}`}
              role="status"
            >
              Your answer: <strong>{state.typedAnswer}</strong>
              {state.isCorrect ? ' ✓' : ' ✗'}
            </div>
          )}
        </div>
      );
    }

    // Default: multiple_choice
    return (
      <div className="asgf-quiz-options" role="radiogroup" aria-label="Answer options">
        {question.options.map((option, i) => {
          let variant = '';
          if (state.isCorrect && i === question.correct_index) {
            variant = ' asgf-quiz-option--correct';
          } else if (state.wrongIndices.has(i)) {
            variant = ' asgf-quiz-option--wrong';
          } else if (!state.isCorrect && state.selectedIndex === i) {
            variant = ' asgf-quiz-option--selected';
          }

          return (
            <button
              key={i}
              className={`asgf-quiz-option${variant}`}
              onClick={() => handleOptionClick(i)}
              disabled={state.isCorrect || state.wrongIndices.has(i)}
              role="radio"
              aria-checked={state.selectedIndex === i}
              aria-label={`Option ${OPTION_LETTERS[i]}: ${option}`}
              type="button"
            >
              <span className="asgf-quiz-option-letter">{OPTION_LETTERS[i]}</span>
              <span>{option}</span>
            </button>
          );
        })}
      </div>
    );
  };

  return (
    <div className="asgf-quiz" data-session={sessionId}>
      <div className="asgf-quiz-card">
        {/* Header */}
        <div className="asgf-quiz-header">
          <span className="asgf-quiz-progress">
            Question {currentIndex + 1} of {questions.length}
          </span>
          <span className="asgf-quiz-bloom">{question.bloom_tier}</span>
        </div>

        {/* Question text */}
        <p className="asgf-quiz-question">{question.question_text}</p>

        {/* Options — MCQ, T/F, or fill_blank */}
        {renderOptions()}

        {/* Hint bubble (shown on wrong answer) */}
        {state.showHint && !state.isCorrect && (
          <div className="asgf-quiz-hint" role="status" aria-label={`Hint for attempt ${state.attempts}`}>
            <span className="asgf-quiz-hint-label">Hint</span>
            <p>{question.hint_text}</p>
          </div>
        )}

        {/* XP badge + explanation (shown on correct) */}
        {state.isCorrect && xp !== null && (
          <>
            <div className="asgf-quiz-xp" role="status" aria-live="polite">
              +{xp} XP{state.attempts === 1 ? ' — First try!' : ''}
            </div>
            <div className="asgf-quiz-explanation" role="status">
              <span className="asgf-quiz-explanation-label">Why correct</span>
              <p>{question.explanation}</p>
            </div>
            <button
              className="asgf-quiz-next"
              onClick={handleNext}
              type="button"
            >
              {currentIndex < questions.length - 1 ? 'Next Question' : 'See Results'}
              <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </>
        )}
      </div>
    </div>
  );
}
