/**
 * ASGFEntryButton — Reusable entry point for the ASGF flow.
 *
 * Renders a subtle button that navigates to the ASGF question input flow,
 * optionally pre-populating a question and context.
 *
 * Issue: #3407
 */
import { useNavigate } from 'react-router-dom';
import './ASGFEntryButton.css';

export interface ASGFEntryButtonProps {
  label: string;
  prefilledQuestion?: string;
  prefilledContext?: string;
  /** Render variant: 'inline' fits inside cards, 'sidebar' for sidebar sections */
  variant?: 'inline' | 'sidebar';
  className?: string;
}

export function ASGFEntryButton({
  label,
  prefilledQuestion,
  prefilledContext,
  variant = 'inline',
  className,
}: ASGFEntryButtonProps) {
  const navigate = useNavigate();

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    const params = new URLSearchParams();
    if (prefilledQuestion) params.set('question', prefilledQuestion);
    if (prefilledContext) params.set('context', prefilledContext);
    const qs = params.toString();
    navigate(`/ask${qs ? `?${qs}` : ''}`);
  };

  return (
    <button
      className={`asgf-entry-btn asgf-entry-btn--${variant}${className ? ` ${className}` : ''}`}
      onClick={handleClick}
      type="button"
      title={label}
    >
      <svg
        className="asgf-entry-btn__icon"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
      </svg>
      <span className="asgf-entry-btn__label">{label}</span>
    </button>
  );
}
