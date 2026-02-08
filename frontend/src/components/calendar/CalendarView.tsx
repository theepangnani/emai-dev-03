import { useState, useMemo } from 'react';
import { useCalendarNav } from './useCalendarNav';
import { CalendarHeader } from './CalendarHeader';
import { CalendarMonthGrid } from './CalendarMonthGrid';
import { CalendarWeekGrid } from './CalendarWeekGrid';
import { CalendarDayGrid } from './CalendarDayGrid';
import { CalendarEntryPopover } from './CalendarEntryPopover';
import type { CalendarAssignment } from './types';
import { dateKey } from './types';
import './Calendar.css';

interface CalendarViewProps {
  assignments: CalendarAssignment[];
  onCreateStudyGuide: (assignment: CalendarAssignment) => void;
}

function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

function getMonday(d: Date): Date {
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  return addDays(new Date(d.getFullYear(), d.getMonth(), d.getDate()), diff);
}

export function CalendarView({ assignments, onCreateStudyGuide }: CalendarViewProps) {
  const nav = useCalendarNav('month');
  const [popover, setPopover] = useState<{ assignment: CalendarAssignment; rect: DOMRect } | null>(null);

  const handleAssignmentClick = (assignment: CalendarAssignment, anchorRect: DOMRect) => {
    setPopover({ assignment, rect: anchorRect });
  };

  const handleDayClick = (date: Date) => {
    nav.goToDate(date);
    nav.setViewMode('day');
  };

  // Filter assignments to visible range
  const visibleAssignments = useMemo(() => {
    let start: Date, end: Date;
    switch (nav.viewMode) {
      case 'month': {
        // Include entire grid (42 cells), not just the month
        const first = new Date(nav.currentDate.getFullYear(), nav.currentDate.getMonth(), 1);
        let dow = first.getDay();
        if (dow === 0) dow = 7;
        start = addDays(first, -(dow - 1));
        end = addDays(start, 42);
        break;
      }
      case 'week': {
        start = getMonday(nav.currentDate);
        end = addDays(start, 7);
        break;
      }
      case '3day': {
        start = new Date(nav.currentDate.getFullYear(), nav.currentDate.getMonth(), nav.currentDate.getDate());
        end = addDays(start, 3);
        break;
      }
      case 'day': {
        start = new Date(nav.currentDate.getFullYear(), nav.currentDate.getMonth(), nav.currentDate.getDate());
        end = addDays(start, 1);
        break;
      }
    }
    return assignments.filter(a => {
      const dk = dateKey(a.dueDate);
      const sk = dateKey(start);
      const ek = dateKey(end);
      return dk >= sk && dk < ek;
    });
  }, [assignments, nav.currentDate, nav.viewMode]);

  // Build dates arrays for week/3-day views
  const weekDates = useMemo(() => {
    if (nav.viewMode === 'week') {
      const mon = getMonday(nav.currentDate);
      return Array.from({ length: 7 }, (_, i) => addDays(mon, i));
    }
    if (nav.viewMode === '3day') {
      const start = new Date(nav.currentDate.getFullYear(), nav.currentDate.getMonth(), nav.currentDate.getDate());
      return Array.from({ length: 3 }, (_, i) => addDays(start, i));
    }
    return [];
  }, [nav.currentDate, nav.viewMode]);

  // Filter for day view
  const dayAssignments = useMemo(() => {
    if (nav.viewMode !== 'day') return [];
    const dk = dateKey(nav.currentDate);
    return assignments.filter(a => dateKey(a.dueDate) === dk);
  }, [assignments, nav.currentDate, nav.viewMode]);

  return (
    <div className="parent-calendar">
      <CalendarHeader
        headerLabel={nav.headerLabel}
        viewMode={nav.viewMode}
        onViewModeChange={nav.setViewMode}
        onPrev={nav.goPrev}
        onNext={nav.goNext}
        onToday={nav.goToday}
      />

      {nav.viewMode === 'month' && (
        <CalendarMonthGrid
          currentDate={nav.currentDate}
          assignments={visibleAssignments}
          onAssignmentClick={handleAssignmentClick}
          onDayClick={handleDayClick}
        />
      )}

      {(nav.viewMode === 'week' || nav.viewMode === '3day') && (
        <CalendarWeekGrid
          dates={weekDates}
          assignments={visibleAssignments}
          onAssignmentClick={handleAssignmentClick}
        />
      )}

      {nav.viewMode === 'day' && (
        <CalendarDayGrid
          date={nav.currentDate}
          assignments={dayAssignments}
          onAssignmentClick={handleAssignmentClick}
        />
      )}

      {popover && (
        <CalendarEntryPopover
          assignment={popover.assignment}
          anchorRect={popover.rect}
          onClose={() => setPopover(null)}
          onCreateStudyGuide={(a) => { setPopover(null); onCreateStudyGuide(a); }}
        />
      )}
    </div>
  );
}
