import { useState, useCallback, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notesApi } from '../api/notes';
import { RichTextEditor } from './RichTextEditor';
import type { ImageValidationError } from '../utils/imageValidation';
import './NotesPanel.css';

interface NotesPanelProps {
  courseContentId: number;
}

export function NotesPanel({ courseContentId }: NotesPanelProps) {
  const queryClient = useQueryClient();
  const [, setEditorContent] = useState('');
  const [, setPlainText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const contentRef = useRef({ html: '', text: '' });

  // Fetch existing note
  const { data: note, isLoading } = useQuery({
    queryKey: ['note', courseContentId],
    queryFn: () => notesApi.get(courseContentId),
    retry: (failureCount, err: { response?: { status: number } }) => {
      // Don't retry on 404 (no note yet)
      if (err?.response?.status === 404) return false;
      return failureCount < 2;
    },
  });

  // Upsert mutation
  const upsertMutation = useMutation({
    mutationFn: (data: { content: string | null; plain_text: string | null }) =>
      notesApi.upsert(courseContentId, data),
    onSuccess: () => {
      setSaveStatus('saved');
      queryClient.invalidateQueries({ queryKey: ['note', courseContentId] });
      // Reset status after 2 seconds
      setTimeout(() => setSaveStatus('idle'), 2000);
    },
    onError: () => {
      setSaveStatus('error');
      setError('Failed to save note. Please try again.');
    },
  });

  // Auto-save with debounce
  const scheduleSave = useCallback(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    setSaveStatus('saving');
    saveTimeoutRef.current = setTimeout(() => {
      const { html, text } = contentRef.current;
      upsertMutation.mutate({
        content: html || null,
        plain_text: text || null,
      });
    }, 1500);
  }, [upsertMutation]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  const handleUpdate = useCallback(
    (html: string, text: string) => {
      setEditorContent(html);
      setPlainText(text);
      contentRef.current = { html, text };
      setError(null);
      scheduleSave();
    },
    [scheduleSave],
  );

  const handleImageError = useCallback((err: ImageValidationError) => {
    setError(err.message);
    // Auto-dismiss after 5 seconds
    setTimeout(() => setError(null), 5000);
  }, []);

  const initialContent = note?.content || '';

  return (
    <div className="notes-panel">
      <div className="notes-panel__header">
        <h3 className="notes-panel__title">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="M3 2h7l3 3v8a2 2 0 01-2 2H5a2 2 0 01-2-2V4a2 2 0 012-2z"
              stroke="currentColor"
              strokeWidth="1.3"
            />
            <path d="M10 2v3h3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
            <path d="M5.5 7.5h5M5.5 10h3.5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
          </svg>
          My Notes
        </h3>
        <span className={`notes-panel__status notes-panel__status--${saveStatus}`}>
          {saveStatus === 'saving' && 'Saving...'}
          {saveStatus === 'saved' && 'Saved'}
          {saveStatus === 'error' && 'Save failed'}
        </span>
      </div>

      {error && (
        <div className="notes-panel__error" role="alert">
          {error}
          <button className="notes-panel__error-dismiss" onClick={() => setError(null)}>
            &times;
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="notes-panel__loading">Loading notes...</div>
      ) : (
        <RichTextEditor
          content={initialContent}
          onUpdate={handleUpdate}
          onError={handleImageError}
          placeholder="Add your notes here... Paste images from clipboard, drag & drop, or use the toolbar to upload."
        />
      )}

      <div className="notes-panel__footer">
        <span className="notes-panel__hint">
          Paste images from clipboard, drag & drop files, or click the image button. Max 5 MB/image, 10 images/note.
        </span>
      </div>
    </div>
  );
}
