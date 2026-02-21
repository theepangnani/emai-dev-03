import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { tasksApi, parentApi } from '../api/client';
import type { TaskItem, AssignableUser, ChildSummary } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { useConfirm } from '../components/ConfirmModal';
import { CHILD_COLORS } from '../components/parent/useParentDashboard';
import { ListSkeleton } from '../components/Skeleton';
import './TasksPage.css';

type FilterStatus = 'all' | 'pending' | 'completed' | 'archived';
type FilterPriority = 'all' | 'low' | 'medium' | 'high';
type FilterDue = 'all' | 'overdue' | 'today' | 'week';

export function TasksPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [assignableUsers, setAssignableUsers] = useState<AssignableUser[]>([]);
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const isParent = user?.role === 'parent';
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<FilterStatus>(() => {
    const status = searchParams.get('status');
    return (status === 'pending' || status === 'completed' || status === 'archived') ? status : 'all';
  });
  const [filterPriority, setFilterPriority] = useState<FilterPriority>(() => {
    const priority = searchParams.get('priority');
    return (priority === 'low' || priority === 'medium' || priority === 'high') ? priority : 'all';
  });
  const [filterDue, setFilterDue] = useState<FilterDue>(() => {
    const due = searchParams.get('due');
    return (due === 'overdue' || due === 'today' || due === 'week') ? due : 'all';
  });
  const [filterAssignee, setFilterAssignee] = useState<number | 'all'>(() => {
    const navState = location.state as { selectedChild?: number | null } | null;
    if (navState?.selectedChild) return navState.selectedChild;
    const assignee = searchParams.get('assignee');
    if (assignee) return Number(assignee);
    const stored = sessionStorage.getItem('selectedChildId');
    return stored ? Number(stored) : 'all';
  });

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
  const [loadingTaskId, setLoadingTaskId] = useState<number | null>(null);
  const [filtersExpanded, setFiltersExpanded] = useState(false);
  const { confirm, confirmModal } = useConfirm();

  useEffect(() => {
    loadTasks();
    loadAssignableUsers();
    if (isParent) loadChildren();
  }, [filterStatus]);

  // Auto-select first child when children load and no specific child is selected
  useEffect(() => {
    if (isParent && children.length > 0 && filterAssignee === 'all') {
      const first = children[0];
      setFilterAssignee(first.user_id);
      searchParams.set('assignee', String(first.user_id));
      setSearchParams(searchParams, { replace: true });
      sessionStorage.setItem('selectedChildId', String(first.user_id));
    }
  }, [children]);

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

  const loadChildren = async () => {
    try {
      const data = await parentApi.getChildren();
      setChildren(data);
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
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create task');
    } finally {
      setCreating(false);
    }
  };

  const handleToggle = async (task: TaskItem) => {
    setLoadingTaskId(task.id);
    try {
      await tasksApi.update(task.id, { is_completed: !task.is_completed });
      loadTasks();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update task');
    } finally {
      setLoadingTaskId(null);
    }
  };

  const handleDelete = async (taskId: number) => {
    const ok = await confirm({ title: 'Archive Task', message: 'Archive this task? You can restore it later.', confirmLabel: 'Archive' });
    if (!ok) return;
    setLoadingTaskId(taskId);
    try {
      await tasksApi.delete(taskId);
      loadTasks();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete task');
    } finally {
      setLoadingTaskId(null);
    }
  };

  const handleRestore = async (taskId: number) => {
    try {
      await tasksApi.restore(taskId);
      loadTasks();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to restore task');
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
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to permanently delete task');
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
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save task');
    } finally {
      setSaving(false);
    }
  };

  const filteredTasks = tasks.filter(t => {
    if (filterStatus === 'archived') return !!t.archived_at;
    if (filterStatus === 'pending') return !t.is_completed && !t.archived_at;
    if (filterStatus === 'completed') return t.is_completed;
    if (filterPriority !== 'all' && t.priority !== filterPriority) return false;
    if (filterAssignee !== 'all' && t.assigned_to_user_id !== filterAssignee) return false;
    if (filterDue !== 'all' && t.due_date) {
      const due = new Date(t.due_date);
      const now = new Date();
      const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const todayEnd = new Date(todayStart);
      todayEnd.setDate(todayEnd.getDate() + 1);
      if (filterDue === 'overdue') return due < todayStart && !t.is_completed;
      if (filterDue === 'today') return due >= todayStart && due < todayEnd;
      if (filterDue === 'week') {
        const weekEnd = new Date(todayStart);
        weekEnd.setDate(weekEnd.getDate() + 7);
        return due >= todayStart && due < weekEnd;
      }
    } else if (filterDue !== 'all' && !t.due_date) {
      return false;
    }
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
    <DashboardLayout welcomeSubtitle="Manage your tasks" showBackButton>
      <div className="tasks-page">
        {/* Header with title */}
        <div className="tasks-header">
          <h3>Tasks</h3>
        </div>

        {/* Child selector pills (parent only) */}
        {isParent && children.length > 0 && (
          <div className="tasks-child-selector">
            {children.map((child, index) => (
              <button
                key={child.user_id}
                className={`child-tab${filterAssignee === child.user_id ? ' active' : ''}`}
                onClick={() => { setFilterAssignee(child.user_id); searchParams.set('assignee', String(child.user_id)); setSearchParams(searchParams, { replace: true }); sessionStorage.setItem('selectedChildId', String(child.user_id)); }}
              >
                <span className="child-color-dot" style={{ backgroundColor: CHILD_COLORS[index % CHILD_COLORS.length] }} />
                {child.full_name}
                {child.grade_level != null && <span className="grade-badge">Grade {child.grade_level}</span>}
              </button>
            ))}
          </div>
        )}

        {/* New Task button (below child selector) */}
        <button className="tasks-new-btn" onClick={() => setShowCreate(true)}>
          <span className="tasks-new-btn-icon">{'\u2705'}</span>
          <span>New Task</span>
        </button>

        {/* Filter bar: count + toggle + active-filter badges */}
        <div className="tasks-filter-bar">
          <span className="tasks-count">{filteredTasks.length} task{filteredTasks.length !== 1 ? 's' : ''}</span>
          {/* Show active non-default filters as inline badges */}
          {!filtersExpanded && (
            <div className="tasks-active-filters">
              {filterStatus !== 'all' && (
                <span className="tasks-active-badge">{filterStatus === 'pending' ? 'Pending' : filterStatus === 'completed' ? 'Completed' : 'Archived'}</span>
              )}
              {filterPriority !== 'all' && (
                <span className="tasks-active-badge">{filterPriority}</span>
              )}
              {filterDue !== 'all' && (
                <span className="tasks-active-badge">{filterDue === 'overdue' ? 'Overdue' : filterDue === 'today' ? 'Today' : 'This Week'}</span>
              )}
            </div>
          )}
          <button
            className={`tasks-filter-toggle${filtersExpanded ? ' expanded' : ''}`}
            onClick={() => setFiltersExpanded(v => !v)}
          >
            <span className="tasks-filter-toggle-icon">{filtersExpanded ? '\u25B2' : '\u25BC'}</span>
            Filters
            {(() => {
              const count = (filterStatus !== 'all' ? 1 : 0) + (filterPriority !== 'all' ? 1 : 0) + (filterDue !== 'all' ? 1 : 0) + (!isParent && filterAssignee !== 'all' ? 1 : 0);
              return count > 0 ? <span className="tasks-filter-count">{count}</span> : null;
            })()}
          </button>
        </div>

        {/* Collapsible filter panel */}
        {filtersExpanded && (
          <div className="tasks-filters-panel">
            {/* Status */}
            <div className="tasks-chip-group">
              <span className="tasks-chip-label">Status</span>
              <div className="tasks-chip-row">
                {([
                  { key: 'all', label: 'Active' },
                  { key: 'pending', label: 'Pending' },
                  { key: 'completed', label: 'Completed' },
                  { key: 'archived', label: 'Archived' },
                ] as const).map(opt => (
                  <button
                    key={opt.key}
                    className={`tasks-chip${filterStatus === opt.key ? ' active' : ''}`}
                    onClick={() => { setFilterStatus(opt.key); if (opt.key === 'all') { searchParams.delete('status'); } else { searchParams.set('status', opt.key); } setSearchParams(searchParams, { replace: true }); }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Priority */}
            <div className="tasks-chip-group">
              <span className="tasks-chip-label">Priority</span>
              <div className="tasks-chip-row">
                {([
                  { key: 'all', label: 'All' },
                  { key: 'high', label: 'High' },
                  { key: 'medium', label: 'Medium' },
                  { key: 'low', label: 'Low' },
                ] as const).map(opt => (
                  <button
                    key={opt.key}
                    className={`tasks-chip${filterPriority === opt.key ? ' active' : ''}`}
                    onClick={() => { setFilterPriority(opt.key); if (opt.key === 'all') { searchParams.delete('priority'); } else { searchParams.set('priority', opt.key); } setSearchParams(searchParams, { replace: true }); }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Due */}
            <div className="tasks-chip-group">
              <span className="tasks-chip-label">Due</span>
              <div className="tasks-chip-row">
                {([
                  { key: 'all', label: 'All' },
                  { key: 'overdue', label: 'Overdue' },
                  { key: 'today', label: 'Today' },
                  { key: 'week', label: 'This Week' },
                ] as const).map(opt => (
                  <button
                    key={opt.key}
                    className={`tasks-chip${filterDue === opt.key ? ' active' : ''}`}
                    onClick={() => { setFilterDue(opt.key); if (opt.key === 'all') { searchParams.delete('due'); } else { searchParams.set('due', opt.key); } setSearchParams(searchParams, { replace: true }); }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Assignee chip filter (non-parent fallback when no children) */}
            {!isParent && assignableUsers.length > 0 && (
              <div className="tasks-chip-group">
                <span className="tasks-chip-label">Assignee</span>
                <div className="tasks-chip-row">
                  <button
                    className={`tasks-chip${filterAssignee === 'all' ? ' active' : ''}`}
                    onClick={() => { setFilterAssignee('all'); searchParams.delete('assignee'); setSearchParams(searchParams, { replace: true }); }}
                  >
                    All
                  </button>
                  {assignableUsers.map(u => (
                    <button
                      key={u.user_id}
                      className={`tasks-chip${filterAssignee === u.user_id ? ' active' : ''}`}
                      onClick={() => { setFilterAssignee(u.user_id); searchParams.set('assignee', String(u.user_id)); setSearchParams(searchParams, { replace: true }); }}
                    >
                      {u.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Task list */}
        {loading ? (
          <ListSkeleton rows={5} />
        ) : error ? (
          <div className="tasks-empty">
            <p>Error loading tasks: {error}</p>
            <button className="generate-btn" onClick={loadTasks}>Retry</button>
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="tasks-empty">
            <p>No tasks found.</p>
            <p>Click "New Task" to create one.</p>
          </div>
        ) : (
          <div className="tasks-list">
            {filteredTasks.map(task => (
              <div key={task.id} className={`task-row${task.is_completed ? ' completed' : ''}${task.archived_at ? ' archived' : ''}`}>
                {loadingTaskId === task.id ? (
                  <span className="btn-spinner task-row-spinner" />
                ) : (
                  <input
                    type="checkbox"
                    checked={task.is_completed}
                    onChange={() => handleToggle(task)}
                    className="task-row-checkbox"
                    disabled={!!task.archived_at}
                  />
                )}
                <div className="task-row-body" onClick={() => navigate(`/tasks/${task.id}`)} style={{ cursor: 'pointer' }}>
                  <div className="task-row-title">{task.title}</div>
                  <div className="task-row-meta">
                    {task.priority && (
                      <span className={`task-priority-badge ${task.priority}`} aria-label={`Priority: ${task.priority}`}>
                        {task.priority === 'high' ? '\u25B2 ' : task.priority === 'low' ? '\u25BC ' : '\u25CF '}{task.priority}
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
                        title={`Go to ${task.study_guide_title ? (task.study_guide_type === 'quiz' ? 'quiz' : task.study_guide_type === 'flashcards' ? 'flashcards' : 'study guide') : task.course_content_title ? 'material' : 'class'}`}
                      >
                        {task.study_guide_title
                          ? `${task.study_guide_type === 'quiz' ? 'Quiz' : task.study_guide_type === 'flashcards' ? 'Flashcards' : 'Study Guide'}: ${task.study_guide_title}`
                          : task.course_content_title
                            ? `Content: ${task.course_content_title}`
                            : `Class: ${task.course_name}`}
                      </span>
                    )}
                  </div>
                </div>
                {isCreator(task) && task.archived_at ? (
                  <div className="task-row-actions">
                    <button className="task-row-btn restore" onClick={() => handleRestore(task.id)} title="Restore" aria-label="Restore this task">&#8634;</button>
                    <button className="task-row-btn permanent-delete" onClick={() => handlePermanentDelete(task.id)} title="Delete Forever" aria-label="Permanently delete this task">&#128465;</button>
                  </div>
                ) : isCreator(task) ? (
                  <div className="task-row-actions">
                    <button className="task-row-btn" onClick={() => openEdit(task)} title="Edit" aria-label="Edit this task">&#9998;</button>
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
              <div className="task-modal-danger-zone">
                <button
                  className="task-modal-archive-btn"
                  onClick={async () => { setEditTask(null); await handleDelete(editTask.id); }}
                  title="Archive this task"
                >
                  Archive
                </button>
                <button
                  className="task-modal-delete-btn"
                  onClick={async () => { setEditTask(null); await handlePermanentDelete(editTask.id); }}
                  title="Permanently delete this task"
                >
                  Delete Forever
                </button>
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

