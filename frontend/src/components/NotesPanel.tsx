import { useState, useEffect, useCallback, useRef } from 'react';
import { notesApi, type NoteItem, type NoteHighlight } from '../api/notes';
import { NoteTaskForm } from './NoteTaskForm';
import './NotesPanel.css';

interface NotesPanelProps {
  courseContentId: number;
  isOpen: boolean;
  onClose: () => void;
  appendText?: string | null;
  onAppendConsumed?: () => void;
  addHighlight?: { text: string } | null;
  onHighlightConsumed?: () => void;
  onHighlightsChange?: (highlights: NoteHighlight[]) => void;
  removeHighlightText?: string | null;
  onRemoveHighlightConsumed?: () => void;
  readOnly?: boolean;
  childStudentId?: number;
  childName?: string;
}

export function NotesPanel({ courseContentId, isOpen, onClose, appendText, onAppendConsumed, addHighlight, onHighlightConsumed, onHighlightsChange, removeHighlightText, onRemoveHighlightConsumed, readOnly, childStudentId, childName }: NotesPanelProps) {
  const [note, setNote] = useState<NoteItem | null>(null);
  const [content, setContent] = useState('');
  const [highlights, setHighlights] = useState<NoteHighlight[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [showTaskDropdown, setShowTaskDropdown] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [justAppended, setJustAppended] = useState(false);
  const [parentEditing, setParentEditing] = useState(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Drag state
  const panelRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const dragState = useRef<{ startX: number; startY: number; panelX: number; panelY: number } | null>(null);

  const parseHighlights = (json: string | null | undefined): NoteHighlight[] => {
    if (!json) return [];
    try {
      const parsed = JSON.parse(json);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  };

  const loadNote = useCallback(async () => {
    try {
      let data: NoteItem | null;
      if (readOnly && childStudentId && !parentEditing) {
        data = await notesApi.getChildNotes(childStudentId, courseContentId);
      } else {
        data = await notesApi.getByContent(courseContentId);
      }
      if (data) {
        setNote(data);
        setContent(data.content || '');
        const loaded = parseHighlights(data.highlights_json);
        setHighlights(loaded);
        onHighlightsChange?.(loaded);
      } else {
        setNote(null);
        setContent('');
        setHighlights([]);
        onHighlightsChange?.([]);
      }
    } catch {
      setNote(null);
      setContent('');
      setHighlights([]);
      onHighlightsChange?.([]);
    } finally {
      setLoading(false);
    }
  }, [courseContentId, readOnly, childStudentId, parentEditing]); // eslint-disable-line react-hooks/exhaustive-deps

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

  // Drag handlers
  const handleDragStart = useCallback((e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button')) return;
    e.preventDefault();
    const panel = panelRef.current;
    if (!panel) return;
    const rect = panel.getBoundingClientRect();
    dragState.current = {
      startX: e.clientX,
      startY: e.clientY,
      panelX: rect.left,
      panelY: rect.top,
    };

    const handleMove = (ev: MouseEvent) => {
      if (!dragState.current) return;
      const dx = ev.clientX - dragState.current.startX;
      const dy = ev.clientY - dragState.current.startY;
      setPosition({
        x: Math.max(0, dragState.current.panelX + dx),
        y: Math.max(0, dragState.current.panelY + dy),
      });
    };

    const handleUp = () => {
      dragState.current = null;
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleUp);
    };

    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleUp);
  }, []);

  // Handle appended highlighted text
  useEffect(() => {
    if (!appendText || loading) return;
    // When parent is in read-only mode, switch to own notes for editing
    if (readOnly && !parentEditing) {
      setParentEditing(true);
      setLoading(true);
      return; // loadNote will re-run due to parentEditing change, then append will fire again
    }
    const quoted = appendText.split('\n').map(line => `> ${line}`).join('\n');
    const separator = content.trim() ? '\n\n' : '';
    const newContent = content + separator + quoted + '\n';
    setContent(newContent);
    onAppendConsumed?.();

    // Auto-save immediately
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => saveNote(newContent), 300);

    // Flash animation
    setJustAppended(true);
    setTimeout(() => setJustAppended(false), 800);

    // Scroll to bottom
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.scrollTop = textareaRef.current.scrollHeight;
      }
    }, 50);
  }, [appendText, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle addHighlight prop — add highlight entry (deduped by text)
  useEffect(() => {
    if (!addHighlight || loading) return;
    const text = addHighlight.text;
    onHighlightConsumed?.();

    setHighlights(prev => {
      if (prev.some(h => h.text === text)) return prev;
      const updated = [...prev, { text, start: 0, end: 0 }];
      onHighlightsChange?.(updated);
      // Auto-save with updated highlights
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => saveNote(content, updated), 300);
      return updated;
    });
  }, [addHighlight, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle removeHighlightText prop — remove highlight entry by text
  useEffect(() => {
    if (!removeHighlightText || loading) return;
    onRemoveHighlightConsumed?.();

    setHighlights(prev => {
      const updated = prev.filter(h => h.text !== removeHighlightText);
      if (updated.length === prev.length) return prev;
      onHighlightsChange?.(updated);
      // Auto-save with updated highlights
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => saveNote(content, updated), 300);
      return updated;
    });
  }, [removeHighlightText]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveNote = useCallback(async (newContent: string, currentHighlights?: NoteHighlight[]) => {
    setSaving(true);
    try {
      const highlightsToSave = currentHighlights ?? highlights;
      const data = await notesApi.upsert(courseContentId, {
        content: newContent,
        highlights_json: JSON.stringify(highlightsToSave),
      });
      setNote(data);
    } catch (err: any) {
      if (err.response?.status === 204) {
        setNote(null);
      }
    } finally {
      setSaving(false);
    }
  }, [courseContentId, highlights]);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setContent(val);
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

  if (!isOpen) return null;

  const isEffectivelyReadOnly = readOnly && !parentEditing;

  const panelStyle: React.CSSProperties = position
    ? { position: 'fixed', left: position.x, top: position.y, right: 'auto', bottom: 'auto' }
    : {};

  return (
    <div className="notes-panel-floating" ref={panelRef} style={panelStyle}>
      <div className="notes-panel-header" onMouseDown={handleDragStart}>
        <h3>{isEffectivelyReadOnly ? `${childName ? childName + "'s " : "Child's "}Notes` : 'Notes'}</h3>
        <div className="notes-header-actions">
          {!isEffectivelyReadOnly && note && !loading && (
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
          <button className="notes-close-btn" onClick={onClose} title="Close notes" aria-label="Close notes">
            &times;
          </button>
        </div>
      </div>

      {loading ? (
        <div className="notes-panel-body">
          <p className="notes-loading">Loading...</p>
        </div>
      ) : isEffectivelyReadOnly ? (
        <div className="notes-panel-body">
          {content ? (
            <div className="notes-readonly-content">{content}</div>
          ) : (
            <p className="notes-empty">No notes yet.</p>
          )}
          <div className="notes-panel-footer">
            <button className="notes-toggle-view-btn" onClick={() => { setParentEditing(true); setLoading(true); }}>
              My Notes
            </button>
          </div>
        </div>
      ) : showTaskForm && note ? (
        <div className="notes-panel-body">
          <NoteTaskForm
            note={note}
            courseContentId={courseContentId}
            onCreated={handleTaskCreated}
            onCancel={() => setShowTaskForm(false)}
          />
        </div>
      ) : (
        <div className="notes-panel-body">
          <textarea
            ref={textareaRef}
            className={`notes-textarea${justAppended ? ' notes-textarea--appended' : ''}`}
            value={content}
            onChange={handleChange}
            placeholder="Type your notes here..."
          />
          <div className="notes-panel-footer">
            {saving && <span className="notes-saving">Saving...</span>}
            {!saving && note && <span className="notes-saved">Saved</span>}
            {parentEditing && readOnly && (
              <button className="notes-toggle-view-btn" onClick={() => { setParentEditing(false); setLoading(true); }}>
                View {childName ? childName + "'s" : "child's"} notes
              </button>
            )}
          </div>
        </div>
      )}

      {toast && <div className="notes-toast">{toast}</div>}
    </div>
  );
}
