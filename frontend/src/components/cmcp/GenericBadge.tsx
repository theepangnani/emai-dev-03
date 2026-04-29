/**
 * CB-CMCP-001 M1-B 1B-4 (#4492) — "generic — no class-vocab anchoring" badge.
 *
 * Per A1 acceptance: when the CGP returns a generation result whose
 * ``class_context_envelope.fallback_used == true`` (i.e., the resolver yielded
 * an empty envelope and the prompt fell back to CEG-only generic content), the
 * UI MUST render an explicit badge so the user sees that this artifact was
 * NOT anchored to their teacher's vocabulary.
 *
 * Rendering contract:
 * - When ``fallbackUsed`` is true → render the badge.
 * - When ``fallbackUsed`` is false → render nothing.
 *
 * Accessibility (WCAG 1.4.1):
 * - Color is NOT the only indicator: an inline icon and a text label are both
 *   present, and the icon is decorative (``aria-hidden``) while the label
 *   carries the meaning. The component also exposes ``role="status"`` so
 *   assistive tech announces the warning when it appears.
 *
 * Token policy: Uses existing global tokens (``--color-warning-bg``,
 * ``--color-warning-text``, ``--color-warning``, ``--radius-sm``, ``--font-sans``).
 * No new tokens are introduced; the design intentionally reuses the
 * "warning"/"pending" semantic ramp the Bridge stripe already documents in
 * ``THEME.md``.
 */
import './GenericBadge.css';

interface GenericBadgeProps {
  /** Whether the generation result fell back to CEG-only (no class context). */
  fallbackUsed: boolean;
  /** Optional classname pass-through for layout overrides. */
  className?: string;
}

export const GENERIC_BADGE_LABEL = 'generic — no class-vocab anchoring';

export function GenericBadge({ fallbackUsed, className }: GenericBadgeProps) {
  if (!fallbackUsed) return null;

  const classes = ['cmcp-generic-badge'];
  if (className) classes.push(className);

  return (
    <span
      className={classes.join(' ')}
      role="status"
      data-testid="cmcp-generic-badge"
    >
      {/* Decorative warning-triangle icon — text label below carries the
          meaning so color is not the sole indicator (WCAG 1.4.1). */}
      <svg
        className="cmcp-generic-badge-icon"
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        focusable="false"
      >
        <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
      <span className="cmcp-generic-badge-label">{GENERIC_BADGE_LABEL}</span>
    </span>
  );
}
