/**
 * TutorSuggestionChips — follow-up prompts that pop in after Arc's turn.
 *
 * Staggered entrance: each chip delayed by ~60ms. Respects
 * prefers-reduced-motion via CSS (no JS gating needed).
 */
export interface TutorSuggestionChipsProps {
  suggestions: string[];
  onSelect: (text: string) => void;
  disabled?: boolean;
}

export function TutorSuggestionChips({
  suggestions,
  onSelect,
  disabled = false,
}: TutorSuggestionChipsProps) {
  if (!suggestions.length) return null;

  return (
    <div
      className="tutor-chips"
      role="list"
      aria-label="Suggested follow-up questions"
    >
      {suggestions.slice(0, 4).map((s, i) => (
        <button
          key={`${i}-${s}`}
          type="button"
          role="listitem"
          className="tutor-chip"
          onClick={() => onSelect(s)}
          disabled={disabled}
          style={{ animationDelay: `${i * 60}ms` }}
        >
          <span className="tutor-chip__arrow" aria-hidden="true">
            ↳
          </span>
          <span>{s}</span>
        </button>
      ))}
    </div>
  );
}

export default TutorSuggestionChips;
