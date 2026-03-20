import { useState, useEffect } from 'react';
import { useFocusTrap } from '../utils/useFocusTrap';
import { GenerationSpinner } from './GenerationSpinner';
import './GenerateSubGuideModal.css';

interface GenerateSubGuideModalProps {
  open: boolean;
  selectedText: string;
  onClose: () => void;
  onGenerate: (guideType: string, customPrompt?: string, documentType?: string, studyGoal?: string) => Promise<void>;
  aiAvailable: boolean;
  aiRemaining: number;
  documentType?: string;  // From parent course content
  studyGoal?: string;     // From parent course content
}

const GUIDE_TYPES = [
  {
    id: 'study_guide',
    title: 'Study Guide',
    description: 'Deeper explanation of this topic',
    icon: (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M4 6.5C4 5.12 5.12 4 6.5 4H12V24H6.5C5.12 24 4 22.88 4 21.5V6.5Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M12 4H21.5C22.88 4 24 5.12 24 6.5V21.5C24 22.88 22.88 24 21.5 24H12V4Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M8 9H10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
        <path d="M16 9H20" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
        <path d="M16 13H20" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
        <path d="M16 17H20" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: 'quiz',
    title: 'Quiz',
    description: 'Practice questions to test knowledge',
    icon: (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="4" y="4" width="20" height="20" rx="3" stroke="currentColor" strokeWidth="1.8"/>
        <path d="M9 10L11 12L15 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M9 18H11" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
        <path d="M15 18H19" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
        <path d="M15 14H19" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: 'flashcards',
    title: 'Flashcards',
    description: 'Key terms and definitions',
    icon: (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="3" y="7" width="18" height="14" rx="2.5" stroke="currentColor" strokeWidth="1.8"/>
        <rect x="7" y="4" width="18" height="14" rx="2.5" stroke="currentColor" strokeWidth="1.8" fill="var(--subguide-card-bg, var(--color-surface, #fff))"/>
        <path d="M11 10H21" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
        <path d="M11 14H17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
      </svg>
    ),
  },
];

export function GenerateSubGuideModal({
  open,
  selectedText,
  onClose,
  onGenerate,
  aiAvailable,
  aiRemaining,
  documentType,
  studyGoal,
}: GenerateSubGuideModalProps) {
  const [selectedType, setSelectedType] = useState('study_guide');
  const [customPrompt, setCustomPrompt] = useState('');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const trapRef = useFocusTrap(open, onClose);

  // Reset state when modal opens
  useEffect(() => {
    if (open) {
      setSelectedType('study_guide');
      setCustomPrompt('');
      setGenerating(false);
      setError('');
    }
  }, [open]);

  if (!open) return null;

  const truncatedText =
    selectedText.length > 200
      ? selectedText.slice(0, 200) + '...'
      : selectedText;

  const handleGenerate = async () => {
    setGenerating(true);
    setError('');
    try {
      await onGenerate(selectedType, customPrompt || undefined, documentType, studyGoal);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Generation failed. Please try again.'
      );
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="modal-overlay subguide-overlay" onClick={onClose} data-testid="generate-sub-guide-modal">
      <div
        ref={trapRef}
        className="subguide-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="subguide-title"
        onClick={(e) => e.stopPropagation()}
        data-testid="subguide-modal"
      >
        {/* Header */}
        <div className="subguide-header">
          <h2 id="subguide-title">Generate Sub-Guide</h2>
          <button
            className="subguide-close"
            onClick={onClose}
            aria-label="Close"
            type="button"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M4.5 4.5L13.5 13.5M13.5 4.5L4.5 13.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="subguide-body">
          {/* Selected text preview */}
          <div className="subguide-section">
            <label className="subguide-label">Selected Text</label>
            <blockquote className="subguide-preview" data-testid="selected-text-preview">{truncatedText}</blockquote>
          </div>

          {/* Type selection */}
          <div className="subguide-section">
            <label className="subguide-label">Guide Type</label>
            <div className="subguide-types" role="radiogroup" aria-label="Guide type">
              {GUIDE_TYPES.map((type) => (
                <button
                  key={type.id}
                  type="button"
                  role="radio"
                  className={`subguide-type-card${selectedType === type.id ? ' selected' : ''}`}
                  onClick={() => setSelectedType(type.id)}
                  aria-checked={selectedType === type.id}
                  data-testid={`type-${type.id}`}
                >
                  <span className="subguide-type-icon">{type.icon}</span>
                  <span className="subguide-type-title">{type.title}</span>
                  <span className="subguide-type-desc">{type.description}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Optional focus prompt */}
          <div className="subguide-section">
            <label className="subguide-label" htmlFor="subguide-prompt">
              Focus Prompt <span className="subguide-optional">(optional)</span>
            </label>
            <input
              id="subguide-prompt"
              type="text"
              className="subguide-input"
              placeholder="e.g., make it harder, explain for grade 4"
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              disabled={generating}
              data-testid="custom-prompt-input"
            />
          </div>

          {/* Error message */}
          {error && <p className="subguide-error" data-testid="subguide-error">{error}</p>}
        </div>

        {/* Footer */}
        <div className="subguide-footer">
          <span className="subguide-credits" data-testid="credits-info">
            Uses 1 AI credit &middot; {aiRemaining} remaining
          </span>
          <div className="subguide-actions">
            <button
              type="button"
              className="subguide-cancel"
              onClick={onClose}
              disabled={generating}
              data-testid="cancel-btn"
            >
              Cancel
            </button>
            <button
              type="button"
              className="subguide-generate"
              onClick={handleGenerate}
              disabled={!aiAvailable || generating}
              data-testid="generate-btn"
            >
              {generating ? (
                <>
                  <GenerationSpinner size="sm" />
                  Generating&hellip;
                </>
              ) : (
                'Generate'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
