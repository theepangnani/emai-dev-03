import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { parentApi, courseContentsApi, tasksApi } from '../api/client';
import type { ChildSummary, ChildOverview, CourseContentItem, TaskItem } from '../api/client';
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
  const [loading, setLoading] = useState(true);
  const [sectionLoading, setSectionLoading] = useState(false);

  // Collapsible sections
  const [showCourses, setShowCourses] = useState(true);
  const [showMaterials, setShowMaterials] = useState(true);
  const [showTasks, setShowTasks] = useState(true);

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
      return;
    }
    const child = children.find(c => c.student_id === selectedChild);
    if (!child) return;

    setSectionLoading(true);
    Promise.all([
      parentApi.getChildOverview(selectedChild),
      courseContentsApi.listAll({ student_user_id: child.user_id }),
      tasksApi.list({ assigned_to_user_id: child.user_id }),
    ]).then(([ov, mats, tks]) => {
      setOverview(ov);
      setMaterials(mats.filter(m => !m.archived_at));
      setTasks(tks.filter(t => !t.archived_at));
    }).catch(() => {
      setOverview(null);
      setMaterials([]);
      setTasks([]);
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
        </div>
      )}
    </DashboardLayout>
  );
}
