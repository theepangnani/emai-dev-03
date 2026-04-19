import { useState, useCallback, useRef } from 'react';
import { useFocusTrap } from '../hooks/useFocusTrap';

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'danger';
  disableConfirm?: boolean;
  extraActionLabel?: string;
  onExtraAction?: () => void;
  promptLabel?: string;
  promptPlaceholder?: string;
  promptValue?: string;
  onPromptChange?: (value: string) => void;
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
  disableConfirm,
  extraActionLabel,
  onExtraAction,
  promptLabel,
  promptPlaceholder,
  promptValue,
  onPromptChange,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const trapRef = useFocusTrap(open, onCancel);

  if (!open) return null;

  return (
    <div className="modal-overlay">
      <div
        ref={trapRef}
        className="modal confirm-modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        aria-describedby="confirm-message"
      >
        <div className="confirm-modal-icon">
          {variant === 'danger' ? '\u26A0\uFE0F' : '\u2728'}
        </div>
        <h2 id="confirm-title">{title}</h2>
        <p id="confirm-message" className="confirm-modal-message">{message}</p>
        {onPromptChange && (
          <div className="confirm-modal-prompt">
            {promptLabel && <label className="confirm-modal-prompt-label" htmlFor="confirm-modal-input">{promptLabel}</label>}
            <input
              type="text"
              id="confirm-modal-input"
              className="confirm-modal-prompt-input"
              placeholder={promptPlaceholder || ''}
              value={promptValue || ''}
              onChange={(e) => onPromptChange(e.target.value)}
              autoFocus
            />
          </div>
        )}
        <div className="modal-actions">
          <button className="cancel-btn" onClick={onCancel}>{cancelLabel}</button>
          {extraActionLabel && onExtraAction && (
            <button className="generate-btn" onClick={onExtraAction}>
              {extraActionLabel}
            </button>
          )}
          <button
            className={variant === 'danger' ? 'danger-btn' : 'generate-btn'}
            onClick={onConfirm}
            disabled={disableConfirm}
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
  disableConfirm?: boolean;
  extraActionLabel?: string;
  onExtraAction?: () => void;
  promptLabel?: string;
  promptPlaceholder?: string;
}

interface ConfirmState extends ConfirmOptions {
  resolve: (value: boolean) => void;
  promptValue: string;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useConfirm() {
  const [state, setState] = useState<ConfirmState | null>(null);
  const stateRef = useRef<ConfirmState | null>(null);

  const confirm = useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      const s = { ...options, resolve, promptValue: '' };
      stateRef.current = s;
      setState(s);
    });
  }, []);

  const handleCancel = useCallback(() => {
    stateRef.current?.resolve(false);
    stateRef.current = null;
    setState(null);
  }, []);

  const handleExtraAction = useCallback(() => {
    stateRef.current?.onExtraAction?.();
    stateRef.current?.resolve(false);
    stateRef.current = null;
    setState(null);
  }, []);

  const handlePromptChange = useCallback((value: string) => {
    if (stateRef.current) {
      stateRef.current = { ...stateRef.current, promptValue: value };
      setState({ ...stateRef.current });
    }
  }, []);

  const lastPromptValueRef = useRef('');

  // Override handleConfirm to capture prompt value before clearing
  const handleConfirmWithPrompt = useCallback(() => {
    lastPromptValueRef.current = stateRef.current?.promptValue ?? '';
    stateRef.current?.resolve(true);
    stateRef.current = null;
    setState(null);
  }, []);

  const getLastPromptValue = useCallback(() => lastPromptValueRef.current, []);

  // Replace onConfirm in modal with the prompt-capturing version
  const confirmModalFinal = state ? (
    <ConfirmModal
      open={true}
      title={state.title}
      message={state.message}
      confirmLabel={state.confirmLabel}
      cancelLabel={state.cancelLabel}
      variant={state.variant}
      disableConfirm={state.disableConfirm}
      extraActionLabel={state.extraActionLabel}
      onExtraAction={state.onExtraAction ? handleExtraAction : undefined}
      promptLabel={state.promptLabel}
      promptPlaceholder={state.promptPlaceholder}
      promptValue={state.promptValue}
      onPromptChange={state.promptLabel ? handlePromptChange : undefined}
      onConfirm={handleConfirmWithPrompt}
      onCancel={handleCancel}
    />
  ) : null;

  return { confirm, confirmModal: confirmModalFinal, getLastPromptValue };
}
