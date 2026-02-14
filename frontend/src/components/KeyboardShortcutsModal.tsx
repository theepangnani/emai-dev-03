import { useFocusTrap } from '../utils/useFocusTrap';

interface KeyboardShortcutsModalProps {
  open: boolean;
  onClose: () => void;
}

const shortcuts = [
  { keys: 'Ctrl + K', description: 'Open global search' },
  { keys: '?', description: 'Show this shortcuts panel' },
  { keys: 'Esc', description: 'Close modal / cancel action' },
];

export function KeyboardShortcutsModal({ open, onClose }: KeyboardShortcutsModalProps) {
  const trapRef = useFocusTrap(open, onClose);

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        ref={trapRef}
        className="modal shortcuts-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="shortcuts-title">Keyboard Shortcuts</h2>
        <div className="shortcuts-list">
          {shortcuts.map((s) => (
            <div key={s.keys} className="shortcut-row">
              <kbd className="shortcut-key">{s.keys}</kbd>
              <span className="shortcut-desc">{s.description}</span>
            </div>
          ))}
        </div>
        <div className="modal-actions">
          <button className="cancel-btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
