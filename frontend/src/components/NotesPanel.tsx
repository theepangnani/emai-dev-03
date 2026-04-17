import { useState, useEffect, useCallback, useRef } from 'react';
import { notesApi, type NoteItem, type NoteHighlight, type NoteVersionItem, type NoteVersionFull } from '../api/notes';
import { NoteTaskForm } from './NoteTaskForm';
import { downloadAsPdf } from '../utils/exportUtils';
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
  materialTitle?: string;
}

export function NotesPanel({ courseContentId, isOpen, onClose, appendText, onAppendConsumed, addHighlight, onHighlightConsumed, onHighlightsChange, removeHighlightText, onRemoveHighlightConsumed, readOnly, childStudentId, childName, materialTitle }: NotesPanelProps) {
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

  // History state
  const [showHistory, setShowHistory] = useState(false);
  const [versions, setVersions] = useState<NoteVersionItem[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [previewVersion, setPreviewVersion] = useState<NoteVersionFull | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [restoringVersion, setRestoringVersion] = useState(false);

  // Export state
  const [showExportDropdown, setShowExportDropdown] = useState(false);
  const [exporting, setExporting] = useState(false);
  const exportDropdownRef = useRef<HTMLDivElement>(null);

  // Drag state
  const panelRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const dragState = useRef<{ startX: number; startY: number; panelX: number; panelY: number } | null>(null);

  // Resize state
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const resizeState = useRef<{ startX: number; startY: number; startW: number; startH: number } | null>(null);

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
        if (!isChildView) {
          setHighlights([]);
          onHighlightsChange?.([]);
        }
      }
    } catch {
      setNote(null);
      setContent('');
      if (!(readOnly && childStudentId && !parentEditing)) {
        setHighlights([]);
        onHighlightsChange?.([]);
      }
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

  // Close export dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (exportDropdownRef.current && !exportDropdownRef.current.contains(e.target as Node)) {
        setShowExportDropdown(false);
      }
    };
    if (showExportDropdown) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showExportDropdown]);

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
    saveTimer.current = setTimeout(() => saveNote(contentForSave, updated), 300);
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

  // ── Export helpers ──
  const escapeHtml = (str: string) =>
    str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  const sanitizeFilename = (name: string) =>
    name.replace(/[^a-zA-Z0-9\s-_]/g, '').replace(/\s+/g, '-').toLowerCase().slice(0, 80) || 'classbridge-notes';

  const getExportTitle = () => materialTitle || 'ClassBridge Notes';
  const getExportFilename = () => sanitizeFilename(materialTitle || 'classbridge-notes');

  const handleExportPdf = async () => {
    setShowExportDropdown(false);
    setExporting(true);
    let container: HTMLDivElement | null = null;
    try {
      const title = escapeHtml(getExportTitle());
      const dateStr = escapeHtml(new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' }));
      // Convert plain-text content to HTML paragraphs
      const bodyHtml = content
        .split('\n')
        .map(line => line ? `<p style="margin:0.3em 0">${escapeHtml(line)}</p>` : '<br/>')
        .join('');

      container = document.createElement('div');
      container.style.padding = '40px';
      container.style.fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
      container.style.color = '#1a1a2e';
      container.style.lineHeight = '1.6';
      container.innerHTML = `
        <h1 style="font-size:1.4rem;border-bottom:2px solid #4a90d9;padding-bottom:0.4rem">${title} &mdash; Notes</h1>
        <p style="color:#888;font-size:0.8rem;margin-bottom:1.2em">Exported from ClassBridge on ${dateStr}</p>
        <div>${bodyHtml}</div>
      `;

      document.body.appendChild(container);
      await downloadAsPdf(container, `${getExportFilename()}-notes`);
      showToast('PDF downloaded');
    } catch {
      showToast('Failed to export PDF');
    } finally {
      if (container?.parentNode) {
        document.body.removeChild(container);
      }
      setExporting(false);
    }
  };

  const htmlToMarkdown = (html: string): string => {
    const doc = new DOMParser().parseFromString(`<div>${html}</div>`, 'text/html');
    const walk = (node: Node): string => {
      if (node.nodeType === Node.TEXT_NODE) return node.textContent || '';
      if (node.nodeType !== Node.ELEMENT_NODE) return '';
      const el = node as HTMLElement;
      const tag = el.tagName.toLowerCase();
      const inner = () => Array.from(el.childNodes).map(walk).join('');

      switch (tag) {
        case 'h1': return `# ${inner()}\n\n`;
        case 'h2': return `## ${inner()}\n\n`;
        case 'h3': return `### ${inner()}\n\n`;
        case 'h4': return `#### ${inner()}\n\n`;
        case 'strong': case 'b': return `**${inner()}**`;
        case 'em': case 'i': return `*${inner()}*`;
        case 'u': return `__${inner()}__`;
        case 's': case 'del': return `~~${inner()}~~`;
        case 'code':
          if (el.parentElement?.tagName.toLowerCase() === 'pre') return inner();
          return `\`${inner()}\``;
        case 'pre': {
          const code = el.querySelector('code');
          const text = code ? code.textContent || '' : inner();
          return `\n\`\`\`\n${text}\n\`\`\`\n\n`;
        }
        case 'blockquote': return inner().split('\n').filter(Boolean).map(l => `> ${l}`).join('\n') + '\n\n';
        case 'a': return `[${inner()}](${el.getAttribute('href') || ''})`;
        case 'img': return `![${el.getAttribute('alt') || ''}](${el.getAttribute('src') || ''})`;
        case 'br': return '\n';
        case 'p': return `${inner()}\n\n`;
        case 'ul': return Array.from(el.children).map(li => `- ${walk(li).trim()}`).join('\n') + '\n\n';
        case 'ol': return Array.from(el.children).map((li, i) => `${i + 1}. ${walk(li).trim()}`).join('\n') + '\n\n';
        case 'li': return inner();
        case 'hr': return '\n---\n\n';
        default: return inner();
      }
    };
    return walk(doc.body.firstChild!).replace(/\n{3,}/g, '\n\n').trim();
  };

  const handleExportMarkdown = () => {
    setShowExportDropdown(false);
    try {
      // For plain-text content, use as-is; for HTML, convert
      const isHtml = /<[a-z][\s\S]*>/i.test(content);
      const title = getExportTitle();
      const dateStr = new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
      const header = `# ${title} — Notes\n\n*Exported from ClassBridge on ${dateStr}*\n\n---\n\n`;
      const body = isHtml ? htmlToMarkdown(content) : content;
      const markdown = header + body;

      const blob = new Blob([markdown], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${getExportFilename()}-notes.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 100);
      showToast('Markdown downloaded');
    } catch {
      showToast('Failed to export Markdown');
    }
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
          {!loading && content.trim() && (
            <div className="notes-export-dropdown-wrapper" ref={exportDropdownRef}>
              <button
                className="notes-export-btn"
                onClick={() => setShowExportDropdown(!showExportDropdown)}
                title="Download notes"
                aria-label="Download notes"
                disabled={exporting}
              >
                {exporting ? '\u23F3' : '\u2B07'}
              </button>
              {showExportDropdown && (
                <div className="notes-export-dropdown">
                  <button className="notes-export-dropdown-item" onClick={handleExportPdf}>
                    {'\uD83D\uDCC4'} Download as PDF
                  </button>
                  <button className="notes-export-dropdown-item" onClick={handleExportMarkdown}>
                    {'\uD83D\uDCDD'} Download as Markdown
                  </button>
                </div>
              )}
            </div>
          )}
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
      <div className="notes-panel-resize-handle" onMouseDown={handleResizeStart} />
    </div>
  );
}
