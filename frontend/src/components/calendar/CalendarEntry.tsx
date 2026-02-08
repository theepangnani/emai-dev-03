import type { CalendarAssignment } from './types';

interface CalendarEntryProps {
  assignment: CalendarAssignment;
  variant: 'chip' | 'card';
  onClick: (e: React.MouseEvent) => void;
}

export function CalendarEntry({ assignment, variant, onClick }: CalendarEntryProps) {
  if (variant === 'chip') {
    return (
      <div
        className="cal-entry-chip"
        style={{ background: `${assignment.courseColor}18` }}
        onClick={onClick}
        title={assignment.title}
      >
        <span className="cal-entry-dot" style={{ background: assignment.courseColor }} />
        <span className="cal-entry-chip-title">{assignment.title}</span>
      </div>
    );
  }

  return (
    <div
      className="cal-entry-card"
      style={{ borderLeftColor: assignment.courseColor }}
      onClick={onClick}
    >
      <div className="cal-entry-title">{assignment.title}</div>
      <div className="cal-entry-meta">
        <span className="cal-entry-dot" style={{ background: assignment.courseColor }} />
        {assignment.courseName}
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
