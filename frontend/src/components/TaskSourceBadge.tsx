import type { TaskSource, TaskSourceStatus } from '../api/tasks';

/**
 * CB-TASKSYNC-001 (#3920) — Small pill badge rendered next to the priority
 * chip on auto-created Tasks. Visual variants:
 *
 * - assignment                            → slate pill  "Auto"
 * - email_digest + active                 → teal pill   "Auto"
 * - email_digest + tentative              → amber OUTLINE pill "Unverified"
 * - study_guide                           → neutral pill "Auto (study guide)"
 * - manual / null                         → renders nothing
 * - any other non-null string             → renders neutral "Auto" pill so
 *                                           future backend-only source values
 *                                           never render invisibly while the
 *                                           frontend catches up.
 *
 * Accessibility:
 * - Tooltip delivered via the native `title=` attribute (hover + long-press
 *   on touch). `aria-label` mirrors the tooltip so screen readers announce
 *   the full context instead of just the short label.
 * - We intentionally do NOT set `role="status"` (that is a live region and
 *   would announce "Auto" for every row on every re-render) and do NOT add
 *   `tabIndex={0}` (it would insert a keyboard tab-stop on every task row,
 *   hurting WCAG 2.4.3 focus-order UX). Keyboard users already discover the
 *   badge via the row's existing interactive targets.
 */
export interface TaskSourceBadgeProps {
  source?: TaskSource | (string & {}) | null;
  sourceStatus?: TaskSourceStatus | null;
  confidence?: number | null;
  className?: string;
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
): BadgeConfig | null {
  if (source == null || source === 'manual') return null;
  if (source === 'assignment') {
    return {
      variant: 'assignment',
      label: 'Auto',
      tooltip: 'Auto-created from class assignment',
    };
  }
  if (source === 'email_digest') {
    if (status === 'tentative') {
      const pct =
        typeof confidence === 'number' && Number.isFinite(confidence)
          ? Math.round(confidence * 100)
          : null;
      const tooltip =
        pct !== null
          ? `Auto-created from teacher email (${pct}% confidence) — please verify`
          : 'Auto-created from teacher email — please verify';
      return { variant: 'email-tentative', label: 'Unverified', tooltip };
    }
    // Treat missing / active / terminal statuses as active for display.
    return {
      variant: 'email-active',
      label: 'Auto',
      tooltip: 'Auto-created from teacher email',
    };
  }
  if (source === 'study_guide') {
    return {
      variant: 'study-guide',
      label: 'Auto (study guide)',
      tooltip: 'Auto-created from a study guide',
    };
  }
  // Unknown but non-null source — render a neutral fallback so a new backend
  // value isn't silently invisible. Variant class matches study-guide so we
  // don't proliferate styles without a design decision.
  return {
    variant: 'unknown',
    label: 'Auto',
    tooltip: 'Auto-created',
  };
}

export function TaskSourceBadge({
  source,
  sourceStatus,
  confidence,
  className,
}: TaskSourceBadgeProps) {
  const config = resolveBadge(source, sourceStatus, confidence);
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
