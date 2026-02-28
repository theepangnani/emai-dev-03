import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { parentApi, coursesApi, courseContentsApi, googleApi } from '../api/client';
import type { ChildSummary, ChildOverview, CourseContentItem } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { useConfirm } from '../components/ConfirmModal';
import { useFocusTrap } from '../hooks/useFocusTrap';
import { getCourseColor } from '../components/calendar/types';
import { PageSkeleton, CardSkeleton } from '../components/Skeleton';
import EmptyState from '../components/EmptyState';
import './CoursesPage.css';

interface CourseItem {
  id: number;
  name: string;
  description: string | null;
  subject: string | null;
  created_at: string;
  google_classroom_id?: string | null;
  classroom_type?: string | null;
  teacher_name?: string | null;
  teacher_id?: number | null;
  is_private?: boolean;
}

type SyncState = 'idle' | 'syncing' | 'done' | 'error';

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

// Helper for keyboard accessibility
const handleKeyDown = (e: React.KeyboardEvent, callback: () => void) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    callback();
  }
};

export function CoursesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const { confirm, confirmModal } = useConfirm();
  const isParent = user?.role === 'parent';
  const isStudent = user?.role === 'student';
  const urlStudentId = searchParams.get('student_id');

  // Student self-enrollment state
  const [enrolledCourses, setEnrolledCourses] = useState<CourseItem[]>([]);
  const [availableCourses, setAvailableCourses] = useState<CourseItem[]>([]);
  const [studentTab, setStudentTab] = useState<'enrolled' | 'browse'>(() => {
    const tab = searchParams.get('tab');
    return tab === 'browse' ? 'browse' : 'enrolled';
  });
  const [enrollingId, setEnrollingId] = useState<number | null>(null);
  const [searchTerm, setSearchTerm] = useState(() => searchParams.get('q') || '');

  // Parent-specific state
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChild, setSelectedChild] = useState<number | null>(null);
  const [childOverview, setChildOverview] = useState<ChildOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [syncState, setSyncState] = useState<SyncState>('idle');
  const [syncMessage, setSyncMessage] = useState('');
  const [lastSynced, setLastSynced] = useState<Date | null>(null);

  // Shared state
  const [myCourses, setMyCourses] = useState<CourseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [actionError, setActionError] = useState('');

  // Inline course content expansion
  const [expandedCourseId, setExpandedCourseId] = useState<number | null>(null);
  const [expandedContents, setExpandedContents] = useState<CourseContentItem[]>([]);
  const [expandedLoading, setExpandedLoading] = useState(false);

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

  // Collapsible sections
  const [childCoursesExpanded, setChildCoursesExpanded] = useState(true);
  const [myCoursesExpanded, setMyCoursesExpanded] = useState(true);

  // Edit course modal
  const [editCourse, setEditCourse] = useState<CourseItem | null>(null);
  const [editCourseName, setEditCourseName] = useState('');
  const [editCourseSubject, setEditCourseSubject] = useState('');
  const [editCourseDescription, setEditCourseDescription] = useState('');
  const [editCourseLoading, setEditCourseLoading] = useState(false);
  const [editCourseError, setEditCourseError] = useState('');

  // Edit content modal
  const [editContent, setEditContent] = useState<CourseContentItem | null>(null);
  const [editContentTitle, setEditContentTitle] = useState('');
  const [editContentDescription, setEditContentDescription] = useState('');
  const [editContentType, setEditContentType] = useState('');
  const [editContentLoading, setEditContentLoading] = useState(false);
  const [editContentError, setEditContentError] = useState('');
  const createModalRef = useFocusTrap<HTMLDivElement>(showCreateModal);
  const assignModalRef = useFocusTrap<HTMLDivElement>(showAssignModal, () => setShowAssignModal(false));
  const editCourseModalRef = useFocusTrap<HTMLDivElement>(!!editCourse);
  const editContentModalRef = useFocusTrap<HTMLDivElement>(!!editContent);

  useEffect(() => {
    loadData();
    const timeout = setTimeout(() => {
      setLoading(prev => {
        if (prev) setLoadError(true);
        return false;
      });
    }, 15000);
    return () => clearTimeout(timeout);
  }, []);

  useEffect(() => {
    if (selectedChild) {
      loadChildOverview(selectedChild);
    } else if (children.length > 0) {
      loadAllChildrenCourses();
    }
  }, [selectedChild]);

  // Persist selected child to sessionStorage for cross-page consistency
  useEffect(() => {
    if (selectedChild && children.length > 0) {
      const child = children.find(c => c.student_id === selectedChild);
      if (child) sessionStorage.setItem('selectedChildId', String(child.user_id));
    }
  }, [selectedChild, children]);

  // Debounced search term sync to URL
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchTerm) {
        searchParams.set('q', searchTerm);
      } else {
        searchParams.delete('q');
      }
      setSearchParams(searchParams, { replace: true });
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const loadData = async () => {
    setLoadError(false);
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
          if (match) {
            setSelectedChild(match.student_id);
          } else {
            const storedUserId = sessionStorage.getItem('selectedChildId');
            const storedMatch = storedUserId ? childrenData.find(c => c.user_id === Number(storedUserId)) : null;
            setSelectedChild(storedMatch ? storedMatch.student_id : childrenData[0].student_id);
          }
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
    } catch {
      setLoadError(true);
    } finally {
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

  const loadAllChildrenCourses = async () => {
    setOverviewLoading(true);
    try {
      const overviews = await Promise.all(
        children.map(c => parentApi.getChildOverview(c.student_id))
      );
      const seen = new Set<number>();
      const allCourses = overviews.flatMap(o => o.courses).filter(c => {
        if (seen.has(c.id)) return false;
        seen.add(c.id);
        return true;
      });
      setChildOverview({
        student_id: 0,
        user_id: 0,
        full_name: '',
        grade_level: null,
        google_connected: false,
        courses: allCourses,
        assignments: [],
        study_guides_count: 0,
      });
    } catch {
      setChildOverview(null);
    } finally {
      setOverviewLoading(false);
    }
  };

  const CONTENT_TYPE_LABELS: Record<string, string> = {
    notes: 'Notes', syllabus: 'Syllabus', labs: 'Labs',
    assignments: 'Assignments', readings: 'Readings', resources: 'Resources', other: 'Other',
  };

  const toggleCourseExpand = async (courseId: number) => {
    if (expandedCourseId === courseId) {
      setExpandedCourseId(null);
      return;
    }
    setExpandedCourseId(courseId);
    setExpandedLoading(true);
    try {
      const contents = await courseContentsApi.list(courseId);
      setExpandedContents(contents);
    } catch {
      setExpandedContents([]);
    } finally {
      setExpandedLoading(false);
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
      setCreateError(err.response?.data?.detail || 'Failed to create class');
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
      setActionError(err.response?.data?.detail || 'Failed to assign classes');
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
      setLastSynced(new Date());
      loadChildOverview(selectedChild);
      setTimeout(() => { setSyncState('idle'); setSyncMessage(''); }, 4000);
    } catch (err: any) {
      setSyncMessage(err.response?.data?.detail || 'Failed to sync classes');
      setSyncState('error');
    }
  };

  const handleConnectGoogle = async () => {
    try {
      const { authorization_url } = await googleApi.getConnectUrl();
      window.location.href = authorization_url;
    } catch {
      setActionError('Failed to start Google connection');
    }
  };

  const handleUnassignCourse = async (courseId: number, courseName: string) => {
    if (!selectedChild) return;
    const ok = await confirm({
      title: 'Unassign Class',
      message: `Remove "${courseName}" from ${childName}?`,
      confirmLabel: 'Unassign',
    });
    if (!ok) return;
    try {
      await parentApi.unassignCourseFromChild(selectedChild, courseId);
      loadChildOverview(selectedChild);
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to unassign class');
    }
  };

  const handleQuickAssign = async (courseId: number) => {
    if (!selectedChild) return;
    try {
      await parentApi.assignCoursesToChild(selectedChild, [courseId]);
      loadChildOverview(selectedChild);
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to assign class');
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
      title: 'Unenroll from Class',
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

  // ── Edit Course modal handlers ────────────────────────────────
  const openEditCourse = (course: CourseItem) => {
    setEditCourse(course);
    setEditCourseName(course.name);
    setEditCourseSubject(course.subject || '');
    setEditCourseDescription(course.description || '');
    setEditCourseError('');
  };

  const closeEditCourse = () => {
    setEditCourse(null);
    setEditCourseError('');
  };

  const handleSaveEditCourse = async () => {
    if (!editCourse || !editCourseName.trim()) return;
    setEditCourseLoading(true);
    setEditCourseError('');
    try {
      await coursesApi.update(editCourse.id, {
        name: editCourseName.trim(),
        subject: editCourseSubject.trim() || undefined,
        description: editCourseDescription.trim() || undefined,
      });
      closeEditCourse();
      loadData();
    } catch (err: any) {
      setEditCourseError(err.response?.data?.detail || 'Failed to update class');
    } finally {
      setEditCourseLoading(false);
    }
  };

  const handleDeleteCourseFromModal = async () => {
    if (!editCourse) return;
    const ok = await confirm({
      title: 'Delete Class',
      message: `Are you sure you want to delete "${editCourse.name}"? This cannot be undone.`,
      confirmLabel: 'Delete',
    });
    if (!ok) return;
    setEditCourseLoading(true);
    try {
      await coursesApi.delete(editCourse.id);
      closeEditCourse();
      loadData();
    } catch (err: any) {
      setEditCourseError(err.response?.data?.detail || 'Failed to delete class');
      setEditCourseLoading(false);
    }
  };

  // ── Edit Content modal handlers ──────────────────────────────
  const openEditContent = (item: CourseContentItem) => {
    setEditContent(item);
    setEditContentTitle(item.title);
    setEditContentDescription(item.description || '');
    setEditContentType(item.content_type);
    setEditContentError('');
  };

  const closeEditContent = () => {
    setEditContent(null);
    setEditContentError('');
  };

  const handleSaveEditContent = async () => {
    if (!editContent || !editContentTitle.trim()) return;
    setEditContentLoading(true);
    setEditContentError('');
    try {
      await courseContentsApi.update(editContent.id, {
        title: editContentTitle.trim(),
        description: editContentDescription.trim() || undefined,
        content_type: editContentType,
      });
      closeEditContent();
      if (expandedCourseId) {
        const contents = await courseContentsApi.list(expandedCourseId);
        setExpandedContents(contents);
      }
    } catch (err: any) {
      setEditContentError(err.response?.data?.detail || 'Failed to update material');
    } finally {
      setEditContentLoading(false);
    }
  };

  const handleDeleteContentFromModal = async () => {
    if (!editContent) return;
    const ok = await confirm({
      title: 'Delete Material',
      message: `Are you sure you want to delete "${editContent.title}"?`,
      confirmLabel: 'Delete',
    });
    if (!ok) return;
    setEditContentLoading(true);
    try {
      await courseContentsApi.delete(editContent.id);
      closeEditContent();
      if (expandedCourseId) {
        const contents = await courseContentsApi.list(expandedCourseId);
        setExpandedContents(contents);
      }
    } catch (err: any) {
      setEditContentError(err.response?.data?.detail || 'Failed to delete material');
      setEditContentLoading(false);
    }
  };

  const filteredAvailable = availableCourses.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (c.subject && c.subject.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (c.teacher_name && c.teacher_name.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const childName = childOverview?.full_name || children.find(c => c.student_id === selectedChild)?.full_name || '';
  const courseIds = (childOverview?.courses || []).map(c => c.id);

  if (loading || loadError) {
    return (
      <DashboardLayout welcomeSubtitle="Manage classes" showBackButton>
        {loadError ? (
          <div className="no-children-state">
            <h3>Unable to Load Classes</h3>
            <p>Something went wrong while loading your classes. Please try again.</p>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '20px' }}>
              <button className="link-child-btn" onClick={() => { setLoading(true); setLoadError(false); loadData(); }}>
                Retry
              </button>
              <button className="cancel-btn" onClick={() => window.location.reload()}>
                Refresh Page
              </button>
            </div>
          </div>
        ) : (
          <PageSkeleton />
        )}
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      welcomeSubtitle="Manage classes"
      showBackButton
      sidebarActions={[
        { label: '+ Add Class', onClick: () => setShowCreateModal(true) },
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
                onClick={() => setSelectedChild(selectedChild === child.student_id ? null : child.student_id)}
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
              <button className="collapse-toggle" onClick={() => setChildCoursesExpanded(v => !v)}>
                <span className={`section-chevron${childCoursesExpanded ? ' expanded' : ''}`}>&#9654;</span>
                <h3>{childName ? `${childName}'s Classes` : 'Classes'} ({childOverview?.courses.length ?? 0})</h3>
              </button>
              <div className="courses-header-actions">
                <button className="generate-btn" onClick={() => setShowCreateModal(true)}>
                  + Create Class
                </button>
                {myCourses.length > 0 && selectedChild && (
                  <button className="courses-btn secondary" onClick={() => { setSelectedCoursesForAssign(new Set()); setShowAssignModal(true); }}>
                    Assign Class
                  </button>
                )}
                {googleConnected && childOverview?.google_connected && (
                  <>
                    <button className="courses-btn secondary" onClick={handleSyncCourses} disabled={syncState === 'syncing'}>
                      {syncState === 'syncing' ? (<><span className="btn-spinner" /> Syncing...</>) : 'Sync Google'}
                    </button>
                    {lastSynced && syncState !== 'error' && (
                      <span className="last-synced">Last synced: {formatTimeAgo(lastSynced)}</span>
                    )}
                  </>
                )}
              </div>
            </div>
            {childCoursesExpanded && (
            <>
            {syncState === 'error' ? (
              <div className="sync-error">
                <span>{syncMessage || 'Sync failed'}</span>
                <button onClick={handleSyncCourses} className="retry-btn">Retry</button>
              </div>
            ) : syncMessage ? (
              <div className="courses-sync-msg">{syncMessage}</div>
            ) : null}
            {overviewLoading ? (
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                <CardSkeleton />
                <CardSkeleton />
                <CardSkeleton />
              </div>
            ) : childOverview && childOverview.courses.length > 0 ? (
              <div className="courses-list">
                {childOverview.courses.map((course) => (
                  <div key={course.id} className="course-list-item-wrapper">
                    <div
                      className={`course-list-row${expandedCourseId === course.id ? ' expanded' : ''}`}
                      onClick={() => toggleCourseExpand(course.id)}
                      onKeyDown={(e) => handleKeyDown(e, () => toggleCourseExpand(course.id))}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="course-list-color" style={{ background: getCourseColor(course.id, courseIds) }} />
                      <div className="course-list-body">
                        <span className="course-list-title">{course.name}</span>
                        <div className="course-list-meta">
                          {course.subject && <span className="course-card-subject">{course.subject}</span>}
                          {course.teacher_name && <span>{course.teacher_name}</span>}
                          {course.google_classroom_id && <span className="course-card-badge google">Google</span>}
                          {course.classroom_type === 'school' && <span className="course-card-badge school">School</span>}
                          {course.classroom_type === 'private' && course.google_classroom_id && <span className="course-card-badge private-gc">Private</span>}
                        </div>
                      </div>
                      <span className="course-list-expand">{expandedCourseId === course.id ? '▲' : '▼'}</span>
                      <div className="course-list-actions" onClick={(e) => e.stopPropagation()}>
                        <button className="course-list-btn" title="Edit" onClick={() => openEditCourse(course)}>&#9998;</button>
                        <button className="course-list-btn danger" title={`Unassign from ${childName}`} onClick={() => handleUnassignCourse(course.id, course.name)}>&#10005;</button>
                      </div>
                    </div>
                    {expandedCourseId === course.id && (
                      <div className="course-content-panel">
                        <div className="course-content-header">
                          <h5>Class Materials</h5>
                          <button className="courses-btn secondary" onClick={() => navigate(`/courses/${course.id}`)}>
                            View Details &rarr;
                          </button>
                        </div>
                        {expandedLoading ? (
                          <div className="course-content-empty"><p>Loading...</p></div>
                        ) : expandedContents.length === 0 ? (
                          <div className="course-content-empty">
                            <p>No materials yet. <span style={{ cursor: 'pointer', color: 'var(--color-accent)' }} onClick={() => navigate(`/courses/${course.id}`)}>Add content &rarr;</span></p>
                          </div>
                        ) : (
                          <div className="course-content-list">
                            {expandedContents.map((item) => (
                              <div key={item.id} className="content-item">
                                <div className="content-item-info">
                                  <span className={`content-type-badge ${item.content_type}`}>
                                    {CONTENT_TYPE_LABELS[item.content_type] || item.content_type}
                                  </span>
                                  <span className="content-item-title">{item.title}</span>
                                  {item.description && <p className="content-item-desc">{item.description}</p>}
                                </div>
                                <div className="content-item-actions">
                                  {item.reference_url && (
                                    <a href={item.reference_url} target="_blank" rel="noopener noreferrer" className="content-link">Link</a>
                                  )}
                                  {item.google_classroom_url && (
                                    <a href={item.google_classroom_url} target="_blank" rel="noopener noreferrer" className="content-link google">Google</a>
                                  )}
                                  <button className="course-list-btn" title="Edit" onClick={(e) => { e.stopPropagation(); openEditContent(item); }}>&#9998;</button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="courses-empty-grid">
                <button className="courses-empty-card" onClick={handleConnectGoogle}>
                  <span className="courses-empty-card-icon" aria-hidden="true">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
                  </span>
                  <span className="courses-empty-card-title">Connect Google Classroom</span>
                  <span className="courses-empty-card-desc">Import classes and assignments automatically</span>
                </button>
                <button className="courses-empty-card" onClick={() => setShowCreateModal(true)}>
                  <span className="courses-empty-card-icon" aria-hidden="true">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
                  </span>
                  <span className="courses-empty-card-title">Add Class Manually</span>
                  <span className="courses-empty-card-desc">Create a class and add materials yourself</span>
                </button>
              </div>
            )}
            </>
            )}
          </div>
        )}

        {/* Student: Enrollment tabs */}
        {isStudent && (
          <>
            <div className="courses-tabs">
              <button
                className={`courses-tab ${studentTab === 'enrolled' ? 'active' : ''}`}
                onClick={() => { setStudentTab('enrolled'); searchParams.delete('tab'); setSearchParams(searchParams, { replace: true }); }}
              >
                My Classes ({enrolledCourses.length})
              </button>
              <button
                className={`courses-tab ${studentTab === 'browse' ? 'active' : ''}`}
                onClick={() => { setStudentTab('browse'); searchParams.set('tab', 'browse'); setSearchParams(searchParams, { replace: true }); }}
              >
                Browse Classes ({availableCourses.length})
              </button>
            </div>

            {studentTab === 'enrolled' && (
              <div className="courses-section">
                {enrolledCourses.length > 0 ? (
                  <div className="courses-list">
                    {enrolledCourses.map((course) => (
                      <div key={course.id} className="course-list-item-wrapper">
                        <div
                          className={`course-list-row${expandedCourseId === course.id ? ' expanded' : ''}`}
                          onClick={() => toggleCourseExpand(course.id)}
                          onKeyDown={(e) => handleKeyDown(e, () => toggleCourseExpand(course.id))}
                          role="button"
                          tabIndex={0}
                        >
                          <div className="course-list-color" style={{ background: getCourseColor(course.id, enrolledCourses.map(c => c.id)) }} />
                          <div className="course-list-body">
                            <span className="course-list-title">{course.name}</span>
                            <div className="course-list-meta">
                              {course.subject && <span className="course-card-subject">{course.subject}</span>}
                              {course.teacher_name && <span>{course.teacher_name}</span>}
                            </div>
                          </div>
                          <span className="course-list-expand">{expandedCourseId === course.id ? '▲' : '▼'}</span>
                          <div className="course-list-actions" onClick={(e) => e.stopPropagation()}>
                            <button className="course-list-btn" title="Edit" onClick={() => openEditCourse(course)}>&#9998;</button>
                            <button
                              className="course-list-btn danger"
                              title="Unenroll"
                              onClick={() => handleUnenroll(course.id, course.name)}
                              disabled={enrollingId === course.id}
                            >&#10005;</button>
                          </div>
                        </div>
                        {expandedCourseId === course.id && (
                          <div className="course-content-panel">
                            <div className="course-content-header">
                              <h5>Class Materials</h5>
                              <button className="courses-btn secondary" onClick={() => navigate(`/courses/${course.id}`)}>
                                View Details &rarr;
                              </button>
                            </div>
                            {expandedLoading ? (
                              <div className="course-content-empty"><p>Loading...</p></div>
                            ) : expandedContents.length === 0 ? (
                              <div className="course-content-empty">
                                <p>No materials yet.</p>
                              </div>
                            ) : (
                              <div className="course-content-list">
                                {expandedContents.map((item) => (
                                  <div key={item.id} className="content-item">
                                    <div className="content-item-info">
                                      <span className={`content-type-badge ${item.content_type}`}>
                                        {CONTENT_TYPE_LABELS[item.content_type] || item.content_type}
                                      </span>
                                      <span className="content-item-title">{item.title}</span>
                                      {item.description && <p className="content-item-desc">{item.description}</p>}
                                    </div>
                                    <div className="content-item-actions">
                                      {item.reference_url && (
                                        <a href={item.reference_url} target="_blank" rel="noopener noreferrer" className="content-link">Link</a>
                                      )}
                                      {item.google_classroom_url && (
                                        <a href={item.google_classroom_url} target="_blank" rel="noopener noreferrer" className="content-link google">Google</a>
                                      )}
                                      <button className="course-list-btn" title="Edit" onClick={(e) => { e.stopPropagation(); openEditContent(item); }}>&#9998;</button>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    title="Not enrolled in any classes yet"
                    action={{ label: 'Browse Classes', onClick: () => setStudentTab('browse') }}
                    variant="compact"
                  />
                )}
              </div>
            )}

            {studentTab === 'browse' && (
              <div className="courses-section">
                <div className="courses-search">
                  <input
                    type="text"
                    placeholder="Search classes by name, subject, or teacher..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="courses-search-input"
                  />
                </div>
                {filteredAvailable.length > 0 ? (
                  <div className="courses-list">
                    {filteredAvailable.map((course) => (
                      <div key={course.id} className="course-list-row browse">
                        <div className="course-list-color" style={{ background: 'var(--color-accent)' }} />
                        <div className="course-list-body">
                          <span className="course-list-title">{course.name}</span>
                          <div className="course-list-meta">
                            {course.subject && <span className="course-card-subject">{course.subject}</span>}
                            {course.teacher_name && <span>{course.teacher_name}</span>}
                            {course.description && <span className="course-list-desc">{course.description}</span>}
                          </div>
                        </div>
                        <button
                          className="courses-btn primary"
                          onClick={() => handleEnroll(course.id)}
                          disabled={enrollingId === course.id}
                        >
                          {enrollingId === course.id ? (<><span className="btn-spinner" /> Enrolling...</>) : 'Enroll'}
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    title={searchTerm ? 'No classes match your search.' : 'No available classes to browse.'}
                    variant="compact"
                  />
                )}
              </div>
            )}
          </>
        )}

        {/* Parent: Created courses / Non-parent (non-student): All courses */}
        {!isStudent && (
        <div className="courses-section">
          <div className="courses-section-header">
            <button className="collapse-toggle" onClick={() => setMyCoursesExpanded(v => !v)}>
              <span className={`section-chevron${myCoursesExpanded ? ' expanded' : ''}`}>&#9654;</span>
              <h3>{isParent ? 'My Created Classes' : 'Classes'} ({myCourses.length})</h3>
            </button>
            {!isParent && (
              <button className="generate-btn" onClick={() => setShowCreateModal(true)}>
                + Create Class
              </button>
            )}
          </div>
          {myCoursesExpanded && myCourses.length > 0 ? (
            <div className="courses-list">
              {myCourses.map((course) => (
                <div
                  key={course.id}
                  className="course-list-row"
                  onClick={() => navigate(`/courses/${course.id}`)}
                  onKeyDown={(e) => handleKeyDown(e, () => navigate(`/courses/${course.id}`))}
                  role="button"
                  tabIndex={0}
                >
                  <div className="course-list-color" style={{ background: 'var(--color-accent)' }} />
                  <div className="course-list-body">
                    <span className="course-list-title">{course.name}</span>
                    <div className="course-list-meta">
                      {course.subject && <span className="course-card-subject">{course.subject}</span>}
                      {course.description && <span className="course-list-desc">{course.description}</span>}
                    </div>
                  </div>
                  <div className="course-list-actions" onClick={(e) => e.stopPropagation()}>
                    {isParent && selectedChild && (() => {
                      const alreadyAssigned = childOverview?.courses.some(c => c.id === course.id) ?? false;
                      return !alreadyAssigned ? (
                        <button className="course-list-btn assign" title={`Assign to ${childName}`} onClick={() => handleQuickAssign(course.id)}>&#10003;</button>
                      ) : (
                        <span className="course-card-assigned-badge" title={`Assigned to ${childName}`}>&#10003;</span>
                      );
                    })()}
                    <button className="course-list-btn" title="Edit" onClick={() => openEditCourse(course)}>&#9998;</button>
                  </div>
                </div>
              ))}
            </div>
          ) : myCoursesExpanded ? (
            <EmptyState
              title={isParent ? 'No classes created yet.' : 'No classes available. Create one to get started.'}
              variant="compact"
            />
          ) : null}
        </div>
        )}
      </div>

      {/* Create Course Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={closeCreateModal}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Create Class" ref={createModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Create Class</h2>
            <p className="modal-desc">Create a new class.</p>
            <div className="modal-form">
              <label>
                Class Name *
                <input type="text" value={courseName} onChange={(e) => setCourseName(e.target.value)} placeholder="e.g. Math Grade 5" disabled={createLoading} onKeyDown={(e) => e.key === 'Enter' && handleCreateCourse()} />
              </label>
              <label>
                Subject (optional)
                <input type="text" value={courseSubject} onChange={(e) => setCourseSubject(e.target.value)} placeholder="e.g. Mathematics" disabled={createLoading} />
              </label>
              <label>
                Description (optional)
                <textarea value={courseDescription} onChange={(e) => setCourseDescription(e.target.value)} placeholder="Class details..." rows={3} disabled={createLoading} />
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
                {createLoading ? 'Creating...' : 'Create Class'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Assign Course to Child Modal (parent only) */}
      {showAssignModal && selectedChild && (
        <div className="modal-overlay" onClick={() => setShowAssignModal(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label={`Assign Class to ${childName}`} ref={assignModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Assign Class to {childName}</h2>
            <p className="modal-desc">Select classes to assign to your child.</p>
            <div className="modal-form">
              {myCourses.length === 0 ? (
                <EmptyState
                  title="No classes created yet"
                  action={{ label: '+ Create Class', onClick: () => { setShowAssignModal(false); setShowCreateModal(true); } }}
                  variant="compact"
                />
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
                {assignLoading ? 'Assigning...' : `Assign ${selectedCoursesForAssign.size} Class${selectedCoursesForAssign.size !== 1 ? 'es' : ''}`}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Edit Course Modal */}
      {editCourse && (
        <div className="modal-overlay" onClick={closeEditCourse}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Edit Class" ref={editCourseModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Edit Class</h2>
            <div className="modal-form">
              <label>
                Class Name *
                <input type="text" value={editCourseName} onChange={(e) => setEditCourseName(e.target.value)} placeholder="e.g. Math Grade 5" disabled={editCourseLoading} onKeyDown={(e) => e.key === 'Enter' && handleSaveEditCourse()} />
              </label>
              <label>
                Subject
                <input type="text" value={editCourseSubject} onChange={(e) => setEditCourseSubject(e.target.value)} placeholder="e.g. Mathematics" disabled={editCourseLoading} />
              </label>
              <label>
                Description
                <textarea value={editCourseDescription} onChange={(e) => setEditCourseDescription(e.target.value)} placeholder="Class details..." rows={3} disabled={editCourseLoading} />
              </label>
              {editCourseError && <p className="link-error">{editCourseError}</p>}
            </div>
            <div className="modal-actions">
              {!editCourse.google_classroom_id && (
                <button className="cancel-btn danger-text" onClick={handleDeleteCourseFromModal} disabled={editCourseLoading}>Delete Class</button>
              )}
              <button className="cancel-btn" onClick={closeEditCourse} disabled={editCourseLoading}>Cancel</button>
              <button className="generate-btn" onClick={handleSaveEditCourse} disabled={editCourseLoading || !editCourseName.trim()}>
                {editCourseLoading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Content Modal */}
      {editContent && (
        <div className="modal-overlay" onClick={closeEditContent}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Edit Material" ref={editContentModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Edit Material</h2>
            <div className="modal-form">
              <label>
                Title *
                <input type="text" value={editContentTitle} onChange={(e) => setEditContentTitle(e.target.value)} placeholder="Material title" disabled={editContentLoading} onKeyDown={(e) => e.key === 'Enter' && handleSaveEditContent()} />
              </label>
              <label>
                Description
                <textarea value={editContentDescription} onChange={(e) => setEditContentDescription(e.target.value)} placeholder="Material description..." rows={3} disabled={editContentLoading} />
              </label>
              <label>
                Type
                <select value={editContentType} onChange={(e) => setEditContentType(e.target.value)} disabled={editContentLoading}>
                  {Object.entries(CONTENT_TYPE_LABELS).map(([val, label]) => (
                    <option key={val} value={val}>{label}</option>
                  ))}
                </select>
              </label>
              {editContentError && <p className="link-error">{editContentError}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn danger-text" onClick={handleDeleteContentFromModal} disabled={editContentLoading}>Delete Material</button>
              <button className="cancel-btn" onClick={closeEditContent} disabled={editContentLoading}>Cancel</button>
              <button className="generate-btn" onClick={handleSaveEditContent} disabled={editContentLoading || !editContentTitle.trim()}>
                {editContentLoading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmModal}
    </DashboardLayout>
  );
}
