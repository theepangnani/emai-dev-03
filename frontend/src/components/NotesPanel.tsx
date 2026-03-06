import { useState, useEffect, useCallback, useRef } from 'react';
import { notesApi, type NoteItem } from '../api/notes';
import { NoteTaskForm } from './NoteTaskForm';
import './NotesPanel.css';

interface NotesPanelProps {
  courseContentId: number;
  onClose: () => void;
}

export function NotesPanel({ courseContentId, onClose }: NotesPanelProps) {
  const [note, setNote] = useState<NoteItem | null>(null);
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [showTaskDropdown, setShowTaskDropdown] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const loadNote = useCallback(async () => {
    try {
      const data = await notesApi.getByContent(courseContentId);
      setNote(data);
      setContent(data.content || '');
    } catch {
      // 404 = no note yet, that's ok
      setNote(null);
      setContent('');
    } finally {
      setLoading(false);
    }
  }, [courseContentId]);

  useEffect(() => { loadNote(); }, [loadNote]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowTaskDropdown(false);
      }
    };
    if (showTaskDropdown) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showTaskDropdown]);

  const saveNote = useCallback(async (newContent: string) => {
    setSaving(true);
    try {
      const data = await notesApi.upsert(courseContentId, { content: newContent });
      setNote(data);
    } catch (err: any) {
      if (err.response?.status === 204) {
        // Note was auto-deleted (empty)
        setNote(null);
      }
    } finally {
      setSaving(false);
    }
  }, [courseContentId]);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setContent(val);
    // Debounce auto-save
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => saveNote(val), 1000);
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleTaskCreated = () => {
    setShowTaskForm(false);
    showToast('Task created from note');
  };

  const handleCreateQuickTask = () => {
    setShowTaskDropdown(false);
    setShowTaskForm(true);
  };

  if (loading) {
    return (
      <div className="notes-panel">
        <div className="notes-panel-header">
          <h3>Notes</h3>
          <button className="notes-close-btn" onClick={onClose} aria-label="Close notes">&times;</button>
        </div>
        <div className="notes-panel-body">
          <p className="notes-loading">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="notes-panel">
      <div className="notes-panel-header">
        <h3>Notes</h3>
        <div className="notes-header-actions">
          {note && (
            <div className="notes-task-dropdown-wrapper" ref={dropdownRef}>
              <button
                className="notes-create-task-btn"
                onClick={() => setShowTaskDropdown(!showTaskDropdown)}
                title="Create task from note"
              >
                + Task
              </button>
              {showTaskDropdown && (
                <div className="notes-task-dropdown">
                  <button className="notes-task-dropdown-item" onClick={handleCreateQuickTask}>
                    Quick Task (standalone)
                  </button>
                  <button className="notes-task-dropdown-item" onClick={() => {
                    setShowTaskDropdown(false);
                    setShowTaskForm(true);
                  }}>
                    Linked Task (with material)
                  </button>
                </div>
              )}
            </div>
          )}
          <button className="notes-close-btn" onClick={onClose} aria-label="Close notes">&times;</button>
        </div>
      </div>

      {showTaskForm && note ? (
        <div className="notes-panel-body">
          <NoteTaskForm
            note={note}
            onCreated={handleTaskCreated}
            onCancel={() => setShowTaskForm(false)}
          />
        </div>
      ) : (
        <div className="notes-panel-body">
          <textarea
            className="notes-textarea"
            value={content}
            onChange={handleChange}
            placeholder="Type your notes here..."
          />
          <div className="notes-panel-footer">
            {saving && <span className="notes-saving">Saving...</span>}
            {!saving && note && <span className="notes-saved">Saved</span>}
          </div>
        </div>
      )}

      {toast && <div className="notes-toast">{toast}</div>}
    </div>
  );
}
