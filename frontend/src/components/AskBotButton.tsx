import { useCallback } from 'react';
import { useFABContext } from '../context/FABContext';
import './AskBotButton.css';

export interface AskBotButtonProps {
  journeyId: string;
  journeyTitle: string;
  className?: string;
}

/**
 * "Ask the Bot" button that opens the FAB chatbot pre-filled with a
 * context-aware question about a specific journey / tutorial section.
 *
 * Integration guide (for #2600 journey cards):
 *   Place <AskBotButton journeyId="p02" journeyTitle="Add or Link Your Child" />
 *   inside each journey card. The button injects a help question into the
 *   FAB chatbot and opens it automatically.
 */
export function AskBotButton({ journeyId, journeyTitle, className }: AskBotButtonProps) {
  const { openChatWithQuestion } = useFABContext();

  const handleClick = useCallback(() => {
    openChatWithQuestion(
      `I need help with: ${journeyTitle}. Can you walk me through the steps?`
    );
  }, [openChatWithQuestion, journeyTitle]);

  return (
    <button
      type="button"
      className={`ask-bot-btn${className ? ` ${className}` : ''}`}
      onClick={handleClick}
      aria-label={`Ask the bot about ${journeyTitle}`}
      data-journey-id={journeyId}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
      Ask the Bot
    </button>
  );
}
