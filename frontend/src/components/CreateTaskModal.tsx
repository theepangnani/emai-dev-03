import { useState, useEffect } from 'react';
import { tasksApi } from '../api/client';
import type { AssignableUser } from '../api/client';
import { useFocusTrap } from '../utils/useFocusTrap';

interface CreateTaskModalProps {
  open: boolean;
  onClose: () => void;
  onCreated?: () => void;
  prefillTitle?: string;
  prefillDescription?: string;
  courseId?: number;
  courseContentId?: number;
  studyGuideId?: number;
  linkedEntityLabel?: string;
}

export function CreateTaskModal({
  open, onClose, onCreated,
  prefillTitle, prefillDescription,
  courseId, courseContentId, studyGuideId,
  linkedEntityLabel,
}: CreateTaskModalProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [priority, setPriority] = useState('medium');
  const [assignee, setAssignee] = useState<number | ''>('');
  const [assignableUsers, setAssignableUsers] = useState<AssignableUser[]>([]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      setTitle(prefillTitle || '');
      setDescription(prefillDescription || '');
      setDueDate('');
      setPriority('medium');
      setAssignee('');
      setError('');
      tasksApi.getAssignableUsers().then(setAssignableUsers).catch(() => {});
    }
  }, [open, prefillTitle, prefillDescription]);

  const trapRef = useFocusTrap(open, onClose);

  if (!open) return null;

  const handleCreate = async () => {
    if (!title.trim() || creating) return;
    setCreating(true);
    setError('');
    try {
      await tasksApi.create({
        title: title.trim(),
        description: description.trim() || undefined,
        due_date: dueDate || undefined,
        priority,
        assigned_to_user_id: assignee ? Number(assignee) : undefined,
        course_id: courseId,
        course_content_id: courseContentId,
        study_guide_id: studyGuideId,
      });
      onCreated?.();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create task');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div ref={trapRef} className="modal" role="dialog" aria-modal="true" aria-labelledby="create-task-title" onClick={e => e.stopPropagation()}>
        <h2 id="create-task-title">Create Task</h2>
        {linkedEntityLabel && (
          <div className="task-linked-context">
            Linked to: <strong>{linkedEntityLabel}</strong>
          </div>
        )}
        <div className="modal-form">
          <label>
            Title *
            <input
              type="text"
              placeholder="Task title"
              value={title}
              onChange={e => setTitle(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
              disabled={creating}
              autoFocus
            />
          </label>
          <label>
            Description
            <textarea
              placeholder="Description (optional)"
              value={description}
              onChange={e => setDescription(e.target.value)}
              rows={3}
              disabled={creating}
            />
          </label>
          <label>
            Due Date
            <input
              type="datetime-local"
              value={dueDate}
              onChange={e => setDueDate(e.target.value)}
              disabled={creating}
            />
          </label>
          <label>
            Priority
            <select value={priority} onChange={e => setPriority(e.target.value)} disabled={creating}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </label>
          {assignableUsers.length > 0 && (
            <label>
              Assign To
              <select value={assignee} onChange={e => setAssignee(e.target.value ? Number(e.target.value) : '')} disabled={creating}>
                <option value="">Unassigned (personal)</option>
                {assignableUsers.map(u => (
                  <option key={u.user_id} value={u.user_id}>{u.name} ({u.role})</option>
                ))}
              </select>
            </label>
          )}
          {error && <p className="link-error">{error}</p>}
        </div>
        <div className="modal-actions">
          <button className="cancel-btn" onClick={onClose} disabled={creating}>Cancel</button>
          <button className="generate-btn" onClick={handleCreate} disabled={creating || !title.trim()}>
            {creating ? 'Creating...' : 'Create Task'}
          </button>
        </div>
      </div>
    </div>
  );
}
