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
  return (
    <span className={`dci-deadline-chip ${tone}`}>
      <span className="dci-deadline-chip__label">{chip.label}</span>
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
