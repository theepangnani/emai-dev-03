import { useState, useEffect, useCallback, useRef } from 'react';
import { notesApi, type NoteResponse, type ChildNoteResponse } from '../../api/notes';
import { parentApi, type ChildSummary } from '../../api/parent';
import { useAuth } from '../../context/AuthContext';

interface NotesTabProps {
  courseContentId: number;
}

/**
 * NotesTab — renders within the course material detail page.
 * - All users see "My Notes" (editable textarea + save).
 * - Parents also see read-only "Child's Notes" sections for each linked child.
 */
export function NotesTab({ courseContentId }: NotesTabProps) {
  const { user } = useAuth();
  const isParent = user?.role === 'parent' || (user?.roles ?? []).includes('parent');

  // Own note state
  const [myNote, setMyNote] = useState<NoteResponse | null>(null);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  // Child notes state (parent only)
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [childNotes, setChildNotes] = useState<Record<number, ChildNoteResponse[]>>({});
  const [childNotesLoading, setChildNotesLoading] = useState(false);

  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load own note
  const loadMyNote = useCallback(async () => {
    try {
      const notes = await notesApi.list(courseContentId);
      const note = notes.length > 0 ? notes[0] : null;
      setMyNote(note);
      setDraft(note?.content ?? '');
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [courseContentId]);

  // Load children + their notes (parent only)
  const loadChildNotes = useCallback(async () => {
    if (!isParent) return;
    setChildNotesLoading(true);
    try {
      const kids = await parentApi.getChildren();
      setChildren(kids);
      const map: Record<number, ChildNoteResponse[]> = {};
      await Promise.all(
        kids.map(async (child) => {
          try {
            const notes = await notesApi.getChildNotes(child.student_id, courseContentId);
            if (notes.length > 0) {
              map[child.student_id] = notes;
            }
          } catch {
            // child may have no notes — that's fine
          }
        }),
      );
      setChildNotes(map);
    } catch {
      // ignore
    } finally {
      setChildNotesLoading(false);
    }
  }, [isParent, courseContentId]);

  useEffect(() => {
    loadMyNote();
    loadChildNotes();
  }, [loadMyNote, loadChildNotes]);

  // Auto-save with debounce
  const handleChange = (value: string) => {
    setDraft(value);
    setSaved(false);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      doSave(value);
    }, 1000);
  };

  const doSave = async (content: string) => {
    setSaving(true);
    try {
      const result = await notesApi.upsert({
        course_content_id: courseContentId,
        content,
        plain_text: content.replace(/<[^>]*>/g, ''),
      });
      setMyNote(result);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // ignore save errors silently for now
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!myNote) return;
    try {
      await notesApi.delete(myNote.id);
      setMyNote(null);
      setDraft('');
    } catch {
      // ignore
    }
  };

  if (loading) {
    return <div className="notes-tab-loading">Loading notes...</div>;
  }

  const childEntries = Object.entries(childNotes);

  return (
    <div className="notes-tab">
      {/* ── My Notes (editable) ── */}
      <section className="notes-section notes-mine">
        <div className="notes-section-header">
          <h3>My Notes</h3>
          <span className="notes-status">
            {saving && 'Saving...'}
            {saved && !saving && 'Saved'}
          </span>
        </div>
        <textarea
          className="notes-editor"
          value={draft}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="Type your notes here..."
          rows={8}
        />
        <div className="notes-actions">
          {myNote && (
            <button className="btn-text btn-danger-text" onClick={handleDelete} type="button">
              Delete note
            </button>
          )}
        </div>
      </section>

      {/* ── Child Notes (read-only, parent only) ── */}
      {isParent && childNotesLoading && (
        <p className="notes-child-loading">Loading children's notes...</p>
      )}

      {isParent && !childNotesLoading && childEntries.length > 0 && (
        <>
          {childEntries.map(([studentIdStr, notes]) => {
            const childName = notes[0]?.child_name ?? 'Child';
            return (
              <section
                key={studentIdStr}
                className="notes-section notes-child"
              >
                <div className="notes-section-header">
                  <h3>{childName}'s Notes</h3>
                  <span className="notes-badge">Read-only</span>
                </div>
                {notes.map((n) => (
                  <div key={n.id} className="notes-child-content">
                    {n.content || <em className="notes-empty">No content</em>}
                  </div>
                ))}
              </section>
            );
          })}
        </>
      )}
    </div>
  );
}
