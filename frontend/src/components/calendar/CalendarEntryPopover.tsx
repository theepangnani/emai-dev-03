import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import type { CalendarAssignment } from './types';

interface CalendarEntryPopoverProps {
  assignment: CalendarAssignment;
  anchorRect: DOMRect;
  onClose: () => void;
  onCreateStudyGuide: (assignment: CalendarAssignment) => void;
  onGoToCourse?: (courseId: number) => void;
  onViewStudyGuides?: () => void;
  generatingStudyId?: number | null;
}

export function CalendarEntryPopover({ assignment, anchorRect, onClose, onCreateStudyGuide, onGoToCourse, onViewStudyGuides, generatingStudyId }: CalendarEntryPopoverProps) {
  const navigate = useNavigate();
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
  const realTaskId = assignment.taskId ?? assignment.id;

  return (
    <div
      ref={popoverRef}
      className="cal-popover"
      style={{ top, left }}
    >
      <div
        className={`cal-popover-title${assignment.itemType === 'task' ? ' clickable' : ''}`}
        onClick={() => {
          if (assignment.itemType === 'task') {
            onClose();
            navigate(`/tasks/${realTaskId}`);
          }
        }}
      >
        {assignment.title}
      </div>
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
      <div className="cal-popover-actions">
        {assignment.itemType === 'task' && (
          <button
            className="cal-popover-icon-btn primary"
            title="See Task Details"
            onClick={() => { onClose(); navigate(`/tasks/${realTaskId}`); }}
          >
            &#128203;
          </button>
        )}
        <button
          className={`cal-popover-icon-btn${generatingStudyId === assignment.id ? ' loading' : ''}`}
          title={generatingStudyId === assignment.id ? 'Checking for existing material...' : 'Study'}
          disabled={generatingStudyId === assignment.id}
          onClick={() => onCreateStudyGuide(assignment)}
        >
          {generatingStudyId === assignment.id ? '\u23F3' : '\uD83D\uDCD6'}
        </button>
        {assignment.courseId > 0 && onGoToCourse && (
          <button
            className="cal-popover-icon-btn"
            title="Go to Class"
            onClick={() => onGoToCourse(assignment.courseId)}
          >
            &#127891;
          </button>
        )}
        {onViewStudyGuides && (
          <button
            className="cal-popover-icon-btn"
            title="View Study Guides"
            onClick={() => onViewStudyGuides()}
          >
            &#128218;
          </button>
        )}
      </div>
    </div>
  );
}
