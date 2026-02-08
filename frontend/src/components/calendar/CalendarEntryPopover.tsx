import { useEffect, useRef } from 'react';
import type { CalendarAssignment } from './types';

interface CalendarEntryPopoverProps {
  assignment: CalendarAssignment;
  anchorRect: DOMRect;
  onClose: () => void;
  onCreateStudyGuide: (assignment: CalendarAssignment) => void;
}

export function CalendarEntryPopover({ assignment, anchorRect, onClose, onCreateStudyGuide }: CalendarEntryPopoverProps) {
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    const handleClick = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener('keydown', handleKey);
    document.addEventListener('mousedown', handleClick);
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.removeEventListener('mousedown', handleClick);
    };
  }, [onClose]);

  // Position below or above the anchor
  const spaceBelow = window.innerHeight - anchorRect.bottom;
  const top = spaceBelow > 280 ? anchorRect.bottom + 8 : anchorRect.top - 280;
  const left = Math.min(Math.max(anchorRect.left, 8), window.innerWidth - 320);

  return (
    <div
      ref={popoverRef}
      className="cal-popover"
      style={{ top, left }}
    >
      <div className="cal-popover-title">{assignment.title}</div>
      <div className="cal-popover-course">
        <span className="cal-entry-dot" style={{ background: assignment.courseColor }} />
        {assignment.courseName}
      </div>
      <div className="cal-popover-due">
        Due: {assignment.dueDate.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
        {' at '}
        {assignment.dueDate.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}
      </div>
      {assignment.description && (
        <div className="cal-popover-desc">
          {assignment.description.length > 200
            ? assignment.description.slice(0, 200) + '...'
            : assignment.description}
        </div>
      )}
      {assignment.maxPoints != null && (
        <div className="cal-popover-points">{assignment.maxPoints} points</div>
      )}
      {assignment.childName && (
        <div className="cal-popover-child">Student: {assignment.childName}</div>
      )}
      <button
        className="cal-popover-action"
        onClick={() => onCreateStudyGuide(assignment)}
      >
        Create Study Guide
      </button>
    </div>
  );
}
