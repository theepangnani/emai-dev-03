import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { parentApi, courseContentsApi, tasksApi } from '../api/client';
import type { ChildSummary, ChildOverview, CourseContentItem, TaskItem, LinkedTeacher } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageSkeleton } from '../components/Skeleton';
import './MyKidsPage.css';

export function MyKidsPage() {
  const navigate = useNavigate();
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChild, setSelectedChild] = useState<number | null>(null);
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
        if (kids.length === 1) {
          setSelectedChild(kids[0].student_id);
        }
      } catch { /* */ }
      finally { setLoading(false); }
    })();
  }, []);

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
    ]).then(([ov, mats, tks, teachers]) => {
      setOverview(ov);
      setMaterials(mats.filter(m => !m.archived_at));
      setTasks(tks.filter(t => !t.archived_at));
      setLinkedTeachers(teachers);
    }).catch(() => {
      setOverview(null);
      setMaterials([]);
      setTasks([]);
      setLinkedTeachers([]);
    }).finally(() => setSectionLoading(false));
  }, [selectedChild, children]);

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Your children's progress">
        <PageSkeleton />
      </DashboardLayout>
    );
  }

  if (children.length === 0) {
    return (
      <DashboardLayout welcomeSubtitle="Your children's progress">
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

  const activeTasks = tasks.filter(t => !t.is_completed);
  const completedTasks = tasks.filter(t => t.is_completed);

  return (
    <DashboardLayout welcomeSubtitle="Your children's progress">
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
        {children.map(child => (
          <button
            key={child.student_id}
            className={`child-tab ${selectedChild === child.student_id ? 'active' : ''}`}
            onClick={() => setSelectedChild(child.student_id)}
          >
            {child.full_name}
            {child.grade_level != null && <span className="grade-badge">Grade {child.grade_level}</span>}
          </button>
        ))}
      </div>

      {!selectedChild ? (
        /* All-children overview */
        <div className="mykids-overview-grid">
          {children.map(child => (
            <div
              key={child.student_id}
              className="mykids-child-card"
              onClick={() => setSelectedChild(child.student_id)}
            >
              <div className="mykids-child-card-name">
                {child.full_name}
                {child.grade_level != null && <span className="grade-badge">Grade {child.grade_level}</span>}
              </div>
              {child.school_name && <div className="mykids-child-card-school">{child.school_name}</div>}
              <div className="mykids-child-card-action">View details &rarr;</div>
            </div>
          ))}
        </div>
      ) : sectionLoading ? (
        <PageSkeleton />
      ) : (
        <div className="mykids-sections">
          {/* ── Courses ───────────────────────────── */}
          <div className="mykids-section">
            <button className="mykids-section-header" onClick={() => setShowCourses(p => !p)}>
              <span className={`section-chevron${showCourses ? ' expanded' : ''}`}>&#9654;</span>
              Courses ({overview?.courses.length ?? 0})
            </button>
            {showCourses && overview && (
              <div className="mykids-card-grid">
                {overview.courses.length === 0 ? (
                  <p className="mykids-empty-hint">No courses enrolled.</p>
                ) : overview.courses.map(c => (
                  <div key={c.id} className="mykids-item-card" onClick={() => navigate(`/courses/${c.id}`)}>
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
              Course Materials ({materials.length})
            </button>
            {showMaterials && (
              <div className="mykids-card-grid">
                {materials.length === 0 ? (
                  <p className="mykids-empty-hint">No course materials yet.</p>
                ) : materials.map(m => (
                  <div key={m.id} className="mykids-item-card" onClick={() => navigate(`/course-materials/${m.id}`)}>
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
              Tasks ({activeTasks.length} active{completedTasks.length > 0 ? `, ${completedTasks.length} done` : ''})
            </button>
            {showTasks && (
              <div className="mykids-task-list">
                {activeTasks.length === 0 && completedTasks.length === 0 ? (
                  <p className="mykids-empty-hint">No tasks assigned.</p>
                ) : (
                  <>
                    {activeTasks.map(t => (
                      <div key={t.id} className="mykids-task-row" onClick={() => navigate(`/tasks/${t.id}`)}>
                        <span className={`mykids-task-priority ${t.priority || 'medium'}`} />
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
                Teachers ({(overview?.courses.filter(c => c.teacher_name).length ?? 0) + linkedTeachers.length})
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
                  </div>
                ))}
                {/* Directly linked teachers */}
                {linkedTeachers.map(t => (
                  <div key={`link-${t.id}`} className="mykids-teacher-row">
                    <div className="mykids-teacher-info">
                      <span className="mykids-teacher-name">{t.teacher_name || 'Unknown'}</span>
                      <span className="mykids-teacher-email">{t.teacher_email}</span>
                    </div>
                    <button
                      className="mykids-remove-btn"
                      onClick={async () => {
                        if (!selectedChild) return;
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
                className="mykids-modal-submit"
                disabled={addTeacherLoading || !teacherEmail.trim()}
                onClick={async () => {
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
    </DashboardLayout>
  );
}
