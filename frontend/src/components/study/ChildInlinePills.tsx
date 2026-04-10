import './ChildInlinePills.css';

interface ChildInlinePillsProps {
  documentType: string | null;
  studyGoal?: string | null;
}

const TYPE_LABELS: Record<string, string> = {
  teacher_notes: 'Teacher Notes',
  course_syllabus: 'Syllabus',
  past_exam: 'Past Exam',
  mock_exam: 'Mock Exam',
  project_brief: 'Project Brief',
  lab_experiment: 'Lab / Experiment',
  textbook_excerpt: 'Textbook',
};

const GOAL_LABELS: Record<string, string> = {
  upcoming_test: 'Test Prep',
  final_exam: 'Final Exam',
  assignment: 'Assignment',
  lab_prep: 'Lab Prep',
  general_review: 'Review',
  discussion: 'Discussion',
  parent_review: 'Parent Review',
};

export default function ChildInlinePills({
  documentType,
  studyGoal,
}: ChildInlinePillsProps) {
  if (!documentType && !studyGoal) return null;

  return (
    <div className="child-inline-pills">
      {documentType && (
        <span className="child-pill child-pill--type">
          {TYPE_LABELS[documentType] || documentType}
        </span>
      )}
      {studyGoal && (
        <span className="child-pill child-pill--goal">
          {GOAL_LABELS[studyGoal] || studyGoal}
        </span>
      )}
    </div>
  );
}

export type { ChildInlinePillsProps };
