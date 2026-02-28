import './QuickActionBar.css';

interface QuickActionBarProps {
  onUploadMaterial: () => void;
  onCreateTask: () => void;
  onStudyGuide: () => void;
}

export function QuickActionBar({
  onUploadMaterial,
  onCreateTask,
  onStudyGuide,
}: QuickActionBarProps) {
  return (
    <div className="quick-action-bar" role="toolbar" aria-label="Quick actions">
      <button className="quick-action-card" onClick={onUploadMaterial} type="button">
        <span className="quick-action-icon" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        </span>
        <span className="quick-action-label">Upload Material</span>
      </button>
      <button className="quick-action-card" onClick={onCreateTask} type="button">
        <span className="quick-action-icon" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 11 12 14 22 4" />
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
          </svg>
        </span>
        <span className="quick-action-label">Create Task</span>
      </button>
      <button className="quick-action-card" onClick={onStudyGuide} type="button">
        <span className="quick-action-icon" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
        </span>
        <span className="quick-action-label">Study Guide</span>
      </button>
    </div>
  );
}
