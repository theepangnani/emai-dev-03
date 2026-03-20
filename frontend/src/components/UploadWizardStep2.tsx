import React, { useEffect, useState } from 'react';
import type { StudyMaterialType } from './UploadMaterialWizard';
import DocumentTypeSelector from './DocumentTypeSelector';
import StudyGoalSelector from './StudyGoalSelector';
import { classifyDocument } from '../api/study';

interface UploadWizardStep2Props {
  // Upload summary info
  selectedFiles: File[];
  studyContent: string;
  pastedImages: File[];
  // Tool selection
  selectedTypes: Set<StudyMaterialType>;
  onToggleType: (type: StudyMaterialType) => void;
  // Title
  studyTitle: string;
  onStudyTitleChange: (value: string) => void;
  // Focus prompt
  focusPrompt: string;
  onFocusPromptChange: (value: string) => void;
  // State
  isGenerating: boolean;
  // Strategy params
  documentType: string;
  onDocumentTypeChange: (type: string) => void;
  studyGoal: string;
  studyGoalText: string;
  onStudyGoalChange: (goal: string, focusText?: string) => void;
}

const TOOL_CARDS: { type: StudyMaterialType; icon: string; label: string; desc: string }[] = [
  { type: 'study_guide', icon: '\u{1F4D6}', label: 'Study Guide', desc: 'Summarized notes & key concepts' },
  { type: 'quiz',        icon: '\u{2753}',   label: 'Practice Quiz', desc: 'Test your knowledge' },
  { type: 'flashcards',  icon: '\u{1F0CF}',  label: 'Flashcards', desc: 'Quick review cards' },
];

function buildSummaryText(files: File[], content: string, pastedImages: File[]): string {
  const totalFiles = files.length + pastedImages.length;

  if (totalFiles === 0 && content.trim()) {
    return 'Pasted text ready';
  }

  if (totalFiles === 1) {
    const file = files[0] ?? pastedImages[0];
    return `${file.name} ready`;
  }

  if (totalFiles > 1) {
    return `${totalFiles} files ready`;
  }

  return 'Content ready';
}

const UploadWizardStep2: React.FC<UploadWizardStep2Props> = ({
  selectedFiles,
  studyContent,
  pastedImages,
  selectedTypes,
  onToggleType,
  studyTitle,
  onStudyTitleChange,
  focusPrompt,
  onFocusPromptChange,
  isGenerating,
  documentType,
  onDocumentTypeChange,
  studyGoal,
  studyGoalText,
  onStudyGoalChange,
}) => {
  const summaryText = buildSummaryText(selectedFiles, studyContent, pastedImages);
  const hasSelection = selectedTypes.size > 0;

  const [autoDetectedType, setAutoDetectedType] = useState<string | null>(null);
  const [autoConfidence, setAutoConfidence] = useState(0);

  // Auto-detect document type when step mounts
  useEffect(() => {
    let cancelled = false;
    const textContent = studyContent.trim();
    const filename = selectedFiles.length > 0 ? selectedFiles[0].name : '';
    if (!textContent && !filename) return;

    classifyDocument(textContent || '', filename || 'document')
      .then((result) => {
        if (cancelled) return;
        setAutoDetectedType(result.document_type);
        setAutoConfidence(result.confidence);
        // Only pre-select if no type already chosen
        if (!documentType) {
          onDocumentTypeChange(result.document_type);
        }
      })
      .catch(() => { /* auto-detect is best-effort */ });

    return () => { cancelled = true; };
    // Run only once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="upload-wizard-step">
      {/* Upload summary bar */}
      <div className="uw-summary-bar">
        <span className="uw-summary-icon">&#x2705;</span>
        <span className="uw-summary-text">{summaryText}</span>
      </div>

      {/* Document type selector */}
      <DocumentTypeSelector
        defaultType={documentType || autoDetectedType}
        confidence={autoConfidence}
        onChange={(type) => onDocumentTypeChange(type)}
        disabled={isGenerating}
      />

      {/* Study goal selector */}
      <StudyGoalSelector
        defaultGoal={studyGoal || null}
        defaultFocusText={studyGoalText || null}
        onChange={onStudyGoalChange}
        disabled={isGenerating}
      />

      {/* Tool selection cards */}
      <div className="uw-tool-cards">
        {TOOL_CARDS.map((card) => (
          <button
            key={card.type}
            type="button"
            className={`uw-tool-card${selectedTypes.has(card.type) ? ' selected' : ''}`}
            onClick={() => onToggleType(card.type)}
            disabled={isGenerating}
          >
            <span className="uw-tool-card-icon">{card.icon}</span>
            <span className="uw-tool-card-label">{card.label}</span>
            <span className="uw-tool-card-desc">{card.desc}</span>
          </button>
        ))}
      </div>

      {/* Title field */}
      <div className="uw-field">
        <label htmlFor="uw-title">Title</label>
        <input
          id="uw-title"
          type="text"
          value={studyTitle}
          onChange={(e) => onStudyTitleChange(e.target.value)}
          placeholder="e.g., Chapter 5 Review"
          disabled={isGenerating}
        />
      </div>

      {/* Naming preview for multi-file uploads */}
      {selectedFiles.length >= 2 && studyTitle && (
        <div className="upload-wizard-naming-preview">
          <p style={{ fontWeight: 600, fontSize: '0.8125rem', marginBottom: '0.375rem' }}>
            Materials that will be created:
          </p>
          <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.8125rem', color: '#64748b' }}>
            <li><strong>{studyTitle}</strong> (master)</li>
            {Array.from({ length: selectedFiles.length }, (_, i) => (
              <li key={i}>{studyTitle} — Part {i + 1}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Focus prompt — visible only when at least one tool is selected */}
      {hasSelection && (
        <div className="uw-field">
          <label htmlFor="uw-focus">Focus on... (optional)</label>
          <input
            id="uw-focus"
            type="text"
            value={focusPrompt}
            onChange={(e) => onFocusPromptChange(e.target.value)}
            placeholder="e.g., photosynthesis and the Calvin cycle"
            disabled={isGenerating}
          />
        </div>
      )}
    </div>
  );
};

export default UploadWizardStep2;
