import { useState, useRef, useEffect } from 'react';
import './RoleQuickActions.css';

export interface QuickAction {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  badge?: number;
  disabled?: boolean;
}

interface RoleQuickActionsProps {
  actions: QuickAction[];
  maxVisible?: number;
}

export function RoleQuickActions({ actions, maxVisible = 4 }: RoleQuickActionsProps) {
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  const visibleActions = actions.slice(0, maxVisible);
  const overflowActions = actions.slice(maxVisible);

  // Close "More" dropdown on outside click
  useEffect(() => {
    if (!moreOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) {
        setMoreOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [moreOpen]);

  return (
    <div className="rqa-bar" role="toolbar" aria-label="Quick actions">
      {visibleActions.map((action, i) => (
        <button
          key={i}
          className="rqa-card"
          onClick={action.onClick}
          type="button"
          disabled={action.disabled}
        >
          <span className="rqa-icon" aria-hidden="true">
            {action.icon}
          </span>
          <span className="rqa-label">
            {action.label}
            {action.badge != null && action.badge > 0 && (
              <span className="rqa-badge" aria-label={`${action.badge} new`}>
                {action.badge}
              </span>
            )}
          </span>
        </button>
      ))}

      {overflowActions.length > 0 && (
        <div className="rqa-more-wrap" ref={moreRef}>
          <button
            className="rqa-card rqa-more-trigger"
            onClick={() => setMoreOpen(prev => !prev)}
            type="button"
            aria-expanded={moreOpen}
            aria-haspopup="true"
          >
            <span className="rqa-icon" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="1" />
                <circle cx="19" cy="12" r="1" />
                <circle cx="5" cy="12" r="1" />
              </svg>
            </span>
            <span className="rqa-label">More</span>
          </button>

          {moreOpen && (
            <div className="rqa-dropdown" role="menu">
              {overflowActions.map((action, i) => (
                <button
                  key={i}
                  className="rqa-dropdown-item"
                  onClick={() => { action.onClick(); setMoreOpen(false); }}
                  type="button"
                  role="menuitem"
                  disabled={action.disabled}
                >
                  <span className="rqa-dropdown-icon" aria-hidden="true">
                    {action.icon}
                  </span>
                  <span className="rqa-dropdown-label">
                    {action.label}
                    {action.badge != null && action.badge > 0 && (
                      <span className="rqa-badge" aria-label={`${action.badge} new`}>
                        {action.badge}
                      </span>
                    )}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
