import { useCallback, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { howItWorksSteps } from './howItWorks';
import './HowItWorksAccordion.css';

/**
 * CB-LAND-001 §6.136.1 §5 — S6 How It Works.
 *
 * Left: 4-row accordion, active row gets cyan left-border + elevation,
 *       inactive rows collapse to a one-line summary.
 * Right: preview pane cross-fades between 4 mockups tied to the active step.
 *
 * Keyboard (WAI-ARIA Accordion pattern):
 *   ArrowDown / ArrowUp — cycle active step
 *   Home / End          — jump to first / last
 *   Enter / Space       — activate focused step
 *
 * Reduced motion handled via CSS tokens (index.css zeroes spring durations
 * under `prefers-reduced-motion: reduce`), so the cross-fade becomes an
 * instant swap automatically.
 */
export function HowItWorksAccordion() {
  const [activeIdx, setActiveIdx] = useState(0);
  const rowRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const focusRow = useCallback((idx: number) => {
    const next = rowRefs.current[idx];
    if (next) next.focus();
  }, []);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLButtonElement>, idx: number) => {
      const last = howItWorksSteps.length - 1;
      switch (e.key) {
        case 'ArrowDown': {
          e.preventDefault();
          const next = idx === last ? 0 : idx + 1;
          setActiveIdx(next);
          focusRow(next);
          break;
        }
        case 'ArrowUp': {
          e.preventDefault();
          const next = idx === 0 ? last : idx - 1;
          setActiveIdx(next);
          focusRow(next);
          break;
        }
        case 'Home': {
          e.preventDefault();
          setActiveIdx(0);
          focusRow(0);
          break;
        }
        case 'End': {
          e.preventDefault();
          setActiveIdx(last);
          focusRow(last);
          break;
        }
        case 'Enter':
        case ' ': {
          e.preventDefault();
          setActiveIdx(idx);
          break;
        }
      }
    },
    [focusRow],
  );

  return (
    <section
      data-landing="v2"
      className="landing-how"
      aria-labelledby="landing-how-heading"
    >
      <div className="landing-how__container">
        <h2
          id="landing-how-heading"
          className="landing-how__headline"
          /* Headline copy is authored per spec; safe literal string. */
          dangerouslySetInnerHTML={{
            __html: 'From chaos to clarity in <em>4 steps.</em>',
          }}
        />

        <div className="landing-how__grid">
          <div className="landing-how__accordion" role="presentation">
            {howItWorksSteps.map((step, idx) => {
              const expanded = idx === activeIdx;
              const rowId = `landing-how-row-${step.id}`;
              const panelId = `landing-how-panel-${step.id}`;
              return (
                <button
                  key={step.id}
                  id={rowId}
                  ref={(el) => {
                    rowRefs.current[idx] = el;
                  }}
                  type="button"
                  className="landing-how__row"
                  aria-expanded={expanded}
                  aria-controls={panelId}
                  onClick={() => setActiveIdx(idx)}
                  onKeyDown={(e) => handleKeyDown(e, idx)}
                >
                  <span className="landing-how__row-header">
                    <span className="landing-how__row-num" aria-hidden="true">
                      {step.number}.
                    </span>
                    <span className="landing-how__row-title">{step.title}</span>
                  </span>
                  {!expanded && (
                    <p className="landing-how__row-summary">{step.summary}</p>
                  )}
                  <div
                    id={panelId}
                    role="region"
                    aria-labelledby={rowId}
                    className="landing-how__row-body"
                  >
                    {step.body}
                  </div>
                </button>
              );
            })}
          </div>

          <div
            className="landing-how__preview"
            aria-live="polite"
            aria-atomic="true"
          >
            {howItWorksSteps.map((step, idx) => (
              <div
                key={step.id}
                className="landing-how__preview-slide"
                data-step={step.id}
                data-active={idx === activeIdx}
                aria-hidden={idx !== activeIdx}
              >
                <div className="landing-how__preview-mock">{step.previewLabel}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export const section = {
  id: 'how',
  order: 40,
  component: HowItWorksAccordion,
} as const;
