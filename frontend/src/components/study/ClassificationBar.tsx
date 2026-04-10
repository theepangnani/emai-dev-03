import './ClassificationBar.css';

interface ClassificationBarProps {
  documentType: string | null;
  confidence: number;
  isLoading?: boolean;
  onOverrideClick?: () => void;
}

const TYPE_LABELS: Record<string, string> = {
  teacher_notes: 'Teacher Notes / Handout',
  course_syllabus: 'Course Syllabus',
  past_exam: 'Past Exam / Test',
  mock_exam: 'Practice / Mock Exam',
  project_brief: 'Project Brief',
  lab_experiment: 'Lab / Experiment',
  textbook_excerpt: 'Textbook Excerpt',
};

export default function ClassificationBar({
  documentType,
  confidence,
  isLoading = false,
  onOverrideClick,
}: ClassificationBarProps) {
  if (isLoading) {
    return (
      <div className="classification-bar classification-bar--loading">
        <div className="classification-bar__skeleton" />
      </div>
    );
  }

  if (!documentType) return null;

  const label = TYPE_LABELS[documentType] || documentType;
  const pct = Math.round(confidence * 100);

  return (
    <div className="classification-bar">
      <span className="classification-bar__text">
        This looks like <strong>{label}</strong>
        <span className="classification-bar__confidence">({pct}% confidence)</span>
      </span>
      {onOverrideClick && (
        <button
          type="button"
          className="classification-bar__override-btn"
          onClick={onOverrideClick}
        >
          Not right? Change
        </button>
      )}
    </div>
  );
}

export type { ClassificationBarProps };
