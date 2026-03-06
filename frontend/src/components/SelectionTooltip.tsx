import './SelectionTooltip.css';

interface SelectionTooltipProps {
  rect: DOMRect;
  visible: boolean;
  onAddToNotes: () => void;
}

export function SelectionTooltip({ rect, visible, onAddToNotes }: SelectionTooltipProps) {
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
    </div>
  );
}
