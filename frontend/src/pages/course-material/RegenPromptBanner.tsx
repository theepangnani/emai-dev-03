import './RegenPromptBanner.css';

interface RegenPromptBannerProps {
  onRegenerate: (type: 'study_guide' | 'quiz' | 'flashcards') => void;
  onDismiss: () => void;
}

export function RegenPromptBanner({ onRegenerate, onDismiss }: RegenPromptBannerProps) {
  return (
    <div className="cm-regen-prompt">
      <p>Source content was modified. Regenerate study materials?</p>
      <div className="cm-regen-buttons">
        <button className="cm-action-btn" onClick={() => onRegenerate('study_guide')}>{'\u2728'} Study Guide</button>
        <button className="cm-action-btn" onClick={() => onRegenerate('quiz')}>{'\u2728'} Quiz</button>
        <button className="cm-action-btn" onClick={() => onRegenerate('flashcards')}>{'\u2728'} Flashcards</button>
        <button className="cm-action-btn" onClick={onDismiss}>Dismiss</button>
      </div>
    </div>
  );
}
