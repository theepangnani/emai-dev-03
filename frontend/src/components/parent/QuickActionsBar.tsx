import './QuickActionsBar.css';

interface QuickActionsBarProps {
  onCreateMaterial: () => void;
  onCreateTask: () => void;
  onAddChild: () => void;
  onCreateCourse: () => void;
}

export function QuickActionsBar({
  onCreateMaterial,
  onCreateTask,
  onAddChild,
  onCreateCourse,
}: QuickActionsBarProps) {
  return (
    <div className="quick-actions-bar">
      <div className="quick-actions-primary">
        <button className="quick-action-btn primary" onClick={onCreateMaterial}>
          <span className="quick-action-icon icon-with-plus">{'\u{1F4DD}'}</span>
          <span className="quick-action-label">Create Study Material</span>
        </button>
        <button className="quick-action-btn primary" onClick={onCreateTask}>
          <span className="quick-action-icon icon-with-plus">{'\u2705'}</span>
          <span className="quick-action-label">Create Task</span>
        </button>
      </div>
      <div className="quick-actions-secondary">
        <button className="quick-action-btn secondary" onClick={onAddChild} title="Add Child">
          <span className="quick-action-icon icon-with-plus">{'\u{1F476}'}</span>
          <span className="quick-action-label">Child</span>
        </button>
        <button className="quick-action-btn secondary" onClick={onCreateCourse} title="Add Course">
          <span className="quick-action-icon icon-with-plus">{'\u{1F4DA}'}</span>
          <span className="quick-action-label">Course</span>
        </button>
      </div>
    </div>
  );
}
