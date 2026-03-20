import { useState } from 'react';
import './DocumentTypeSelector.css';

interface DocumentTypeSelectorProps {
  defaultType?: string | null;
  confidence?: number;
  onChange: (documentType: string, customLabel?: string) => void;
  disabled?: boolean;
}

const DOCUMENT_TYPES = [
  { value: 'teacher_notes', label: 'Teacher Notes / Handout', icon: '\u{1F4DD}' },
  { value: 'course_syllabus', label: 'Course Syllabus', icon: '\u{1F4CB}' },
  { value: 'past_exam', label: 'Past Exam / Test', icon: '\u{1F4C4}' },
  { value: 'mock_exam', label: 'Practice / Mock Exam', icon: '\u{270F}\u{FE0F}' },
  { value: 'project_brief', label: 'Project Brief', icon: '\u{1F4CC}' },
  { value: 'lab_experiment', label: 'Lab / Experiment', icon: '\u{1F52C}' },
  { value: 'textbook_excerpt', label: 'Textbook Excerpt', icon: '\u{1F4D6}' },
  { value: 'custom', label: 'Custom', icon: '\u{1F3F7}\u{FE0F}' },
] as const;

export default function DocumentTypeSelector({
  defaultType,
  confidence,
  onChange,
  disabled = false,
}: DocumentTypeSelectorProps) {
  const [selected, setSelected] = useState<string>(defaultType || '');
  const [customLabel, setCustomLabel] = useState('');

  const handleSelect = (value: string) => {
    if (disabled) return;
    setSelected(value);
    if (value !== 'custom') {
      onChange(value);
    }
  };

  const handleCustomChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.slice(0, 50);
    setCustomLabel(val);
    onChange('custom', val);
  };

  return (
    <div className="doc-type-selector">
      <div className="doc-type-selector__header">
        <h4 className="doc-type-selector__title">What type of document is this?</h4>
        {defaultType && confidence !== undefined && confidence > 0.5 && (
          <span className="doc-type-selector__auto-tag">Auto-detected</span>
        )}
      </div>
      <div className="doc-type-selector__chips">
        {DOCUMENT_TYPES.map((type) => (
          <button
            key={type.value}
            type="button"
            className={`doc-type-chip ${selected === type.value ? 'doc-type-chip--selected' : ''}`}
            onClick={() => handleSelect(type.value)}
            disabled={disabled}
            aria-pressed={selected === type.value}
          >
            <span className="doc-type-chip__icon" aria-hidden="true">{type.icon}</span>
            <span className="doc-type-chip__label">{type.label}</span>
          </button>
        ))}
      </div>
      {selected === 'custom' && (
        <input
          type="text"
          className="doc-type-selector__custom-input"
          placeholder="e.g., Unit 4 Vocabulary List"
          value={customLabel}
          onChange={handleCustomChange}
          maxLength={50}
          autoFocus
        />
      )}
    </div>
  );
}

export { DOCUMENT_TYPES };
export type { DocumentTypeSelectorProps };
