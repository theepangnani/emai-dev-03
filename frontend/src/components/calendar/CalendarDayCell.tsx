import { CalendarEntry } from './CalendarEntry';
import type { CalendarAssignment } from './types';
import { isSameDay } from './types';

interface CalendarDayCellProps {
  date: Date;
  isCurrentMonth: boolean;
  assignments: CalendarAssignment[];
  onAssignmentClick: (assignment: CalendarAssignment, anchorRect: DOMRect) => void;
  onDayClick: (date: Date) => void;
}

const MAX_VISIBLE = 3;

export function CalendarDayCell({ date, isCurrentMonth, assignments, onAssignmentClick, onDayClick }: CalendarDayCellProps) {
  const isToday = isSameDay(date, new Date());
  const overflow = assignments.length - MAX_VISIBLE;

  return (
    <div
      className={`cal-day-cell${!isCurrentMonth ? ' outside-month' : ''}${isToday ? ' today' : ''}`}
    >
      <div
        className="cal-day-number"
        onClick={() => onDayClick(date)}
        title="View day"
      >
        {date.getDate()}
      </div>
      <div className="cal-day-entries">
        {assignments.slice(0, MAX_VISIBLE).map(a => (
          <CalendarEntry
            key={a.id}
            assignment={a}
            variant="chip"
            onClick={(e) => onAssignmentClick(a, (e.currentTarget as HTMLElement).getBoundingClientRect())}
          />
        ))}
        {overflow > 0 && (
          <div className="cal-day-more" onClick={() => onDayClick(date)}>
            +{overflow} more
          </div>
        )}
      </div>
    </div>
  );
}
