/**
 * ExplanationBubble — Teal/amber explanation shown when a question is resolved.
 * CB-ILE-001 M1
 */
import './ile-components.css';

interface ExplanationBubbleProps {
  explanation: string;
  isCorrect: boolean;
  isAutoRevealed: boolean;
}

export function ExplanationBubble({ explanation, isCorrect, isAutoRevealed }: ExplanationBubbleProps) {
  const variant = isCorrect && !isAutoRevealed ? 'correct' : 'auto-reveal';

  return (
    <div className={`ile-explanation-bubble ile-explanation-${variant}`}>
      <span className="ile-bubble-label ile-explanation-label">
        {isCorrect && !isAutoRevealed ? '\u2713 Why Correct' : "\uD83D\uDCD6 Let's look at this together"}
      </span>
      <p>{explanation}</p>
    </div>
  );
}
