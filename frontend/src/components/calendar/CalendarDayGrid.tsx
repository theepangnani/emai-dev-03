import { CalendarEntry } from './CalendarEntry';
import type { CalendarAssignment } from './types';

interface CalendarDayGridProps {
  date: Date;
  assignments: CalendarAssignment[];
  onAssignmentClick: (assignment: CalendarAssignment, anchorRect: DOMRect) => void;
}

export function CalendarDayGrid({ date, assignments, onAssignmentClick }: CalendarDayGridProps) {
  // Sort by due time
  const sorted = [...assignments].sort((a, b) => a.dueDate.getTime() - b.dueDate.getTime());

  if (sorted.length === 0) {
    return (
      <div className="cal-day-view">
        <div className="cal-day-view-header">
          {date.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
        </div>
        <div className="cal-day-empty">No assignments due this day</div>
      </div>
    );
  }

  return (
    <div className="cal-day-view">
      <div className="cal-day-view-header">
        {date.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
      </div>
      {sorted.map(a => (
        <CalendarEntry
          key={a.id}
          assignment={a}
          variant="card"
          onClick={(e) => onAssignmentClick(a, (e.currentTarget as HTMLElement).getBoundingClientRect())}
        />
      ))}
    </div>
  );
}
