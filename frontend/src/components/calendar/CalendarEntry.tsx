import { useState, useRef } from 'react';
import type { CalendarAssignment } from './types';
import { TASK_PRIORITY_COLORS } from './types';

interface TouchDragHandlers {
  handleTouchStart: (e: React.TouchEvent, data: { id: number; itemType: string }) => void;
  handleTouchMove: (e: React.TouchEvent) => void;
  handleTouchEnd: () => void;
}

interface CalendarEntryProps {
  assignment: CalendarAssignment;
  variant: 'chip' | 'card';
  onClick: (e: React.MouseEvent) => void;
  touchDrag?: TouchDragHandlers;
}

export function CalendarEntry({ assignment, variant, onClick, touchDrag }: CalendarEntryProps) {
  const isTask = assignment.itemType === 'task';
  const color = isTask
    ? TASK_PRIORITY_COLORS[assignment.priority || 'medium']
    : assignment.courseColor;
  const completedClass = isTask && assignment.isCompleted ? ' cal-entry-completed' : '';
  const [dragging, setDragging] = useState(false);
  const didDragRef = useRef(false);

  const handleDragStart = (e: React.DragEvent) => {
    e.dataTransfer.setData('text/plain', JSON.stringify({ id: assignment.id, itemType: 'task' }));
    e.dataTransfer.effectAllowed = 'move';
    setDragging(true);
    didDragRef.current = true;
  };

  const handleDragEnd = () => {
    setDragging(false);
    // Reset drag flag after a tick so the subsequent click is suppressed
    setTimeout(() => { didDragRef.current = false; }, 0);
  };

  const touchProps = isTask && touchDrag ? {
    onTouchStart: (e: React.TouchEvent) => touchDrag.handleTouchStart(e, { id: assignment.id, itemType: 'task' }),
    onTouchMove: touchDrag.handleTouchMove,
    onTouchEnd: touchDrag.handleTouchEnd,
  } : {};

  const dragProps = isTask ? {
    draggable: true,
    onDragStart: handleDragStart,
    onDragEnd: handleDragEnd,
    ...touchProps,
  } : {};

  const draggingClass = dragging ? ' cal-entry-dragging' : '';

  const guardedClick = (e: React.MouseEvent) => {
    if (didDragRef.current) return; // suppress click after drag
    onClick(e);
  };

  if (variant === 'chip') {
    return (
      <div
        className={`cal-entry-chip${isTask ? ' cal-entry-task' : ''}${completedClass}${draggingClass}`}
        style={{ background: `${color}18` }}
        onClick={guardedClick}
        title={assignment.title}
        {...dragProps}
      >
        <span className="cal-entry-dot" style={{ background: color }} />
        <span className="cal-entry-chip-title">{assignment.title}</span>
        {assignment.childName && (
          <span className="cal-entry-chip-child">{assignment.childName.split(' ')[0]}</span>
        )}
      </div>
    );
  }

  return (
    <div
      className={`cal-entry-card${isTask ? ' cal-entry-task' : ''}${completedClass}${draggingClass}`}
      style={{ borderLeftColor: color }}
      onClick={guardedClick}
      {...dragProps}
    >
      <div className="cal-entry-title">{assignment.title}</div>
      <div className="cal-entry-meta">
        <span className="cal-entry-dot" style={{ background: color }} />
        {isTask ? (assignment.priority || 'medium') + ' priority' : assignment.courseName}
        {assignment.dueDate && (
          <span className="cal-entry-time">
            {assignment.dueDate.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}
          </span>
        )}
      </div>
      {assignment.childName && (
        <div className="cal-entry-child">{assignment.childName}</div>
      )}
    </div>
  );
}
