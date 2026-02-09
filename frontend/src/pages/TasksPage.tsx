import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { tasksApi } from '../api/client';
import type { TaskItem, AssignableUser } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { useConfirm } from '../components/ConfirmModal';
import './TasksPage.css';

type FilterStatus = 'all' | 'pending' | 'completed' | 'archived';
type FilterPriority = 'all' | 'low' | 'medium' | 'high';

export function TasksPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [assignableUsers, setAssignableUsers] = useState<AssignableUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');
  const [filterPriority, setFilterPriority] = useState<FilterPriority>('all');

  // Create task form
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newDueDate, setNewDueDate] = useState('');
  const [newPriority, setNewPriority] = useState('medium');
  const [newAssignee, setNewAssignee] = useState<number | ''>('');
  const [creating, setCreating] = useState(false);

  // Edit task
  const [editTask, setEditTask] = useState<TaskItem | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editDueDate, setEditDueDate] = useState('');
  const [editPriority, setEditPriority] = useState('medium');
  const [editAssignee, setEditAssignee] = useState<number | ''>('');
  const [saving, setSaving] = useState(false);
  const { confirm, confirmModal } = useConfirm();

  useEffect(() => {
    loadTasks();
    loadAssignableUsers();
  }, [filterStatus]);

  const loadTasks = async () => {
    try {
      setError(null);
      const params: { include_archived?: boolean; is_completed?: boolean } = {};

      if (filterStatus === 'pending') {
        params.is_completed = false;
      } else if (filterStatus === 'completed') {
        // Completed tasks are archived by backend when marked complete.
        params.include_archived = true;
        params.is_completed = true;
      } else if (filterStatus === 'archived') {
        params.include_archived = true;
      } else {
        params.include_archived = false;
      }

      const data = await tasksApi.list(params);
      setTasks(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load tasks';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const loadAssignableUsers = async () => {
    try {
      const data = await tasksApi.getAssignableUsers();
      setAssignableUsers(data);
    } catch {
      // silently fail
    }
  };

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    setCreating(true);
    try {
      await tasksApi.create({
        title: newTitle.trim(),
        description: newDescription.trim() || undefined,
        due_date: newDueDate || undefined,
        priority: newPriority,
        assigned_to_user_id: newAssignee ? Number(newAssignee) : undefined,
      });
      setNewTitle('');
      setNewDescription('');
      setNewDueDate('');
      setNewPriority('medium');
      setNewAssignee('');
      setShowCreate(false);
      loadTasks();
    } catch {
      // silently fail
    } finally {
      setCreating(false);
    }
  };

  const handleToggle = async (task: TaskItem) => {
    try {
      await tasksApi.update(task.id, { is_completed: !task.is_completed });
      loadTasks();
    } catch {
      // silently fail
    }
  };

  const handleDelete = async (taskId: number) => {
    try {
      await tasksApi.delete(taskId);
      loadTasks();
    } catch {
      // silently fail
    }
  };

  const handleRestore = async (taskId: number) => {
    try {
      await tasksApi.restore(taskId);
      loadTasks();
    } catch {
      // silently fail
    }
  };

  const handlePermanentDelete = async (taskId: number) => {
    const ok = await confirm({
      title: 'Permanently Delete Task',
      message: 'This task will be permanently deleted. This action cannot be undone.',
      confirmLabel: 'Delete Forever',
      variant: 'danger',
    });
    if (!ok) return;
    try {
      await tasksApi.permanentDelete(taskId);
      loadTasks();
    } catch {
      // silently fail
    }
  };

  const openEdit = (task: TaskItem) => {
    setEditTask(task);
    setEditTitle(task.title);
    setEditDescription(task.description || '');
    setEditDueDate(task.due_date ? task.due_date.slice(0, 16) : '');
    setEditPriority(task.priority || 'medium');
    setEditAssignee(task.assigned_to_user_id || '');
  };

  const handleSaveEdit = async () => {
    if (!editTask || !editTitle.trim()) return;
    setSaving(true);
    try {
      await tasksApi.update(editTask.id, {
        title: editTitle.trim(),
        description: editDescription.trim() || undefined,
        due_date: editDueDate || undefined,
        priority: editPriority,
        assigned_to_user_id: editAssignee ? Number(editAssignee) : 0,
      });
      setEditTask(null);
      loadTasks();
    } catch {
      // silently fail
    } finally {
      setSaving(false);
    }
  };

  const filteredTasks = tasks.filter(t => {
    if (filterStatus === 'archived') return !!t.archived_at;
    if (filterStatus === 'pending') return !t.is_completed && !t.archived_at;
    if (filterStatus === 'completed') return t.is_completed;
    if (filterPriority !== 'all' && t.priority !== filterPriority) return false;
    return true;
  });

  const isCreator = (task: TaskItem) => task.created_by_user_id === user?.id;

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const getLinkedEntityRoute = (task: TaskItem): string | null => {
    if (task.study_guide_id) {
      const guideType = task.study_guide_type || 'study_guide';
      if (guideType === 'quiz') return `/study/quiz/${task.study_guide_id}`;
      if (guideType === 'flashcards') return `/study/flashcards/${task.study_guide_id}`;
      return `/study/guide/${task.study_guide_id}`;
    }
    if (task.course_id) return `/courses/${task.course_id}`;
    return null;
  };

  return (
    <DashboardLayout welcomeSubtitle="Manage your tasks">
      <div className="tasks-page">
        {/* Header */}
        <div className="tasks-header">
          <h3>Tasks</h3>
          <button className="generate-btn" onClick={() => setShowCreate(true)}>
            + New Task
          </button>
        </div>

        {/* Filters */}
        <div className="tasks-filters">
          <div className="tasks-filter-group">
            <label>Status:</label>
            <select value={filterStatus} onChange={e => setFilterStatus(e.target.value as FilterStatus)} className="form-input">
              <option value="all">Active</option>
              <option value="pending">Pending</option>
              <option value="completed">Completed</option>
              <option value="archived">Archived</option>
            </select>
          </div>
          <div className="tasks-filter-group">
            <label>Priority:</label>
            <select value={filterPriority} onChange={e => setFilterPriority(e.target.value as FilterPriority)} className="form-input">
              <option value="all">All</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
          <span className="tasks-count">{filteredTasks.length} task{filteredTasks.length !== 1 ? 's' : ''}</span>
        </div>

        {/* Task list */}
        {loading ? (
          <div className="tasks-empty">Loading tasks...</div>
        ) : error ? (
          <div className="tasks-empty">
            <p>Error loading tasks: {error}</p>
            <button className="generate-btn" onClick={loadTasks}>Retry</button>
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="tasks-empty">
            <p>No tasks found.</p>
            <p>Click "+ New Task" to create one.</p>
          </div>
        ) : (
          <div className="tasks-list">
            {filteredTasks.map(task => (
              <div key={task.id} className={`task-row${task.is_completed ? ' completed' : ''}${task.archived_at ? ' archived' : ''}`}>
                <input
                  type="checkbox"
                  checked={task.is_completed}
                  onChange={() => handleToggle(task)}
                  className="task-row-checkbox"
                  disabled={!!task.archived_at}
                />
                <div className="task-row-body">
                  <div className="task-row-title">{task.title}</div>
                  <div className="task-row-meta">
                    {task.priority && (
                      <span className={`task-priority-badge ${task.priority}`}>
                        {task.priority}
                      </span>
                    )}
                    {task.due_date && (
                      <span className="task-row-due">{formatDate(task.due_date)}</span>
                    )}
                    {task.assignee_name && (
                      <span className="task-row-assignee">
                        {isCreator(task) ? `→ ${task.assignee_name}` : `← ${task.creator_name}`}
                      </span>
                    )}
                    {(task.study_guide_title || task.course_content_title || task.course_name) && (
                      <span
                        className="task-row-link clickable"
                        onClick={(e) => { e.stopPropagation(); const route = getLinkedEntityRoute(task); if (route) navigate(route); }}
                        title={`Go to ${task.study_guide_title ? (task.study_guide_type === 'quiz' ? 'quiz' : task.study_guide_type === 'flashcards' ? 'flashcards' : 'study guide') : task.course_content_title ? 'course' : 'course'}`}
                      >
                        {task.study_guide_title
                          ? `${task.study_guide_type === 'quiz' ? 'Quiz' : task.study_guide_type === 'flashcards' ? 'Flashcards' : 'Study Guide'}: ${task.study_guide_title}`
                          : task.course_content_title
                            ? `Content: ${task.course_content_title}`
                            : `Course: ${task.course_name}`}
                      </span>
                    )}
                  </div>
                </div>
                {isCreator(task) && task.archived_at ? (
                  <div className="task-row-actions">
                    <button className="task-row-btn restore" onClick={() => handleRestore(task.id)} title="Restore">&#8634;</button>
                    <button className="task-row-btn permanent-delete" onClick={() => handlePermanentDelete(task.id)} title="Delete Forever">&#128465;</button>
                  </div>
                ) : isCreator(task) ? (
                  <div className="task-row-actions">
                    <button className="task-row-btn" onClick={() => openEdit(task)} title="Edit">&#9998;</button>
                    <button className="task-row-btn danger" onClick={() => handleDelete(task.id)} title="Archive">&times;</button>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}

        {/* Create modal */}
        {showCreate && (
          <div className="modal-overlay" onClick={() => setShowCreate(false)}>
            <div className="modal" onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h2>Create Task</h2>
                <button className="modal-close" onClick={() => setShowCreate(false)}>&times;</button>
              </div>
              <div className="modal-body">
                <label className="form-label">Title</label>
                <input
                  type="text"
                  placeholder="Task title"
                  value={newTitle}
                  onChange={e => setNewTitle(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleCreate()}
                  className="form-input"
                  autoFocus
                />
                <label className="form-label">Description</label>
                <textarea
                  placeholder="Description (optional)"
                  value={newDescription}
                  onChange={e => setNewDescription(e.target.value)}
                  className="form-input"
                  rows={3}
                />
                <label className="form-label">Due Date</label>
                <input
                  type="datetime-local"
                  value={newDueDate}
                  onChange={e => setNewDueDate(e.target.value)}
                  className="form-input"
                />
                <label className="form-label">Priority</label>
                <select value={newPriority} onChange={e => setNewPriority(e.target.value)} className="form-input">
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
                {assignableUsers.length > 0 && (
                  <>
                    <label className="form-label">Assign To</label>
                    <select value={newAssignee} onChange={e => setNewAssignee(e.target.value ? Number(e.target.value) : '')} className="form-input">
                      <option value="">Unassigned (personal)</option>
                      {assignableUsers.map(u => (
                        <option key={u.user_id} value={u.user_id}>{u.name}</option>
                      ))}
                    </select>
                  </>
                )}
              </div>
              <div className="modal-actions">
                <button className="modal-cancel" onClick={() => setShowCreate(false)} disabled={creating}>Cancel</button>
                <button className="generate-btn" onClick={handleCreate} disabled={creating || !newTitle.trim()}>
                  {creating ? 'Creating...' : 'Create Task'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Edit modal */}
        {editTask && (
          <div className="modal-overlay" onClick={() => setEditTask(null)}>
            <div className="modal" onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h2>Edit Task</h2>
                <button className="modal-close" onClick={() => setEditTask(null)}>&times;</button>
              </div>
              <div className="modal-body">
                <label className="form-label">Title</label>
                <input
                  type="text"
                  value={editTitle}
                  onChange={e => setEditTitle(e.target.value)}
                  className="form-input"
                />
                <label className="form-label">Description</label>
                <textarea
                  value={editDescription}
                  onChange={e => setEditDescription(e.target.value)}
                  className="form-input"
                  rows={3}
                />
                <label className="form-label">Due Date</label>
                <input
                  type="datetime-local"
                  value={editDueDate}
                  onChange={e => setEditDueDate(e.target.value)}
                  className="form-input"
                />
                <label className="form-label">Priority</label>
                <select value={editPriority} onChange={e => setEditPriority(e.target.value)} className="form-input">
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
                {assignableUsers.length > 0 && (
                  <>
                    <label className="form-label">Assign To</label>
                    <select value={editAssignee} onChange={e => setEditAssignee(e.target.value ? Number(e.target.value) : '')} className="form-input">
                      <option value="">Unassigned (personal)</option>
                      {assignableUsers.map(u => (
                        <option key={u.user_id} value={u.user_id}>{u.name}</option>
                      ))}
                    </select>
                  </>
                )}
              </div>
              <div className="modal-actions">
                <button className="modal-cancel" onClick={() => setEditTask(null)}>Cancel</button>
                <button className="generate-btn" onClick={handleSaveEdit} disabled={saving || !editTitle.trim()}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
      {confirmModal}
    </DashboardLayout>
  );
}

