import type { TaskSource, TaskSourceStatus } from '../api/tasks';

/**
 * CB-TASKSYNC-001 (#3920) — Small pill badge rendered next to the priority
 * chip on auto-created Tasks. Visual variants:
 *
 * - assignment                            → slate pill  "Auto"
 * - email_digest + active                 → teal pill   "Auto"
 * - email_digest + tentative              → amber OUTLINE pill "Unverified"
 * - study_guide                           → neutral pill "Auto (study guide)"
 * - manual / null / unknown               → renders nothing
 *
 * Accessibility:
 * - Semantic `<span role="status">` so screen readers announce the label.
 * - Tooltip delivered via `title=` attribute (works on hover + keyboard focus
 *   when the element is focusable; we set `tabIndex={0}` so keyboard users can
 *   reach it).
 */
export interface TaskSourceBadgeProps {
  source?: TaskSource | null;
  sourceStatus?: TaskSourceStatus | null;
  confidence?: number | null;
  className?: string;
}

interface BadgeConfig {
  variant: 'assignment' | 'email-active' | 'email-tentative' | 'study-guide';
  label: string;
  tooltip: string;
}

function resolveBadge(
  source: TaskSource | null | undefined,
  status: TaskSourceStatus | null | undefined,
  confidence: number | null | undefined,
): BadgeConfig | null {
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
  return null;
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
      role="status"
      className={classes}
      title={config.tooltip}
      aria-label={config.tooltip}
      tabIndex={0}
    >
      {config.label}
    </span>
  );
}

export default TaskSourceBadge;
