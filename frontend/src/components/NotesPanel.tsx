import { useState, useEffect, useRef, useCallback } from 'react';
import { notesApi } from '../api/notes';
import type { NoteResponse } from '../api/notes';
import { RichTextEditor } from './RichTextEditor';
import './NotesPanel.css';

interface NotesPanelProps {
  courseContentId: number;
  isOpen: boolean;
  onClose: () => void;
}

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

export function NotesPanel({ courseContentId, isOpen, onClose }: NotesPanelProps) {
  const [content, setContent] = useState('');
  const [noteId, setNoteId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const panelRef = useRef<HTMLDivElement>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestContentRef = useRef({ content: '', plainText: '' });
  const isOpenRef = useRef(isOpen);
  isOpenRef.current = isOpen;

  // Load existing note
  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setLoading(true);
    notesApi.list(courseContentId).then(async (summaries) => {
      if (cancelled) return;
      if (summaries.length > 0) {
        const full = await notesApi.get(summaries[0].id);
        if (cancelled) return;
        setContent(full.content);
        setNoteId(full.id);
        latestContentRef.current = { content: full.content, plainText: full.plain_text };
      } else {
        setContent('');
        setNoteId(null);
        latestContentRef.current = { content: '', plainText: '' };
      }
      setLoading(false);
    }).catch(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [isOpen, courseContentId]);

  // Save function
  const doSave = useCallback(async (html: string, text: string) => {
    // Auto-delete empty notes
    if (!text.trim() && noteId) {
      try {
        await notesApi.delete(noteId);
        setNoteId(null);
        setSaveStatus('saved');
      } catch {
        setSaveStatus('error');
      }
      return;
    }
    // Don't save if empty and no existing note
    if (!text.trim()) {
      setSaveStatus('idle');
      return;
    }

    setSaveStatus('saving');
    try {
      const result: NoteResponse = await notesApi.upsert({
        course_content_id: courseContentId,
        content: html,
        plain_text: text,
        has_images: false,
      });
      setNoteId(result.id);
      setSaveStatus('saved');
    } catch {
      setSaveStatus('error');
    }
  }, [courseContentId, noteId]);

  // Debounced auto-save on content change
  const handleChange = useCallback((html: string, text: string) => {
    setContent(html);
    latestContentRef.current = { content: html, plainText: text };
    setSaveStatus('idle');

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
    doSave(c, pt);
    onClose();
  }, [onClose, doSave]);

  // Click outside to close
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        handleClose();
      }
    };
    // Delay to avoid immediate close from the toggle button click
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handler);
    }, 100);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handler);
    };
  }, [isOpen, handleClose]);

  // Escape key to close
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen, handleClose]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  if (!isOpen) return null;

  return (
    <>
      <div className="notes-panel-overlay" />
      <div className="notes-panel" ref={panelRef} role="complementary" aria-label="Notes">
        <div className="notes-panel-header">
          <h3 className="notes-panel-title">Notes</h3>
          <div className="notes-panel-header-right">
            <span className={`notes-save-indicator notes-save-indicator--${saveStatus}`}>
              {saveStatus === 'saving' && 'Saving...'}
              {saveStatus === 'saved' && 'Saved'}
              {saveStatus === 'error' && 'Error saving'}
            </span>
            <button
              className="notes-panel-close"
              onClick={handleClose}
              aria-label="Close notes"
            >
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M4 4l10 10M14 4L4 14" />
              </svg>
            </button>
          </div>
        </div>

        <div className="notes-panel-body">
          {loading ? (
            <div className="notes-panel-loading">Loading notes...</div>
          ) : (
            <RichTextEditor
              content={content}
              onChange={handleChange}
              placeholder="Take notes on this material..."
            />
          )}
        </div>
      </div>
    </>
  );
}
