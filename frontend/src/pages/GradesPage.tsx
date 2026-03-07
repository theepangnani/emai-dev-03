import { useState, useEffect, useMemo, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { gradesApi } from '../api/grades';
import type { ChildGradeSummary, CourseGradesResponse } from '../api/grades';
import { useAuth } from '../context/AuthContext';
import { PageSkeleton, ListSkeleton } from '../components/Skeleton';
import { PageNav } from '../components/PageNav';
import './GradesPage.css';

function letterColor(color: string): string {
  if (color === 'green') return 'grades-color-green';
  if (color === 'yellow') return 'grades-color-yellow';
  return 'grades-color-red';
}

export function GradesPage() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [children, setChildren] = useState<ChildGradeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCourse, setExpandedCourse] = useState<number | null>(null);
  const [courseGrades, setCourseGrades] = useState<CourseGradesResponse | null>(null);
  const [courseLoading, setCourseLoading] = useState(false);
  const [syncing, setSyncing] = useState<number | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  // Filter state from URL params
  const filterCourseId = searchParams.get('course') ? Number(searchParams.get('course')) : null;
  const filterStudentId = searchParams.get('student') ? Number(searchParams.get('student')) : null;

  // Load grade summary
  const loadSummary = useCallback(async (studentId?: number, courseIdToExpand?: number | null) => {
    setLoading(true);
    setError(null);
    try {
      const data = await gradesApi.summary(studentId);
      setChildren(data.children);
      if (courseIdToExpand) {
        setExpandedCourse(courseIdToExpand);
      }
    } catch {
      setError('Failed to load grades. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSummary(filterStudentId ?? undefined, filterCourseId);
  }, [filterStudentId, filterCourseId, loadSummary]);

  // Load detailed course grades when a course is expanded
  const loadCourseDetail = useCallback(async (courseId: number, studentId?: number) => {
    setCourseLoading(true);
    try {
      const data = await gradesApi.byCourse(courseId, studentId);
      setCourseGrades(data);
    } catch {
      setCourseGrades(null);
    } finally {
      setCourseLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!expandedCourse) {
      setCourseGrades(null);
      return;
    }
    loadCourseDetail(expandedCourse, filterStudentId ?? undefined);
  }, [expandedCourse, filterStudentId, loadCourseDetail]);

  const handleToggleCourse = (courseId: number) => {
    if (expandedCourse === courseId) {
      setExpandedCourse(null);
      // Clear course param from URL
      const params = new URLSearchParams(searchParams);
      params.delete('course');
      setSearchParams(params, { replace: true });
    } else {
      setExpandedCourse(courseId);
    }
  };

  const handleSyncGrades = async (courseId: number) => {
    setSyncing(courseId);
    setSyncMessage(null);
    try {
      const result = await gradesApi.syncGrades(courseId);
      setSyncMessage(result.message);
      // Reload data
      const data = await gradesApi.summary(filterStudentId ?? undefined);
      setChildren(data.children);
      if (expandedCourse === courseId) {
        const courseData = await gradesApi.byCourse(courseId, filterStudentId ?? undefined);
        setCourseGrades(courseData);
      }
    } catch {
      setSyncMessage('Failed to sync grades. Make sure Google Classroom is connected.');
    } finally {
      setSyncing(null);
    }
  };

  // Get all courses across children for course filter dropdown
  const allCourses = useMemo(() => {
    const seen = new Set<number>();
    const courses: Array<{ id: number; name: string }> = [];
    for (const child of children) {
      for (const c of child.courses) {
        if (!seen.has(c.course_id)) {
          seen.add(c.course_id);
          courses.push({ id: c.course_id, name: c.course_name });
        }
      }
    }
    return courses;
  }, [children]);

  // Filter children by course
  const filteredChildren = useMemo(() => {
    if (!filterCourseId) return children;
    return children
      .map(child => ({
        ...child,
        courses: child.courses.filter(c => c.course_id === filterCourseId),
      }))
      .filter(child => child.courses.length > 0);
  }, [children, filterCourseId]);

  const isParent = user?.role === 'parent' || user?.roles?.includes('parent');

  return (
    <DashboardLayout>
      <div className="gp-container">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Grades' },
        ]} />
        <div className="gp-header">
          <div className="gp-header-left">
            <h1 className="gp-title">Grades</h1>
            <p className="gp-subtitle">
              {isParent ? "Your children's grade overview from Google Classroom" : 'Your grade overview from Google Classroom'}
            </p>
          </div>
          <div className="gp-header-actions">
            {allCourses.length > 1 && (
              <select
                className="gp-filter-select"
                value={filterCourseId ?? ''}
                onChange={e => {
                  const params = new URLSearchParams(searchParams);
                  if (e.target.value) {
                    params.set('course', e.target.value);
                  } else {
                    params.delete('course');
                  }
                  setSearchParams(params, { replace: true });
                }}
                aria-label="Filter by class"
              >
                <option value="">All Classes</option>
                {allCourses.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            )}
            <Link to="/analytics" className="gp-analytics-link">
              Analytics
            </Link>
          </div>
        </div>

        {syncMessage && (
          <div className="gp-sync-message" role="status">
            {syncMessage}
            <button className="gp-sync-dismiss" onClick={() => setSyncMessage(null)} aria-label="Dismiss">&times;</button>
          </div>
        )}

        {loading ? (
          <PageSkeleton />
        ) : error ? (
          <div className="gp-error">
            <p>{error}</p>
          </div>
        ) : filteredChildren.length === 0 || filteredChildren.every(c => c.courses.length === 0) ? (
          <div className="gp-empty">
            <span className="gp-empty-icon" aria-hidden="true">&#128218;</span>
            <h2>No Grades Available</h2>
            <p>Grades will appear here once they are synced from Google Classroom. Make sure your courses are connected and assignments have been graded.</p>
            <Link to="/dashboard" className="gp-empty-cta">Back to Dashboard</Link>
          </div>
        ) : (
          <div className="gp-children-list">
            {filteredChildren.map(child => (
              <div key={child.student_id} className="gp-child-section section-card">
                {/* Show child header only for parents with multiple children */}
                {isParent && children.length > 1 && (
                  <div className="gp-child-header">
                    <h2 className="gp-child-name">{child.student_name}</h2>
                    <span className={`gp-overall-badge ${letterColor(child.color)}`}>
                      {child.letter_grade} - {child.overall_average}%
                    </span>
                  </div>
                )}

                {/* Overall average for single-child/student */}
                {((!isParent) || children.length === 1) && (
                  <div className="gp-overall-row">
                    <span className={`gp-overall-letter ${letterColor(child.color)}`}>
                      {child.letter_grade}
                    </span>
                    <div className="gp-overall-info">
                      <span className="gp-overall-pct">{child.overall_average}%</span>
                      <span className="gp-overall-label">Overall Average</span>
                    </div>
                  </div>
                )}

                {/* Course grade table */}
                <div className="gp-courses-table">
                  <div className="gp-table-header">
                    <span className="gp-th course">Class</span>
                    <span className="gp-th grade">Grade</span>
                    <span className="gp-th avg">Average</span>
                    <span className="gp-th progress">Progress</span>
                    <span className="gp-th actions">Actions</span>
                  </div>
                  {child.courses.map(course => (
                    <div key={course.course_id} className="gp-course-block">
                      <button
                        className={`gp-course-row${expandedCourse === course.course_id ? ' expanded' : ''}`}
                        onClick={() => handleToggleCourse(course.course_id)}
                        aria-expanded={expandedCourse === course.course_id}
                      >
                        <span className="gp-td course">
                          <span className={`gp-expand-icon${expandedCourse === course.course_id ? ' open' : ''}`} aria-hidden="true">{'\u25B6'}</span>
                          {course.course_name}
                        </span>
                        <span className="gp-td grade">
                          <span className={`gp-letter-badge ${letterColor(course.color)}`}>
                            {course.letter_grade}
                          </span>
                        </span>
                        <span className="gp-td avg">{course.average_grade}%</span>
                        <span className="gp-td progress">
                          <span className="gp-progress-text">{course.graded_count}/{course.assignment_count}</span>
                          <span className="gp-progress-bar">
                            <span
                              className="gp-progress-fill"
                              style={{ width: `${course.assignment_count > 0 ? (course.graded_count / course.assignment_count) * 100 : 0}%` }}
                            />
                          </span>
                        </span>
                        <span className="gp-td actions" onClick={e => e.stopPropagation()}>
                          <button
                            className="gp-sync-btn"
                            onClick={() => handleSyncGrades(course.course_id)}
                            disabled={syncing === course.course_id}
                            title="Sync grades from Google Classroom"
                          >
                            {syncing === course.course_id ? 'Syncing...' : 'Sync'}
                          </button>
                        </span>
                      </button>

                      {/* Expanded assignment detail */}
                      {expandedCourse === course.course_id && (
                        <div className="gp-assignments-detail">
                          {courseLoading ? (
                            <ListSkeleton rows={3} />
                          ) : courseGrades && courseGrades.assignments.length > 0 ? (
                            <div className="gp-assignments-table">
                              <div className="gp-asgn-header">
                                <span className="gp-ath title">Assignment</span>
                                <span className="gp-ath score">Score</span>
                                <span className="gp-ath pct">%</span>
                                <span className="gp-ath letter">Grade</span>
                                <span className="gp-ath due">Due Date</span>
                              </div>
                              {courseGrades.assignments.map(asgn => (
                                <div key={asgn.grade_record_id} className="gp-asgn-row">
                                  <span className="gp-atd title">{asgn.assignment_title}</span>
                                  <span className="gp-atd score">{asgn.grade}/{asgn.max_grade}</span>
                                  <span className="gp-atd pct">{asgn.percentage}%</span>
                                  <span className="gp-atd letter">
                                    <span className={`gp-mini-badge ${letterColor(asgn.color)}`}>
                                      {asgn.letter_grade}
                                    </span>
                                  </span>
                                  <span className="gp-atd due">
                                    {asgn.due_date ? new Date(asgn.due_date).toLocaleDateString([], { month: 'short', day: 'numeric' }) : '--'}
                                  </span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="gp-no-assignments">No graded assignments yet for this course.</p>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
