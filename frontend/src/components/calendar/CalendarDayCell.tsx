import { useState } from 'react';
import { CalendarEntry } from './CalendarEntry';
import type { CalendarAssignment } from './types';
import { isSameDay } from './types';

interface TouchDragHandlers {
  handleTouchStart: (e: React.TouchEvent, data: { id: number; itemType: string }) => void;
  handleTouchMove: (e: React.TouchEvent) => void;
  handleTouchEnd: () => void;
}

interface CalendarDayCellProps {
  date: Date;
  isCurrentMonth: boolean;
  assignments: CalendarAssignment[];
  onAssignmentClick: (assignment: CalendarAssignment, anchorRect: DOMRect) => void;
  onDayClick: (date: Date) => void;
  onTaskDrop?: (assignmentId: number, newDate: Date) => void;
  touchDrag?: TouchDragHandlers;
}

const MAX_VISIBLE = 3;

export function CalendarDayCell({ date, isCurrentMonth, assignments, onAssignmentClick, onDayClick, onTaskDrop, touchDrag }: CalendarDayCellProps) {
  const isToday = isSameDay(date, new Date());
  const overflow = assignments.length - MAX_VISIBLE;
  const [dragOver, setDragOver] = useState(false);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    // Only clear if leaving the cell entirely (not entering a child element)
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setDragOver(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    try {
      const data = JSON.parse(e.dataTransfer.getData('text/plain'));
      if (data.itemType === 'task' && onTaskDrop) {
        onTaskDrop(data.id, date);
      }
    } catch {
      // Invalid drag data
    }
  };

  return (
    <div
      className={`cal-day-cell${!isCurrentMonth ? ' outside-month' : ''}${isToday ? ' today' : ''}${dragOver ? ' cal-day-drag-over' : ''}`}
      data-drop-date={`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`}
      onDragOver={handleDragOver}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
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
            touchDrag={touchDrag}
          />
        ))}
        {overflow > 0 && (
          <div className="cal-day-more" role="button" tabIndex={0} onClick={() => onDayClick(date)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onDayClick(date); } }}>
            +{overflow} more
          </div>
        )}
      </div>
    </div>
  );
}
