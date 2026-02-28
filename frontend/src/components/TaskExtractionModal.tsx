import { useState } from 'react';
import { courseContentsApi } from '../api/client';
import type { ExtractedTaskItem, TaskCreateFromExtraction } from '../api/client';
import { useFocusTrap } from '../utils/useFocusTrap';
import './TaskExtractionModal.css';

interface TaskExtractionModalProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (count: number) => void;
  contentId: number;
  contentTitle: string;
  courseName?: string;
}

interface EditableTask extends ExtractedTaskItem {
  _key: number;
}

export function TaskExtractionModal({
  open,
  onClose,
  onCreated,
  contentId,
  contentTitle,
  courseName,
}: TaskExtractionModalProps) {
  const [tasks, setTasks] = useState<EditableTask[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [creating, setCreating] = useState(false);
  const [extracted, setExtracted] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const trapRef = useFocusTrap(open, onClose);

  if (!open) return null;

  const handleExtract = async () => {
    setExtracting(true);
    setError('');
    setMessage('');
    setTasks([]);
    try {
      const result = await courseContentsApi.extractTasks(contentId);
      const editableTasks = result.tasks.map((t, i) => ({
        ...t,
        included: true,
        _key: i,
      }));
      setTasks(editableTasks);
      setMessage(result.message);
      setExtracted(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to extract tasks. Please try again.');
    } finally {
      setExtracting(false);
    }
  };

  const handleCreate = async () => {
    const includedTasks = tasks.filter((t) => t.included);
    if (includedTasks.length === 0) return;

    setCreating(true);
    setError('');
    try {
      const payload: TaskCreateFromExtraction[] = includedTasks.map((t) => ({
        title: t.title,
        description: t.description,
        due_date: t.due_date,
        priority: t.priority,
      }));
      const result = await courseContentsApi.createTasksFromExtraction(contentId, payload);
      onCreated?.(result.created_count);
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create tasks. Please try again.');
    } finally {
      setCreating(false);
    }
  };

  const updateTask = (key: number, updates: Partial<EditableTask>) => {
    setTasks((prev) =>
      prev.map((t) => (t._key === key ? { ...t, ...updates } : t))
    );
  };

  const toggleTask = (key: number) => {
    updateTask(key, { included: !tasks.find((t) => t._key === key)?.included });
  };

  const removeTask = (key: number) => {
    setTasks((prev) => prev.filter((t) => t._key !== key));
  };

  const includedCount = tasks.filter((t) => t.included).length;
  const busy = extracting || creating;

  const handleClose = () => {
    if (!busy) {
      setTasks([]);
      setExtracted(false);
      setMessage('');
      setError('');
      onClose();
    }
  };

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div
        ref={trapRef}
        className="modal modal-lg task-extraction-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="extract-tasks-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="extract-tasks-title">Extract Tasks from Document</h2>
        <p className="modal-desc">
          AI will analyze <strong>{contentTitle}</strong>
          {courseName ? ` (${courseName})` : ''} and find actionable tasks, assignments,
          and deadlines.
        </p>

        {!extracted && !extracting && (
          <div className="te-start-section">
            <p className="te-start-text">
              Click the button below to scan the document for tasks using AI.
            </p>
            <button
              className="generate-btn te-extract-btn"
              onClick={handleExtract}
              disabled={busy}
            >
              Analyze Document
            </button>
          </div>
        )}

        {extracting && (
          <div className="te-loading">
            <div className="te-spinner" />
            <p>Analyzing document for tasks and deadlines...</p>
          </div>
        )}

        {extracted && tasks.length === 0 && !extracting && (
          <div className="te-empty">
            <p>{message || 'No actionable tasks found in this document.'}</p>
          </div>
        )}

        {tasks.length > 0 && (
          <div className="te-task-list">
            <div className="te-task-list-header">
              <span className="te-task-count">
                {includedCount} of {tasks.length} task{tasks.length !== 1 ? 's' : ''} selected
              </span>
            </div>
            {tasks.map((task) => (
              <div
                key={task._key}
                className={`te-task-card${task.included ? '' : ' te-excluded'}`}
              >
                <div className="te-task-toggle">
                  <input
                    type="checkbox"
                    checked={task.included}
                    onChange={() => toggleTask(task._key)}
                    disabled={busy}
                    aria-label={`Include task: ${task.title}`}
                  />
                </div>
                <div className="te-task-fields">
                  <div className="te-field-row">
                    <input
                      type="text"
                      className="te-task-title-input"
                      value={task.title}
                      onChange={(e) => updateTask(task._key, { title: e.target.value })}
                      disabled={busy || !task.included}
                      placeholder="Task title"
                    />
                    <button
                      className="te-remove-btn"
                      onClick={() => removeTask(task._key)}
                      disabled={busy}
                      title="Remove task"
                      aria-label="Remove task"
                    >
                      &times;
                    </button>
                  </div>
                  <div className="te-field-row te-field-row-details">
                    <input
                      type="text"
                      className="te-task-desc-input"
                      value={task.description || ''}
                      onChange={(e) =>
                        updateTask(task._key, { description: e.target.value || null })
                      }
                      disabled={busy || !task.included}
                      placeholder="Description (optional)"
                    />
                    <input
                      type="date"
                      className="te-task-date-input"
                      value={task.due_date || ''}
                      onChange={(e) =>
                        updateTask(task._key, { due_date: e.target.value || null })
                      }
                      disabled={busy || !task.included}
                    />
                    <select
                      className="te-task-priority-input"
                      value={task.priority}
                      onChange={(e) => updateTask(task._key, { priority: e.target.value })}
                      disabled={busy || !task.included}
                    >
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                    </select>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="modal-error" style={{ margin: '0 24px' }}>
            <span className="error-icon">!</span>
            <span className="error-message">{error}</span>
          </div>
        )}

        <div className="modal-actions">
          <button className="cancel-btn" onClick={handleClose} disabled={busy}>
            {extracted && tasks.length > 0 ? 'Cancel' : 'Close'}
          </button>
          {extracted && tasks.length > 0 && (
            <button
              className="generate-btn"
              onClick={handleCreate}
              disabled={busy || includedCount === 0}
            >
              {creating ? (
                <>
                  <span className="btn-spinner" /> Creating...
                </>
              ) : (
                `Create ${includedCount} Task${includedCount !== 1 ? 's' : ''}`
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
