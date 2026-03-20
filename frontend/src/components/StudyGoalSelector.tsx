import { useState } from 'react';
import './StudyGoalSelector.css';

interface StudyGoalSelectorProps {
  defaultGoal?: string | null;
  defaultFocusText?: string | null;
  onChange: (studyGoal: string, focusText?: string) => void;
  disabled?: boolean;
}

const STUDY_GOALS = [
  { value: '', label: 'Select study goal (optional)' },
  { value: 'upcoming_test', label: 'Upcoming Test / Quiz' },
  { value: 'final_exam', label: 'Final Exam' },
  { value: 'assignment', label: 'Assignment / Project Submission' },
  { value: 'lab_prep', label: 'Lab Preparation / Report' },
  { value: 'general_review', label: 'General Review / Consolidation' },
  { value: 'discussion', label: 'In-class Discussion / Presentation' },
  { value: 'parent_review', label: 'Parent Review (parent-facing summary mode)' },
] as const;

export default function StudyGoalSelector({
  defaultGoal,
  defaultFocusText,
  onChange,
  disabled = false,
}: StudyGoalSelectorProps) {
  const [goal, setGoal] = useState(defaultGoal || '');
  const [focusText, setFocusText] = useState(defaultFocusText || '');

  const handleGoalChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setGoal(val);
    onChange(val, focusText || undefined);
  };

  const handleFocusChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.slice(0, 200);
    setFocusText(val);
    onChange(goal, val || undefined);
  };

  return (
    <div className="study-goal-selector">
      <label className="study-goal-selector__label" htmlFor="study-goal-dropdown">
        What are you preparing for?
      </label>
      <select
        id="study-goal-dropdown"
        className="study-goal-selector__dropdown"
        value={goal}
        onChange={handleGoalChange}
        disabled={disabled}
      >
        {STUDY_GOALS.map((g) => (
          <option key={g.value} value={g.value}>
            {g.label}
          </option>
        ))}
      </select>

      <div className="study-goal-selector__focus-field">
        <label className="study-goal-selector__focus-label" htmlFor="study-focus-input">
          Focus area <span className="study-goal-selector__optional">(optional)</span>
        </label>
        <input
          id="study-focus-input"
          type="text"
          className="study-goal-selector__focus-input"
          placeholder="Anything specific to focus on? (e.g., Chapter 4 only, quadratic equations, the water cycle)"
          value={focusText}
          onChange={handleFocusChange}
          maxLength={200}
          disabled={disabled}
        />
        <span className="study-goal-selector__char-count">
          {focusText.length}/200
        </span>
      </div>
    </div>
  );
}

export { STUDY_GOALS };
export type { StudyGoalSelectorProps };
