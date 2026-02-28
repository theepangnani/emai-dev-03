import type { CourseContentItem } from '../../api/client';
import './MaterialHeader.css';

interface MaterialHeaderProps {
  content: CourseContentItem;
  onCreateTask: () => void;
  onEdit: () => void;
  onArchive: () => void;
}

export function MaterialHeader({
  content,
  onCreateTask,
  onEdit,
  onArchive,
}: MaterialHeaderProps) {
  return (
    <div className="cm-detail-header">
      <div className="cm-detail-title-row">
        <h2>{content.title}</h2>
        {content.course_name && (
          <span className="cm-course-badge">{content.course_name}</span>
        )}
      </div>
      <div className="cm-detail-meta">
        {content.course_name && <span className="cm-type-badge">{content.course_name}</span>}
        <span>{new Date(content.created_at).toLocaleDateString()}</span>
        <div className="cm-header-icon-actions">
          <button className="cm-icon-btn cm-icon-btn-task" title="Create Task" aria-label="Create task" onClick={onCreateTask}>
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <rect x="3" y="2" width="14" height="16" rx="2" stroke="currentColor" strokeWidth="1.6"/>
              <path d="M7 7h6M7 10.5h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              <circle cx="14.5" cy="14.5" r="4.5" fill="var(--color-accent-strong, #2a9fa8)"/>
              <path d="M14.5 12.5v4M12.5 14.5h4" stroke="#fff" strokeWidth="1.4" strokeLinecap="round"/>
            </svg>
          </button>
          <button className="cm-icon-btn" title="Edit" aria-label="Edit material" onClick={onEdit}>&#9998;</button>
          <button className="cm-icon-btn" title="Archive" aria-label="Archive material" onClick={onArchive}>&#128465;</button>
        </div>
      </div>
    </div>
  );
}
