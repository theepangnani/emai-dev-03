import './ClassificationBar.css';

const MATERIAL_TYPE_LABELS: Record<string, string> = {
  teacher_notes: 'Teacher Notes',
  course_syllabus: 'Syllabus',
  past_exam: 'Past Exam',
  mock_exam: 'Mock Exam',
  project_brief: 'Assignment',
  lab_experiment: 'Lab Material',
  textbook_excerpt: 'Class Material',
  worksheet: 'Worksheet',
  student_test: 'Student Test',
  quiz_paper: 'Quiz',
  custom: 'Document',
};

export function getMaterialTypeLabel(documentType: string | null): string {
  if (!documentType) return 'Document';
  return MATERIAL_TYPE_LABELS[documentType] ?? 'Document';
}

interface ClassificationBarProps {
  detectedSubject: string | null;
  confidence: number;
  childName: string | null;
  materialTypeDisplay: string | null;
  isClassifying: boolean;
  onEditClick: () => void;
}

export function ClassificationBar({
  detectedSubject,
  confidence,
  childName,
  materialTypeDisplay,
  isClassifying,
  onEditClick,
}: ClassificationBarProps) {
  if (isClassifying) {
    return (
      <div className="classification-bar classification-bar--loading" aria-busy="true" aria-live="polite">
        <span className="classification-bar__text">Analyzing your document...</span>
      </div>
    );
  }

  const label = materialTypeDisplay ?? 'Document';
  const hasClassification = confidence > 0 && detectedSubject;

  if (!hasClassification) {
    return (
      <div className="classification-bar classification-bar--unknown">
        <span className="classification-bar__text">
          We couldn&apos;t determine the document type.
        </span>
        <button type="button" className="classification-bar__link" onClick={onEditClick}>
          Tell us what it is
        </button>
      </div>
    );
  }

  const isHighConfidence = confidence >= 0.8;
  const verb = isHighConfidence ? 'looks like' : 'might be';
  const forChild = childName ? (
    <>
      {' '}for <strong>{childName}</strong>
    </>
  ) : null;

  const linkText = isHighConfidence ? 'Not right?' : 'Confirm or change';

  return (
    <div
      className={`classification-bar ${isHighConfidence ? 'classification-bar--high' : 'classification-bar--low'}`}
    >
      <span className="classification-bar__text">
        This {verb} a <strong>{detectedSubject} {label}</strong>
        {forChild}.
      </span>
      <button type="button" className="classification-bar__link" onClick={onEditClick}>
        {linkText}
      </button>
    </div>
  );
}
