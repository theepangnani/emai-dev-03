import { useState } from 'react';

interface GenerateSubGuideModalProps {
  open: boolean;
  selectedText: string;
  onClose: () => void;
  onGenerate: (guideType: string, customPrompt?: string) => Promise<void>;
  aiAvailable: boolean;
  aiRemaining: number;
}

export function GenerateSubGuideModal({ open, selectedText, onClose, onGenerate, aiAvailable, aiRemaining }: GenerateSubGuideModalProps) {
  const [selectedType, setSelectedType] = useState('study_guide');
  const [customPrompt, setCustomPrompt] = useState('');
  const [generating, setGenerating] = useState(false);

  if (!open) return null;

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await onGenerate(selectedType, customPrompt || undefined);
    } finally {
      setGenerating(false);
    }
  };

  const preview = selectedText.length > 200 ? selectedText.slice(0, 200) + '...' : selectedText;

  return (
    <div className="modal-overlay" onClick={onClose} data-testid="generate-sub-guide-modal">
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <h3>Generate Study Material</h3>
        <p data-testid="selected-text-preview">{preview}</p>
        <div role="radiogroup" aria-label="Guide type">
          {(['study_guide', 'quiz', 'flashcards'] as const).map(t => (
            <button
              key={t}
              role="radio"
              aria-checked={selectedType === t}
              onClick={() => setSelectedType(t)}
              data-testid={`type-${t}`}
            >
              {t === 'study_guide' ? 'Study Guide' : t === 'quiz' ? 'Quiz' : 'Flashcards'}
            </button>
          ))}
        </div>
        <input
          type="text"
          value={customPrompt}
          onChange={e => setCustomPrompt(e.target.value)}
          placeholder="Focus prompt (optional)"
          data-testid="custom-prompt-input"
        />
        <p data-testid="credits-info">Uses 1 AI credit · {aiRemaining} remaining</p>
        <button onClick={onClose} data-testid="cancel-btn">Cancel</button>
        <button
          onClick={handleGenerate}
          disabled={!aiAvailable || generating}
          data-testid="generate-btn"
        >
          {generating ? 'Generating...' : 'Generate'}
        </button>
      </div>
    </div>
  );
}
