import { useState, useEffect, useRef, useCallback } from 'react';
import { notesApi } from '../api/notes';
import { RichTextEditor } from './RichTextEditor';
import './NotesPanel.css';

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

interface NotesPanelProps {
  courseContentId: number;
  onClose: () => void;
}

export function NotesPanel({ courseContentId, onClose }: NotesPanelProps) {
  const [content, setContent] = useState('');
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const [loaded, setLoaded] = useState(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const latestContentRef = useRef({ content: '', plainText: '' });

  // Load existing note
  useEffect(() => {
    let cancelled = false;
    notesApi.getByContent(courseContentId).then((note) => {
      if (cancelled) return;
      if (note) {
        setContent(note.content);
        latestContentRef.current = { content: note.content, plainText: note.plain_text };
      }
      setLoaded(true);
    }).catch(() => {
      if (!cancelled) setLoaded(true);
    });
    return () => { cancelled = true; };
  }, [courseContentId]);

  // Save function
  const doSave = useCallback(async (html: string, text: string) => {
    // Auto-delete if empty
    const isEmpty = !text.trim();
    if (isEmpty) {
      try {
        await notesApi.delete(courseContentId);
        setSaveStatus('saved');
      } catch {
        // Note might not exist yet, that's fine
        setSaveStatus('idle');
      }
      return;
    }

    setSaveStatus('saving');
    try {
      await notesApi.upsert(courseContentId, {
        content: html,
        plain_text: text,
        has_images: html.includes('<img'),
      });
      setSaveStatus('saved');
    } catch {
      setSaveStatus('error');
    }
  }, [courseContentId]);

  // Debounced auto-save (1s)
  const handleChange = useCallback((html: string, text: string) => {
    setContent(html);
    latestContentRef.current = { content: html, plainText: text };
    setSaveStatus('saving');

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      doSave(html, text);
    }, 1000);
  }, [doSave]);

  // Save on close
  const handleClose = useCallback(() => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    const { content: c, plainText: pt } = latestContentRef.current;
    if (c || pt.trim()) {
      doSave(c, pt);
    }
    onClose();
  }, [onClose, doSave]);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleClose]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  const statusLabel = {
    idle: '',
    saving: 'Saving...',
    saved: 'Saved',
    error: 'Save failed',
  };

  return (
    <>
      <div className="notes-panel-overlay" onClick={handleClose} />
      <div className="notes-panel" ref={panelRef} role="dialog" aria-label="Notes">
        <div className="notes-panel-header">
          <h3>Notes</h3>
          <div className="notes-panel-status">
            {saveStatus !== 'idle' && (
              <span className={`notes-save-indicator ${saveStatus}`}>
                {statusLabel[saveStatus]}
              </span>
            )}
            <button
              className="notes-panel-close"
              onClick={handleClose}
              aria-label="Close notes"
            >
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M4.5 4.5l9 9M13.5 4.5l-9 9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        </div>
        {loaded && (
          <RichTextEditor
            content={content}
            onChange={handleChange}
            placeholder="Take notes while studying..."
          />
        )}
      </div>
    </>
  );
}
