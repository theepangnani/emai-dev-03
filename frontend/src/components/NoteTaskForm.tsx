import { useState } from 'react';
import { notesApi, type NoteItem } from '../api/notes';

interface NoteTaskFormProps {
  note: NoteItem;
  onCreated?: () => void;
  onCancel: () => void;
}

export function NoteTaskForm({ note, onCreated, onCancel }: NoteTaskFormProps) {
  // Pre-fill title from first line of plain text
  const firstLine = note.plain_text?.split('\n')[0]?.trim().slice(0, 200) || '';
  const [title, setTitle] = useState(firstLine || 'Task from note');
  const [dueDate, setDueDate] = useState('');
  const [priority, setPriority] = useState('medium');
  const [linked, setLinked] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || creating) return;
    setCreating(true);
    setError('');
    try {
      await notesApi.createTask(note.id, {
        title: title.trim(),
        due_date: dueDate ? new Date(dueDate).toISOString() : undefined,
        priority,
        linked,
      });
      onCreated?.();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create task');
    } finally {
      setCreating(false);
    }
  };

  return (
    <form className="note-task-form" onSubmit={handleSubmit}>
      <div className="note-task-form-header">
        <strong>Create Task from Note</strong>
        <button type="button" className="note-task-close-btn" onClick={onCancel} aria-label="Cancel">
          &times;
        </button>
      </div>
      <div className="note-task-field">
        <label htmlFor="note-task-title">Title</label>
        <input
          id="note-task-title"
          type="text"
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="Task title"
          autoFocus
          maxLength={200}
        />
      </div>
      <div className="note-task-row">
        <div className="note-task-field">
          <label htmlFor="note-task-due">Due Date</label>
          <input
            id="note-task-due"
            type="datetime-local"
            value={dueDate}
            onChange={e => setDueDate(e.target.value)}
          />
        </div>
        <div className="note-task-field">
          <label htmlFor="note-task-priority">Priority</label>
          <select
            id="note-task-priority"
            value={priority}
            onChange={e => setPriority(e.target.value)}
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>
      </div>
      <div className="note-task-field">
        <label className="note-task-checkbox-label">
          <input
            type="checkbox"
            checked={linked}
            onChange={e => setLinked(e.target.checked)}
          />
          Link task to this material
        </label>
      </div>
      {error && <div className="note-task-error">{error}</div>}
      <div className="note-task-actions">
        <button type="button" className="note-task-cancel-btn" onClick={onCancel} disabled={creating}>
          Cancel
        </button>
        <button type="submit" className="note-task-submit-btn" disabled={creating || !title.trim()}>
          {creating ? 'Creating...' : 'Create Task'}
        </button>
      </div>
    </form>
  );
}
