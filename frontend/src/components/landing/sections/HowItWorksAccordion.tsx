import { useCallback, useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { howItWorksSteps } from './howItWorks';
import { emitStepView } from '../analytics';
import { useSectionViewTracker } from '../useSectionViewTracker';
import './HowItWorksAccordion.css';

/**
 * CB-LAND-001 §6.136.1 §5 — S6 How It Works.
 *
 * Left: 4-row accordion, active row gets cyan left-border + elevation,
 *       inactive rows collapse to a one-line summary.
 * Right: preview pane cross-fades between 4 mockups tied to the active step.
 *
 * Keyboard (WAI-ARIA Accordion pattern — panel is a sibling of the header
 * button, never nested inside the button):
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
  const sectionRef = useSectionViewTracker<HTMLElement>('how');

  // Fire `landing_v2.step_view` whenever the active step changes (including
  // the initial render — we track the first step the user sees expanded).
  useEffect(() => {
    const step = howItWorksSteps[activeIdx];
    if (step) emitStepView(step.number);
  }, [activeIdx]);

  const focusRow = useCallback((idx: number) => {
    const next = rowRefs.current[idx];
    if (next) next.focus();
  }, []);

  const activate = useCallback(
    (idx: number) => {
      setActiveIdx(idx);
      focusRow(idx);
    },
    [focusRow],
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLButtonElement>, idx: number) => {
      const last = howItWorksSteps.length - 1;
      switch (e.key) {
        case 'ArrowDown': {
          e.preventDefault();
          activate(idx === last ? 0 : idx + 1);
          break;
        }
        case 'ArrowUp': {
          e.preventDefault();
          activate(idx === 0 ? last : idx - 1);
          break;
        }
        case 'Home': {
          e.preventDefault();
          activate(0);
          break;
        }
        case 'End': {
          e.preventDefault();
          activate(last);
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
    [activate],
  );

  return (
    <section
      ref={sectionRef}
      data-landing="v2"
      className="landing-how"
      aria-labelledby="landing-how-heading"
    >
      <div className="landing-how__container">
        <h2 id="landing-how-heading" className="landing-how__headline">
          From chaos to clarity in <em>4 steps.</em>
        </h2>

        <div className="landing-how__grid">
          <div className="landing-how__accordion">
            {howItWorksSteps.map((step, idx) => {
              const expanded = idx === activeIdx;
              const rowId = `landing-how-row-${step.id}`;
              const panelId = `landing-how-panel-${step.id}`;
              return (
                <div
                  key={step.id}
                  className="landing-how__row"
                  data-expanded={expanded}
                >
                  <h3 className="landing-how__row-heading">
                    <button
                      id={rowId}
                      ref={(el) => {
                        rowRefs.current[idx] = el;
                      }}
                      type="button"
                      className="landing-how__row-button"
                      aria-expanded={expanded}
                      aria-controls={panelId}
                      onClick={() => activate(idx)}
                      onKeyDown={(e) => handleKeyDown(e, idx)}
                    >
                      <span className="landing-how__row-header">
                        <span
                          className="landing-how__row-num"
                          aria-hidden="true"
                        >
                          {step.number}.
                        </span>
                        <span className="landing-how__row-title">
                          {step.title}
                        </span>
                      </span>
                      {!expanded && (
                        <span className="landing-how__row-summary">
                          {step.summary}
                        </span>
                      )}
                    </button>
                  </h3>
                  <div
                    id={panelId}
                    role="region"
                    aria-labelledby={rowId}
                    className="landing-how__row-body"
                    hidden={!expanded}
                  >
                    {step.body}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="landing-how__preview" aria-hidden="true">
            {howItWorksSteps.map((step, idx) => (
              <div
                key={step.id}
                className="landing-how__preview-slide"
                data-step={step.id}
                data-active={idx === activeIdx}
              >
                <div className="landing-how__preview-mock">
                  {step.previewLabel}
                </div>
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
