import DocumentTypeSelector from '../DocumentTypeSelector';
import StudyGoalSelector from '../StudyGoalSelector';
import './ClassificationOverridePanel.css';

interface ClassificationOverridePanelProps {
  documentType: string;
  studyGoal: string;
  studyGoalText: string;
  autoConfidence: number;
  onDocumentTypeChange: (type: string) => void;
  onStudyGoalChange: (goal: string, text?: string) => void;
  onGenerate: () => void;
  onClose: () => void;
  disabled?: boolean;
  atLimit?: boolean;
  hasSourceContent?: boolean;
}

export default function ClassificationOverridePanel({
  documentType,
  studyGoal,
  studyGoalText,
  autoConfidence,
  onDocumentTypeChange,
  onStudyGoalChange,
  onGenerate,
  onClose,
  disabled = false,
  atLimit = false,
  hasSourceContent = true,
}: ClassificationOverridePanelProps) {
  return (
    <div className="classification-override-panel">
      <div className="classification-override-panel__header">
        <h4>Customize generation</h4>
        <button
          type="button"
          className="classification-override-panel__close"
          onClick={onClose}
          aria-label="Close override panel"
        >
          {'\u2715'}
        </button>
      </div>
      <div className="classification-override-panel__body">
        <DocumentTypeSelector
          defaultType={documentType}
          confidence={autoConfidence}
          onChange={onDocumentTypeChange}
          disabled={disabled}
        />
        <StudyGoalSelector
          defaultGoal={studyGoal || null}
          defaultFocusText={studyGoalText || null}
          onChange={onStudyGoalChange}
          disabled={disabled}
        />
      </div>
      <div className="classification-override-panel__actions">
        <span className={atLimit ? 'ai-btn-disabled-wrapper' : ''}>
          <button
            className="cm-empty-generate-btn"
            onClick={onGenerate}
            disabled={disabled || !hasSourceContent || atLimit}
          >
            {'\u2728'} Generate Study Guide
          </button>
          {atLimit && <span className="ai-limit-tooltip">AI limit reached</span>}
        </span>
      </div>
    </div>
  );
}

export type { ClassificationOverridePanelProps };
