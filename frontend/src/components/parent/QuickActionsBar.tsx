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
      <button className="quick-action-btn" onClick={onCreateMaterial}>
        <span className="quick-action-icon">{'\uD83D\uDCC4'}</span>
        <span className="quick-action-label">Material</span>
      </button>
      <button className="quick-action-btn" onClick={onCreateTask}>
        <span className="quick-action-icon">{'\u2705'}</span>
        <span className="quick-action-label">Task</span>
      </button>
      <button className="quick-action-btn" onClick={onAddChild}>
        <span className="quick-action-icon">{'\uD83D\uDC76'}</span>
        <span className="quick-action-label">Child</span>
      </button>
      <button className="quick-action-btn" onClick={onCreateCourse}>
        <span className="quick-action-icon">{'\uD83C\uDF93'}</span>
        <span className="quick-action-label">Course</span>
      </button>
    </div>
  );
}
