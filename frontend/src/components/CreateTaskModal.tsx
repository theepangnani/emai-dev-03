import { useState, useEffect } from 'react';
import { tasksApi } from '../api/client';
import type { AssignableUser, TaskTemplate } from '../api/client';
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
  const [recurrence, setRecurrence] = useState('');
  const [assignableUsers, setAssignableUsers] = useState<AssignableUser[]>([]);
  const [templates, setTemplates] = useState<TaskTemplate[]>([]);
  const [creating, setCreating] = useState(false);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [error, setError] = useState('');
  const [templateSaved, setTemplateSaved] = useState(false);

  useEffect(() => {
    if (open) {
      setTitle(prefillTitle || '');
      setDescription(prefillDescription || '');
      setDueDate('');
      setPriority('medium');
      setAssignee('');
      setRecurrence('');
      setError('');
      setTemplateSaved(false);
      tasksApi.getAssignableUsers().then(setAssignableUsers).catch(() => {});
      tasksApi.listTemplates().then(setTemplates).catch(() => {});
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
        recurrence_rule: recurrence || undefined,
      });
      onCreated?.();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create task');
    } finally {
      setCreating(false);
    }
  };

  const handleSelectTemplate = (templateId: string) => {
    if (!templateId) return;
    const tpl = templates.find(t => t.id === Number(templateId));
    if (tpl) {
      setTitle(tpl.title);
      setDescription(tpl.description || '');
      setPriority(tpl.priority || 'medium');
    }
  };

  const handleSaveAsTemplate = async () => {
    if (!title.trim() || savingTemplate) return;
    setSavingTemplate(true);
    try {
      const tpl = await tasksApi.createTemplate({
        title: title.trim(),
        description: description.trim() || undefined,
        priority,
      });
      setTemplates(prev => [tpl, ...prev]);
      setTemplateSaved(true);
      setTimeout(() => setTemplateSaved(false), 3000);
    } catch {
      setError('Failed to save template');
    } finally {
      setSavingTemplate(false);
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
          {templates.length > 0 && (
            <label>
              From Template
              <select
                onChange={e => handleSelectTemplate(e.target.value)}
                disabled={creating}
                defaultValue=""
              >
                <option value="">-- Select a template --</option>
                {templates.map(t => (
                  <option key={t.id} value={t.id}>{t.title}</option>
                ))}
              </select>
            </label>
          )}
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
          <label>
            Recurrence
            <select value={recurrence} onChange={e => setRecurrence(e.target.value)} disabled={creating}>
              <option value="">None</option>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="biweekly">Biweekly</option>
              <option value="monthly">Monthly</option>
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
          {error && (
            <div className="modal-error">
              <span className="error-icon">!</span>
              <span className="error-message">{error}</span>
              <button onClick={handleCreate} className="retry-btn" disabled={creating}>Try Again</button>
            </div>
          )}
        </div>
        <div className="modal-actions">
          <button
            className="cancel-btn template-save-btn"
            onClick={handleSaveAsTemplate}
            disabled={creating || savingTemplate || !title.trim()}
            title="Save current fields as a reusable template"
          >
            {templateSaved ? 'Saved!' : savingTemplate ? 'Saving...' : 'Save as Template'}
          </button>
          <span style={{ flex: 1 }} />
          <button className="cancel-btn" onClick={onClose} disabled={creating}>Cancel</button>
          <button className="generate-btn" onClick={handleCreate} disabled={creating || !title.trim()}>
            {creating ? <><span className="btn-spinner" /> Creating...</> : 'Create Task'}
          </button>
        </div>
      </div>
    </div>
  );
}
