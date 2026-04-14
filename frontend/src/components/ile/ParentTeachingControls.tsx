/**
 * ParentTeachingControls — Controls shown during Parent Teaching Mode sessions.
 * CB-ILE-001 M3 (#3212)
 *
 * - Text input for adding a personal hint before AI hint
 * - Flag question button for later review
 */
import { useState } from 'react';
import './ile-components.css';

interface ParentTeachingControlsProps {
  childName: string;
  onSubmitHint: (hint: string) => void;
  currentHint: string | null;
  disabled?: boolean;
}

export function ParentTeachingControls({
  childName,
  onSubmitHint,
  currentHint,
  disabled = false,
}: ParentTeachingControlsProps) {
  const [hintText, setHintText] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => {
    if (!hintText.trim()) return;
    onSubmitHint(hintText.trim());
    setSubmitted(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Reset when hint is cleared (new question)
  if (!currentHint && submitted) {
    setSubmitted(false);
    setHintText('');
  }

  return (
    <div className="ile-parent-controls">
      <div className="ile-parent-controls-header">
        <span className="ile-parent-controls-label">Parent Teaching Mode</span>
      </div>

      {currentHint ? (
        <div className="ile-parent-hint-display" role="status" aria-label="Your hint">
          <span className="ile-bubble-label ile-parent-hint-label">Your Hint</span>
          <p>{currentHint}</p>
        </div>
      ) : (
        <div className="ile-parent-hint-input">
          <label htmlFor="parent-hint-input" className="ile-parent-hint-prompt">
            Add your own hint for {childName}
          </label>
          <div className="ile-parent-hint-row">
            <input
              id="parent-hint-input"
              type="text"
              value={hintText}
              onChange={e => setHintText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g., Remember what we talked about at dinner..."
              maxLength={500}
              disabled={disabled}
              className="ile-parent-hint-field"
            />
            <button
              className="ile-parent-hint-btn"
              onClick={handleSubmit}
              disabled={disabled || !hintText.trim()}
            >
              Add Hint
            </button>
          </div>
          <span className="ile-parent-hint-note">
            This hint will show before the AI hint if they answer incorrectly
          </span>
        </div>
      )}
    </div>
  );
}
