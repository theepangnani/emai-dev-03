/**
 * Fill-in-the-Blank answer card — CB-ILE-001 M2 (#3208)
 *
 * Text input for typed answers (no MCQ options).
 */
import { useState, useRef, useEffect } from 'react';
import './FillBlankCard.css';

interface FillBlankCardProps {
  question: string;
  onSubmit: (answer: string) => void;
  disabled: boolean;
}

export function FillBlankCard({ question, onSubmit, disabled }: FillBlankCardProps) {
  const [answer, setAnswer] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset answer and focus input when question changes
  useEffect(() => {
    setAnswer(''); // eslint-disable-line react-hooks/set-state-in-effect -- intentional reset on question change
    if (!disabled) {
      inputRef.current?.focus();
    }
  }, [question, disabled]);

  const handleSubmit = () => {
    const trimmed = answer.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="fts-fill-blank">
      <input
        ref={inputRef}
        type="text"
        className="fts-fill-blank-input"
        placeholder="Type your answer..."
        value={answer}
        onChange={e => setAnswer(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        autoComplete="off"
        spellCheck={false}
      />
      <button
        className="fts-btn fts-btn-primary fts-fill-blank-submit"
        onClick={handleSubmit}
        disabled={disabled || !answer.trim()}
      >
        Submit Answer
      </button>
    </div>
  );
}
