import { useState, useEffect, useCallback, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';
import Placeholder from '@tiptap/extension-placeholder';
import Highlight from '@tiptap/extension-highlight';
import { TextStyle } from '@tiptap/extension-text-style';
import Color from '@tiptap/extension-color';
import { notesApi, type NoteItem, type NoteHighlight, type NoteVersionItem, type NoteVersionFull } from '../api/notes';
import { NoteTaskForm } from './NoteTaskForm';
import { NotesToolbar } from './NotesToolbar';
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

  // History state
  const [showHistory, setShowHistory] = useState(false);
  const [versions, setVersions] = useState<NoteVersionItem[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [previewVersion, setPreviewVersion] = useState<NoteVersionFull | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [restoringVersion, setRestoringVersion] = useState(false);

  // Drag state
  const panelRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const dragState = useRef<{ startX: number; startY: number; panelX: number; panelY: number } | null>(null);

  // Resize state
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const resizeState = useRef<{ startX: number; startY: number; startW: number; startH: number } | null>(null);

  // Ref to hold the latest saveNote function for use in editor onUpdate
  const saveNoteRef = useRef<((content: string, hl?: NoteHighlight[]) => Promise<void>) | undefined>(undefined);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      Link.configure({ openOnClick: false }),
      Image,
      Placeholder.configure({ placeholder: 'Start typing your notes...' }),
      Highlight.configure({ multicolor: true }),
      TextStyle,
      Color,
    ],
    editable: !(readOnly && !parentEditing),
    content: '',
    onUpdate: ({ editor: ed }) => {
      const html = ed.getHTML();
      // Treat empty editor (just an empty paragraph) as empty
      const isEmpty = html === '<p></p>' || html === '';
      const val = isEmpty ? '' : html;
      setContent(val);
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => {
        saveNoteRef.current?.(val);
      }, 1000);
    },
  });

  // Sync editable state when readOnly or parentEditing changes
  useEffect(() => {
    if (editor) {
      editor.setEditable(!(readOnly && !parentEditing));
    }
  }, [editor, readOnly, parentEditing]);

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
      const isChildView = !!(readOnly && childStudentId && !parentEditing);
      if (isChildView) {
        data = await notesApi.getChildNotes(childStudentId, courseContentId);
      } else {
        data = await notesApi.getByContent(courseContentId);
      }
      if (data) {
        setNote(data);
        setContent(data.content || '');
        // Set editor content — use setTimeout to ensure editor is ready
        if (editor) {
          editor.commands.setContent(data.content || '');
        }
        // Only sync highlights when loading own notes — child notes
        // don't carry the parent's highlights and must not overwrite them
        if (!isChildView) {
          const loaded = parseHighlights(data.highlights_json);
          setHighlights(loaded);
          onHighlightsChange?.(loaded);
        }
      } else {
        setNote(null);
        setContent('');
        if (editor) {
          editor.commands.setContent('');
        }
        if (!isChildView) {
          setHighlights([]);
          onHighlightsChange?.([]);
        }
      }
    } catch {
      setNote(null);
      setContent('');
      if (editor) {
        editor.commands.setContent('');
      }
      if (!(readOnly && childStudentId && !parentEditing)) {
        setHighlights([]);
        onHighlightsChange?.([]);
      }
    } finally {
      setLoading(false);
    }
  }, [courseContentId, readOnly, childStudentId, parentEditing, editor]); // eslint-disable-line react-hooks/exhaustive-deps

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

  // Resize handler
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const panel = panelRef.current;
    if (!panel) return;
    const rect = panel.getBoundingClientRect();
    resizeState.current = {
      startX: e.clientX,
      startY: e.clientY,
      startW: rect.width,
      startH: rect.height,
    };

    const handleMove = (ev: MouseEvent) => {
      if (!resizeState.current) return;
      const dw = ev.clientX - resizeState.current.startX;
      const dh = ev.clientY - resizeState.current.startY;
      setSize({
        w: Math.min(Math.max(280, resizeState.current.startW + dw), window.innerWidth * 0.8),
        h: Math.min(Math.max(200, resizeState.current.startH + dh), window.innerHeight * 0.8),
      });
    };

    const handleUp = () => {
      resizeState.current = null;
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleUp);
    };

    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleUp);
  }, []);

  // Handle appended highlighted text
  useEffect(() => {
    if (!appendText || loading || !editor) return;
    // When parent is in read-only mode, switch to own notes for editing
    if (readOnly && !parentEditing) {
      setParentEditing(true);
      setLoading(true);
      return; // loadNote will re-run due to parentEditing change, then append will fire again
    }
    const quotedHtml = `<blockquote><p>${appendText.replace(/\n/g, '<br>')}</p></blockquote><p></p>`;
    editor.chain().focus().insertContent(quotedHtml).run();
    const newContent = editor.getHTML();
    setContent(newContent);
    onAppendConsumed?.();

    // Auto-save immediately
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => saveNoteRef.current?.(newContent), 300);

    // Flash animation
    setJustAppended(true);
    setTimeout(() => setJustAppended(false), 800);
  }, [appendText, loading, editor]); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle addHighlight prop — add highlight entry (deduped by text)
  useEffect(() => {
    if (!addHighlight || loading) return;
    // Wait for parent editing switch to complete before processing
    if (readOnly && !parentEditing) return;
    const text = addHighlight.text;
    onHighlightConsumed?.();

    if (highlights.some(h => h.text === text)) return;
    const updated = [...highlights, { text, start: 0, end: 0 }];
    setHighlights(updated);
    onHighlightsChange?.(updated);

    // Compute content including any pending append text for combined save
    let contentForSave = content;
    if (appendText) {
      const quoted = appendText.split('\n').map(line => `> ${line}`).join('\n');
      const separator = content.trim() ? '\n\n' : '';
      contentForSave = content + separator + quoted + '\n';
    }

    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => saveNoteRef.current?.(contentForSave, updated), 300);
  }, [addHighlight, loading, readOnly, parentEditing]); // eslint-disable-line react-hooks/exhaustive-deps

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
      saveTimer.current = setTimeout(() => saveNoteRef.current?.(content, updated), 300);
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

  // Keep saveNoteRef in sync with latest saveNote
  useEffect(() => {
    saveNoteRef.current = saveNote;
  }, [saveNote]);

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

  // History handlers
  const handleOpenHistory = async () => {
    if (!note) return;
    setShowHistory(true);
    setLoadingVersions(true);
    setPreviewVersion(null);
    try {
      const v = await notesApi.listVersions(note.id);
      setVersions(v);
    } catch {
      setVersions([]);
      showToast('Failed to load version history');
    } finally {
      setLoadingVersions(false);
    }
  };

  const handlePreviewVersion = async (versionId: number) => {
    if (!note) return;
    setLoadingPreview(true);
    try {
      const v = await notesApi.getVersion(note.id, versionId);
      setPreviewVersion(v);
    } catch {
      showToast('Failed to load version');
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleRestoreVersion = async (versionId: number) => {
    if (!note) return;
    setRestoringVersion(true);
    try {
      const restored = await notesApi.restoreVersion(note.id, versionId);
      setNote(restored);
      setContent(restored.content || '');
      if (editor) {
        editor.commands.setContent(restored.content || '');
      }
      setPreviewVersion(null);
      setShowHistory(false);
      showToast('Version restored');
    } catch {
      showToast('Failed to restore version');
    } finally {
      setRestoringVersion(false);
    }
  };

  const handleCloseHistory = () => {
    setShowHistory(false);
    setPreviewVersion(null);
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined });
  };

  if (!isOpen) return null;

  const isEffectivelyReadOnly = readOnly && !parentEditing;

  const panelStyle: React.CSSProperties = {
    ...(position ? { position: 'fixed', left: position.x, top: position.y, right: 'auto', bottom: 'auto' } : {}),
    ...(size ? { width: size.w, maxHeight: size.h } : {}),
  };

  // History view
  if (showHistory) {
    return (
      <div className="notes-panel-floating" ref={panelRef} style={panelStyle}>
        <div className="notes-panel-header" onMouseDown={handleDragStart}>
          <h3>
            <button className="notes-back-btn" onClick={handleCloseHistory} title="Back to notes" aria-label="Back to notes">
              &#8592;
            </button>
            {previewVersion ? `Version ${previewVersion.version_number}` : 'Version History'}
          </h3>
          <div className="notes-header-actions">
            <button className="notes-close-btn" onClick={onClose} title="Close notes" aria-label="Close notes">
              &times;
            </button>
          </div>
        </div>

        <div className="notes-panel-body">
          {previewVersion ? (
            <div className="notes-version-preview">
              <div className="notes-version-preview-meta">
                {formatDate(previewVersion.created_at)}
              </div>
              <div className="notes-version-preview-content">{previewVersion.content}</div>
              <div className="notes-version-preview-actions">
                <button
                  className="notes-version-back-btn"
                  onClick={() => setPreviewVersion(null)}
                >
                  Back to list
                </button>
                {!isEffectivelyReadOnly && (
                  <button
                    className="notes-version-restore-btn"
                    onClick={() => handleRestoreVersion(previewVersion.id)}
                    disabled={restoringVersion}
                  >
                    {restoringVersion ? 'Restoring...' : 'Restore this version'}
                  </button>
                )}
              </div>
            </div>
          ) : loadingVersions ? (
            <p className="notes-loading">Loading versions...</p>
          ) : versions.length === 0 ? (
            <p className="notes-empty">No previous versions yet. Versions are saved automatically when you edit.</p>
          ) : (
            <div className="notes-version-list">
              {versions.map(v => (
                <button
                  key={v.id}
                  className="notes-version-item"
                  onClick={() => handlePreviewVersion(v.id)}
                  disabled={loadingPreview}
                >
                  <div className="notes-version-item-header">
                    <span className="notes-version-number">v{v.version_number}</span>
                    <span className="notes-version-date">{formatDate(v.created_at)}</span>
                  </div>
                  <div className="notes-version-item-preview">{v.preview || '(empty)'}</div>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="notes-panel-resize-handle" onMouseDown={handleResizeStart} />
      </div>
    );
  }

  return (
    <div className="notes-panel-floating" ref={panelRef} style={panelStyle}>
      <div className="notes-panel-header" onMouseDown={handleDragStart}>
        <h3>{isEffectivelyReadOnly ? `${childName ? childName + "'s " : "Child's "}Notes` : 'Notes'}</h3>
        <div className="notes-header-actions">
          {!isEffectivelyReadOnly && note && !loading && (
            <>
              <button
                className="notes-history-btn"
                onClick={handleOpenHistory}
                title="Version history"
                aria-label="Version history"
              >
                &#x1f553;
              </button>
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
            </>
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
            <div className="notes-readonly-content" dangerouslySetInnerHTML={{ __html: content }} />
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
          <NotesToolbar editor={editor} />
          <div className={`notes-editor-wrap${justAppended ? ' notes-editor--appended' : ''}`}>
            <EditorContent editor={editor} />
          </div>
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
      <div className="notes-panel-resize-handle" onMouseDown={handleResizeStart} />
    </div>
  );
}
