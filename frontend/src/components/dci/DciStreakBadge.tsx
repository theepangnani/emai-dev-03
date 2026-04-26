/**
 * DciStreakBadge — kid-side streak chip rendered on Screen 3 of the
 * /checkin flow. No XP coupling per design lock § 7 (VPC: streak ≠ XP).
 *
 * Extracted from CheckInDonePage as part of issue #4198 — uses CSS classes
 * + design tokens instead of inline styles so theming stays consistent
 * with the rest of the kid /checkin chrome.
 */
import './DciStreakBadge.css';

export interface DciStreakBadgeProps {
  current: number;
  longest: number;
}

export function DciStreakBadge({ current, longest }: DciStreakBadgeProps) {
  return (
    <div
      role="status"
      aria-label={`Current streak ${current} days, longest ${longest} days`}
      className="dci-streak-badge"
    >
      <span className="dci-streak-badge__count">{current}</span>
      <span className="dci-streak-badge__label">
        day{current === 1 ? '' : 's'} in a row
      </span>
      {longest > 0 && (
        <span className="dci-streak-badge__longest">Longest {longest}</span>
      )}
    </div>
  );
}

export default DciStreakBadge;
