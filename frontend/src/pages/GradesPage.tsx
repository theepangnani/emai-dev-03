import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { gradesApi } from '../api/grades';
import type { ClassroomGradeItem } from '../api/grades';
import { parentApi } from '../api/parent';
import type { ChildSummary } from '../api/parent';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageSkeleton } from '../components/Skeleton';
import './GradesPage.css';

type SortMode = 'recent' | 'highest' | 'lowest';

function gradeChipColor(pct: number): 'green' | 'amber' | 'red' {
  if (pct >= 80) return 'green';
  if (pct >= 60) return 'amber';
  return 'red';
}

function formatGradedAt(dateStr: string | null): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}

export function GradesPage() {
  const { user } = useAuth();
  const isParent = user?.role === 'parent' || (user?.roles?.includes('parent') ?? false);

  // Children (for parents)
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChildUserId, setSelectedChildUserId] = useState<number | null>(null);

  // Data
  const [grades, setGrades] = useState<ClassroomGradeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // UI state
  const [sortMode, setSortMode] = useState<SortMode>('recent');
  const [expandedCourses, setExpandedCourses] = useState<Set<string>>(new Set());

  // Load children (parents only)
  useEffect(() => {
    if (!isParent) return;
    parentApi.getChildren()
      .then((kids) => {
        setChildren(kids);
        if (kids.length > 0 && selectedChildUserId === null) {
          const storedId = sessionStorage.getItem('selectedChildId');
          const match = storedId ? kids.find(k => k.user_id === Number(storedId)) : null;
          setSelectedChildUserId(match ? match.user_id : kids[0].user_id);
        }
      })
      .catch(() => {});
  }, [isParent]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load grades when child changes (or on mount for students)
  useEffect(() => {
    if (isParent && selectedChildUserId === null) return;
    loadGrades(isParent ? (selectedChildUserId ?? undefined) : undefined);
  }, [isParent, selectedChildUserId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadGrades(childId?: number) {
    setLoading(true);
    setError('');
    try {
      const data = await gradesApi.getGrades(childId);
      setGrades(data);
      // Auto-expand all courses on first load
      const courseNames = Array.from(new Set(data.map(g => g.course_name)));
      setExpandedCourses(new Set(courseNames));
    } catch (err: any) {
      if (err?.response?.status === 400 || err?.response?.status === 404) {
        // Google not connected or no grades — show empty state
        setGrades([]);
      } else {
        setError('Failed to load grades. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }

  // Group grades by course and apply sort
  const courseGroups = useMemo(() => {
    const map = new Map<string, ClassroomGradeItem[]>();
    for (const g of grades) {
      const key = g.course_name;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(g);
    }

    // Sort items within each course
    map.forEach((items, key) => {
      const sorted = [...items];
      if (sortMode === 'recent') {
        sorted.sort((a, b) => (b.graded_at ?? '').localeCompare(a.graded_at ?? ''));
      } else if (sortMode === 'highest') {
        sorted.sort((a, b) => b.percentage - a.percentage);
      } else {
        sorted.sort((a, b) => a.percentage - b.percentage);
      }
      map.set(key, sorted);
    });

    return map;
  }, [grades, sortMode]);

  const toggleCourse = (courseName: string) => {
    setExpandedCourses(prev => {
      const next = new Set(prev);
      if (next.has(courseName)) {
        next.delete(courseName);
      } else {
        next.add(courseName);
      }
      return next;
    });
  };

  const handleChildSelect = (userId: number) => {
    setSelectedChildUserId(userId);
    sessionStorage.setItem('selectedChildId', String(userId));
  };

  const totalGraded = grades.length;
  const overallAvg = totalGraded > 0
    ? Math.round(grades.reduce((sum, g) => sum + g.percentage, 0) / totalGraded)
    : null;

  return (
    <DashboardLayout welcomeSubtitle="Your grades from Google Classroom">
      <div className="gp-container">
        <div className="gp-header">
          <div className="gp-header-left">
            <h1 className="gp-title">Grades</h1>
            <p className="gp-subtitle">
              {isParent
                ? "Your child's grades from Google Classroom"
                : 'Your grades from Google Classroom'}
            </p>
          </div>
          <div className="gp-header-actions">
            {overallAvg !== null && (
              <span className={`gp-overall-chip gp-chip--${gradeChipColor(overallAvg)}`}>
                Overall: {overallAvg}%
              </span>
            )}
            <Link to="/analytics" className="gp-analytics-link">
              Analytics
            </Link>
          </div>
        </div>

        {/* Child selector pills (parents only) */}
        {isParent && children.length > 0 && (
          <div className="gp-child-pills">
            {children.map(child => (
              <button
                key={child.user_id}
                className={`gp-child-pill${selectedChildUserId === child.user_id ? ' active' : ''}`}
                onClick={() => handleChildSelect(child.user_id)}
              >
                {child.full_name}
              </button>
            ))}
          </div>
        )}

        {/* Sort controls */}
        {grades.length > 0 && (
          <div className="gp-sort-bar">
            <span className="gp-sort-label">Sort by:</span>
            {(['recent', 'highest', 'lowest'] as SortMode[]).map(mode => (
              <button
                key={mode}
                className={`gp-sort-btn${sortMode === mode ? ' active' : ''}`}
                onClick={() => setSortMode(mode)}
              >
                {mode === 'recent' ? 'Most Recent' : mode === 'highest' ? 'Highest Grade' : 'Lowest Grade'}
              </button>
            ))}
          </div>
        )}

        {loading ? (
          <PageSkeleton />
        ) : error ? (
          <div className="gp-error">{error}</div>
        ) : grades.length === 0 ? (
          <div className="gp-empty">
            <span className="gp-empty-icon" aria-hidden="true">&#128202;</span>
            <h2>No graded work yet</h2>
            <p>
              Grades will appear here once your teacher returns graded assignments in Google Classroom.
              Make sure Google Classroom is connected on your dashboard.
            </p>
            <Link to="/dashboard" className="gp-empty-cta">Back to Dashboard</Link>
          </div>
        ) : (
          <div className="gp-courses-list">
            {Array.from(courseGroups.entries()).map(([courseName, items]) => {
              const isExpanded = expandedCourses.has(courseName);
              const courseAvg = items.length > 0
                ? Math.round(items.reduce((s, g) => s + g.percentage, 0) / items.length)
                : null;
              const courseColor = courseAvg !== null ? gradeChipColor(courseAvg) : 'green';

              return (
                <div key={courseName} className="gp-course-accordion">
                  <button
                    className={`gp-course-accordion__header${isExpanded ? ' expanded' : ''}`}
                    onClick={() => toggleCourse(courseName)}
                    aria-expanded={isExpanded}
                  >
                    <div className="gp-course-accordion__title-row">
                      <svg
                        className={`gp-course-accordion__chevron${isExpanded ? ' rotated' : ''}`}
                        width="16" height="16" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" strokeWidth="2"
                        strokeLinecap="round" strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <polyline points="6 9 12 15 18 9" />
                      </svg>
                      <span className="gp-course-accordion__name">{courseName}</span>
                    </div>
                    <div className="gp-course-accordion__meta">
                      <span className="gp-course-accordion__count">{items.length} graded</span>
                      {courseAvg !== null && (
                        <span className={`gp-chip gp-chip--${courseColor}`}>
                          Avg {courseAvg}%
                        </span>
                      )}
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="gp-course-accordion__body">
                      <div className="gp-asgn-header">
                        <span className="gp-ath title">Assignment</span>
                        <span className="gp-ath date">Graded</span>
                        <span className="gp-ath chip">Score</span>
                      </div>
                      {items.map((g, idx) => {
                        const chipColor = gradeChipColor(g.percentage);
                        return (
                          <div key={idx} className="gp-asgn-row">
                            <span className="gp-atd title">{g.assignment_title}</span>
                            <span className="gp-atd date">{formatGradedAt(g.graded_at)}</span>
                            <span className={`gp-chip gp-chip--${chipColor}`}>
                              {g.grade}/{g.max_grade} &mdash; {g.percentage}%
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
