import { useState, useEffect, useRef, useCallback } from 'react';
import './QuickActionFAB.css';

export interface FABAction {
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  color?: string;
}

interface QuickActionFABProps {
  actions: FABAction[];
}

export function QuickActionFAB({ actions }: QuickActionFABProps) {
  const [open, setOpen] = useState(false);
  const fabRef = useRef<HTMLDivElement>(null);
  const mainButtonRef = useRef<HTMLButtonElement>(null);
  const actionRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const close = useCallback(() => setOpen(false), []);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        close();
        mainButtonRef.current?.focus();
      }
      // Tab-trap: keep focus within the FAB when open
      if (e.key === 'Tab') {
        const focusable: HTMLElement[] = [
          mainButtonRef.current,
          ...actionRefs.current,
        ].filter((el): el is HTMLElement => el !== null);
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, close]);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handleMouseDown = (e: MouseEvent) => {
      if (fabRef.current && !fabRef.current.contains(e.target as Node)) {
        close();
      }
    };
    document.addEventListener('mousedown', handleMouseDown);
    return () => document.removeEventListener('mousedown', handleMouseDown);
  }, [open, close]);

  // When FAB opens, move focus to first action button
  useEffect(() => {
    if (open && actionRefs.current[0]) {
      // Small delay to allow CSS transition to start
      const id = setTimeout(() => actionRefs.current[0]?.focus(), 50);
      return () => clearTimeout(id);
    }
  }, [open]);

  const handleActionClick = (action: FABAction) => {
    action.onClick();
    close();
    mainButtonRef.current?.focus();
  };

  if (actions.length === 0) return null;

  return (
    <div className="qaf-root" ref={fabRef}>
      {/* Speed-dial action items — rendered in reverse so first item is closest to button */}
      <div className={`qaf-actions${open ? ' qaf-actions--open' : ''}`} role="menu" aria-label="Quick action options">
        {[...actions].reverse().map((action, reversedIndex) => {
          // The reversed index maps back to the forward index for stagger delays
          const forwardIndex = actions.length - 1 - reversedIndex;
          return (
            <div
              key={forwardIndex}
              className="qaf-action-item"
              style={{ '--i': forwardIndex } as React.CSSProperties}
            >
              <span className="qaf-action-label">{action.label}</span>
              <button
                ref={(el) => { actionRefs.current[forwardIndex] = el; }}
                className="qaf-action-btn"
                onClick={() => handleActionClick(action)}
                aria-label={action.label}
                role="menuitem"
                tabIndex={open ? 0 : -1}
                style={action.color ? { backgroundColor: action.color } : undefined}
                type="button"
              >
                {action.icon}
              </button>
            </div>
          );
        })}
      </div>

      {/* Main FAB button */}
      <button
        ref={mainButtonRef}
        className={`qaf-main-btn${open ? ' qaf-main-btn--open' : ''}`}
        onClick={() => setOpen(prev => !prev)}
        aria-label="Quick actions"
        aria-expanded={open}
        aria-haspopup="true"
        type="button"
      >
        <svg
          className="qaf-plus-icon"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
      </button>

      {/* Backdrop overlay (mobile) */}
      {open && (
        <div className="qaf-backdrop" onClick={close} aria-hidden="true" />
      )}
    </div>
  );
}
