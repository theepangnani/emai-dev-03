import { useState, useEffect } from 'react';
import { notesApi } from '../api/notes';
import './NotesFAB.css';

interface NotesFABProps {
  courseContentId: number;
  isOpen: boolean;
  onToggle: () => void;
  /** When true, shifts the FAB up to make room for the Help Chatbot FAB */
  hasChatbotFab?: boolean;
  /** When true, shifts the FAB further up to avoid the open chatbot panel */
  chatbotPanelOpen?: boolean;
}

export function NotesFAB({ courseContentId, isOpen, onToggle, hasChatbotFab, chatbotPanelOpen }: NotesFABProps) {
  const [hasNote, setHasNote] = useState(false);

  useEffect(() => {
    notesApi.list(courseContentId).then((notes) => {
      setHasNote(notes.length > 0);
    }).catch(() => {});
  }, [courseContentId, isOpen]);

  const classNames = [
    'notes-fab',
    isOpen && 'notes-fab--open',
    hasChatbotFab && 'has-chatbot-fab',
    chatbotPanelOpen && 'chatbot-panel-open',
  ].filter(Boolean).join(' ');

  return (
    <button
      className={classNames}
      onClick={onToggle}
      title={isOpen ? 'Close notes' : 'Open notes'}
      aria-label={isOpen ? 'Close notes' : 'Open notes'}
    >
      {isOpen ? (
        <svg width="22" height="22" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M5 5l10 10M15 5L5 15" />
        </svg>
      ) : (
        <svg width="22" height="22" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 3h10l3 3v10a1 1 0 01-1 1H4a1 1 0 01-1-1V3z" />
          <path d="M6.5 8h7M6.5 11h4" />
        </svg>
      )}
      {hasNote && !isOpen && <span className="notes-fab-badge" />}
    </button>
  );
}
