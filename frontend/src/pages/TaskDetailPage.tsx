import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { tasksApi, coursesApi, studyApi, courseContentsApi, type TaskItem, type StudyGuide, type CourseContentItem, type AssignableUser } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { useConfirm } from '../components/ConfirmModal';
import { useFocusTrap } from '../hooks/useFocusTrap';
import { DetailSkeleton, ListSkeleton } from '../components/Skeleton';
import { PageNav } from '../components/PageNav';
import './TaskDetailPage.css';

interface CourseOption { id: number; name: string; }
interface ContentOption { id: number; title: string; content_type: string; }
interface GuideOption { id: number; title: string; guide_type: string; }

type LinkType = 'course' | 'course_content' | 'study_guide';

export function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { confirm, confirmModal } = useConfirm();
  const [task, setTask] = useState<TaskItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit mode state
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editDueDate, setEditDueDate] = useState('');
  const [editDueTime, setEditDueTime] = useState('');
  const [editPriority, setEditPriority] = useState('medium');
  const [editAssignee, setEditAssignee] = useState<string>('');
  const [assignableUsers, setAssignableUsers] = useState<AssignableUser[]>([]);
  const [saving, setSaving] = useState(false);

  // Link modal state
  const [linkModalOpen, setLinkModalOpen] = useState(false);
  const [linkType, setLinkType] = useState<LinkType>('course');
  const [linkSearch, setLinkSearch] = useState('');
  const [courses, setCourses] = useState<CourseOption[]>([]);
  const [contents, setContents] = useState<ContentOption[]>([]);
  const [guides, setGuides] = useState<GuideOption[]>([]);
  const [linkLoading, setLinkLoading] = useState(false);

  const linkModalRef = useFocusTrap<HTMLDivElement>(linkModalOpen, () => setLinkModalOpen(false));

  const taskId = parseInt(id || '0');

  useEffect(() => {
    if (!taskId) return;
    (async () => {
      try {
        const data = await tasksApi.get(taskId);
        setTask(data);
      } catch {
        setError('Task not found or not accessible');
      } finally {
        setLoading(false);
      }
    })();
  }, [taskId]);

  const handleToggleComplete = async () => {
    if (!task) return;
    try {
      const updated = await tasksApi.update(task.id, { is_completed: !task.is_completed });
      setTask(updated);
    } catch { /* ignore */ }
  };

  const handleDelete = async () => {
    if (!task) return;
    const ok = await confirm({
      title: 'Delete Task',
      message: `Delete "${task.title}"? This cannot be undone.`,
      confirmLabel: 'Delete',
      variant: 'danger',
    });
    if (!ok) return;
    try {
      await tasksApi.delete(task.id);
      navigate('/tasks');
    } catch { /* ignore */ }
  };

  const startEditing = () => {
    if (!task) return;
    setEditTitle(task.title);
    setEditDescription(task.description || '');
    // Format due_date for separate date + time inputs
    if (task.due_date) {
      const d = new Date(task.due_date);
      const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
      setEditDueDate(local.toISOString().slice(0, 10));
      setEditDueTime(local.toISOString().slice(11, 16));
    } else {
      setEditDueDate('');
      setEditDueTime('');
    }
    setEditPriority(task.priority || 'medium');
    setEditAssignee(task.assigned_to_user_id ? String(task.assigned_to_user_id) : '');
    setEditing(true);
    // Load assignable users
    tasksApi.getAssignableUsers().then(setAssignableUsers).catch(() => {});
  };

  const cancelEditing = () => {
    setEditing(false);
  };

  const handleSaveEdit = async () => {
    if (!task || !editTitle.trim()) return;
    setSaving(true);
    try {
      const updated = await tasksApi.update(task.id, {
        title: editTitle.trim(),
        description: editDescription.trim() || undefined,
        due_date: editDueDate ? new Date(`${editDueDate}T${editDueTime || '00:00'}`).toISOString() : undefined,
        priority: editPriority,
        assigned_to_user_id: editAssignee ? Number(editAssignee) : 0,
      });
      setTask(updated);
      setEditing(false);
    } catch { /* ignore */ }
    setSaving(false);
  };

  const handleUnlink = async (type: LinkType) => {
    if (!task) return;
    try {
      const payload: Record<string, number> = {};
      if (type === 'course') payload.course_id = 0;
      if (type === 'course_content') payload.course_content_id = 0;
      if (type === 'study_guide') payload.study_guide_id = 0;
      const updated = await tasksApi.update(task.id, payload);
      setTask(updated);
    } catch { /* ignore */ }
  };

  const openLinkModal = async (type: LinkType) => {
    setLinkType(type);
    setLinkSearch('');
    setLinkModalOpen(true);
    setLinkLoading(true);
    try {
      if (type === 'course') {
        const data = await coursesApi.list();
        setCourses(data.map((c: { id: number; name: string }) => ({ id: c.id, name: c.name })));
      } else if (type === 'course_content') {
        // Load content from all courses the user has access to
        const courseList = await coursesApi.list();
        const allContent: ContentOption[] = [];
        for (const c of courseList) {
          try {
            const items: CourseContentItem[] = await courseContentsApi.list(c.id);
            allContent.push(...items.map((cc) => ({ id: cc.id, title: cc.title, content_type: cc.content_type })));
          } catch { /* skip courses with no access */ }
        }
        setContents(allContent);
      } else {
        const data: StudyGuide[] = await studyApi.listGuides({ include_children: true });
        setGuides(data.map(g => ({ id: g.id, title: g.title, guide_type: g.guide_type || 'study_guide' })));
      }
    } catch { /* ignore */ }
    setLinkLoading(false);
  };

  const handleLink = async (resourceId: number) => {
    if (!task) return;
    try {
      const payload: Record<string, number> = {};
      if (linkType === 'course') payload.course_id = resourceId;
      if (linkType === 'course_content') payload.course_content_id = resourceId;
      if (linkType === 'study_guide') payload.study_guide_id = resourceId;
      const updated = await tasksApi.update(task.id, payload);
      setTask(updated);
      setLinkModalOpen(false);
    } catch { /* ignore */ }
  };

  const getStudyGuideRoute = (task: TaskItem): string | null => {
    if (!task.study_guide_id) return null;
    const guideType = task.study_guide_type || 'study_guide';
    if (guideType === 'quiz') return `/study/quiz/${task.study_guide_id}`;
    if (guideType === 'flashcards') return `/study/flashcards/${task.study_guide_id}`;
    return `/study/guide/${task.study_guide_id}`;
  };

  const guideTypeIcon = (type: string | null) => {
    if (type === 'quiz') return '\u2753';
    if (type === 'flashcards') return '\uD83C\uDCCF';
    return '\uD83D\uDCD6';
  };

  const priorityLabel = (p: string | null) => {
    if (p === 'high') return '\u25B2 High';
    if (p === 'low') return '\u25BC Low';
    return '\u25CF Medium';
  };

  const linkTypeLabel: Record<LinkType, string> = {
    course: 'Class',
    course_content: 'Class Material',
    study_guide: 'Study Guide',
  };

  const guideTypeLabel = (t: string) => {
    if (t === 'quiz') return 'Quiz';
    if (t === 'flashcards') return 'Flashcards';
    return 'Study Guide';
  };

  // Filter helpers
  const filteredCourses = courses.filter(c => c.name.toLowerCase().includes(linkSearch.toLowerCase()));
  const filteredContents = contents.filter(c => c.title.toLowerCase().includes(linkSearch.toLowerCase()));
  const filteredGuides = guides.filter(g => g.title.toLowerCase().includes(linkSearch.toLowerCase()));

  if (loading) return <DashboardLayout headerSlot={() => null}><DetailSkeleton /></DashboardLayout>;
  if (error || !task) return (
    <DashboardLayout headerSlot={() => null}>
      <div className="td-error">
        <p>{error || 'Task not found'}</p>
        <Link to="/tasks" className="td-back-link">Back to Tasks</Link>
      </div>
    </DashboardLayout>
  );

  const studyGuideRoute = getStudyGuideRoute(task);
  const hasLinkedResources = !!(task.study_guide_id || task.course_content_id || task.course_id || task.note_id);

  return (
    <DashboardLayout headerSlot={() => null}>
      <div className="td-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Tasks', to: '/tasks' },
          { label: task?.title || 'Task' },
        ]} />

        {/* Task Info Card */}
        <div className="td-card">
          {editing ? (
            /* ---- Edit Mode ---- */
            <div className="td-edit-form">
              <div className="td-edit-group">
                <label className="td-edit-label">Title</label>
                <input
                  type="text"
                  className="td-edit-input"
                  value={editTitle}
                  onChange={e => setEditTitle(e.target.value)}
                  autoFocus
                />
              </div>
              <div className="td-edit-group">
                <label className="td-edit-label">Description</label>
                <textarea
                  className="td-edit-textarea"
                  value={editDescription}
                  onChange={e => setEditDescription(e.target.value)}
                  rows={3}
                  placeholder="Optional description..."
                />
              </div>
              <div className="td-edit-row">
                <div className="td-edit-group">
                  <label className="td-edit-label">Due Date</label>
                  <div className="td-edit-datetime-row">
                    <input
                      type="date"
                      className="td-edit-input"
                      value={editDueDate}
                      onChange={e => setEditDueDate(e.target.value)}
                    />
                    <input
                      type="time"
                      className="td-edit-input td-edit-time"
                      value={editDueTime}
                      onChange={e => setEditDueTime(e.target.value)}
                    />
                  </div>
                </div>
                <div className="td-edit-group">
                  <label className="td-edit-label">Priority</label>
                  <select
                    className="td-edit-input"
                    value={editPriority}
                    onChange={e => setEditPriority(e.target.value)}
                  >
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
                <div className="td-edit-group">
                  <label className="td-edit-label">Assignee</label>
                  <select
                    className="td-edit-input"
                    value={editAssignee}
                    onChange={e => setEditAssignee(e.target.value)}
                  >
                    <option value="">Unassigned</option>
                    {assignableUsers.map(u => (
                      <option key={u.user_id} value={u.user_id}>{u.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="td-actions">
                <button className="td-action-btn primary" onClick={handleSaveEdit} disabled={saving || !editTitle.trim()}>
                  {saving ? 'Saving...' : 'Save'}
                </button>
                <button className="td-action-btn" onClick={cancelEditing} disabled={saving}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            /* ---- View Mode ---- */
            <>
              <div className="td-title-row">
                <button
                  className={`td-check${task.is_completed ? ' checked' : ''}`}
                  onClick={handleToggleComplete}
                  title={task.is_completed ? 'Mark incomplete' : 'Mark complete'}
                  aria-label={task.is_completed ? 'Mark incomplete' : 'Mark complete'}
                >
                  <span aria-hidden="true">{task.is_completed ? '\u2705' : '\u2B1C'}</span>
                </button>
                <h2 className={task.is_completed ? 'td-completed' : ''}>{task.title}</h2>
              </div>

              {task.description && (
                <p className="td-description">{task.description}</p>
              )}

              <div className="td-meta">
                {task.due_date && (
                  <div className="td-meta-item">
                    <span className="td-meta-label">Due</span>
                    <span className="td-meta-value">
                      {new Date(task.due_date.includes('T') ? task.due_date : task.due_date + 'T00:00:00').toLocaleDateString(undefined, {
                        weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
                      })}
                      {task.due_date.includes('T') && (
                        <>
                          {' at '}
                          {new Date(task.due_date).toLocaleTimeString(undefined, {
                            hour: 'numeric', minute: '2-digit',
                          })}
                        </>
                      )}
                    </span>
                  </div>
                )}
                <div className="td-meta-item">
                  <span className="td-meta-label">Priority</span>
                  <span className={`td-priority-badge ${task.priority || 'medium'}`} aria-label={`Priority: ${task.priority || 'medium'}`}>
                    {priorityLabel(task.priority)}
                  </span>
                </div>
                <div className="td-meta-item">
                  <span className="td-meta-label">Status</span>
                  <span className={`td-status-badge ${task.is_completed ? 'done' : 'pending'}`}>
                    {task.is_completed ? 'Completed' : 'Pending'}
                  </span>
                </div>
                {task.assignee_name && (
                  <div className="td-meta-item">
                    <span className="td-meta-label">Assigned to</span>
                    <span className="td-meta-value">{task.assignee_name}</span>
                  </div>
                )}
                <div className="td-meta-item">
                  <span className="td-meta-label">Created by</span>
                  <span className="td-meta-value">{task.creator_name}</span>
                </div>
                <div className="td-meta-item">
                  <span className="td-meta-label">Created</span>
                  <span className="td-meta-value">
                    {new Date(task.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>

              <div className="td-actions">
                <button className="td-action-btn primary" onClick={startEditing}>
                  Edit
                </button>
                <button className="td-action-btn" onClick={handleToggleComplete}>
                  {task.is_completed ? 'Mark Incomplete' : 'Mark Complete'}
                </button>
                <button className="td-action-btn danger" onClick={handleDelete}>
                  Delete
                </button>
              </div>
            </>
          )}
        </div>

        {/* Linked Resources */}
        <div className="td-section">
          <div className="td-section-header">
            <h3>Linked Resources</h3>
            <div className="td-link-buttons">
              {!task.course_id && (
                <button className="td-link-icon-btn" title="Link Class" onClick={() => openLinkModal('course')}>
                  &#127891;
                </button>
              )}
              {!task.course_content_id && (
                <button className="td-link-icon-btn" title="Link Class Material" onClick={() => openLinkModal('course_content')}>
                  &#128196;
                </button>
              )}
              {!task.study_guide_id && (
                <button className="td-link-icon-btn" title="Link Study Guide" onClick={() => openLinkModal('study_guide')}>
                  &#128214;
                </button>
              )}
            </div>
          </div>

          {hasLinkedResources ? (
            <div className="td-resources">
              {task.study_guide_id && studyGuideRoute && (
                <div className="td-resource-row">
                  <Link to={studyGuideRoute} className="td-resource-card">
                    <span className="td-resource-icon" aria-hidden="true">{guideTypeIcon(task.study_guide_type)}</span>
                    <div className="td-resource-info">
                      <span className="td-resource-type">
                        {task.study_guide_type === 'quiz' ? 'Quiz' : task.study_guide_type === 'flashcards' ? 'Flashcards' : 'Study Guide'}
                      </span>
                      <span className="td-resource-title">{task.study_guide_title}</span>
                    </div>
                    <span className="td-resource-arrow">&rarr;</span>
                  </Link>
                  <button className="td-unlink-btn" title="Unlink study guide" onClick={() => handleUnlink('study_guide')}>
                    &#10005;
                  </button>
                </div>
              )}
              {task.course_content_id && (
                <div className="td-resource-row">
                  <Link to={`/course-materials/${task.course_content_id}`} className="td-resource-card">
                    <span className="td-resource-icon" aria-hidden="true">{'\uD83D\uDCC4'}</span>
                    <div className="td-resource-info">
                      <span className="td-resource-type">Class Material</span>
                      <span className="td-resource-title">{task.course_content_title || 'View Material'}</span>
                    </div>
                    <span className="td-resource-arrow">&rarr;</span>
                  </Link>
                  <button className="td-unlink-btn" title="Unlink class material" onClick={() => handleUnlink('course_content')}>
                    &#10005;
                  </button>
                </div>
              )}
              {task.note_id && task.course_content_id && (
                <div className="td-resource-row">
                  <Link to={`/course-materials/${task.course_content_id}?notes=open`} className="td-resource-card">
                    <span className="td-resource-icon" aria-hidden="true">{'\uD83D\uDDD2'}</span>
                    <div className="td-resource-info">
                      <span className="td-resource-type">Note</span>
                      <span className="td-resource-title">View Note</span>
                    </div>
                    <span className="td-resource-arrow">&rarr;</span>
                  </Link>
                </div>
              )}
              {task.course_id && (
                <div className="td-resource-row">
                  <Link to={`/courses/${task.course_id}`} className="td-resource-card">
                    <span className="td-resource-icon" aria-hidden="true">{'\uD83D\uDCDA'}</span>
                    <div className="td-resource-info">
                      <span className="td-resource-type">Class</span>
                      <span className="td-resource-title">{task.course_name || 'View Class'}</span>
                    </div>
                    <span className="td-resource-arrow">&rarr;</span>
                  </Link>
                  <button className="td-unlink-btn" title="Unlink class" onClick={() => handleUnlink('course')}>
                    &#10005;
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="td-empty-resources">
              <p>No class materials linked to this task.</p>
              <div className="td-empty-link-actions">
                <button className="td-empty-link-btn" onClick={() => openLinkModal('course')} title="Link Class">
                  &#127891; Class
                </button>
                <button className="td-empty-link-btn" onClick={() => openLinkModal('course_content')} title="Link Class Material">
                  &#128196; Material
                </button>
                <button className="td-empty-link-btn" onClick={() => openLinkModal('study_guide')} title="Link Study Guide">
                  &#128214; Study Guide
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Link Resource Modal */}
      {linkModalOpen && (
        <div className="modal-overlay" onClick={() => setLinkModalOpen(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label={`Link ${linkTypeLabel[linkType]}`} ref={linkModalRef} onClick={(e) => e.stopPropagation()}>
            <h3>Link {linkTypeLabel[linkType]}</h3>

            {/* Tab buttons for switching type */}
            <div className="td-link-tabs">
              {(['course', 'course_content', 'study_guide'] as LinkType[]).map(t => (
                <button
                  key={t}
                  className={`td-link-tab${linkType === t ? ' active' : ''}`}
                  onClick={() => { setLinkType(t); setLinkSearch(''); openLinkModal(t); }}
                >
                  {t === 'course' ? '\u{1F393}' : t === 'course_content' ? '\u{1F4C4}' : '\u{1F4D6}'} {linkTypeLabel[t]}
                </button>
              ))}
            </div>

            <label htmlFor="td-link-search" className="sr-only">Search resources</label>
            <input
              id="td-link-search"
              type="text"
              className="td-link-search"
              placeholder={`Search ${linkType === 'course' ? 'classes' : linkTypeLabel[linkType].toLowerCase() + 's'}...`}
              value={linkSearch}
              onChange={(e) => setLinkSearch(e.target.value)}
              autoFocus
            />

            <div className="td-link-list">
              {linkLoading ? (
                <ListSkeleton rows={2} />
              ) : linkType === 'course' ? (
                filteredCourses.length > 0 ? filteredCourses.map(c => (
                  <button key={c.id} className="td-link-item" onClick={() => handleLink(c.id)}>
                    <span className="td-link-item-icon" aria-hidden="true">&#127891;</span>
                    <span className="td-link-item-title">{c.name}</span>
                  </button>
                )) : <div className="td-link-empty">No classes found</div>
              ) : linkType === 'course_content' ? (
                filteredContents.length > 0 ? filteredContents.map(c => (
                  <button key={c.id} className="td-link-item" onClick={() => handleLink(c.id)}>
                    <span className="td-link-item-icon" aria-hidden="true">&#128196;</span>
                    <div className="td-link-item-text">
                      <span className="td-link-item-title">{c.title}</span>
                      <span className="td-link-item-sub">{c.content_type}</span>
                    </div>
                  </button>
                )) : <div className="td-link-empty">No class materials found</div>
              ) : (
                filteredGuides.length > 0 ? filteredGuides.map(g => (
                  <button key={g.id} className="td-link-item" onClick={() => handleLink(g.id)}>
                    <span className="td-link-item-icon" aria-hidden="true">{guideTypeIcon(g.guide_type)}</span>
                    <div className="td-link-item-text">
                      <span className="td-link-item-title">{g.title}</span>
                      <span className="td-link-item-sub">{guideTypeLabel(g.guide_type)}</span>
                    </div>
                  </button>
                )) : <div className="td-link-empty">No study guides found</div>
              )}
            </div>

            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setLinkModalOpen(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {confirmModal}
    </DashboardLayout>
  );
}
