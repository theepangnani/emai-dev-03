import { useState, useEffect } from 'react';
import { notesApi } from '../api/notes';
import { NotesPanel } from './NotesPanel';
import './NotesPanel.css';

interface NotesPanelToggleProps {
  courseContentId: number;
}

export function NotesPanelToggle({ courseContentId }: NotesPanelToggleProps) {
  const [open, setOpen] = useState(false);
  const [hasNote, setHasNote] = useState(false);

  useEffect(() => {
    if (!courseContentId) return;
    notesApi.getByContent(courseContentId).then((note) => {
      setHasNote(!!note && !!note.plain_text?.trim());
    }).catch(() => {});
  }, [courseContentId, open]);

  return (
    <>
      <button
        className="notes-toggle-btn"
        onClick={() => setOpen(true)}
        title="Open notes"
        aria-label="Open notes"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M12.5 2.5h-9a1 1 0 00-1 1v9a1 1 0 001 1h9a1 1 0 001-1v-9a1 1 0 00-1-1z" stroke="currentColor" strokeWidth="1.3"/>
          <path d="M5.5 5.5h5M5.5 8h5M5.5 10.5h3" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
        </svg>
        <span className="notes-toggle-label">Notes</span>
        {hasNote && <span className="notes-badge" />}
      </button>
      {open && (
        <NotesPanel
          courseContentId={courseContentId}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
