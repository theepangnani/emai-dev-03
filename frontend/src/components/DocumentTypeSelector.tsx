import { useState } from 'react'

export const DOCUMENT_TYPES = [
  { value: 'teacher_notes', label: 'Teacher Notes / Handout' },
  { value: 'past_exam', label: 'Past Exam / Test' },
  { value: 'textbook_excerpt', label: 'Textbook Excerpt' },
  { value: 'lab_experiment', label: 'Lab / Experiment' },
  { value: 'lecture_slides', label: 'Lecture Slides' },
  { value: 'worksheet', label: 'Worksheet' },
  { value: 'reading_material', label: 'Reading Material' },
  { value: 'custom', label: 'Custom' },
] as const

interface DocumentTypeSelectorProps {
  onChange: (value: string) => void
  defaultType?: string
  confidence?: number
  disabled?: boolean
}

export default function DocumentTypeSelector({
  onChange,
  defaultType,
  confidence,
  disabled,
}: DocumentTypeSelectorProps) {
  const [selected, setSelected] = useState<string | null>(defaultType ?? null)
  const [customText, setCustomText] = useState('')

  const handleClick = (value: string) => {
    if (disabled) return
    setSelected(value)
    if (value === 'custom') {
      onChange(customText || value)
    } else {
      onChange(value)
    }
  }

  const showAutoDetected = defaultType && confidence !== undefined && confidence >= 0.7

  return (
    <div className="document-type-selector">
      <h4>What type of document is this?</h4>
      {showAutoDetected && <span className="auto-detected-badge">Auto-detected</span>}
      <div className="document-type-chips">
        {DOCUMENT_TYPES.map((type) => (
          <button
            key={type.value}
            type="button"
            className={`chip ${selected === type.value ? 'selected' : ''}`}
            aria-pressed={selected === type.value}
            disabled={disabled}
            onClick={() => handleClick(type.value)}
          >
            {type.label}
          </button>
        ))}
      </div>
      {selected === 'custom' && (
        <input
          type="text"
          className="custom-type-input"
          placeholder="e.g., Unit 4 Vocabulary List"
          value={customText}
          onChange={(e) => {
            setCustomText(e.target.value)
            onChange(e.target.value || 'custom')
          }}
        />
      )}
    </div>
  )
}
