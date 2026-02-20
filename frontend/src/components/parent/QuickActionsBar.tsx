import './QuickActionsBar.css';

interface QuickActionsBarProps {
  onCreateMaterial: () => void;
  onCreateTask: () => void;
}

export function QuickActionsBar({
  onCreateMaterial,
  onCreateTask,
}: QuickActionsBarProps) {
  return (
    <div className="quick-actions-bar">
      <button className="quick-action-btn secondary" onClick={onCreateMaterial}>
        <span className="quick-action-icon icon-with-plus">{'\u{1F4DD}'}</span>
        <span className="quick-action-label">Upload Documents</span>
      </button>
      <button className="quick-action-btn secondary" onClick={onCreateTask}>
        <span className="quick-action-icon icon-with-plus">{'\u2705'}</span>
        <span className="quick-action-label">Create Task</span>
      </button>
    </div>
  );
}
