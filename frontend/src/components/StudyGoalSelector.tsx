import { useState } from 'react'

export const STUDY_GOALS = [
  { value: 'upcoming_test', label: 'Upcoming Test' },
  { value: 'final_exam', label: 'Final Exam' },
  { value: 'homework_help', label: 'Homework Help' },
  { value: 'general_review', label: 'General Review' },
  { value: 'concept_mastery', label: 'Concept Mastery' },
] as const

interface StudyGoalSelectorProps {
  onChange: (goal: string, focus?: string) => void
  defaultGoal?: string
  disabled?: boolean
}

export default function StudyGoalSelector({
  onChange,
  defaultGoal = '',
  disabled,
}: StudyGoalSelectorProps) {
  const [goal, setGoal] = useState(defaultGoal)
  const [focus, setFocus] = useState('')

  const handleGoalChange = (value: string) => {
    setGoal(value)
    onChange(value, focus || undefined)
  }

  const handleFocusChange = (value: string) => {
    setFocus(value)
    onChange(goal, value)
  }

  return (
    <div className="study-goal-selector">
      <label htmlFor="study-goal-select">What are you preparing for?</label>
      <select
        id="study-goal-select"
        value={goal}
        onChange={(e) => handleGoalChange(e.target.value)}
        disabled={disabled}
      >
        <option value="">Select a goal...</option>
        {STUDY_GOALS.map((g) => (
          <option key={g.value} value={g.value}>
            {g.label}
          </option>
        ))}
      </select>
      <div className="focus-field">
        <input
          type="text"
          placeholder="e.g., Chapter 4 only, skip intro topics"
          value={focus}
          onChange={(e) => handleFocusChange(e.target.value)}
          maxLength={200}
          disabled={disabled}
        />
        <span className="char-count">{focus.length}/200</span>
      </div>
    </div>
  )
}
