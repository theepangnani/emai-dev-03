import { useState, useCallback } from 'react';
import './CollapsibleSection.css';

interface CollapsibleSectionProps {
  id: string;
  title: string;
  guideId: string | number;
  children: React.ReactNode;
}

function getStorageKey(guideId: string | number) {
  return `sg-collapse-${guideId}`;
}

function loadCollapseState(guideId: string | number): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(getStorageKey(guideId));
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveCollapseState(guideId: string | number, state: Record<string, boolean>) {
  try {
    localStorage.setItem(getStorageKey(guideId), JSON.stringify(state));
  } catch {
    // localStorage full or unavailable
  }
}

export function CollapsibleSection({ id, title, guideId, children }: CollapsibleSectionProps) {
  const [expanded, setExpanded] = useState(() => {
    const state = loadCollapseState(guideId);
    return state[id] !== false; // default expanded
  });

  const toggle = useCallback(() => {
    setExpanded(prev => {
      const next = !prev;
      const state = loadCollapseState(guideId);
      state[id] = next;
      saveCollapseState(guideId, state);
      return next;
    });
  }, [guideId, id]);

  return (
    <div className="sg-collapsible" id={id}>
      <button
        className="sg-collapsible-toggle"
        onClick={toggle}
        aria-expanded={expanded}
        aria-controls={`${id}-body`}
        type="button"
      >
        <svg className={`sg-collapsible-chevron ${expanded ? 'sg-collapsible-chevron--open' : ''}`} width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span className="sg-collapsible-title">{title}</span>
      </button>
      <div id={`${id}-body`} className="sg-collapsible-body" hidden={!expanded}>
        {children}
      </div>
    </div>
  );
}
