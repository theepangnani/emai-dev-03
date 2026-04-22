import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { tasksApi, parentApi } from '../api/client';
import type { TaskItem, AssignableUser, ChildSummary } from '../api/client';
import type { ChildOverview } from '../api/parent';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { useConfirm } from '../components/ConfirmModal';
import { useFocusTrap } from '../hooks/useFocusTrap';
import { CHILD_COLORS } from '../components/parent/useParentDashboard';
import { CalendarView } from '../components/calendar/CalendarView';
import type { CalendarAssignment } from '../components/calendar/types';
import { getCourseColor, TASK_PRIORITY_COLORS } from '../components/calendar/types';
import { ListSkeleton } from '../components/Skeleton';
import { AddActionButton } from '../components/AddActionButton';
import EmptyState from '../components/EmptyState';
import { PageNav } from '../components/PageNav';
import { ReportBugLink } from '../components/ReportBugLink';
import { ASGFEntryButton } from '../components/asgf/ASGFEntryButton';
import { TaskSourceBadge } from '../components/TaskSourceBadge';
import './TasksPage.css';

type FilterStatus = 'all' | 'pending' | 'completed' | 'archived';
type FilterPriority = 'all' | 'low' | 'medium' | 'high';
type FilterDue = 'all' | 'overdue' | 'today' | 'week' | 'upcoming';

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
    return (due === 'overdue' || due === 'today' || due === 'week' || due === 'upcoming') ? due as FilterDue : 'all';
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
  const [showCreate, setShowCreate] = useState(() => searchParams.get('create') === 'true');
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
  const [remindingTaskId, setRemindingTaskId] = useState<number | null>(null);
  const [reminderToast, setReminderToast] = useState<string | null>(null);
  const [filtersExpanded, setFiltersExpanded] = useState(false);

  // Request completion modal
  const [requestCompletionTask, setRequestCompletionTask] = useState<TaskItem | null>(null);
  const [requestCompletionMessage, setRequestCompletionMessage] = useState('');
  const [requestingCompletion, setRequestingCompletion] = useState(false);
  const { confirm, confirmModal } = useConfirm();
  const createModalRef = useFocusTrap<HTMLDivElement>(showCreate, () => setShowCreate(false));
  const editModalRef = useFocusTrap<HTMLDivElement>(!!editTask, () => setEditTask(null));

  // Calendar state — default expanded on desktop (>= 768px) when no saved preference
  const [calendarCollapsed, setCalendarCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('calendar_collapsed');
      if (saved !== null) return saved !== '0';
      return typeof window !== 'undefined' ? window.innerWidth < 768 : true;
    } catch { return true; }
  });
  const [overviews, setOverviews] = useState<ChildOverview[]>([]);


  useEffect(() => {
    loadTasks();
    loadAssignableUsers();
    if (isParent) loadChildren();
  }, [filterStatus]);

  // Auto-select first child only when there is exactly one child
  useEffect(() => {
    if (isParent && children.length === 1 && filterAssignee === 'all') {
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

  // Fetch overviews for calendar (parent only)
  useEffect(() => {
    if (!isParent || children.length === 0) return;
    const fetchOverviews = async () => {
      try {
        const results = await Promise.all(
          children.map(c => parentApi.getChildOverview(c.student_id))
        );
        setOverviews(results);
      } catch { /* silently fail */ }
    };
    fetchOverviews();
  }, [children]);

  const toggleCalendar = () => {
    setCalendarCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem('calendar_collapsed', next ? '1' : '0'); } catch { /* */ }
      return next;
    });
  };

  // Calendar assignments derived from overviews + tasks
  const courseIds = useMemo(() => overviews.flatMap(o => o.courses.map(c => c.id)), [overviews]);

  const calendarAssignments: CalendarAssignment[] = useMemo(() => {
    const filteredOverviews = filterAssignee === 'all'
      ? overviews
      : overviews.filter(o => o.user_id === filterAssignee);
    const assignments = filteredOverviews.flatMap(overview =>
      overview.assignments
        .filter(a => a.due_date)
        .map(a => ({
          id: a.id,
          title: a.title,
          description: a.description,
          courseId: a.course_id,
          courseName: overview.courses.find(c => c.id === a.course_id)?.name || 'Unknown',
          courseColor: getCourseColor(a.course_id, courseIds),
          dueDate: new Date(a.due_date!),
          childName: children.length > 1 ? overview.full_name : '',
          maxPoints: a.max_points,
          itemType: 'assignment' as const,
        }))
    );
    // CB-TASKSYNC-001 (#3920) — Dedup via structured FK-ish check.
    // When an auto-created Task with source='assignment' exists, its
    // `source_ref` holds the underlying Assignment id. We skip the raw
    // Assignment so only the Task row (which has full task UX) is shown.
    // This retires the older string-level title+date dedup (#3379) now that
    // the backend provides a reliable identifier.
    const assignmentSourceRefs = new Set(
      tasks
        .filter(t => t.source === 'assignment' && t.source_ref != null)
        .map(t => String(t.source_ref))
    );
    const dedupedAssignments = assignmentSourceRefs.size > 0
      ? assignments.filter(a => !assignmentSourceRefs.has(String(a.id)))
      : assignments;
    const filteredCalendarTasks = filterAssignee === 'all'
      ? tasks
      : tasks.filter(t => t.assigned_to_user_id === filterAssignee);
    const taskItems: CalendarAssignment[] = filteredCalendarTasks
      .filter(t => t.due_date)
      .map(t => ({
        id: t.id + 1_000_000,
        taskId: t.id,
        title: t.title,
        description: t.description,
        courseId: 0,
        courseName: '',
        courseColor: TASK_PRIORITY_COLORS[t.priority || 'medium'],
        dueDate: new Date(t.due_date!),
        childName: t.assignee_name || '',
        maxPoints: null,
        itemType: 'task' as const,
        priority: (t.priority || 'medium') as 'low' | 'medium' | 'high',
        isCompleted: t.is_completed,
      }));
    return [...dedupedAssignments, ...taskItems];
  }, [overviews, courseIds, children.length, tasks, filterAssignee]);

  const handleTaskDrop = async (calendarId: number, newDate: Date) => {
    const taskId = calendarId - 1_000_000;
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    const newDueDate = newDate.toISOString();
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, due_date: newDueDate } : t));
    try {
      await tasksApi.update(taskId, { due_date: newDueDate });
    } catch {
      loadTasks(); // revert on failure
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

  const handleRemind = async (task: TaskItem) => {
    setRemindingTaskId(task.id);
    try {
      const result = await tasksApi.remind(task.id);
      // Update the task's last_reminder_sent_at in local state
      setTasks(prev => prev.map(t =>
        t.id === task.id ? { ...t, last_reminder_sent_at: result.reminded_at } : t
      ));
      setReminderToast(`Reminder sent to ${result.assignee_name}`);
      setTimeout(() => setReminderToast(null), 4000);
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to send reminder';
      setReminderToast(detail);
      setTimeout(() => setReminderToast(null), 4000);
    } finally {
      setRemindingTaskId(null);
    }
  };

  const getReminderStatus = (task: TaskItem): { canRemind: boolean; label: string } => {
    if (!task.last_reminder_sent_at) return { canRemind: true, label: 'Send Reminder' };
    const sentAt = new Date(task.last_reminder_sent_at);
    const hoursSince = (Date.now() - sentAt.getTime()) / (1000 * 60 * 60);
    if (hoursSince < 24) {
      const hoursAgo = Math.floor(hoursSince);
      return { canRemind: false, label: hoursAgo < 1 ? 'Reminded just now' : `Reminded ${hoursAgo}h ago` };
    }
    return { canRemind: true, label: 'Send Reminder' };
  };

  const handleRequestCompletion = async () => {
    if (!requestCompletionTask) return;
    setRequestingCompletion(true);
    try {
      // Find the student_id from children based on the task's assigned_to_user_id
      const child = children.find(c => c.user_id === requestCompletionTask.assigned_to_user_id);
      if (!child) {
        setReminderToast('Could not find the linked child for this task');
        setTimeout(() => setReminderToast(null), 4000);
        return;
      }
      const result = await parentApi.requestCompletion(
        child.student_id,
        requestCompletionTask.id,
        requestCompletionMessage.trim() || undefined,
      );
      setReminderToast(result.message);
      setTimeout(() => setReminderToast(null), 4000);
      setRequestCompletionTask(null);
      setRequestCompletionMessage('');
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to send completion request';
      setReminderToast(detail);
      setTimeout(() => setReminderToast(null), 4000);
    } finally {
      setRequestingCompletion(false);
    }
  };

  const filteredTasks = tasks.filter(t => {
    // Status filter
    if (filterStatus === 'archived' && !t.archived_at) return false;
    if (filterStatus === 'pending' && (t.is_completed || t.archived_at)) return false;
    if (filterStatus === 'completed' && !t.is_completed) return false;
    // Assignee, priority, and due filters apply across all status tabs
    if (filterPriority !== 'all' && t.priority !== filterPriority) return false;
    if (filterAssignee !== 'all' && t.assigned_to_user_id !== filterAssignee) return false;
    if (filterDue !== 'all' && t.due_date) {
      const due = t.due_date.includes('T') ? new Date(t.due_date) : new Date(t.due_date + 'T00:00:00');
      const now = new Date();
      const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const todayEnd = new Date(todayStart);
      todayEnd.setDate(todayEnd.getDate() + 1);
      if (filterDue === 'overdue') return due < todayStart && !t.is_completed;
      if (filterDue === 'today') return due >= todayStart && due < todayEnd;
      if (filterDue === 'week' || filterDue === 'upcoming') {
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
      return task.course_content_id ? `/course-materials/${task.course_content_id}?tab=guide` : `/study/guide/${task.study_guide_id}`;
    }
    if (task.course_content_id) return `/course-materials/${task.course_content_id}?tab=document`;
    if (task.course_id) return `/courses/${task.course_id}`;
    return null;
  };

  return (
    <DashboardLayout welcomeSubtitle="Manage your tasks" showBackButton>
      <div className="tasks-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Tasks' },
        ]} />
        {/* Header with title */}
        <div className="tasks-header">
          <h3>Tasks</h3>
          <button className="title-add-btn" onClick={() => setShowCreate(true)} title="New Task" aria-label="New Task">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 11 12 14 22 4" />
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
          </button>
        </div>

        {/* Child selector pills (parent only) + add action button */}
        {isParent && children.length > 0 ? (
          <div className="tasks-child-selector">
            {/* "All" button — shown when there are multiple children */}
            {children.length > 1 && (
              <button
                className={`pd-child-tab pd-child-tab-all${filterAssignee === 'all' ? ' active' : ''}`}
                onClick={() => { setFilterAssignee('all'); searchParams.delete('assignee'); setSearchParams(searchParams, { replace: true }); sessionStorage.removeItem('selectedChildId'); }}
                title="All children"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </button>
            )}
            {children.map((child, index) => (
              <button
                key={child.user_id}
                className={`pd-child-tab${filterAssignee === child.user_id ? ' active' : ''}`}
                onClick={() => { setFilterAssignee(child.user_id); searchParams.set('assignee', String(child.user_id)); setSearchParams(searchParams, { replace: true }); sessionStorage.setItem('selectedChildId', String(child.user_id)); }}
              >
                <span className="pd-child-color-dot" style={{ backgroundColor: CHILD_COLORS[index % CHILD_COLORS.length] }} />
                {child.full_name}
                {child.grade_level != null && <span className="pd-grade-badge">Grade {child.grade_level}</span>}
              </button>
            ))}
            <AddActionButton actions={[
              { icon: '\u2705', label: 'New Task', onClick: () => setShowCreate(true) },
            ]} />
          </div>
        ) : (
          <div className="tasks-child-selector" />
        )}

        {/* Collapsible Calendar Section */}
        {(
          <>
            <div className="calendar-collapse-section">
              <button className="calendar-collapse-toggle" onClick={toggleCalendar}>
                <span className={`calendar-collapse-chevron${calendarCollapsed ? '' : ' expanded'}`}>&#9654;</span>
                <span className="calendar-collapse-label">Calendar</span>
                {calendarCollapsed && calendarAssignments.length > 0 && (
                  <span className="calendar-badge">{calendarAssignments.length} item{calendarAssignments.length !== 1 ? 's' : ''}</span>
                )}
              </button>
            </div>

            {!calendarCollapsed && (
              calendarAssignments.length === 0 ? (
                <EmptyState
                  icon={'\uD83D\uDCC5'}
                  title="Calendar is clear"
                  description="No upcoming assignments or tasks this week."
                  className="tasks-calendar-empty"
                />
              ) : (
                <CalendarView
                  assignments={calendarAssignments}
                  onCreateStudyGuide={() => {}}
                  onGoToCourse={(courseId) => navigate(`/courses?highlight=${courseId}`)}
                  onViewStudyGuides={() => navigate('/course-materials')}
                  onTaskDrop={handleTaskDrop}
                />
              )
            )}
          </>
        )}

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
          <div className="tasks-empty empty-state">
            <p>Error loading tasks: {error}</p>
            <ReportBugLink errorMessage={error} />
            <button className="generate-btn btn-primary" onClick={loadTasks}>Retry</button>
          </div>
        ) : filteredTasks.length === 0 ? (
          <EmptyState
            icon={<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2" /><rect x="9" y="3" width="6" height="4" rx="1" /><path d="m9 14 2 2 4-4" /></svg>}
            title="No tasks yet"
            description="Create tasks to track assignments and study activities for your children."
            action={{ label: 'Create Your First Task', onClick: () => setShowCreate(true) }}
          />
        ) : (
          <div className="tasks-list">
            {(() => {
              const renderTaskRow = (task: TaskItem) => (
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
                      <TaskSourceBadge
                        source={task.source}
                        sourceStatus={task.source_status}
                        confidence={task.source_confidence}
                      />
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
                      {!task.is_completed && !task.archived_at && (
                        <ASGFEntryButton
                          label="Help me understand"
                          prefilledQuestion={task.title}
                          prefilledContext={task.course_name || undefined}
                          variant="inline"
                        />
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
                      {isParent && task.assigned_to_user_id && !task.is_completed && (() => {
                        const { canRemind, label } = getReminderStatus(task);
                        return (
                          <>
                            <button
                              className={`task-row-btn remind${!canRemind ? ' reminded' : ''}`}
                              onClick={(e) => { e.stopPropagation(); handleRemind(task); }}
                              disabled={!canRemind || remindingTaskId === task.id}
                              title={label}
                              aria-label={label}
                            >
                              {remindingTaskId === task.id ? <span className="btn-spinner" /> : '\uD83D\uDD14'} {canRemind ? '' : label}
                            </button>
                            <button
                              className="task-row-btn request-completion"
                              onClick={(e) => { e.stopPropagation(); setRequestCompletionTask(task); }}
                              title="Request completion"
                              aria-label="Request child to complete this task"
                            >
                              &#9993;
                            </button>
                          </>
                        );
                      })()}
                      <button className="task-row-btn" onClick={() => openEdit(task)} title="Edit" aria-label="Edit this task">&#9998;</button>
                    </div>
                  ) : null}
                </div>
              );

              // Only group when showing 'all' or 'pending' — flat list for completed/archived
              if (filterStatus === 'completed' || filterStatus === 'archived') {
                return filteredTasks.map(renderTaskRow);
              }

              const today = new Date();
              today.setHours(0, 0, 0, 0);
              const weekFromNow = new Date(today);
              weekFromNow.setDate(today.getDate() + 7);

              const overdue = filteredTasks.filter(t => !t.is_completed && !t.archived_at && t.due_date && new Date(t.due_date) < today);
              const dueToday = filteredTasks.filter(t => !t.is_completed && !t.archived_at && t.due_date && new Date(t.due_date).toDateString() === today.toDateString());
              const thisWeek = filteredTasks.filter(t => !t.is_completed && !t.archived_at && t.due_date && new Date(t.due_date) > today && new Date(t.due_date) <= weekFromNow);
              const later = filteredTasks.filter(t => !t.is_completed && !t.archived_at && (!t.due_date || new Date(t.due_date) > weekFromNow));
              const completedGroup = filteredTasks.filter(t => t.is_completed && !t.archived_at);
              const archivedGroup = filteredTasks.filter(t => !!t.archived_at);

              return (
                <>
                  {overdue.length > 0 && (
                    <>
                      <div className="task-group-header task-group-overdue">
                        <span className="task-group-icon">{'\uD83D\uDD34'}</span>
                        Overdue
                        <span className="task-group-count">{overdue.length}</span>
                      </div>
                      {overdue.map(renderTaskRow)}
                    </>
                  )}
                  {dueToday.length > 0 && (
                    <>
                      <div className="task-group-header task-group-today">
                        <span className="task-group-icon">{'\u2600\uFE0F'}</span>
                        Due Today
                        <span className="task-group-count">{dueToday.length}</span>
                      </div>
                      {dueToday.map(renderTaskRow)}
                    </>
                  )}
                  {thisWeek.length > 0 && (
                    <>
                      <div className="task-group-header task-group-week">
                        <span className="task-group-icon">{'\uD83D\uDCC5'}</span>
                        This Week
                        <span className="task-group-count">{thisWeek.length}</span>
                      </div>
                      {thisWeek.map(renderTaskRow)}
                    </>
                  )}
                  {later.length > 0 && (
                    <>
                      <div className="task-group-header task-group-later">
                        <span className="task-group-icon">{'\uD83D\uDD52'}</span>
                        Later
                        <span className="task-group-count">{later.length}</span>
                      </div>
                      {later.map(renderTaskRow)}
                    </>
                  )}
                  {completedGroup.length > 0 && (
                    <>
                      <div className="task-group-header task-group-completed">
                        <span className="task-group-icon">{'\u2705'}</span>
                        Completed
                        <span className="task-group-count">{completedGroup.length}</span>
                      </div>
                      {completedGroup.map(renderTaskRow)}
                    </>
                  )}
                  {archivedGroup.length > 0 && (
                    <>
                      <div className="task-group-header task-group-archived">
                        <span className="task-group-icon">{'\uD83D\uDCE6'}</span>
                        Archived
                        <span className="task-group-count">{archivedGroup.length}</span>
                      </div>
                      {archivedGroup.map(renderTaskRow)}
                    </>
                  )}
                </>
              );
            })()}
          </div>
        )}

        {/* Create modal */}
        {showCreate && (
          <div className="modal-overlay" onClick={() => setShowCreate(false)}>
            <div className="modal" role="dialog" aria-modal="true" aria-label="Create Task" ref={createModalRef} onClick={e => e.stopPropagation()}>
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
                <button className="modal-cancel btn-secondary" onClick={() => setShowCreate(false)} disabled={creating}>Cancel</button>
                <button className="generate-btn btn-primary" onClick={handleCreate} disabled={creating || !newTitle.trim()}>
                  {creating ? 'Creating...' : 'Create Task'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Edit modal */}
        {editTask && (
          <div className="modal-overlay" onClick={() => setEditTask(null)}>
            <div className="modal" role="dialog" aria-modal="true" aria-label="Edit Task" ref={editModalRef} onClick={e => e.stopPropagation()}>
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
                <button className="modal-cancel btn-secondary" onClick={() => setEditTask(null)}>Cancel</button>
                <button className="generate-btn btn-primary" onClick={handleSaveEdit} disabled={saving || !editTitle.trim()}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
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
            </div>
          </div>
        )}
      </div>
      {/* Request Completion modal */}
      {requestCompletionTask && (
        <div className="modal-overlay" onClick={() => { setRequestCompletionTask(null); setRequestCompletionMessage(''); }}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Request Completion" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Request Completion</h2>
              <button className="modal-close" onClick={() => { setRequestCompletionTask(null); setRequestCompletionMessage(''); }}>&times;</button>
            </div>
            <div className="modal-body">
              <p style={{ margin: '0 0 12px', color: 'var(--color-text-secondary, #6b7280)', fontSize: '14px' }}>
                Send a notification to <strong>{requestCompletionTask.assignee_name}</strong> asking them to complete:
              </p>
              <p style={{ margin: '0 0 16px', fontWeight: 600 }}>{requestCompletionTask.title}</p>
              <label className="form-label">Message (optional)</label>
              <textarea
                placeholder="Add a note for your child..."
                value={requestCompletionMessage}
                onChange={e => setRequestCompletionMessage(e.target.value)}
                className="form-input"
                rows={3}
                maxLength={500}
              />
            </div>
            <div className="modal-actions">
              <button className="modal-cancel btn-secondary" onClick={() => { setRequestCompletionTask(null); setRequestCompletionMessage(''); }} disabled={requestingCompletion}>Cancel</button>
              <button className="generate-btn btn-primary" onClick={handleRequestCompletion} disabled={requestingCompletion}>
                {requestingCompletion ? 'Sending...' : 'Send Request'}
              </button>
            </div>
          </div>
        </div>
      )}
      {confirmModal}
      {reminderToast && <div className="toast-notification">{reminderToast}</div>}
    </DashboardLayout>
  );
}

