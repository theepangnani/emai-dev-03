/**
 * CB-BRIDGE-002 — kebab menu for the kid hero card (#4113).
 *
 * Presentational. Parent passes callbacks; per-item rendering is gated
 * by the optional callbacks themselves so pending-only or linked-only
 * actions don't appear when they don't apply.
 */
import { useEffect, useId, useRef, useState } from 'react';

interface KidActionsMenuProps {
  onEdit: () => void;
  onExport: () => void;
  onResetPassword?: () => void;
  onAwardXp?: () => void;
  onResendInvite?: () => void;
  onCopyInviteLink?: () => void;
  onRemove: () => void;
  resending?: boolean;
  resendSuccess?: boolean;
  copyInviteSuccess?: boolean;
}

export function KidActionsMenu({
  onEdit,
  onExport,
  onResetPassword,
  onAwardXp,
  onResendInvite,
  onCopyInviteLink,
  onRemove,
  resending,
  resendSuccess,
  copyInviteSuccess,
}: KidActionsMenuProps) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const choose = (fn: () => void) => () => {
    setOpen(false);
    fn();
  };

  return (
    <div className="bridge-overflow-wrap" ref={wrapRef}>
      <button
        type="button"
        className="bridge-overflow-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen(o => !o)}
      >
        <span aria-hidden="true" className="bridge-overflow-dots">···</span>
        <span className="bridge-visually-hidden">Manage child</span>
      </button>
      {open && (
        <div className="bridge-overflow-menu" role="menu" id={menuId}>
          <button type="button" role="menuitem" onClick={choose(onEdit)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
            </svg>
            Edit child
          </button>
          <button type="button" role="menuitem" onClick={choose(onExport)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Export data
          </button>
          {onResetPassword && (
            <button type="button" role="menuitem" onClick={choose(onResetPassword)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                <circle cx="9" cy="14" r="5" />
                <path d="m13 10 8-8" />
                <path d="m17 6 3 3" />
              </svg>
              Reset password
            </button>
          )}
          {onAwardXp && (
            <button type="button" role="menuitem" onClick={choose(onAwardXp)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                <polygon points="12 2 15 8.5 22 9.3 17 14 18.2 21 12 17.8 5.8 21 7 14 2 9.3 9 8.5 12 2" />
              </svg>
              Award XP
            </button>
          )}
          {onResendInvite && (
            <button
              type="button"
              role="menuitem"
              disabled={resending}
              onClick={choose(onResendInvite)}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                <path d="M3 8l9 6 9-6" />
                <rect x="3" y="5" width="18" height="14" rx="2" />
              </svg>
              {resending ? 'Sending…' : resendSuccess ? '✓ Sent' : 'Resend invite'}
            </button>
          )}
          {onCopyInviteLink && (
            <button type="button" role="menuitem" onClick={choose(onCopyInviteLink)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
              </svg>
              {copyInviteSuccess ? '✓ Copied' : 'Copy invite link'}
            </button>
          )}
          <div className="bridge-overflow-divider" role="separator" />
          <button type="button" role="menuitem" className="danger" onClick={choose(onRemove)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
              <path d="M10 11v6M14 11v6" />
            </svg>
            Remove child
          </button>
        </div>
      )}
    </div>
  );
}
