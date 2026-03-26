import type { TaskItem } from '../../api/tasks';

interface ContentMetaBarProps {
  courseName?: string | null;
  createdAt?: string | null;
  linkedTasks?: TaskItem[];
}

export function ContentMetaBar({ courseName, createdAt, linkedTasks = [] }: ContentMetaBarProps) {
  if (!courseName && !createdAt && linkedTasks.length === 0) return null;

  return (
    <div className="cm-guide-meta">
      {courseName && (
        <span className="cm-guide-meta-item">
          <span className="cm-guide-meta-label">Class:</span> {courseName}
        </span>
      )}
      {createdAt && (
        <span className="cm-guide-meta-item">
          <span className="cm-guide-meta-label">Created:</span>{' '}
          {new Date(createdAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
        </span>
      )}
      {linkedTasks.length > 0 ? (
        <span className="cm-guide-meta-item">
          <span className="cm-guide-meta-label">Tasks:</span> {linkedTasks.length} linked
        </span>
      ) : (
        <span className="cm-guide-meta-item cm-guide-meta-item--muted">
          <span className="cm-guide-meta-label">Tasks:</span> No tasks linked
        </span>
      )}
    </div>
  );
}
