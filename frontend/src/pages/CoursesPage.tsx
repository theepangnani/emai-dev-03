import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { parentApi, coursesApi, googleApi } from '../api/client';
import type { ChildSummary, ChildOverview } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { useConfirm } from '../components/ConfirmModal';
import { getCourseColor } from '../components/calendar/types';
import { PageSkeleton, CardSkeleton } from '../components/Skeleton';
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

// Helper for keyboard accessibility
const handleKeyDown = (e: React.KeyboardEvent, callback: () => void) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    callback();
  }
};

export function CoursesPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const { confirm, confirmModal } = useConfirm();
  const isParent = user?.role === 'parent';
  const isStudent = user?.role === 'student';
  const urlStudentId = searchParams.get('student_id');

  // Student self-enrollment state
  const [enrolledCourses, setEnrolledCourses] = useState<CourseItem[]>([]);
  const [availableCourses, setAvailableCourses] = useState<CourseItem[]>([]);
  const [studentTab, setStudentTab] = useState<'enrolled' | 'browse'>('enrolled');
  const [enrollingId, setEnrollingId] = useState<number | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

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
  const [actionError, setActionError] = useState('');

  // Create course modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [courseName, setCourseName] = useState('');
  const [courseSubject, setCourseSubject] = useState('');
  const [courseDescription, setCourseDescription] = useState('');
  const [courseTeacherEmail, setCourseTeacherEmail] = useState('');
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
          const urlSid = urlStudentId ? Number(urlStudentId) : null;
          const match = urlSid ? childrenData.find(c => c.student_id === urlSid) : null;
          setSelectedChild(match ? match.student_id : childrenData[0].student_id);
        }
        try {
          const status = await googleApi.getStatus();
          setGoogleConnected(status.connected);
        } catch { /* ignore */ }
      } else if (isStudent) {
        // Student: load enrolled courses and all visible courses for browsing
        const [enrolled, allVisible] = await Promise.all([
          coursesApi.enrolledByMe(),
          coursesApi.list(),
        ]);
        setEnrolledCourses(enrolled);
        const enrolledIds = new Set(enrolled.map((c: CourseItem) => c.id));
        setAvailableCourses(allVisible.filter((c: CourseItem) => !enrolledIds.has(c.id) && !c.is_private));
      } else {
        // Teacher/Admin: show all visible courses
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
        teacher_email: courseTeacherEmail.trim() || undefined,
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
    setCourseTeacherEmail('');
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
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to assign courses');
    } finally {
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
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to unassign course');
    }
  };

  const handleQuickAssign = async (courseId: number) => {
    if (!selectedChild) return;
    try {
      await parentApi.assignCoursesToChild(selectedChild, [courseId]);
      loadChildOverview(selectedChild);
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to assign course');
    }
  };

  const handleEnroll = async (courseId: number) => {
    setEnrollingId(courseId);
    try {
      await coursesApi.enroll(courseId);
      // Move course from available to enrolled
      const course = availableCourses.find(c => c.id === courseId);
      if (course) {
        setEnrolledCourses(prev => [...prev, course]);
        setAvailableCourses(prev => prev.filter(c => c.id !== courseId));
      }
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to enroll');
    } finally {
      setEnrollingId(null);
    }
  };

  const handleUnenroll = async (courseId: number, courseName: string) => {
    const ok = await confirm({
      title: 'Unenroll from Course',
      message: `Are you sure you want to unenroll from "${courseName}"?`,
      confirmLabel: 'Unenroll',
    });
    if (!ok) return;
    setEnrollingId(courseId);
    try {
      await coursesApi.unenroll(courseId);
      // Move course from enrolled to available
      const course = enrolledCourses.find(c => c.id === courseId);
      if (course) {
        setAvailableCourses(prev => [...prev, course]);
        setEnrolledCourses(prev => prev.filter(c => c.id !== courseId));
      }
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to unenroll');
    } finally {
      setEnrollingId(null);
    }
  };

  const filteredAvailable = availableCourses.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (c.subject && c.subject.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (c.teacher_name && c.teacher_name.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const childName = childOverview?.full_name || children.find(c => c.student_id === selectedChild)?.full_name || '';
  const courseIds = (childOverview?.courses || []).map(c => c.id);

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Manage courses">
        <PageSkeleton />
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
        {actionError && (
          <div className="error-banner" style={{ background: '#fef2f2', color: '#991b1b', padding: '8px 16px', borderRadius: '8px', marginBottom: 12 }}>
            {actionError}
            <button onClick={() => setActionError('')} style={{ marginLeft: 8, background: 'none', border: 'none', cursor: 'pointer', color: '#991b1b' }}>&times;</button>
          </div>
        )}
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
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                <CardSkeleton />
                <CardSkeleton />
                <CardSkeleton />
              </div>
            ) : childOverview && childOverview.courses.length > 0 ? (
              <div className="courses-grid">
                {childOverview.courses.map((course) => (
                  <div key={course.id} className="course-card-wrapper">
                    <div
                      className="course-card"
                      onClick={() => navigate(`/courses/${course.id}`)}
                      onKeyDown={(e) => handleKeyDown(e, () => navigate(`/courses/${course.id}`))}
                      role="button"
                      tabIndex={0}
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

        {/* Student: Enrollment tabs */}
        {isStudent && (
          <>
            <div className="courses-tabs">
              <button
                className={`courses-tab ${studentTab === 'enrolled' ? 'active' : ''}`}
                onClick={() => setStudentTab('enrolled')}
              >
                My Courses ({enrolledCourses.length})
              </button>
              <button
                className={`courses-tab ${studentTab === 'browse' ? 'active' : ''}`}
                onClick={() => setStudentTab('browse')}
              >
                Browse Courses ({availableCourses.length})
              </button>
            </div>

            {studentTab === 'enrolled' && (
              <div className="courses-section">
                {enrolledCourses.length > 0 ? (
                  <div className="courses-grid">
                    {enrolledCourses.map((course) => (
                      <div key={course.id} className="course-card-wrapper">
                        <div
                          className="course-card"
                          onClick={() => navigate(`/courses/${course.id}`)}
                          onKeyDown={(e) => handleKeyDown(e, () => navigate(`/courses/${course.id}`))}
                          role="button"
                          tabIndex={0}
                          style={{ cursor: 'pointer' }}
                        >
                          <div className="course-card-color" style={{ background: getCourseColor(course.id, enrolledCourses.map(c => c.id)) }} />
                          <div className="course-card-body">
                            <h4>{course.name}</h4>
                            {course.subject && <span className="course-card-subject">{course.subject}</span>}
                            {course.teacher_name && <span className="course-card-teacher">{course.teacher_name}</span>}
                          </div>
                          <div className="course-card-actions">
                            <button
                              className="course-card-action-btn unassign"
                              title="Unenroll"
                              onClick={(e) => { e.stopPropagation(); handleUnenroll(course.id, course.name); }}
                              disabled={enrollingId === course.id}
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
                    <p>Not enrolled in any courses yet.</p>
                    <button className="courses-btn primary" style={{ marginTop: 12 }} onClick={() => setStudentTab('browse')}>
                      Browse Courses
                    </button>
                  </div>
                )}
              </div>
            )}

            {studentTab === 'browse' && (
              <div className="courses-section">
                <div className="courses-search">
                  <input
                    type="text"
                    placeholder="Search courses by name, subject, or teacher..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="courses-search-input"
                  />
                </div>
                {filteredAvailable.length > 0 ? (
                  <div className="courses-grid">
                    {filteredAvailable.map((course) => (
                      <div key={course.id} className="course-card-wrapper">
                        <div className="course-card">
                          <div className="course-card-color" style={{ background: 'var(--color-accent)' }} />
                          <div className="course-card-body">
                            <h4>{course.name}</h4>
                            {course.subject && <span className="course-card-subject">{course.subject}</span>}
                            {course.teacher_name && <span className="course-card-teacher">{course.teacher_name}</span>}
                            {course.description && <p className="course-card-desc">{course.description}</p>}
                          </div>
                          <div style={{ padding: '12px', display: 'flex', alignItems: 'center' }}>
                            <button
                              className="courses-btn primary"
                              onClick={() => handleEnroll(course.id)}
                              disabled={enrollingId === course.id}
                            >
                              {enrollingId === course.id ? 'Enrolling...' : 'Enroll'}
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="courses-empty">
                    <p>{searchTerm ? 'No courses match your search.' : 'No available courses to browse.'}</p>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* Parent: Created courses / Non-parent (non-student): All courses */}
        {!isStudent && (
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
                    onKeyDown={(e) => handleKeyDown(e, () => navigate(`/courses/${course.id}`))}
                    role="button"
                    tabIndex={0}
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
        )}
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
              {user?.role !== 'teacher' && (
                <label>
                  Teacher Email (optional)
                  <input type="email" value={courseTeacherEmail} onChange={(e) => setCourseTeacherEmail(e.target.value)} placeholder="teacher@example.com" disabled={createLoading} />
                </label>
              )}
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
