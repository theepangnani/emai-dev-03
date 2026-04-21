/**
 * CB-LAND-001 S9 — LearnerSegmentTabs
 *
 * "One platform. Every role." segment tabs section of the landing v2 redesign
 * (#3809 / §6.136.1 §9). Left column stacks 5 tab cards (title + subtitle);
 * right column renders the active role's detail panel (icon + role title +
 * description + 4-6 bullet checklist).
 *
 * Active tab: cyan left-border (--color-accent-cyan) + raised card elevation.
 * Private Tutors tab shows a "Coming Phase 4" pill.
 *
 * Keyboard (WAI-ARIA Tabs pattern — manual activation):
 *   ArrowUp / ArrowDown — move focus between tabs (wraps)
 *   Home / End         — jump to first / last tab
 *   Enter / Space      — activate the focused tab
 *
 * Replaces the standalone <RoleSwitcher /> block on landing-v2 (the legacy
 * LaunchLandingPage still mounts RoleSwitcher behind the kill-switch).
 *
 * Reference: docs/design/landing-v2-reference/10-learner-segments.png
 */

import { useCallback, useRef, useState } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent } from 'react';
import './LearnerSegmentTabs.css';
import { learnerSegments } from '../content/learnerSegments';
import type { LearnerSegment } from '../content/learnerSegments';

export function LearnerSegmentTabs() {
  const [activeId, setActiveId] = useState<LearnerSegment['id']>(learnerSegments[0].id);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const activeIndex = learnerSegments.findIndex((s) => s.id === activeId);
  const active = learnerSegments[activeIndex] ?? learnerSegments[0];

  const focusTab = useCallback((index: number) => {
    const count = learnerSegments.length;
    const next = ((index % count) + count) % count;
    tabRefs.current[next]?.focus();
  }, []);

  const onKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLButtonElement>, index: number) => {
      switch (event.key) {
        case 'ArrowDown':
          event.preventDefault();
          focusTab(index + 1);
          break;
        case 'ArrowUp':
          event.preventDefault();
          focusTab(index - 1);
          break;
        case 'Home':
          event.preventDefault();
          focusTab(0);
          break;
        case 'End':
          event.preventDefault();
          focusTab(learnerSegments.length - 1);
          break;
        case 'Enter':
        case ' ':
          event.preventDefault();
          setActiveId(learnerSegments[index].id);
          break;
        default:
          break;
      }
    },
    [focusTab],
  );

  return (
    <section
      data-landing="v2"
      className="landing-segments"
      aria-labelledby="landing-segments-heading"
    >
      <header className="landing-segments__header">
        <h2 id="landing-segments-heading" className="landing-segments__headline">
          One platform. <em>Every role.</em>
        </h2>
      </header>

      <div className="landing-segments__layout">
        <div
          role="tablist"
          aria-orientation="vertical"
          aria-labelledby="landing-segments-heading"
          className="landing-segments__tablist"
        >
          {learnerSegments.map((segment, index) => {
            const isActive = segment.id === activeId;
            return (
              <button
                key={segment.id}
                ref={(el) => {
                  tabRefs.current[index] = el;
                }}
                type="button"
                role="tab"
                id={`landing-segment-tab-${segment.id}`}
                aria-selected={isActive}
                aria-controls={`landing-segment-panel-${segment.id}`}
                tabIndex={isActive ? 0 : -1}
                className={`landing-segment-tab${
                  isActive ? ' landing-segment-tab--active' : ''
                }`}
                onClick={() => setActiveId(segment.id)}
                onKeyDown={(event) => onKeyDown(event, index)}
              >
                <span className="landing-segment-tab__title">
                  {segment.title}
                  {segment.comingPhase4 ? (
                    <span
                      className="landing-segment-tab__pill"
                      aria-label="Coming Phase 4"
                    >
                      Coming Phase 4
                    </span>
                  ) : null}
                </span>
                <span className="landing-segment-tab__subtitle">{segment.subtitle}</span>
              </button>
            );
          })}
        </div>

        <div
          role="tabpanel"
          id={`landing-segment-panel-${active.id}`}
          aria-labelledby={`landing-segment-tab-${active.id}`}
          className="landing-segment-panel"
        >
          <div className="landing-segment-panel__icon" aria-hidden="true" />
          <h3 className="landing-segment-panel__role">{active.roleTitle}</h3>
          <p className="landing-segment-panel__description">{active.description}</p>
          <ul className="landing-segment-panel__bullets">
            {active.bullets.map((bullet) => (
              <li key={bullet} className="landing-segment-panel__bullet">
                <span className="landing-segment-panel__check" aria-hidden="true" />
                <span>{bullet}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

export const section = {
  id: 'segments',
  order: 70,
  component: LearnerSegmentTabs,
};

export default LearnerSegmentTabs;
