import { Link } from 'react-router-dom';
import type { TaskItem } from '../../api/tasks';

interface LinkedTasksBannerProps {
  tasks: TaskItem[];
}

function TaskListIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <rect x="3" y="2" width="14" height="16" rx="2" stroke="currentColor" strokeWidth="1.6"/>
      <path d="M7 7h6M7 10.5h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  );
}

export function LinkedTasksBanner({ tasks }: LinkedTasksBannerProps) {
  if (tasks.length === 0) return null;

  return (
    <div className="cm-linked-tasks">
      {tasks.map(task => (
        <Link key={task.id} to={`/tasks/${task.id}`} className="cm-linked-task">
          <span className="cm-linked-task-icon">
            <TaskListIcon />
          </span>
          <span className="cm-linked-task-title">{task.title}</span>
          {task.due_date && (() => {
            // Append T00:00:00 to date-only strings so JS parses as local midnight, not UTC
            const d = new Date(task.due_date.includes('T') ? task.due_date : task.due_date + 'T00:00:00');
            const isOverdue = d < new Date() && !task.is_completed;
            return (
              <span className={`cm-linked-task-due${isOverdue ? ' overdue' : ''}`}>
                Due: {d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
              </span>
            );
          })()}
          {task.is_completed && <span className="cm-linked-task-done">Done</span>}
        </Link>
      ))}
    </div>
  );
}
