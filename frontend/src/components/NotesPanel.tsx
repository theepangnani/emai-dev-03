import { useState, useEffect, useCallback, useRef } from 'react';
import { notesApi, type NoteItem, type ChildNoteItem } from '../api/notes';
import { parentApi, type ChildSummary } from '../api/parent';
import { useAuth } from '../context/AuthContext';
import './NotesPanel.css';

interface NotesPanelProps {
  courseContentId: number;
  /** Whether to show as a side panel (true) or inline (false). */
  inline?: boolean;
}

/** Debounce helper — returns the latest value after `delay` ms of inactivity. */
function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function NotesPanel({ courseContentId, inline }: NotesPanelProps) {
  const { user } = useAuth();
  const isParent = user?.role === 'parent' || (user?.roles ?? []).includes('parent');

  // Own note state
  const [note, setNote] = useState<NoteItem | null>(null);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'error' | null>(null);
  const initialLoadDone = useRef(false);

  // Child notes state (parent only)
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [childNotes, setChildNotes] = useState<Record<number, ChildNoteItem[]>>({});
  const [childNotesLoading, setChildNotesLoading] = useState(false);

  const debouncedDraft = useDebounce(draft, 1000);

  // Load own note
  const loadNote = useCallback(async () => {
    try {
      const n = await notesApi.get(courseContentId);
      setNote(n);
      setDraft(n.content);
    } catch {
      // No note yet
      setNote(null);
      setDraft('');
    } finally {
      setLoading(false);
      initialLoadDone.current = true;
    }
  }, [courseContentId]);

  // Load children + their notes (parent only)
  const loadChildNotes = useCallback(async () => {
    if (!isParent) return;
    setChildNotesLoading(true);
    try {
      const kids = await parentApi.getChildren();
      setChildren(kids);
      const notesMap: Record<number, ChildNoteItem[]> = {};
      await Promise.all(
        kids.map(async (child) => {
          try {
            const cn = await notesApi.getChildNotes(child.student_id, courseContentId);
            if (cn.length > 0) {
              notesMap[child.student_id] = cn;
            }
          } catch {
            // Ignore — child may have no notes
          }
        })
      );
      setChildNotes(notesMap);
    } catch {
      // Ignore
    } finally {
      setChildNotesLoading(false);
    }
  }, [isParent, courseContentId]);

  useEffect(() => {
    loadNote();
    loadChildNotes();
  }, [loadNote, loadChildNotes]);

  // Auto-save on debounced draft change
  useEffect(() => {
    if (!initialLoadDone.current) return;
    // Skip if draft hasn't changed from the loaded note
    if (debouncedDraft === (note?.content ?? '')) return;
    const save = async () => {
      setSaving(true);
      setSaveStatus('saving');
      try {
        if (!debouncedDraft.trim()) {
          // Auto-delete empty notes
          if (note) {
            await notesApi.delete(courseContentId);
            setNote(null);
          }
          setSaveStatus('saved');
        } else {
          const updated = await notesApi.upsert(courseContentId, debouncedDraft);
          setNote(updated);
          setSaveStatus('saved');
        }
      } catch {
        setSaveStatus('error');
      } finally {
        setSaving(false);
        // Clear status after a delay
        setTimeout(() => setSaveStatus(null), 2000);
      }
    };
    save();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedDraft, courseContentId]);

  const hasChildNotes = Object.keys(childNotes).length > 0;

  return (
    <div className={`notes-panel${inline ? ' notes-panel--inline' : ''}`}>
      {/* My Notes section */}
      <div className="notes-section notes-section--own">
        <div className="notes-section-header">
          <h4 className="notes-section-title">My Notes</h4>
          {saveStatus && (
            <span className={`notes-save-status notes-save-status--${saveStatus}`}>
              {saveStatus === 'saving' && 'Saving...'}
              {saveStatus === 'saved' && 'Saved'}
              {saveStatus === 'error' && 'Save failed'}
            </span>
          )}
        </div>
        {loading ? (
          <div className="notes-loading">Loading notes...</div>
        ) : (
          <textarea
            className="notes-editor"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Add your notes here..."
            disabled={saving}
            rows={6}
          />
        )}
      </div>

      {/* Child's Notes section (parent only) */}
      {isParent && (childNotesLoading || hasChildNotes) && (
        <div className="notes-section notes-section--children">
          <h4 className="notes-section-title notes-section-title--children">
            {"Child's Notes"}
          </h4>
          {childNotesLoading ? (
            <div className="notes-loading">Loading...</div>
          ) : (
            Object.entries(childNotes).map(([studentIdStr, notes]) => {
              const studentId = parseInt(studentIdStr);
              const child = children.find(c => c.student_id === studentId);
              const childName = notes[0]?.student_name || child?.full_name || 'Child';
              return (
                <div key={studentId} className="notes-child-block">
                  <div className="notes-child-label">{childName}</div>
                  {notes.map((cn) => (
                    <div key={cn.id} className="notes-child-content">
                      <div className="notes-child-text">{cn.plain_text || cn.content}</div>
                      <div className="notes-child-meta">
                        {cn.updated_at
                          ? new Date(cn.updated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
                          : new Date(cn.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
                        }
                      </div>
                    </div>
                  ))}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
