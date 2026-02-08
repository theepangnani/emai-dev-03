interface ParentActionBarProps {
  onAddChild: () => void;
  onAddCourse: () => void;
  onCreateStudyGuide: () => void;
}

export function ParentActionBar({ onAddChild, onAddCourse, onCreateStudyGuide }: ParentActionBarProps) {
  return (
    <div className="parent-action-bar">
      <button className="action-icon-btn" onClick={onAddChild}>
        <span className="action-icon">+</span>
        Add Child
      </button>
      <button className="action-icon-btn" onClick={onAddCourse}>
        <span className="action-icon">+</span>
        Add Course
      </button>
      <button className="action-icon-btn" onClick={onCreateStudyGuide}>
        <span className="action-icon">+</span>
        Create Study Guide
      </button>
    </div>
  );
}
