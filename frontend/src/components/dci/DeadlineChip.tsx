import type { DciDeadlineChip } from '../../api/dciSummary';
import './DeadlineChip.css';

interface Props {
  chip: DciDeadlineChip;
}

/**
 * CB-DCI-001 M0-10 — single deadline chip.
 *
 * Spec § 8: amber for ≤7 days, red for overdue OR paper-only, plus a
 * "Not yet on Google Classroom" badge for paper handouts.
 */
export function DeadlineChip({ chip }: Props) {
  const tone = chip.urgency === 'red' ? 'dci-deadline-chip--red' : 'dci-deadline-chip--amber';
  const showNotOnClassroom = chip.not_yet_on_classroom || chip.paper_only;
  // S-1 (#4214): expose due_date via a semantic <time> tag so screen readers
  // and tooltip hovers see the actual ISO date — previously the field was
  // typed but never rendered.
  const formattedDate = formatDueDate(chip.due_date);
  return (
    <span
      className={`dci-deadline-chip ${tone}`}
      title={formattedDate ? `Due ${formattedDate}` : undefined}
    >
      <span className="dci-deadline-chip__label">{chip.label}</span>
      {chip.due_date && (
        <time className="dci-deadline-chip__date" dateTime={chip.due_date}>
          {formattedDate}
        </time>
      )}
      {showNotOnClassroom && (
        <span
          className="dci-deadline-chip__badge"
          title="Not yet on Google Classroom"
        >
          Not yet on Google Classroom
        </span>
      )}
    </span>
  );
}

/**
 * Format an ISO yyyy-mm-dd string as "Apr 28" for chip display. Returns the
 * raw string on parse failure so we never break the render.
 */
function formatDueDate(iso: string | undefined): string {
  if (!iso) return '';
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
