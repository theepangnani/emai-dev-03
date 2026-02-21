import { useState, useRef, useEffect } from 'react';
import './AddActionButton.css';

export interface ActionItem {
  icon: string;
  label: string;
  onClick: () => void;
}

interface AddActionButtonProps {
  actions: ActionItem[];
}

export function AddActionButton({ actions }: AddActionButtonProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  return (
    <div className="add-action-wrapper" ref={ref}>
      <button
        className={`add-action-trigger${open ? ' active' : ''}`}
        onClick={() => setOpen(v => !v)}
        aria-label="Add new"
        aria-expanded={open}
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <path d="M9 3v12M3 9h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
      {open && (
        <div className="add-action-popover">
          {actions.map((action) => (
            <button
              key={action.label}
              className="add-action-item"
              onClick={() => { setOpen(false); action.onClick(); }}
            >
              <span className="add-action-item-icon">{action.icon}</span>
              <span className="add-action-item-label">{action.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
