import type { StudyGuide } from '../api/client';
import './StreakHistory.css';

interface StreakHistoryProps {
  studyGuides: StudyGuide[];
}

const DAY_LABELS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

/**
 * Compute which of the last 7 days had study activity.
 * Returns an array of 7 booleans, index 0 = 6 days ago, index 6 = today.
 */
function getLast7DaysActivity(guides: StudyGuide[]): { label: string; dateNum: number; active: boolean }[] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // Build a set of date strings when the student studied
  const studyDates = new Set(
    guides.map(g => {
      const d = new Date(g.created_at);
      d.setHours(0, 0, 0, 0);
      return d.toDateString();
    })
  );

  const days: { label: string; dateNum: number; active: boolean }[] = [];
  for (let i = 6; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);
    const dayOfWeek = date.getDay(); // 0=Sun, 1=Mon, ...
    // Map: Sun=0 -> index 6, Mon=1 -> index 0, etc.
    const labelIndex = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
    days.push({
      label: DAY_LABELS[labelIndex],
      dateNum: date.getDate(),
      active: studyDates.has(date.toDateString()),
    });
  }

  return days;
}

export function StreakHistory({ studyGuides }: StreakHistoryProps) {
  const days = getLast7DaysActivity(studyGuides);

  // Don't render if there's no activity at all in the last 7 days
  const hasAnyActivity = days.some(d => d.active);
  if (!hasAnyActivity) return null;

  return (
    <div className="streak-history" aria-label="Study activity for the last 7 days">
      <div className="streak-history-dots">
        {days.map((day, i) => (
          <div key={i} className="streak-history-day">
            <div
              className={`streak-history-dot ${day.active ? 'active' : ''}`}
              title={day.active ? 'Studied' : 'No activity'}
              aria-label={`${day.label}: ${day.active ? 'studied' : 'no activity'}`}
            />
            <span className="streak-history-label">{day.label} {day.dateNum}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
