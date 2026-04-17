import { useState, useEffect } from 'react';
import { notesApi, type NoteItem } from '../api/notes';
import { coursesApi } from '../api/courses';

interface NoteMaterialFormProps {
  note: NoteItem;
  courseContentId: number;
  onCreated?: () => void;
  onCancel: () => void;
}

interface CourseOption {
  id: number;
  name: string;
}

export function NoteMaterialForm({ note, courseContentId, onCreated, onCancel }: NoteMaterialFormProps) {
  const firstLine = note.plain_text?.split('\n')[0]?.trim().slice(0, 200) || '';
  const [title, setTitle] = useState(firstLine ? `Notes — ${firstLine}` : 'Notes — Untitled');
  const [courseId, setCourseId] = useState<number | ''>('');
  const [courses, setCourses] = useState<CourseOption[]>([]);
  const [loadingCourses, setLoadingCourses] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        // Get the course_id from the current course content
        const content = await import('../api/courses').then(m => m.courseContentsApi.get(courseContentId));
        const courseList = await coursesApi.list();
        if (cancelled) return;
        setCourses(courseList.map((c: any) => ({ id: c.id, name: c.name })));
        if (content?.course_id) {
          setCourseId(content.course_id);
        } else if (courseList.length > 0) {
          setCourseId(courseList[0].id);
        }
      } catch {
        if (!cancelled) {
          setError('Failed to load courses');
        }
      } finally {
        if (!cancelled) setLoadingCourses(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [courseContentId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !courseId || saving) return;
    setSaving(true);
    setError('');
    try {
      await notesApi.saveAsMaterial(note.id, title.trim(), courseId as number);
      onCreated?.();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save as material');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="note-task-form" onSubmit={handleSubmit}>
      <div className="note-task-form-header">
        <strong>Save as Class Material</strong>
        <button type="button" className="note-task-close-btn" onClick={onCancel} aria-label="Cancel">
          &times;
        </button>
      </div>
      <div className="note-task-field">
        <label htmlFor="note-material-title">Title</label>
        <input
          id="note-material-title"
          type="text"
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="Material title"
          autoFocus
          maxLength={255}
        />
      </div>
      <div className="note-task-field">
        <label htmlFor="note-material-course">Course</label>
        {loadingCourses ? (
          <select id="note-material-course" disabled>
            <option>Loading courses...</option>
          </select>
        ) : courses.length === 0 ? (
          <select id="note-material-course" disabled>
            <option>No courses available</option>
          </select>
        ) : (
          <select
            id="note-material-course"
            value={courseId}
            onChange={e => setCourseId(Number(e.target.value))}
          >
            {courses.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        )}
      </div>
      {error && <div className="note-task-error">{error}</div>}
      <div className="note-task-actions">
        <button type="button" className="note-task-cancel-btn" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
        <button type="submit" className="note-task-submit-btn" disabled={saving || !title.trim() || !courseId || loadingCourses}>
          {saving ? 'Saving...' : 'Save as Material'}
        </button>
      </div>
    </form>
  );
}
