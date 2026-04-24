/**
 * CycleFeedback — renders the beat after a user answers (CB-TUTOR-002 #4069).
 *
 * Three visual states:
 *   - correct → "Here's why:" + explanation + XP ticker
 *   - wrong + attempts left → re-teach snippet + "Try again" CTA
 *   - wrong + 3rd attempt   → reveal answer + "Moving on" CTA
 *
 * The XP ticker uses a CSS counter-up animation (no Motion library; we
 * build without adding a new dependency). The Fraunces-style heading
 * treatment is driven by the `cycle-feedback__heading` class in CSS.
 *
 * Shell-only — parent drives state transitions.
 */
import { useEffect, useState } from 'react';
import type { CycleQuestion } from './types';

export type CycleFeedbackVerdict = 'correct' | 'retry' | 'reveal';

export interface CycleFeedbackProps {
  verdict: CycleFeedbackVerdict;
  question: CycleQuestion;
  /** XP earned on this question (visible only when verdict='correct'). */
  xp?: number;
  /** Fired when the user wants to continue (next question / re-try / move on). */
  onContinue: () => void;
}

function TickingXp({ target }: { target: number }) {
  const [displayed, setDisplayed] = useState(0);
  useEffect(() => {
    if (target <= 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional reset when target changes
      setDisplayed(0);
      return;
    }
    const duration = 600;
    const startedAt = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - startedAt) / duration);
      // Ease-out cubic for a satisfying tick.
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplayed(Math.round(target * eased));
      if (t < 1) raf = window.requestAnimationFrame(step);
    };
    raf = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(raf);
  }, [target]);
  return (
    <span className="cycle-feedback__xp" aria-live="polite">
      +{displayed} XP
    </span>
  );
}

export function CycleFeedback({
  verdict,
  question,
  xp = 0,
  onContinue,
}: CycleFeedbackProps) {
  if (verdict === 'correct') {
    return (
      <section
        className="cycle-feedback cycle-feedback--correct"
        role="status"
        aria-live="polite"
      >
        <div className="cycle-feedback__badge">
          <span className="cycle-feedback__check" aria-hidden="true">
            ✓
          </span>
          <span>Nice one!</span>
        </div>
        <h3 className="cycle-feedback__heading">Here&apos;s why:</h3>
        <p className="cycle-feedback__explanation">{question.explanation}</p>
        <div className="cycle-feedback__footer">
          <TickingXp target={xp} />
          <button
            type="button"
            className="cycle-cta cycle-cta--primary"
            onClick={onContinue}
          >
            Next question
          </button>
        </div>
      </section>
    );
  }

  if (verdict === 'retry') {
    return (
      <section
        className="cycle-feedback cycle-feedback--retry"
        role="status"
        aria-live="polite"
      >
        <div className="cycle-feedback__badge cycle-feedback__badge--warn">
          <span className="cycle-feedback__cross" aria-hidden="true">
            ·
          </span>
          <span>Not quite — here&apos;s a nudge</span>
        </div>
        <h3 className="cycle-feedback__heading">Remember:</h3>
        <p className="cycle-feedback__reteach">{question.reteach_snippet}</p>
        <div className="cycle-feedback__footer">
          <button
            type="button"
            className="cycle-cta cycle-cta--primary"
            onClick={onContinue}
          >
            Try again
          </button>
        </div>
      </section>
    );
  }

  // verdict === 'reveal'
  const correctAnswer = question.options[question.correct_index] ?? '';
  return (
    <section
      className="cycle-feedback cycle-feedback--reveal"
      role="status"
      aria-live="polite"
    >
      <div className="cycle-feedback__badge cycle-feedback__badge--reveal">
        <span>Let&apos;s move on — we&apos;ll revisit this</span>
      </div>
      <h3 className="cycle-feedback__heading">The answer was:</h3>
      <p className="cycle-feedback__reveal-answer">{correctAnswer}</p>
      <p className="cycle-feedback__explanation">{question.explanation}</p>
      <div className="cycle-feedback__footer">
        <button
          type="button"
          className="cycle-cta cycle-cta--secondary"
          onClick={onContinue}
        >
          Moving on
        </button>
      </div>
    </section>
  );
}

export default CycleFeedback;
