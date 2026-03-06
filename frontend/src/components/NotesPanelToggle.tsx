import { useState, useEffect } from 'react';
import { notesApi } from '../api/notes';
import { NotesPanel } from './NotesPanel';
import './NotesPanelToggle.css';

interface NotesPanelToggleProps {
  courseContentId: number;
}

export function NotesPanelToggle({ courseContentId }: NotesPanelToggleProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [hasNote, setHasNote] = useState(false);

  // Check if a note exists for badge display
  useEffect(() => {
    notesApi.list(courseContentId).then((summaries) => {
      setHasNote(summaries.length > 0);
    }).catch(() => {});
  }, [courseContentId, isOpen]);

  return (
    <>
      <button
        className="notes-toggle-btn"
        onClick={() => setIsOpen(!isOpen)}
        title="Notes"
        aria-label={isOpen ? 'Close notes' : 'Open notes'}
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 3h9l3 3v9a1 1 0 01-1 1H4a1 1 0 01-1-1V3z" />
          <path d="M6 8h6M6 11h4" />
        </svg>
        <span className="notes-toggle-label">Notes</span>
        {hasNote && <span className="notes-toggle-badge" aria-label="Has notes" />}
      </button>
      <NotesPanel
        courseContentId={courseContentId}
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
      />
    </>
  );
}
