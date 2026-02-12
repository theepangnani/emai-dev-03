import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { parentApi, coursesApi, googleApi } from '../api/client';
import type { ChildSummary, ChildOverview } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { useConfirm } from '../components/ConfirmModal';
import { getCourseColor } from '../components/calendar/types';
import './CoursesPage.css';

interface CourseItem {
  id: number;
  name: string;
  description: string | null;
  subject: string | null;
  created_at: string;
  google_classroom_id?: string | null;
  teacher_name?: string | null;
  teacher_id?: number | null;
  is_private?: boolean;
}

type SyncState = 'idle' | 'syncing' | 'done' | 'error';

export function CoursesPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { confirm, confirmModal } = useConfirm();
  const isParent = user?.role === 'parent';

  // Parent-specific state
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChild, setSelectedChild] = useState<number | null>(null);
  const [childOverview, setChildOverview] = useState<ChildOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [syncState, setSyncState] = useState<SyncState>('idle');
  const [syncMessage, setSyncMessage] = useState('');

  // Shared state
  const [myCourses, setMyCourses] = useState<CourseItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Create course modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [courseName, setCourseName] = useState('');
  const [courseSubject, setCourseSubject] = useState('');
  const [courseDescription, setCourseDescription] = useState('');
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState('');

  // Assign course modal (parent only)
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [selectedCoursesForAssign, setSelectedCoursesForAssign] = useState<Set<number>>(new Set());
  const [assignLoading, setAssignLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (selectedChild) loadChildOverview(selectedChild);
  }, [selectedChild]);

  const loadData = async () => {
    try {
      if (isParent) {
        const [childrenData, courses] = await Promise.all([
          parentApi.getChildren(),
          coursesApi.createdByMe(),
        ]);
        setChildren(childrenData);
        setMyCourses(courses);
        if (childrenData.length > 0) {
          setSelectedChild(childrenData[0].student_id);
        }
        try {
          const status = await googleApi.getStatus();
          setGoogleConnected(status.connected);
        } catch { /* ignore */ }
      } else {
        // Non-parent: show all visible courses
        const courses = await coursesApi.list();
        setMyCourses(courses);
      }
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  };

  const loadChildOverview = async (studentId: number) => {
    setOverviewLoading(true);
    try {
      const data = await parentApi.getChildOverview(studentId);
      setChildOverview(data);
    } catch {
      setChildOverview(null);
    } finally {
      setOverviewLoading(false);
    }
  };

  const handleCreateCourse = async () => {
    if (!courseName.trim()) return;
    setCreateError('');
    setCreateLoading(true);
    try {
      const newCourse = await coursesApi.create({
        name: courseName.trim(),
        subject: courseSubject.trim() || undefined,
        description: courseDescription.trim() || undefined,
      });
      closeCreateModal();
      if (isParent) {
        const courses = await coursesApi.createdByMe();
        setMyCourses(courses);
        if (selectedChild) loadChildOverview(selectedChild);
      } else {
        const courses = await coursesApi.list();
        setMyCourses(courses);
      }
      // Navigate to the new course detail page
      navigate(`/courses/${newCourse.id}`);
    } catch (err: any) {
      setCreateError(err.response?.data?.detail || 'Failed to create course');
    } finally {
      setCreateLoading(false);
    }
  };

  const closeCreateModal = () => {
    setShowCreateModal(false);
    setCourseName('');
    setCourseSubject('');
    setCourseDescription('');
    setCreateError('');
  };

  const handleAssignCourses = async () => {
    if (!selectedChild || selectedCoursesForAssign.size === 0) return;
    setAssignLoading(true);
    try {
      await parentApi.assignCoursesToChild(selectedChild, Array.from(selectedCoursesForAssign));
      setShowAssignModal(false);
      setSelectedCoursesForAssign(new Set());
      loadChildOverview(selectedChild);
    } catch { /* ignore */ } finally {
      setAssignLoading(false);
    }
  };

  const handleSyncCourses = async () => {
    if (!selectedChild) return;
    setSyncState('syncing');
    setSyncMessage('');
    try {
      const result = await parentApi.syncChildCourses(selectedChild);
      setSyncMessage(result.message);
      setSyncState('done');
      loadChildOverview(selectedChild);
      setTimeout(() => { setSyncState('idle'); setSyncMessage(''); }, 4000);
    } catch (err: any) {
      setSyncMessage(err.response?.data?.detail || 'Failed to sync courses');
      setSyncState('error');
      setTimeout(() => { setSyncState('idle'); setSyncMessage(''); }, 4000);
    }
  };

  const handleUnassignCourse = async (courseId: number, courseName: string) => {
    if (!selectedChild) return;
    const ok = await confirm({
      title: 'Unassign Course',
      message: `Remove "${courseName}" from ${childName}?`,
      confirmLabel: 'Unassign',
    });
    if (!ok) return;
    try {
      await parentApi.unassignCourseFromChild(selectedChild, courseId);
      loadChildOverview(selectedChild);
    } catch { /* ignore */ }
  };

  const handleQuickAssign = async (courseId: number) => {
    if (!selectedChild) return;
    try {
      await parentApi.assignCoursesToChild(selectedChild, [courseId]);
      loadChildOverview(selectedChild);
    } catch { /* ignore */ }
  };

  const childName = childOverview?.full_name || children.find(c => c.student_id === selectedChild)?.full_name || '';
  const courseIds = (childOverview?.courses || []).map(c => c.id);

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Manage courses">
        <div className="loading-state">Loading...</div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      welcomeSubtitle="Manage courses"
      sidebarActions={[
        { label: '+ Add Course', onClick: () => setShowCreateModal(true) },
      ]}
    >
      <div className="courses-page">
        {/* Parent: Child selector */}
        {isParent && children.length > 1 && (
          <div className="child-selector" style={{ marginBottom: 20 }}>
            {children.map((child) => (
              <button
                key={child.student_id}
                className={`child-tab ${selectedChild === child.student_id ? 'active' : ''}`}
                onClick={() => setSelectedChild(child.student_id)}
              >
                {child.full_name}
              </button>
            ))}
          </div>
        )}

        {/* Parent: Child's courses */}
        {isParent && (
          <div className="courses-section">
            <div className="courses-section-header">
              <h3>{childName ? `${childName}'s Courses` : 'Courses'}</h3>
              <div className="courses-header-actions">
                <button className="generate-btn" onClick={() => setShowCreateModal(true)}>
                  + Create Course
                </button>
                {myCourses.length > 0 && selectedChild && (
                  <button className="courses-btn secondary" onClick={() => { setSelectedCoursesForAssign(new Set()); setShowAssignModal(true); }}>
                    Assign Course
                  </button>
                )}
                {googleConnected && childOverview?.google_connected && (
                  <button className="courses-btn secondary" onClick={handleSyncCourses} disabled={syncState === 'syncing'}>
                    {syncState === 'syncing' ? 'Syncing...' : 'Sync Google'}
                  </button>
                )}
              </div>
            </div>
            {syncMessage && (
              <div className={`courses-sync-msg ${syncState === 'error' ? 'error' : ''}`}>{syncMessage}</div>
            )}
            {overviewLoading ? (
              <div className="loading-state">Loading courses...</div>
            ) : childOverview && childOverview.courses.length > 0 ? (
              <div className="courses-grid">
                {childOverview.courses.map((course) => (
                  <div key={course.id} className="course-card-wrapper">
                    <div
                      className="course-card"
                      onClick={() => navigate(`/courses/${course.id}`)}
                      style={{ cursor: 'pointer' }}
                    >
                      <div className="course-card-color" style={{ background: getCourseColor(course.id, courseIds) }} />
                      <div className="course-card-body">
                        <h4>{course.name}</h4>
                        {course.subject && <span className="course-card-subject">{course.subject}</span>}
                        {course.teacher_name && <span className="course-card-teacher">{course.teacher_name}</span>}
                        {course.google_classroom_id && <span className="course-card-badge google">Google</span>}
                      </div>
                      <div className="course-card-actions">
                        <button
                          className="course-card-action-btn unassign"
                          title={`Unassign from ${childName}`}
                          onClick={(e) => { e.stopPropagation(); handleUnassignCourse(course.id, course.name); }}
                        >
                          &#10005;
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="courses-empty">
                <p>No courses yet. Create a course or sync from Google Classroom.</p>
              </div>
            )}
          </div>
        )}

        {/* Parent: Created courses / Non-parent: All courses */}
        <div className="courses-section">
          <div className="courses-section-header">
            <h3>{isParent ? 'My Created Courses' : 'Courses'}</h3>
            {!isParent && (
              <button className="generate-btn" onClick={() => setShowCreateModal(true)}>
                + Create Course
              </button>
            )}
          </div>
          {myCourses.length > 0 ? (
            <div className="courses-grid">
              {myCourses.map((course) => (
                <div key={course.id} className="course-card-wrapper">
                  <div
                    className="course-card"
                    onClick={() => navigate(`/courses/${course.id}`)}
                    style={{ cursor: 'pointer' }}
                  >
                    <div className="course-card-color" style={{ background: 'var(--color-accent)' }} />
                    <div className="course-card-body">
                      <h4>{course.name}</h4>
                      {course.subject && <span className="course-card-subject">{course.subject}</span>}
                      {course.description && <p className="course-card-desc">{course.description}</p>}
                    </div>
                    <div className="course-card-actions">
                      {isParent && selectedChild && (() => {
                        const alreadyAssigned = childOverview?.courses.some(c => c.id === course.id) ?? false;
                        return !alreadyAssigned ? (
                          <button
                            className="course-card-action-btn assign"
                            title={`Assign to ${childName}`}
                            onClick={(e) => { e.stopPropagation(); handleQuickAssign(course.id); }}
                          >
                            &#10003;
                          </button>
                        ) : (
                          <span className="course-card-assigned-badge" title={`Assigned to ${childName}`}>&#10003;</span>
                        );
                      })()}
                      <button
                        className="course-card-action-btn edit"
                        title="Edit course"
                        onClick={(e) => { e.stopPropagation(); navigate(`/courses/${course.id}`); }}
                      >
                        &#9998;
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="courses-empty">
              <p>{isParent ? 'No courses created yet.' : 'No courses available. Create one to get started.'}</p>
            </div>
          )}
        </div>
      </div>

      {/* Create Course Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={closeCreateModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Create Course</h2>
            <p className="modal-desc">Create a new course.</p>
            <div className="modal-form">
              <label>
                Course Name *
                <input type="text" value={courseName} onChange={(e) => setCourseName(e.target.value)} placeholder="e.g. Math Grade 5" disabled={createLoading} onKeyDown={(e) => e.key === 'Enter' && handleCreateCourse()} />
              </label>
              <label>
                Subject (optional)
                <input type="text" value={courseSubject} onChange={(e) => setCourseSubject(e.target.value)} placeholder="e.g. Mathematics" disabled={createLoading} />
              </label>
              <label>
                Description (optional)
                <textarea value={courseDescription} onChange={(e) => setCourseDescription(e.target.value)} placeholder="Course details..." rows={3} disabled={createLoading} />
              </label>
              {createError && <p className="link-error">{createError}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={closeCreateModal} disabled={createLoading}>Cancel</button>
              <button className="generate-btn" onClick={handleCreateCourse} disabled={createLoading || !courseName.trim()}>
                {createLoading ? 'Creating...' : 'Create Course'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Assign Course to Child Modal (parent only) */}
      {showAssignModal && selectedChild && (
        <div className="modal-overlay" onClick={() => setShowAssignModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Assign Course to {childName}</h2>
            <p className="modal-desc">Select courses to assign to your child.</p>
            <div className="modal-form">
              {myCourses.length === 0 ? (
                <div className="empty-state">
                  <p>No courses created yet</p>
                  <button className="link-child-btn-small" onClick={() => { setShowAssignModal(false); setShowCreateModal(true); }}>+ Create Course</button>
                </div>
              ) : (
                <div className="discovered-list">
                  {myCourses.map((course) => {
                    const alreadyAssigned = childOverview?.courses.some(c => c.id === course.id) ?? false;
                    return (
                      <label key={course.id} className={`discovered-item ${alreadyAssigned ? 'disabled' : ''}`}>
                        <input type="checkbox" checked={selectedCoursesForAssign.has(course.id)} onChange={() => { setSelectedCoursesForAssign(prev => { const next = new Set(prev); if (next.has(course.id)) next.delete(course.id); else next.add(course.id); return next; }); }} disabled={alreadyAssigned} />
                        <div className="discovered-info">
                          <span className="discovered-name">{course.name}</span>
                          {course.subject && <span className="discovered-email">{course.subject}</span>}
                          {alreadyAssigned && <span className="discovered-linked-badge">Already assigned</span>}
                        </div>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowAssignModal(false)} disabled={assignLoading}>Cancel</button>
              <button className="generate-btn" onClick={handleAssignCourses} disabled={assignLoading || selectedCoursesForAssign.size === 0}>
                {assignLoading ? 'Assigning...' : `Assign ${selectedCoursesForAssign.size} Course${selectedCoursesForAssign.size !== 1 ? 's' : ''}`}
              </button>
            </div>
          </div>
        </div>
      )}
      {confirmModal}
    </DashboardLayout>
  );
}
