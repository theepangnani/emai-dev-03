/**
 * HintBubble — Amber-bordered hint shown on wrong answers in Learning Mode.
 * CB-ILE-001 M1
 */
import './ile-components.css';

interface HintBubbleProps {
  hint: string;
  attemptNumber: number;
}

export function HintBubble({ hint, attemptNumber }: HintBubbleProps) {
  return (
    <div className="ile-hint-bubble" data-attempt={attemptNumber}>
      <span className="ile-bubble-label ile-hint-label">Hint</span>
      <p>{hint}</p>
    </div>
  );
}
