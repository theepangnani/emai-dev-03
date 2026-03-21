import './SelectionTooltip.css';

interface SelectionTooltipProps {
  rect: DOMRect;
  visible: boolean;
  onAddToNotes: () => void;
  onGenerateStudyMaterial?: () => void;
}

export function SelectionTooltip({ rect, visible, onAddToNotes, onGenerateStudyMaterial }: SelectionTooltipProps) {
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
      {onGenerateStudyMaterial && (
        <button
          className="selection-tooltip-btn selection-tooltip-btn-generate"
          onClick={onGenerateStudyMaterial}
          onTouchEnd={(e) => { e.preventDefault(); onGenerateStudyMaterial(); }}
          data-testid="selection-tooltip-generate"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M8 1v2M8 13v2M1 8h2M13 8h2" />
            <path d="M3.5 3.5l1.4 1.4M11.1 11.1l1.4 1.4M12.5 3.5l-1.4 1.4M4.9 11.1l-1.4 1.4" />
            <circle cx="8" cy="8" r="2.5" />
          </svg>
          <span>Generate Study Material</span>
        </button>
      )}
    </div>
  );
}
