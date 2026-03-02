import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { notesApi, type NoteItem } from '../api/notes';
import { api } from '../api/client';
import './NotesPage.css';

interface CourseOption {
  id: number;
  name: string;
}

const NOTE_COLORS = ['yellow', 'blue', 'green', 'pink', 'purple'] as const;
type NoteColor = typeof NOTE_COLORS[number];

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

// Inline new-note card (appears first in the grid)
function NewNoteCard({ onSave, onCancel }: { onSave: (title: string, content: string, color: NoteColor) => void; onCancel: () => void }) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [color, setColor] = useState<NoteColor>('yellow');
  const contentRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    contentRef.current?.focus();
  }, []);

  const handleSave = () => {
    if (!content.trim()) return;
    onSave(title, content, color);
  };

  return (
    <div className={`note-card note-card--new note-card--${color}`}>
      <div className="note-card__color-row">
        {NOTE_COLORS.map((c) => (
          <button
            key={c}
            className={`note-color-dot note-color-dot--${c}${color === c ? ' selected' : ''}`}
            onClick={() => setColor(c)}
            aria-label={c}
            type="button"
          />
        ))}
      </div>
      <input
        className="note-card__title-input"
        placeholder="Title (optional)"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />
      <textarea
        ref={contentRef}
        className="note-card__content-input"
        placeholder="Take a note..."
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={4}
      />
      <div className="note-card__actions">
        <button className="note-btn note-btn--primary" onClick={handleSave} disabled={!content.trim()}>
          Save
        </button>
        <button className="note-btn note-btn--ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

// Edit modal for an existing note
function NoteEditModal({
  note,
  courses,
  onSave,
  onClose,
}: {
  note: NoteItem;
  courses: CourseOption[];
  onSave: (id: number, data: Partial<NoteItem>) => void;
  onClose: () => void;
}) {
  const [title, setTitle] = useState(note.title || '');
  const [content, setContent] = useState(note.content);
  const [color, setColor] = useState<NoteColor>((note.color as NoteColor) || 'yellow');
  const [courseId, setCourseId] = useState<number | null>(note.course_id);

  const handleSave = () => {
    if (!content.trim()) return;
    onSave(note.id, { title: title || null, content, color, course_id: courseId });
  };

  return (
    <div className="note-modal-backdrop" onClick={onClose}>
      <div className={`note-modal note-modal--${color}`} onClick={(e) => e.stopPropagation()}>
        <div className="note-modal__header">
          <div className="note-card__color-row">
            {NOTE_COLORS.map((c) => (
              <button
                key={c}
                className={`note-color-dot note-color-dot--${c}${color === c ? ' selected' : ''}`}
                onClick={() => setColor(c)}
                aria-label={c}
                type="button"
              />
            ))}
          </div>
          <button className="note-modal__close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>
        <input
          className="note-modal__title"
          placeholder="Title (optional)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <textarea
          className="note-modal__content"
          placeholder="Write your note here... (Markdown supported)"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={10}
        />
        <div className="note-modal__footer">
          <select
            className="note-modal__course-select"
            value={courseId ?? ''}
            onChange={(e) => setCourseId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">No course link</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <div className="note-modal__footer-actions">
            <button className="note-btn note-btn--ghost" onClick={onClose}>Cancel</button>
            <button className="note-btn note-btn--primary" onClick={handleSave} disabled={!content.trim()}>
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// A single note card in the masonry grid
function NoteCard({
  note,
  onPin,
  onDelete,
  onClick,
}: {
  note: NoteItem;
  onPin: (id: number, pinned: boolean) => void;
  onDelete: (id: number) => void;
  onClick: (note: NoteItem) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    if (menuOpen) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  return (
    <div
      className={`note-card note-card--${note.color || 'yellow'}`}
      onClick={() => onClick(note)}
    >
      <div className="note-card__top">
        {note.title && <h3 className="note-card__title">{note.title}</h3>}
        <div className="note-card__controls" onClick={(e) => e.stopPropagation()}>
          <button
            className={`note-pin-btn${note.is_pinned ? ' pinned' : ''}`}
            title={note.is_pinned ? 'Unpin' : 'Pin'}
            onClick={() => onPin(note.id, !note.is_pinned)}
            aria-label={note.is_pinned ? 'Unpin note' : 'Pin note'}
          >
            {note.is_pinned ? '📌' : '📍'}
          </button>
          <div className="note-menu-wrap" ref={menuRef}>
            <button
              className="note-menu-btn"
              onClick={() => setMenuOpen((v) => !v)}
              aria-label="Note options"
            >
              &#8942;
            </button>
            {menuOpen && (
              <div className="note-dropdown">
                <button onClick={() => { setMenuOpen(false); onClick(note); }}>Edit</button>
                <button className="note-dropdown__delete" onClick={() => { setMenuOpen(false); onDelete(note.id); }}>
                  Delete
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      <p className="note-card__preview">{note.content}</p>
      {(note.course_name || note.study_guide_title || note.task_title) && (
        <div className="note-card__chips">
          {note.course_name && <span className="note-chip note-chip--course">{note.course_name}</span>}
          {note.study_guide_title && <span className="note-chip note-chip--guide">{note.study_guide_title}</span>}
          {note.task_title && <span className="note-chip note-chip--task">{note.task_title}</span>}
        </div>
      )}
    </div>
  );
}

export function NotesPage() {
  const queryClient = useQueryClient();
  const [showNewCard, setShowNewCard] = useState(false);
  const [editingNote, setEditingNote] = useState<NoteItem | null>(null);
  const [filterCourseId, setFilterCourseId] = useState<number | null>(null);
  const [filterPinned, setFilterPinned] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const debouncedSearch = useDebounce(searchInput, 300);

  // Fetch courses for filter and linking
  const { data: coursesData } = useQuery({
    queryKey: ['notes-courses'],
    queryFn: async () => {
      const res = await api.get('/api/courses/');
      return (res.data?.courses ?? res.data ?? []) as CourseOption[];
    },
    staleTime: 60_000,
  });
  const courses: CourseOption[] = coursesData ?? [];

  const notesQueryKey = ['notes', { course_id: filterCourseId, search: debouncedSearch, pinned: filterPinned || undefined }];

  const { data: notes = [], isLoading } = useQuery({
    queryKey: notesQueryKey,
    queryFn: () =>
      notesApi.list({
        course_id: filterCourseId ?? undefined,
        search: debouncedSearch || undefined,
        pinned: filterPinned || undefined,
      }),
  });

  const createMutation = useMutation({
    mutationFn: notesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      setShowNewCard(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof notesApi.update>[1] }) =>
      notesApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      setEditingNote(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: notesApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notes'] }),
  });

  const handleSaveNew = useCallback(
    (title: string, content: string, color: NoteColor) => {
      createMutation.mutate({ title: title || undefined, content, color });
    },
    [createMutation],
  );

  const handleSaveEdit = useCallback(
    (id: number, data: Partial<NoteItem>) => {
      updateMutation.mutate({ id, data: data as Parameters<typeof notesApi.update>[1] });
    },
    [updateMutation],
  );

  const handlePin = useCallback(
    (id: number, pinned: boolean) => {
      updateMutation.mutate({ id, data: { is_pinned: pinned } });
    },
    [updateMutation],
  );

  const handleDelete = useCallback(
    (id: number) => {
      if (window.confirm('Delete this note?')) {
        deleteMutation.mutate(id);
      }
    },
    [deleteMutation],
  );

  return (
    <DashboardLayout welcomeSubtitle="Your personal notes">
      <div className="notes-page">
        <div className="notes-header">
          <h1 className="notes-title">Notes</h1>
          <button
            className="notes-new-btn"
            onClick={() => setShowNewCard(true)}
            disabled={showNewCard}
          >
            + New Note
          </button>
        </div>

        {/* Filter bar */}
        <div className="notes-filter-bar">
          <button
            className={`notes-filter-chip${!filterPinned && !filterCourseId ? ' active' : ''}`}
            onClick={() => { setFilterPinned(false); setFilterCourseId(null); }}
          >
            All
          </button>
          <button
            className={`notes-filter-chip${filterPinned ? ' active' : ''}`}
            onClick={() => setFilterPinned((v) => !v)}
          >
            Pinned
          </button>
          <select
            className="notes-course-select"
            value={filterCourseId ?? ''}
            onChange={(e) => setFilterCourseId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">All Courses</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <input
            className="notes-search"
            placeholder="Search notes..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>

        {/* Masonry grid */}
        <div className="notes-grid">
          {showNewCard && (
            <NewNoteCard
              onSave={handleSaveNew}
              onCancel={() => setShowNewCard(false)}
            />
          )}
          {isLoading && <p className="notes-loading">Loading notes...</p>}
          {!isLoading && notes.length === 0 && !showNewCard && (
            <p className="notes-empty">No notes yet. Click "+ New Note" to get started.</p>
          )}
          {notes.map((note) => (
            <NoteCard
              key={note.id}
              note={note}
              onPin={handlePin}
              onDelete={handleDelete}
              onClick={setEditingNote}
            />
          ))}
        </div>

        {editingNote && (
          <NoteEditModal
            note={editingNote}
            courses={courses}
            onSave={handleSaveEdit}
            onClose={() => setEditingNote(null)}
          />
        )}
      </div>
    </DashboardLayout>
  );
}
