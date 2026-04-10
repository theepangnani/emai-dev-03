import './MaterialTypeSuggestionChips.css';

/* ── Types ──────────────────────────────────── */

export interface ChipAction {
  label: string;
  action: string;
  templateKey?: string;
  creditCost: number;
  variant: 'primary' | 'secondary' | 'subtle';
}

export interface MaterialTypeSuggestionChipsProps {
  documentType: string;
  detectedSubject: string | null;
  onChipClick: (action: string, templateKey?: string) => void;
  generatingAction: string | null;
  disabled: boolean;
  remainingCredits: number | null;
  atLimit: boolean;
}

/* ── Chip Set Definitions ───────────────────── */

const TEACHER_NOTES_CHIPS: ChipAction[] = [
  { label: 'Generate Worksheets', action: 'worksheet', creditCost: 1, variant: 'primary' },
  { label: 'Create Sample Test', action: 'practice_test', creditCost: 1, variant: 'secondary' },
  { label: 'Create Quiz', action: 'quiz', creditCost: 1, variant: 'secondary' },
  { label: 'Create Flashcards', action: 'flashcards', creditCost: 1, variant: 'secondary' },
  { label: 'High Level Summary', action: 'high_level_summary', creditCost: 0, variant: 'secondary' },
  { label: 'Full Study Guide', action: 'full_study_guide', creditCost: 1, variant: 'subtle' },
];

const PAST_EXAM_CHIPS: ChipAction[] = [
  { label: 'Create Practice Test', action: 'practice_test', creditCost: 1, variant: 'primary' },
  { label: 'Create Study Guide', action: 'study_guide', creditCost: 1, variant: 'secondary' },
  { label: 'Create Flashcards', action: 'flashcards', creditCost: 1, variant: 'secondary' },
  { label: 'Weak Area Analysis', action: 'weak_area', creditCost: 2, variant: 'secondary' },
];

const STUDENT_TEST_CHIPS: ChipAction[] = [
  { label: 'Create Practice Test', action: 'practice_test', creditCost: 1, variant: 'primary' },
  { label: 'Weak Area Analysis', action: 'weak_area', creditCost: 2, variant: 'secondary' },
  { label: 'Create Study Guide', action: 'study_guide', creditCost: 1, variant: 'secondary' },
  { label: 'Create Flashcards', action: 'flashcards', creditCost: 1, variant: 'secondary' },
];

const WORKSHEET_CHIPS: ChipAction[] = [
  { label: 'Generate More Worksheets', action: 'worksheet', creditCost: 1, variant: 'primary' },
  { label: 'Generate Answer Key', action: 'answer_key', creditCost: 0, variant: 'secondary' },
  { label: 'Create Quiz', action: 'quiz', creditCost: 1, variant: 'secondary' },
  { label: 'Create Flashcards', action: 'flashcards', creditCost: 1, variant: 'secondary' },
];

const PROJECT_BRIEF_CHIPS: ChipAction[] = [
  { label: 'Create Study Guide', action: 'study_guide', creditCost: 1, variant: 'primary' },
  { label: 'Create Flashcards', action: 'flashcards', creditCost: 1, variant: 'secondary' },
  { label: 'Ask Bot', action: 'ask_bot', creditCost: 0, variant: 'subtle' },
];

const CUSTOM_CHIPS: ChipAction[] = [
  { label: 'Create Study Guide', action: 'study_guide', creditCost: 1, variant: 'primary' },
  { label: 'Create Quiz', action: 'quiz', creditCost: 1, variant: 'secondary' },
  { label: 'Create Flashcards', action: 'flashcards', creditCost: 1, variant: 'secondary' },
];

const CHIP_SETS: Record<string, ChipAction[]> = {
  teacher_notes: TEACHER_NOTES_CHIPS,
  course_syllabus: TEACHER_NOTES_CHIPS,
  lab_experiment: TEACHER_NOTES_CHIPS,
  textbook_excerpt: TEACHER_NOTES_CHIPS,
  worksheet: WORKSHEET_CHIPS,
  past_exam: PAST_EXAM_CHIPS,
  mock_exam: PAST_EXAM_CHIPS,
  student_test: STUDENT_TEST_CHIPS,
  quiz_paper: STUDENT_TEST_CHIPS,
  project_brief: PROJECT_BRIEF_CHIPS,
  custom: CUSTOM_CHIPS,
};

/* ── Plain-English Headers ──────────────────── */

const HEADERS: Record<string, string> = {
  past_exam: "Your child had a test. Here's how we can help:",
  mock_exam: "Your child had a test. Here's how we can help:",
  student_test: "Your child had a test. Here's how we can help:",
  quiz_paper: "Your child had a test. Here's how we can help:",
  teacher_notes: "Your child's teacher shared notes. Here's what we can do:",
  course_syllabus: "Your child's teacher shared notes. Here's what we can do:",
  lab_experiment: "Your child's teacher shared notes. Here's what we can do:",
  textbook_excerpt: "Your child's teacher shared notes. Here's what we can do:",
  worksheet: "This is a worksheet. Want to do more with it?",
};

const DEFAULT_HEADER = "Here's what we can do with this document:";

/* ── Helpers ────────────────────────────────── */

function getChips(documentType: string): ChipAction[] {
  return CHIP_SETS[documentType] ?? CHIP_SETS.custom;
}

function getHeader(documentType: string): string {
  return HEADERS[documentType] ?? DEFAULT_HEADER;
}

/* ── Component ──────────────────────────────── */

export default function MaterialTypeSuggestionChips({
  documentType,
  detectedSubject: _detectedSubject,
  onChipClick,
  generatingAction,
  disabled,
  remainingCredits,
  atLimit,
}: MaterialTypeSuggestionChipsProps) {
  const chips = getChips(documentType);
  const header = getHeader(documentType);
  const isAnyGenerating = !!generatingAction;

  return (
    <div className="mt-chip-section">
      <p className="mt-chip-header">{header}</p>

      <div className="mt-chip-list">
        {chips.map((chip) => {
          const isThisGenerating = generatingAction === chip.action;
          const isDisabled = disabled || atLimit || (isAnyGenerating && !isThisGenerating);

          return (
            <button
              key={chip.action + chip.label}
              className={[
                'mt-chip',
                `mt-chip--${chip.variant}`,
                isDisabled && 'mt-chip--disabled',
                isThisGenerating && 'mt-chip--generating',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => onChipClick(chip.action, chip.templateKey)}
              disabled={isDisabled || isThisGenerating}
              aria-label={chip.label}
            >
              {isThisGenerating && <span className="mt-chip-spinner" />}
              <span className="mt-chip-label">
                {chip.label}
                {chip.creditCost >= 2 && (
                  <span className="mt-chip-cost">
                    {' \u00B7 '}
                    {chip.creditCost} credits
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>

      {remainingCredits !== null && (
        <p className="mt-chip-credits">
          You have {remainingCredits} credit{remainingCredits !== 1 ? 's' : ''} remaining
        </p>
      )}
    </div>
  );
}

export { getChips, getHeader, CHIP_SETS };
