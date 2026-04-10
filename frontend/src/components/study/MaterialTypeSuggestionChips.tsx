import './MaterialTypeSuggestionChips.css';

export interface ChipAction {
  label: string;
  action: string;
  icon: string;
  templateKey?: string;
}

interface MaterialTypeSuggestionChipsProps {
  chips: ChipAction[];
  onChipClick: (action: string, templateKey?: string) => void;
  disabled?: boolean;
  generatingAction?: string | null;
}

const CHIP_MAP: Record<string, ChipAction[]> = {
  teacher_notes: [
    { label: 'Study Guide', action: 'study_guide', icon: '\u{1F4D6}' },
    { label: 'Quick Quiz', action: 'quiz', icon: '\u{1F9E0}' },
    { label: 'Flashcards', action: 'flashcards', icon: '\u{1F3B4}' },
    { label: 'Key Concepts', action: 'study_guide', icon: '\u{1F4A1}', templateKey: 'key_concepts' },
  ],
  course_syllabus: [
    { label: 'Course Overview', action: 'study_guide', icon: '\u{1F4CB}', templateKey: 'course_overview' },
    { label: 'Study Plan', action: 'study_guide', icon: '\u{1F4C5}', templateKey: 'study_plan' },
    { label: 'Key Dates', action: 'study_guide', icon: '\u{1F4C6}', templateKey: 'key_dates' },
  ],
  past_exam: [
    { label: 'Practice Answers', action: 'study_guide', icon: '\u{270F}\u{FE0F}', templateKey: 'practice_answers' },
    { label: 'Topic Review', action: 'study_guide', icon: '\u{1F4D6}' },
    { label: 'Quick Quiz', action: 'quiz', icon: '\u{1F9E0}' },
  ],
  mock_exam: [
    { label: 'Practice Answers', action: 'study_guide', icon: '\u{270F}\u{FE0F}', templateKey: 'practice_answers' },
    { label: 'Study Guide', action: 'study_guide', icon: '\u{1F4D6}' },
    { label: 'Flashcards', action: 'flashcards', icon: '\u{1F3B4}' },
  ],
  project_brief: [
    { label: 'Project Plan', action: 'study_guide', icon: '\u{1F4CC}', templateKey: 'project_plan' },
    { label: 'Research Guide', action: 'study_guide', icon: '\u{1F50D}', templateKey: 'research_guide' },
    { label: 'Key Requirements', action: 'study_guide', icon: '\u{1F4CB}', templateKey: 'key_requirements' },
  ],
  lab_experiment: [
    { label: 'Lab Prep Guide', action: 'study_guide', icon: '\u{1F52C}', templateKey: 'lab_prep' },
    { label: 'Key Concepts', action: 'study_guide', icon: '\u{1F4A1}', templateKey: 'key_concepts' },
    { label: 'Quick Quiz', action: 'quiz', icon: '\u{1F9E0}' },
  ],
  textbook_excerpt: [
    { label: 'Study Guide', action: 'study_guide', icon: '\u{1F4D6}' },
    { label: 'Flashcards', action: 'flashcards', icon: '\u{1F3B4}' },
    { label: 'Quick Quiz', action: 'quiz', icon: '\u{1F9E0}' },
    { label: 'Key Concepts', action: 'study_guide', icon: '\u{1F4A1}', templateKey: 'key_concepts' },
  ],
};

const DEFAULT_CHIPS: ChipAction[] = [
  { label: 'Study Guide', action: 'study_guide', icon: '\u{1F4D6}' },
  { label: 'Quick Quiz', action: 'quiz', icon: '\u{1F9E0}' },
  { label: 'Flashcards', action: 'flashcards', icon: '\u{1F3B4}' },
];

export function getChipsForType(documentType: string | null): ChipAction[] {
  if (!documentType) return DEFAULT_CHIPS;
  return CHIP_MAP[documentType] || DEFAULT_CHIPS;
}

export default function MaterialTypeSuggestionChips({
  chips,
  onChipClick,
  disabled = false,
  generatingAction = null,
}: MaterialTypeSuggestionChipsProps) {
  if (!chips.length) return null;

  const isAnyGenerating = !!generatingAction;

  return (
    <div className="mt-suggestion-chips">
      {chips.map((chip) => {
        const isThis = generatingAction === (chip.templateKey || chip.action);
        return (
          <button
            key={chip.templateKey || chip.label}
            type="button"
            className={`mt-chip ${isThis ? 'mt-chip--generating' : ''}`}
            onClick={() => onChipClick(chip.action, chip.templateKey)}
            disabled={disabled || isAnyGenerating}
            title={chip.label}
          >
            {isThis && <span className="mt-chip-spinner" />}
            <span className="mt-chip-icon">{chip.icon}</span>
            <span className="mt-chip-label">{chip.label}</span>
          </button>
        );
      })}
    </div>
  );
}
