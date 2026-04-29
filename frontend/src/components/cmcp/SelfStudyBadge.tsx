/**
 * CB-CMCP-001 M3-B 3B-2 (#4578) — "AI-generated, not teacher-approved" badge
 * for SELF_STUDY artifacts.
 *
 * Rendering contract:
 * - A small pill: warning-icon + label "AI-generated, not teacher-approved".
 * - Two size variants: ``sm`` (default, matches inline chip density) and
 *   ``md`` (slightly larger for card headers).
 *
 * Accessibility (WCAG 1.4.1):
 * - Color is NOT the only indicator: an inline icon and a text label are
 *   both present. The icon is decorative (``aria-hidden``) and the visible
 *   text label carries the meaning.
 * - Mirrors the pattern set by ``GenericBadge`` (1B-4 #4492): we deliberately
 *   do NOT use ``role="status"`` — a static label on an artifact is not a
 *   live region and live-region semantics produce duplicate / no
 *   announcements depending on AT.
 *
 * Token policy: Reuses the global "warning"/"pending" semantic ramp
 * (``--color-warning-bg``, ``--color-warning-text``, ``--radius-sm``,
 * ``--font-sans``) defined in ``index.css`` / documented in ``THEME.md``.
 * No new tokens are introduced. Colour palette intentionally matches
 * ``GenericBadge`` so the two warning chips read as a coherent family
 * across rust/ivory and the default Bridge theme.
 */
import './SelfStudyBadge.css';

interface SelfStudyBadgeProps {
  /** Pill size. ``sm`` is the inline default; ``md`` is for card headers. */
  size?: 'sm' | 'md';
  /** Optional classname pass-through for layout overrides. */
  className?: string;
  /**
   * Optional tooltip copy shown on hover / long-press. When provided it is
   * exposed via the native ``title`` attribute and folded into the
   * accessible name so screen readers announce both the label and the
   * detail. When omitted only the label is announced.
   */
  tooltip?: string;
}

export const SELF_STUDY_BADGE_LABEL = 'AI-generated, not teacher-approved';
export const SELF_STUDY_BADGE_ARIA_LABEL =
  'Warning: AI-generated, not teacher-approved.';

export function SelfStudyBadge({
  size = 'sm',
  className,
  tooltip,
}: SelfStudyBadgeProps) {
  const classes = ['cmcp-self-study-badge', `cmcp-self-study-badge--${size}`];
  if (className) classes.push(className);

  // When a tooltip is supplied we extend the accessible name so AT users
  // hear both the static warning and the additional detail. Without a
  // tooltip we keep the canonical aria-label so the badge always carries a
  // queryable accessible name.
  const ariaLabel = tooltip
    ? `${SELF_STUDY_BADGE_ARIA_LABEL} ${tooltip}`
    : SELF_STUDY_BADGE_ARIA_LABEL;

  return (
    <span
      className={classes.join(' ')}
      aria-label={ariaLabel}
      title={tooltip}
      data-testid="cmcp-self-study-badge"
    >
      {/* Decorative warning-circle icon (Lucide AlertCircle path) — the
          text label below carries the meaning so colour is not the sole
          indicator (WCAG 1.4.1). */}
      <svg
        className="cmcp-self-study-badge-icon"
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
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <span className="cmcp-self-study-badge-label">
        {SELF_STUDY_BADGE_LABEL}
      </span>
    </span>
  );
}
