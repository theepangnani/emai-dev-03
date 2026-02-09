import { useState, useCallback, useRef } from 'react';

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'danger';
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'default',
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal confirm-modal" onClick={(e) => e.stopPropagation()}>
        <div className="confirm-modal-icon">
          {variant === 'danger' ? '\u26A0\uFE0F' : '\u2728'}
        </div>
        <h2>{title}</h2>
        <p className="confirm-modal-message">{message}</p>
        <div className="modal-actions">
          <button className="cancel-btn" onClick={onCancel}>{cancelLabel}</button>
          <button
            className={variant === 'danger' ? 'danger-btn' : 'generate-btn'}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// Hook: promise-based confirm() — drop-in replacement for window.confirm
interface ConfirmOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'danger';
}

interface ConfirmState extends ConfirmOptions {
  resolve: (value: boolean) => void;
}

export function useConfirm() {
  const [state, setState] = useState<ConfirmState | null>(null);
  const stateRef = useRef<ConfirmState | null>(null);

  const confirm = useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      const s = { ...options, resolve };
      stateRef.current = s;
      setState(s);
    });
  }, []);

  const handleConfirm = useCallback(() => {
    stateRef.current?.resolve(true);
    stateRef.current = null;
    setState(null);
  }, []);

  const handleCancel = useCallback(() => {
    stateRef.current?.resolve(false);
    stateRef.current = null;
    setState(null);
  }, []);

  const confirmModal = state ? (
    <ConfirmModal
      open={true}
      title={state.title}
      message={state.message}
      confirmLabel={state.confirmLabel}
      cancelLabel={state.cancelLabel}
      variant={state.variant}
      onConfirm={handleConfirm}
      onCancel={handleCancel}
    />
  ) : null;

  return { confirm, confirmModal };
}
