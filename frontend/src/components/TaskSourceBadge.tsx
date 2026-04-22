import type { TaskSource, TaskSourceStatus } from '../api/tasks';

/**
 * CB-TASKSYNC-001 (#3920, #3921) — Small pill badge rendered next to the
 * priority chip on auto-created Tasks. Visual variants:
 *
 * - assignment                            → slate pill  "Auto"
 * - email_digest + active                 → teal pill   "Auto"
 * - email_digest + tentative              → amber OUTLINE pill
 *                                           "Unverified · {pct}%"
 * - study_guide                           → neutral pill "Auto (study guide)"
 * - manual / null                         → renders nothing
 * - any other non-null string             → renders neutral "Auto" pill so
 *                                           future backend-only source values
 *                                           never render invisibly while the
 *                                           frontend catches up.
 *
 * I9 polish (#3921):
 * - Tooltip now includes the source-created date (formatted "MMM d") when
 *   `sourceCreatedAt` is provided and parseable. Missing/invalid values
 *   fall back to the I8 copy unchanged.
 * - Tentative email_digest badge shows an inline "· {pct}%" next to the
 *   "Unverified" label so low-confidence items can be spotted at a glance
 *   without waiting for the tooltip.
 * - A soft background/border transition (see TasksPage.css) animates the
 *   variant flip when a Task upgrades from email_digest → assignment (I6).
 *
 * Accessibility:
 * - Tooltip delivered via the native `title=` attribute (hover + long-press
 *   on touch). `aria-label` mirrors the tooltip so screen readers announce
 *   the full context instead of just the short label.
 * - We intentionally do NOT set `role="status"` (that is a live region and
 *   would announce "Auto" for every row on every re-render) and do NOT add
 *   `tabIndex={0}` (it would insert a keyboard tab-stop on every task row,
 *   hurting WCAG 2.4.3 focus-order UX). Keyboard users already discover the
 *   badge via the row's existing interactive targets. A scoped
 *   `:focus-visible` style is still declared in CSS so if the badge is ever
 *   wrapped in an interactive element, the outline is consistent.
 */
export interface TaskSourceBadgeProps {
  source?: TaskSource | (string & {}) | null;
  sourceStatus?: TaskSourceStatus | null;
  confidence?: number | null;
  /**
   * ISO date string or Date. When present and parseable the tooltip includes
   * "on MMM d" (e.g. "Apr 21"). Missing/invalid values fall back to the
   * shorter legacy copy without the date fragment.
   */
  sourceCreatedAt?: string | Date | null;
  className?: string;
}

/** Formats a date as "MMM d" (e.g. "Apr 21"). Returns null on invalid input. */
function formatShortDate(input: string | Date | null | undefined): string | null {
  if (input == null) return null;
  const date = input instanceof Date ? input : new Date(input);
  if (Number.isNaN(date.getTime())) return null;
  try {
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(date);
  } catch {
    return null;
  }
}

interface BadgeConfig {
  variant:
    | 'assignment'
    | 'email-active'
    | 'email-tentative'
    | 'study-guide'
    | 'unknown';
  label: string;
  tooltip: string;
}

function resolveBadge(
  source: TaskSource | (string & {}) | null | undefined,
  status: TaskSourceStatus | null | undefined,
  confidence: number | null | undefined,
  sourceCreatedAt: string | Date | null | undefined,
): BadgeConfig | null {
  if (source == null || source === 'manual') return null;
  const formattedDate = formatShortDate(sourceCreatedAt);
  const onDate = formattedDate ? ` on ${formattedDate}` : '';

  if (source === 'assignment') {
    return {
      variant: 'assignment',
      label: 'Auto',
      tooltip: `Auto-created from class assignment${onDate}`,
    };
  }
  if (source === 'email_digest') {
    if (status === 'tentative') {
      const pct =
        typeof confidence === 'number' && Number.isFinite(confidence)
          ? Math.round(confidence * 100)
          : null;
      // Inline confidence readout next to "Unverified" so low-quality items
      // are visible at a glance without the tooltip (I9 polish — #3921).
      const label = pct !== null ? `Unverified · ${pct}%` : 'Unverified';
      const confidenceFragment = pct !== null ? ` (${pct}% confidence)` : '';
      const tooltip = `Auto-created from teacher email${onDate}${confidenceFragment} — please verify`;
      return { variant: 'email-tentative', label, tooltip };
    }
    // Treat missing / active / terminal statuses as active for display.
    return {
      variant: 'email-active',
      label: 'Auto',
      tooltip: `Auto-created from teacher email${onDate}`,
    };
  }
  if (source === 'study_guide') {
    return {
      variant: 'study-guide',
      label: 'Auto (study guide)',
      tooltip: `Auto-created from a study guide${onDate}`,
    };
  }
  // Unknown but non-null source — render a neutral fallback so a new backend
  // value isn't silently invisible. Variant class matches study-guide so we
  // don't proliferate styles without a design decision.
  return {
    variant: 'unknown',
    label: 'Auto',
    tooltip: `Auto-created${onDate}`,
  };
}

export function TaskSourceBadge({
  source,
  sourceStatus,
  confidence,
  sourceCreatedAt,
  className,
}: TaskSourceBadgeProps) {
  const config = resolveBadge(source, sourceStatus, confidence, sourceCreatedAt);
  if (!config) return null;

  const classes = [
    'task-source-badge',
    `task-source-badge--${config.variant}`,
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <span
      className={classes}
      title={config.tooltip}
      aria-label={config.tooltip}
    >
      {config.label}
    </span>
  );
}
