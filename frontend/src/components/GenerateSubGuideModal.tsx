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
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: 480 }}>
        <h3>Generate Study Material</h3>
        <p style={{ fontStyle: 'italic', fontSize: '0.85rem', color: '#64748b', borderLeft: '3px solid #2a9fa8', paddingLeft: '0.75rem' }}>{preview}</p>
        <div style={{ display: 'flex', gap: '0.5rem', margin: '1rem 0' }}>
          {['study_guide', 'quiz', 'flashcards'].map(t => (
            <button key={t} onClick={() => setSelectedType(t)} style={{ flex: 1, padding: '0.75rem', borderRadius: 8, border: selectedType === t ? '2px solid #2a9fa8' : '1px solid #e2e8f0', background: selectedType === t ? '#e6f7f8' : '#fff', cursor: 'pointer' }}>
              {t === 'study_guide' ? 'Study Guide' : t === 'quiz' ? 'Quiz' : 'Flashcards'}
            </button>
          ))}
        </div>
        <input type="text" value={customPrompt} onChange={e => setCustomPrompt(e.target.value)} placeholder="Focus prompt (optional)" style={{ width: '100%', padding: '0.5rem', borderRadius: 8, border: '1px solid #e2e8f0', marginBottom: '1rem', boxSizing: 'border-box' }} />
        <p style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Uses 1 AI credit · {aiRemaining} remaining</p>
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{ padding: '0.5rem 1rem', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer' }}>Cancel</button>
          <button onClick={handleGenerate} disabled={!aiAvailable || generating} style={{ padding: '0.5rem 1rem', borderRadius: 8, border: 'none', background: '#2a9fa8', color: '#fff', fontWeight: 600, cursor: 'pointer', opacity: !aiAvailable || generating ? 0.5 : 1 }}>{generating ? 'Generating...' : 'Generate'}</button>
        </div>
      </div>
    </div>
  );
}
