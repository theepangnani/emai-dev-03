import './SelectionTooltip.css';

interface SelectionTooltipProps {
  rect: DOMRect;
  visible: boolean;
  onAddToNotes: () => void;
  onAskChatBot?: () => void;
  onStartSession?: () => void;
}

export function SelectionTooltip({ rect, visible, onAddToNotes, onAskChatBot, onStartSession }: SelectionTooltipProps) {
  if (!visible) return null;

  const top = rect.top + window.scrollY - 44;
  const left = rect.left + window.scrollX + rect.width / 2;

  return (
    <div
      className="selection-tooltip"
      style={{ top, left }}
      onMouseDown={(e) => e.preventDefault()}
    >
      <button
        className="selection-tooltip-btn"
        onClick={onAddToNotes}
        onTouchEnd={(e) => { e.preventDefault(); onAddToNotes(); }}
      >
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 3h7l3 3v7a1 1 0 01-1 1H4a1 1 0 01-1-1V3z" />
          <path d="M5.5 7h5M5.5 9.5h3" />
        </svg>
        <span>Add to Notes</span>
      </button>
      {onAskChatBot && (
        <button
          className="selection-tooltip-btn selection-tooltip-btn-chat"
          onClick={onAskChatBot}
          onTouchEnd={(e) => { e.preventDefault(); onAskChatBot(); }}
          data-testid="selection-tooltip-chat"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 3a1 1 0 011-1h10a1 1 0 011 1v7a1 1 0 01-1 1H5l-3 3V3z" />
          </svg>
          <span>Ask Chat Bot</span>
        </button>
      )}
      {onStartSession && (
        <button
          className="selection-tooltip-btn selection-tooltip-btn-session"
          onClick={onStartSession}
          onTouchEnd={(e) => { e.preventDefault(); onStartSession(); }}
          data-testid="selection-tooltip-session"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="5,3 13,8 5,13" />
          </svg>
          <span>Start Session</span>
        </button>
      )}
    </div>
  );
}
