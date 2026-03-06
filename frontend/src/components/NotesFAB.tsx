import { useState, useEffect } from 'react';
import { notesApi } from '../api/notes';
import './NotesFAB.css';

interface NotesFABProps {
  courseContentId: number;
  isOpen: boolean;
  onToggle: () => void;
}

export function NotesFAB({ courseContentId, isOpen, onToggle }: NotesFABProps) {
  const [hasNote, setHasNote] = useState(false);

  useEffect(() => {
    notesApi.list(courseContentId).then((notes) => {
      setHasNote(notes.length > 0);
    }).catch(() => {});
  }, [courseContentId, isOpen]);

  return (
    <button
      className={`notes-fab${isOpen ? ' notes-fab--open' : ''}`}
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
