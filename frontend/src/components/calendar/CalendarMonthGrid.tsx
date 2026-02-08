import { useMemo } from 'react';
import { CalendarDayCell } from './CalendarDayCell';
import type { CalendarAssignment } from './types';
import { dateKey } from './types';

interface CalendarMonthGridProps {
  currentDate: Date;
  assignments: CalendarAssignment[];
  onAssignmentClick: (assignment: CalendarAssignment, anchorRect: DOMRect) => void;
  onDayClick: (date: Date) => void;
}

const DAY_HEADERS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function getMonthGridDates(year: number, month: number): Date[] {
  const firstDay = new Date(year, month, 1);
  // Get Monday before or on the 1st
  let dow = firstDay.getDay();
  if (dow === 0) dow = 7; // Sunday = 7
  const startDate = new Date(year, month, 1 - (dow - 1));

  const dates: Date[] = [];
  for (let i = 0; i < 42; i++) {
    dates.push(new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate() + i));
  }
  return dates;
}

export function CalendarMonthGrid({ currentDate, assignments, onAssignmentClick, onDayClick }: CalendarMonthGridProps) {
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const gridDates = useMemo(() => getMonthGridDates(year, month), [year, month]);

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
    <div className="cal-month-wrapper">
      <div className="cal-month-grid">
        {DAY_HEADERS.map(d => (
          <div key={d} className="cal-day-header">{d}</div>
        ))}
        {gridDates.map((date, i) => (
          <CalendarDayCell
            key={i}
            date={date}
            isCurrentMonth={date.getMonth() === month}
            assignments={assignmentsByDate.get(dateKey(date)) || []}
            onAssignmentClick={onAssignmentClick}
            onDayClick={onDayClick}
          />
        ))}
      </div>
    </div>
  );
}
