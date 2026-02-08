import { useMemo } from 'react';
import { CalendarEntry } from './CalendarEntry';
import type { CalendarAssignment } from './types';
import { dateKey, isSameDay } from './types';

interface CalendarWeekGridProps {
  dates: Date[];
  assignments: CalendarAssignment[];
  onAssignmentClick: (assignment: CalendarAssignment, anchorRect: DOMRect) => void;
}

const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export function CalendarWeekGrid({ dates, assignments, onAssignmentClick }: CalendarWeekGridProps) {
  const today = new Date();

  const assignmentsByDate = useMemo(() => {
    const map = new Map<string, CalendarAssignment[]>();
    for (const a of assignments) {
      const key = dateKey(a.dueDate);
      const list = map.get(key) || [];
      list.push(a);
      map.set(key, list);
    }
    return map;
  }, [assignments]);

  return (
    <div className="cal-week-grid" style={{ gridTemplateColumns: `repeat(${dates.length}, 1fr)` }}>
      {dates.map((date, i) => {
        const isToday = isSameDay(date, today);
        const dayAssignments = assignmentsByDate.get(dateKey(date)) || [];
        return (
          <div key={i} className="cal-week-column">
            <div className={`cal-week-column-header${isToday ? ' today' : ''}`}>
              <div className="cal-week-day-name">{DAY_NAMES[date.getDay()]}</div>
              <div className={`cal-week-day-num${isToday ? ' today' : ''}`}>{date.getDate()}</div>
            </div>
            <div className="cal-week-column-body">
              {dayAssignments.length === 0 ? (
                <div className="cal-week-empty" />
              ) : (
                dayAssignments.map(a => (
                  <CalendarEntry
                    key={a.id}
                    assignment={a}
                    variant="card"
                    onClick={(e) => onAssignmentClick(a, (e.currentTarget as HTMLElement).getBoundingClientRect())}
                  />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
