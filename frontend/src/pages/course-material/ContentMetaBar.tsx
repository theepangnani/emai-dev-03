import { useState, useRef, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import type { TaskItem } from '../../api/tasks';

interface ContentMetaBarProps {
  courseName?: string | null;
  createdAt?: string | null;
  linkedTasks?: TaskItem[];
  courseId?: number;
}

export function ContentMetaBar({ courseName, createdAt, linkedTasks = [], courseId }: ContentMetaBarProps) {
  const [classPopover, setClassPopover] = useState(false);
  const [tasksPopover, setTasksPopover] = useState(false);
  const classRef = useRef<HTMLSpanElement>(null);
  const tasksRef = useRef<HTMLSpanElement>(null);

  const closePopovers = useCallback(() => {
    setClassPopover(false);
    setTasksPopover(false);
  }, []);

  useEffect(() => {
    if (!classPopover && !tasksPopover) return;
    const handleClick = (e: MouseEvent) => {
      if (classRef.current?.contains(e.target as Node)) return;
      if (tasksRef.current?.contains(e.target as Node)) return;
      closePopovers();
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closePopovers();
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [classPopover, tasksPopover, closePopovers]);

  return (
    <div className="cm-guide-meta">
      {courseName && (
        <span className="cm-guide-meta-item cm-guide-meta-item--popover-anchor" ref={classRef}>
          <button
            type="button"
            className="cm-meta-popover-btn"
            onClick={() => { setClassPopover(v => !v); setTasksPopover(false); }}
          >
            <span className="cm-guide-meta-label">Class:</span> {courseName}
          </button>
          {classPopover && (
            <div className="cm-meta-popover">
              <div className="cm-meta-popover-title">{courseName}</div>
              {courseId && (
                <Link to={`/courses/${courseId}`} className="cm-meta-popover-link" onClick={closePopovers}>
                  View Course
                </Link>
              )}
            </div>
          )}
        </span>
      )}
      {createdAt && (
        <span className="cm-guide-meta-item">
          <span className="cm-guide-meta-label">Created:</span>{' '}
          {new Date(createdAt).toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })}
        </span>
      )}
      {linkedTasks.length > 0 ? (
        <span className="cm-guide-meta-item cm-guide-meta-item--popover-anchor" ref={tasksRef}>
          <button
            type="button"
            className="cm-meta-popover-btn"
            onClick={() => { setTasksPopover(v => !v); setClassPopover(false); }}
          >
            <span className="cm-guide-meta-label">Tasks:</span> {linkedTasks.length} linked
          </button>
          {tasksPopover && (
            <div className="cm-meta-popover cm-meta-popover--tasks">
              <div className="cm-meta-popover-title">Linked Tasks</div>
              <ul className="cm-meta-popover-task-list">
                {(() => { const today = new Date(); today.setHours(0, 0, 0, 0); return linkedTasks.map(task => {
                  const dateOnly = task.due_date?.substring(0, 10);
                  const d = dateOnly ? new Date(dateOnly + 'T00:00:00') : null;
                  const isOverdue = d ? d < today && !task.is_completed : false;
                  return (
                    <li key={task.id} className="cm-meta-popover-task">
                      <Link to={`/tasks/${task.id}`} className="cm-meta-popover-task-link" onClick={closePopovers}>
                        <span className={`cm-meta-popover-task-status ${task.is_completed ? 'cm-meta-popover-task-status--done' : isOverdue ? 'cm-meta-popover-task-status--overdue' : ''}`}>
                          {task.is_completed ? '\u2713' : isOverdue ? '!' : '\u25CB'}
                        </span>
                        <span className="cm-meta-popover-task-title">{task.title}</span>
                        {d && (
                          <span className={`cm-meta-popover-task-due ${isOverdue ? 'cm-meta-popover-task-due--overdue' : ''}`}>
                            {d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                          </span>
                        )}
                      </Link>
                    </li>
                  );
                }); })()}
              </ul>
            </div>
          )}
        </span>
      ) : (
        <span className="cm-guide-meta-item cm-guide-meta-item--muted">
          <span className="cm-guide-meta-label">Tasks:</span> No tasks linked
        </span>
      )}
    </div>
  );
}
