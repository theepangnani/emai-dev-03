import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { parentApi, courseContentsApi, coursesApi, tasksApi } from '../api/client';
import type { ChildSummary, ChildOverview, CourseContentItem, TaskItem, LinkedTeacher } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { useConfirm } from '../components/ConfirmModal';
import { PageSkeleton } from '../components/Skeleton';
import { isValidEmail } from '../utils/validation';
import './MyKidsPage.css';

const CHILD_COLORS = [
  '#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b',
  '#3b82f6', '#ef4444', '#10b981', '#6366f1',
];

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return (parts[0]?.[0] || '?').toUpperCase();
}

// Helper for keyboard accessibility
const handleKeyDown = (e: React.KeyboardEvent, callback: () => void) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    callback();
  }
};

export function MyKidsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { confirm, confirmModal } = useConfirm();
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChild, setSelectedChild] = useState<number | null>(null);
  const urlStudentId = searchParams.get('student_id');
  const [overview, setOverview] = useState<ChildOverview | null>(null);
  const [materials, setMaterials] = useState<CourseContentItem[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [linkedTeachers, setLinkedTeachers] = useState<LinkedTeacher[]>([]);
  const [loading, setLoading] = useState(true);
  const [sectionLoading, setSectionLoading] = useState(false);

  // Collapsible sections
  const [showCourses, setShowCourses] = useState(true);
  const [showMaterials, setShowMaterials] = useState(true);
  const [showTasks, setShowTasks] = useState(true);
  const [showTeachers, setShowTeachers] = useState(true);

  // Reassign course material to course
  const [reassignContent, setReassignContent] = useState<CourseContentItem | null>(null);
  const [courses, setCourses] = useState<{ id: number; name: string }[]>([]);
  const [categorizeCourseId, setCategorizeCourseId] = useState<number | string>('');
  const [categorizeSearch, setCategorizeSearch] = useState('');
  const [categorizeNewName, setCategorizeNewName] = useState('');
  const [categorizeCreating, setCategorizeCreating] = useState(false);

  // Add teacher modal
  const [showAddTeacher, setShowAddTeacher] = useState(false);
  const [teacherEmail, setTeacherEmail] = useState('');
  const [teacherName, setTeacherName] = useState('');
  const [addTeacherError, setAddTeacherError] = useState('');
  const [addTeacherLoading, setAddTeacherLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const kids = await parentApi.getChildren();
        setChildren(kids);
        const urlSid = urlStudentId ? Number(urlStudentId) : null;
        const match = urlSid ? kids.find(k => k.student_id === urlSid) : null;
        if (match) {
          setSelectedChild(match.student_id);
        } else if (kids.length === 1) {
          setSelectedChild(kids[0].student_id);
        }
      } catch { /* */ }
      finally { setLoading(false); }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Load child data when selection changes
  useEffect(() => {
    if (!selectedChild) {
      setOverview(null);
      setMaterials([]);
      setTasks([]);
      setLinkedTeachers([]);
      return;
    }
    const child = children.find(c => c.student_id === selectedChild);
    if (!child) return;

    setSectionLoading(true);
    Promise.all([
      parentApi.getChildOverview(selectedChild),
      courseContentsApi.listAll({ student_user_id: child.user_id }),
      tasksApi.list({ assigned_to_user_id: child.user_id }),
      parentApi.getLinkedTeachers(selectedChild),
      coursesApi.list(),
    ]).then(([ov, mats, tks, teachers, courseList]) => {
      setOverview(ov);
      setMaterials(mats.filter(m => !m.archived_at));
      setTasks(tks.filter(t => !t.archived_at));
      setLinkedTeachers(teachers);
      setCourses(courseList);
    }).catch(() => {
      setOverview(null);
      setMaterials([]);
      setTasks([]);
      setLinkedTeachers([]);
    }).finally(() => setSectionLoading(false));
  }, [selectedChild, children]);

  // Per-child task stats for the selected child (must be before early returns to follow Rules of Hooks)
  const selectedTaskStats = useMemo(() => {
    if (!selectedChild || tasks.length === 0) return null;
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const activeTasks = tasks.filter(t => !t.is_completed);
    const completedTasks = tasks.filter(t => t.is_completed);
    const totalTasks = tasks.length;
    const completed = completedTasks.length;
    const completionPct = totalTasks > 0 ? Math.round((completed / totalTasks) * 100) : 0;
    const pendingWithDue = activeTasks
      .filter(t => t.due_date)
      .sort((a, b) => new Date(a.due_date!).getTime() - new Date(b.due_date!).getTime());
    let nextDeadline: { title: string; label: string } | null = null;
    if (pendingWithDue.length > 0) {
      const next = pendingWithDue[0];
      const dueDate = new Date(next.due_date!);
      const diffDays = Math.floor((dueDate.getTime() - todayStart.getTime()) / 86400000);
      let label: string;
      if (diffDays < 0) label = `overdue by ${Math.abs(diffDays)}d`;
      else if (diffDays === 0) label = 'due today';
      else if (diffDays === 1) label = 'due tomorrow';
      else label = `due in ${diffDays} days`;
      nextDeadline = { title: next.title, label };
    }
    return { totalTasks, completed, completionPct, nextDeadline };
  }, [selectedChild, tasks]);

  const activeTasks = tasks.filter(t => !t.is_completed);
  const completedTasks = tasks.filter(t => t.is_completed);

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Detailed child profiles, courses, and teacher management" showBackButton>
        <PageSkeleton />
      </DashboardLayout>
    );
  }

  if (children.length === 0) {
    return (
      <DashboardLayout welcomeSubtitle="Detailed child profiles, courses, and teacher management" showBackButton>
        <div className="mykids-empty">
          <h3>No children linked yet</h3>
          <p>Add a child from your Dashboard to get started.</p>
          <button className="mykids-btn" onClick={() => navigate('/dashboard')}>
            Go to Dashboard
          </button>
        </div>
      </DashboardLayout>
    );
  }

  const openReassignModal = (m: CourseContentItem) => {
    setReassignContent(m);
    setCategorizeCourseId('');
    setCategorizeSearch('');
    setCategorizeNewName('');
  };

  const handleReassignContent = async (courseId?: number) => {
    if (!reassignContent) return;
    const targetCourseId = courseId ?? (categorizeCourseId ? Number(categorizeCourseId) : null);
    if (!targetCourseId) return;
    try {
      await courseContentsApi.update(reassignContent.id, { course_id: targetCourseId });
      // Update local state
      setMaterials(prev => prev.map(m =>
        m.id === reassignContent.id
          ? { ...m, course_id: targetCourseId, course_name: courses.find(c => c.id === targetCourseId)?.name ?? null }
          : m
      ));
      setReassignContent(null);
    } catch { /* ignore */ }
  };

  const handleCreateAndReassign = async () => {
    if (!reassignContent || !categorizeNewName.trim()) return;
    setCategorizeCreating(true);
    try {
      const newCourse = await coursesApi.create({ name: categorizeNewName.trim() });
      setCourses(prev => [...prev, newCourse]);
      await handleReassignContent(newCourse.id);
    } catch { /* ignore */ }
    setCategorizeCreating(false);
  };

  return (
    <DashboardLayout welcomeSubtitle="Detailed child profiles, courses, and teacher management" showBackButton>
      {/* Child Tabs */}
      <div className="child-selector">
        {children.length > 1 && (
          <button
            className={`child-tab ${selectedChild === null ? 'active' : ''}`}
            onClick={() => setSelectedChild(null)}
          >
            All Children
          </button>
        )}
        {children.map((child, index) => (
          <button
            key={child.student_id}
            className={`child-tab ${selectedChild === child.student_id ? 'active' : ''}`}
            onClick={() => setSelectedChild(child.student_id)}
          >
            <span className="child-color-dot" style={{ backgroundColor: CHILD_COLORS[index % CHILD_COLORS.length] }} />
            {child.full_name}
            {child.grade_level != null && <span className="grade-badge">Grade {child.grade_level}</span>}
          </button>
        ))}
      </div>

      {!selectedChild ? (
        /* All-children overview */
        <div className="mykids-overview-grid">
          {children.map((child, index) => (
            <div
              key={child.student_id}
              className="mykids-child-card-enhanced"
              onClick={() => setSelectedChild(child.student_id)}
              onKeyDown={(e) => handleKeyDown(e, () => setSelectedChild(child.student_id))}
              role="button"
              tabIndex={0}
            >
              <div className="mykids-child-avatar" style={{ backgroundColor: CHILD_COLORS[index % CHILD_COLORS.length] }}>
                {getInitials(child.full_name)}
              </div>
              <div className="mykids-child-card-content">
                <div className="mykids-child-card-header">
                  <span className="mykids-child-card-name">{child.full_name}</span>
                  {child.grade_level != null && <span className="grade-badge">Grade {child.grade_level}</span>}
                </div>
                {child.school_name && <div className="mykids-child-card-school">{child.school_name}</div>}
                <div className="mykids-child-card-stats">
                  <span className="mykids-child-stat">{child.course_count} {child.course_count === 1 ? 'course' : 'courses'}</span>
                  <span className="mykids-child-stat">{child.active_task_count} active {child.active_task_count === 1 ? 'task' : 'tasks'}</span>
                </div>
              </div>
              <div className="mykids-child-card-arrow">&rarr;</div>
            </div>
          ))}
        </div>
      ) : sectionLoading ? (
        <PageSkeleton />
      ) : (
        <div className="mykids-sections">
          {/* ── Progress Summary ──────────────────── */}
          {selectedTaskStats && selectedTaskStats.totalTasks > 0 && (() => {
            const childIndex = children.findIndex(c => c.student_id === selectedChild);
            const color = CHILD_COLORS[childIndex >= 0 ? childIndex % CHILD_COLORS.length : 0];
            return (
              <div className="mykids-progress-summary">
                <div className="mykids-progress-info">
                  <span className="mykids-progress-text">
                    {selectedTaskStats.completed}/{selectedTaskStats.totalTasks} tasks complete
                  </span>
                  {selectedTaskStats.nextDeadline && (
                    <span className="mykids-next-deadline">
                      Next: <strong>{selectedTaskStats.nextDeadline.title}</strong> — {selectedTaskStats.nextDeadline.label}
                    </span>
                  )}
                </div>
                <div className="mykids-progress-bar-wrap">
                  <div className="mykids-progress-bar">
                    <div className="mykids-progress-fill" style={{ width: `${selectedTaskStats.completionPct}%`, backgroundColor: color }} />
                  </div>
                  <span className="mykids-progress-pct">{selectedTaskStats.completionPct}%</span>
                </div>
              </div>
            );
          })()}

          {/* ── Courses ───────────────────────────── */}
          <div className="mykids-section">
            <button className="mykids-section-header" onClick={() => setShowCourses(p => !p)}>
              <span className={`section-chevron${showCourses ? ' expanded' : ''}`}>&#9654;</span>
              <span className="section-icon">&#128218;</span> Courses ({overview?.courses.length ?? 0})
            </button>
            {showCourses && overview && (
              <div className="mykids-card-grid">
                {overview.courses.length === 0 ? (
                  <p className="mykids-empty-hint">No courses enrolled.</p>
                ) : overview.courses.map(c => (
                  <div key={c.id} className="mykids-item-card" onClick={() => navigate(`/courses/${c.id}`)} onKeyDown={(e) => handleKeyDown(e, () => navigate(`/courses/${c.id}`))} role="button" tabIndex={0}>
                    <div className="mykids-item-title">{c.name}</div>
                    {c.teacher_name && <div className="mykids-item-sub">{c.teacher_name}</div>}
                    {c.subject && <div className="mykids-item-sub">{c.subject}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Course Materials ───────────────────── */}
          <div className="mykids-section">
            <button className="mykids-section-header" onClick={() => setShowMaterials(p => !p)}>
              <span className={`section-chevron${showMaterials ? ' expanded' : ''}`}>&#9654;</span>
              <span className="section-icon">&#128196;</span> Course Materials ({materials.length})
            </button>
            {showMaterials && (
              <div className="mykids-card-grid">
                {materials.length === 0 ? (
                  <p className="mykids-empty-hint">No course materials yet.</p>
                ) : materials.map(m => (
                  <div key={m.id} className="mykids-item-card mykids-item-card--material" onClick={() => navigate(`/course-materials/${m.id}`)} onKeyDown={(e) => handleKeyDown(e, () => navigate(`/course-materials/${m.id}`))} role="button" tabIndex={0}>
                    <div className="mykids-item-card-actions">
                      <button
                        className="mykids-item-action-btn"
                        title="Move to course"
                        onClick={(e) => { e.stopPropagation(); openReassignModal(m); }}
                      >&#128194;</button>
                    </div>
                    <div className="mykids-item-title">{m.title}</div>
                    <div className="mykids-item-sub">
                      <span className="mykids-badge">{m.content_type}</span>
                      {m.course_name && <span> &middot; {m.course_name}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Tasks ─────────────────────────────── */}
          <div className="mykids-section">
            <button className="mykids-section-header" onClick={() => setShowTasks(p => !p)}>
              <span className={`section-chevron${showTasks ? ' expanded' : ''}`}>&#9654;</span>
              <span className="section-icon">&#9989;</span> Tasks ({activeTasks.length} active{completedTasks.length > 0 ? `, ${completedTasks.length} done` : ''})
            </button>
            {showTasks && (
              <div className="mykids-task-list">
                {activeTasks.length === 0 && completedTasks.length === 0 ? (
                  <p className="mykids-empty-hint">No tasks assigned.</p>
                ) : (
                  <>
                    {activeTasks.map(t => (
                      <div key={t.id} className="mykids-task-row" onClick={() => navigate(`/tasks/${t.id}`)} onKeyDown={(e) => handleKeyDown(e, () => navigate(`/tasks/${t.id}`))} role="button" tabIndex={0}>
                        <span className={`task-priority-badge ${t.priority || 'medium'}`} aria-label={`Priority: ${t.priority || 'medium'}`}>{(t.priority || 'medium') === 'high' ? '\u25B2 ' : (t.priority || 'medium') === 'low' ? '\u25BC ' : '\u25CF '}{t.priority || 'medium'}</span>
                        <span className="mykids-task-title">{t.title}</span>
                        {t.due_date && (
                          <span className="mykids-task-due">
                            {new Date(t.due_date).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    ))}
                    {completedTasks.length > 0 && (
                      <div className="mykids-completed-count">
                        + {completedTasks.length} completed
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          {/* ── Linked Teachers ────────────────────── */}
          <div className="mykids-section">
            <div className="mykids-section-header-row">
              <button className="mykids-section-toggle" onClick={() => setShowTeachers(p => !p)}>
                <span className={`section-chevron${showTeachers ? ' expanded' : ''}`}>&#9654;</span>
                <span className="section-icon">&#128105;&#8205;&#127979;</span> Teachers ({(overview?.courses.filter(c => c.teacher_name).length ?? 0) + linkedTeachers.length})
              </button>
              <button
                className="mykids-add-teacher-btn"
                onClick={() => { setShowAddTeacher(true); setTeacherEmail(''); setTeacherName(''); setAddTeacherError(''); }}
              >
                + Add Teacher
              </button>
            </div>
            {showTeachers && (
              <div className="mykids-task-list">
                {/* Teachers from courses */}
                {overview?.courses.filter(c => c.teacher_name).map(c => (
                  <div key={`course-${c.id}`} className="mykids-teacher-row">
                    <div className="mykids-teacher-info">
                      <span className="mykids-teacher-name">{c.teacher_name}</span>
                      <span className="mykids-teacher-email">{c.teacher_email || c.name} (via course)</span>
                    </div>
                    {c.teacher_id && (
                      <button
                        className="mykids-message-btn"
                        onClick={() => navigate(`/messages?recipient_id=${c.teacher_id}`)}
                      >
                        Message
                      </button>
                    )}
                  </div>
                ))}
                {/* Directly linked teachers */}
                {linkedTeachers.map(t => (
                  <div key={`link-${t.id}`} className="mykids-teacher-row">
                    <div className="mykids-teacher-info">
                      <span className="mykids-teacher-name">{t.teacher_name || 'Unknown'}</span>
                      <span className="mykids-teacher-email">{t.teacher_email}</span>
                    </div>
                    {t.teacher_user_id && (
                      <button
                        className="mykids-message-btn"
                        onClick={() => navigate(`/messages?recipient_id=${t.teacher_user_id}`)}
                      >
                        Message
                      </button>
                    )}
                    <button
                      className="mykids-remove-btn"
                      onClick={async () => {
                        if (!selectedChild) return;
                        const ok = await confirm({ title: 'Remove Teacher', message: `Remove ${t.teacher_name || t.teacher_email} as a linked teacher?`, confirmLabel: 'Remove', variant: 'danger' });
                        if (!ok) return;
                        await parentApi.unlinkTeacher(selectedChild, t.id);
                        setLinkedTeachers(prev => prev.filter(lt => lt.id !== t.id));
                      }}
                    >
                      Remove
                    </button>
                  </div>
                ))}
                {(overview?.courses.filter(c => c.teacher_name).length ?? 0) === 0 && linkedTeachers.length === 0 && (
                  <p className="mykids-empty-hint">No teachers linked yet. Add a teacher by email to start messaging.</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
      {/* Add Teacher Modal */}
      {showAddTeacher && selectedChild && (
        <div className="mykids-modal-overlay" onClick={() => setShowAddTeacher(false)}>
          <div className="mykids-modal" onClick={e => e.stopPropagation()}>
            <h3>Add Teacher</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              Link a teacher by email so you can send them messages directly.
            </p>
            {addTeacherError && <div className="mykids-modal-error">{addTeacherError}</div>}
            <label>Teacher Email *</label>
            <input
              type="email"
              placeholder="teacher@school.edu"
              value={teacherEmail}
              onChange={e => setTeacherEmail(e.target.value)}
            />
            <label>Teacher Name (optional)</label>
            <input
              type="text"
              placeholder="Ms. Smith"
              value={teacherName}
              onChange={e => setTeacherName(e.target.value)}
            />
            <div className="mykids-modal-actions">
              <button onClick={() => setShowAddTeacher(false)}>Cancel</button>
              <button
                className="mykids-modal-submit generate-btn"
                disabled={addTeacherLoading || !teacherEmail.trim()}
                onClick={async () => {
                  if (!isValidEmail(teacherEmail.trim())) {
                    setAddTeacherError('Please enter a valid email address');
                    return;
                  }
                  setAddTeacherLoading(true);
                  setAddTeacherError('');
                  try {
                    const linked = await parentApi.linkTeacher(
                      selectedChild,
                      teacherEmail.trim(),
                      teacherName.trim() || undefined,
                    );
                    setLinkedTeachers(prev => [...prev, linked]);
                    setShowAddTeacher(false);
                  } catch (err: any) {
                    setAddTeacherError(err?.response?.data?.detail || 'Failed to link teacher');
                  } finally {
                    setAddTeacherLoading(false);
                  }
                }}
              >
                {addTeacherLoading ? 'Adding...' : 'Add Teacher'}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Reassign course material to course modal */}
      {reassignContent && (
        <div className="modal-overlay" onClick={() => setReassignContent(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Move to Course</h2>
            <p className="modal-desc">Assign &ldquo;{reassignContent.title}&rdquo; to a course.</p>
            <div className="modal-form">
              <input
                type="text"
                placeholder="Search courses or type a new name..."
                value={categorizeSearch}
                onChange={(e) => { setCategorizeSearch(e.target.value); setCategorizeCourseId(''); setCategorizeNewName(''); }}
                autoFocus
              />
              <div className="categorize-list">
                {courses
                  .filter(c => !categorizeSearch || c.name.toLowerCase().includes(categorizeSearch.toLowerCase()))
                  .map(c => (
                    <div
                      key={c.id}
                      className={`categorize-item${categorizeCourseId === c.id ? ' selected' : ''}${c.id === reassignContent.course_id ? ' current' : ''}`}
                      onClick={() => { setCategorizeCourseId(c.id); setCategorizeNewName(''); }}
                    >
                      &#127891; {c.name}{c.id === reassignContent.course_id ? ' (current)' : ''}
                    </div>
                  ))
                }
                {categorizeSearch.trim() && !courses.some(c => c.name.toLowerCase() === categorizeSearch.trim().toLowerCase()) && (
                  <div
                    className={`categorize-item create-new${categorizeNewName ? ' selected' : ''}`}
                    onClick={() => { setCategorizeNewName(categorizeSearch.trim()); setCategorizeCourseId(''); }}
                  >
                    &#10133; Create &ldquo;{categorizeSearch.trim()}&rdquo;
                  </div>
                )}
              </div>
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setReassignContent(null)}>Cancel</button>
              {categorizeNewName ? (
                <button className="generate-btn" disabled={categorizeCreating} onClick={handleCreateAndReassign}>
                  {categorizeCreating ? 'Creating...' : 'Create & Move'}
                </button>
              ) : (
                <button className="generate-btn" disabled={!categorizeCourseId || categorizeCourseId === reassignContent.course_id} onClick={() => handleReassignContent()}>Move</button>
              )}
            </div>
          </div>
        </div>
      )}
      {confirmModal}
    </DashboardLayout>
  );
}
