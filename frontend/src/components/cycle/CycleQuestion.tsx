/**
 * CycleQuestion — renders a single question of a Learning Cycle chunk
 * (CB-TUTOR-002 #4069).
 *
 * Branches on `question.format`:
 *   - multiple_choice → A/B/C/D option buttons
 *   - true_false      → two large True/False buttons
 *   - fill_blank      → text input + submit
 *
 * Rendering logic follows the ASGFQuizBridge shape so visual parity is
 * maintained. Handles the 3-try loop: after each wrong attempt the parent
 * decides whether to show the re-teach snippet, try again, or reveal.
 *
 * Shell-only — the submit callback receives raw answer data; scoring/XP/
 * attempt-persistence is the parent's job (and will wire to backend in the
 * route PR).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { CycleQuestion as CycleQuestionType } from './types';

const OPTION_LETTERS = ['A', 'B', 'C', 'D'];

export interface CycleQuestionProps {
  question: CycleQuestionType;
  /** Attempt index, 0-based. 0 = first try, max = 2 (3rd attempt). */
  attempt: number;
  /** Max attempts before forced reveal (hard-coded to 3 upstream). */
  maxAttempts?: number;
  /** Called with the user's answer. Shape differs by format. */
  onAnswer: (payload: { index?: number; text?: string }) => void;
  /** Disable inputs when feedback is being shown. */
  locked?: boolean;
}

const normalize = (s: string): string =>
  s
    .toLowerCase()
    .replace(/[^\w\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

export function CycleQuestion({
  question,
  attempt,
  maxAttempts = 3,
  onAnswer,
  locked = false,
}: CycleQuestionProps) {
  const [fillDraft, setFillDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // Re-focus the fill-blank input when the attempt changes (user retries).
  useEffect(() => {
    if (question.format === 'fill_blank') {
      inputRef.current?.focus();
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional reset on question/attempt change
      setFillDraft('');
    }
  }, [question.id, attempt, question.format]);

  const handleOptionClick = useCallback(
    (i: number) => {
      if (locked) return;
      onAnswer({ index: i });
    },
    [locked, onAnswer],
  );

  const handleFillSubmit = useCallback(() => {
    if (locked) return;
    const trimmed = fillDraft.trim();
    if (!trimmed) return;
    onAnswer({ text: trimmed });
  }, [locked, fillDraft, onAnswer]);

  // Shared check for fill_blank styling (purely visual — real verdict is
  // decided by the parent after onAnswer).
  const fillPreviewCorrect = (() => {
    if (question.format !== 'fill_blank') return null;
    const canonical = question.options[question.correct_index] ?? '';
    if (!fillDraft.trim() || !canonical) return null;
    return normalize(fillDraft) === normalize(canonical);
  })();

  return (
    <div className="cycle-question" data-format={question.format}>
      <div className="cycle-question__header">
        <span className="cycle-question__attempt">
          Attempt {Math.min(attempt + 1, maxAttempts)} of {maxAttempts}
        </span>
        <span className="cycle-question__format-chip">
          {question.format === 'multiple_choice' && 'Multiple choice'}
          {question.format === 'true_false' && 'True or False'}
          {question.format === 'fill_blank' && 'Fill the blank'}
        </span>
      </div>

      <p className="cycle-question__prompt">{question.question_text}</p>

      {question.format === 'multiple_choice' && (
        <div
          className="cycle-question__options"
          role="radiogroup"
          aria-label="Answer options"
        >
          {question.options.map((option, i) => (
            <button
              key={i}
              type="button"
              className="cycle-option"
              role="radio"
              aria-checked={false}
              aria-label={`Option ${OPTION_LETTERS[i]}: ${option}`}
              disabled={locked}
              onClick={() => handleOptionClick(i)}
            >
              <span className="cycle-option__letter" aria-hidden="true">
                {OPTION_LETTERS[i]}
              </span>
              <span className="cycle-option__text">{option}</span>
            </button>
          ))}
        </div>
      )}

      {question.format === 'true_false' && (
        <div
          className="cycle-question__options cycle-question__options--tf"
          role="radiogroup"
          aria-label="True or False"
        >
          {(question.options.length >= 2
            ? question.options.slice(0, 2)
            : ['True', 'False']
          ).map((option, i) => (
            <button
              key={i}
              type="button"
              className="cycle-option cycle-option--tf"
              role="radio"
              aria-checked={false}
              aria-label={option}
              disabled={locked}
              onClick={() => handleOptionClick(i)}
            >
              {option}
            </button>
          ))}
        </div>
      )}

      {question.format === 'fill_blank' && (
        <div className="cycle-question__fill">
          <label htmlFor={`cycle-fill-${question.id}`} className="cycle-question__fill-label">
            Your answer
          </label>
          <input
            id={`cycle-fill-${question.id}`}
            ref={inputRef}
            type="text"
            className="cycle-question__fill-input"
            placeholder="Type your answer..."
            value={fillDraft}
            onChange={(e) => setFillDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleFillSubmit();
              }
            }}
            disabled={locked}
            autoComplete="off"
            spellCheck={false}
            maxLength={200}
            aria-describedby={`cycle-fill-${question.id}-hint`}
            data-preview-correct={fillPreviewCorrect ?? undefined}
          />
          <span
            id={`cycle-fill-${question.id}-hint`}
            className="cycle-visually-hidden"
          >
            Type your answer and press Enter or click Submit
          </span>
          <button
            type="button"
            className="cycle-cta cycle-cta--primary cycle-question__fill-submit"
            onClick={handleFillSubmit}
            disabled={locked || !fillDraft.trim()}
          >
            Submit answer
          </button>
        </div>
      )}
    </div>
  );
}

export default CycleQuestion;
