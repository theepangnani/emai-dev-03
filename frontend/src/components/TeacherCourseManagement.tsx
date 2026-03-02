import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { coursesApi } from '../api/client';
import type { TeacherCourseManagement as TCM } from '../api/client';
import EmptyState from './EmptyState';
import './TeacherCourseManagement.css';

type SourceFilter = 'all' | 'google' | 'manual' | 'admin';
type SortKey = 'name' | 'students' | 'activity' | 'assignments';

const SOURCE_LABELS: Record<string, string> = {
  google: 'Google Classroom',
  manual: 'Manual',
  admin: 'Admin',
};

const SOURCE_ICONS: Record<string, React.ReactNode> = {
  google: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  ),
  manual: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  ),
  admin: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
};

function formatRelativeDate(dateStr: string | null): string {
  if (!dateStr) return 'No activity';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} week${Math.floor(diffDays / 7) !== 1 ? 's' : ''} ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} month${Math.floor(diffDays / 30) !== 1 ? 's' : ''} ago`;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

interface TeacherCourseManagementProps {
  googleConnected: boolean;
  onSync: () => Promise<void>;
  syncing: boolean;
  onCreateCourse: () => void;
}

export function TeacherCourseManagement({
  googleConnected,
  onSync,
  syncing,
  onCreateCourse,
}: TeacherCourseManagementProps) {
  const navigate = useNavigate();
  const [courses, setCourses] = useState<TCM[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filters and sort
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all');
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [searchQuery, setSearchQuery] = useState('');
  const [expanded, setExpanded] = useState(true);

  const loadCourses = useCallback(async () => {
    try {
      const data = await coursesApi.teachingManagement();
      setCourses(data);
    } catch {
      setError('Failed to load course data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCourses();
  }, [loadCourses]);

  // Compute source counts for filter pills
  const sourceCounts = useMemo(() => {
    const counts: Record<string, number> = { all: courses.length, google: 0, manual: 0, admin: 0 };
    for (const c of courses) {
      counts[c.source] = (counts[c.source] || 0) + 1;
    }
    return counts;
  }, [courses]);

  // Apply filters, search, and sort
  const filteredCourses = useMemo(() => {
    let result = courses;

    // Source filter
    if (sourceFilter !== 'all') {
      result = result.filter(c => c.source === sourceFilter);
    }

    // Search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(c =>
        c.name.toLowerCase().includes(q) ||
        (c.subject && c.subject.toLowerCase().includes(q)) ||
        (c.description && c.description.toLowerCase().includes(q))
      );
    }

    // Sort
    result = [...result].sort((a, b) => {
      switch (sortKey) {
        case 'name':
          return a.name.localeCompare(b.name);
        case 'students':
          return b.student_count - a.student_count;
        case 'activity': {
          const aTime = a.last_activity ? new Date(a.last_activity).getTime() : 0;
          const bTime = b.last_activity ? new Date(b.last_activity).getTime() : 0;
          return bTime - aTime;
        }
        case 'assignments':
          return b.assignment_count - a.assignment_count;
        default:
          return 0;
      }
    });

    return result;
  }, [courses, sourceFilter, searchQuery, sortKey]);

  const handleSyncAndReload = async () => {
    await onSync();
    await loadCourses();
  };

  if (loading) {
    return (
      <section className="section tcm-section">
        <div className="section-header">
          <h3>Class Management</h3>
        </div>
        <div className="tcm-loading">Loading class data...</div>
      </section>
    );
  }

  return (
    <section className="section tcm-section">
      <div className="section-header">
        <button className="collapse-toggle" onClick={() => setExpanded(v => !v)}>
          <span className={`section-chevron${expanded ? ' expanded' : ''}`}>&#9654;</span>
          <h3>Class Management ({courses.length})</h3>
        </button>
        <div className="section-header-actions">
          {googleConnected && (
            <button className="sync-btn" onClick={handleSyncAndReload} disabled={syncing}>
              {syncing ? 'Syncing...' : 'Sync Classes'}
            </button>
          )}
          <button className="create-custom-btn" onClick={onCreateCourse}>
            + Create Class
          </button>
        </div>
      </div>

      {expanded && (
        <>
          {error && <div className="tcm-error">{error}</div>}

          {courses.length > 0 && (
            <div className="tcm-toolbar">
              {/* Source filter pills */}
              <div className="tcm-filters">
                {(['all', 'google', 'manual', 'admin'] as SourceFilter[]).map((filter) => (
                  sourceCounts[filter] > 0 || filter === 'all' ? (
                    <button
                      key={filter}
                      className={`tcm-filter-pill${sourceFilter === filter ? ' active' : ''}${filter !== 'all' ? ` source-${filter}` : ''}`}
                      onClick={() => setSourceFilter(filter)}
                    >
                      {filter === 'all' ? 'All' : SOURCE_LABELS[filter]}
                      <span className="tcm-filter-count">{sourceCounts[filter]}</span>
                    </button>
                  ) : null
                ))}
              </div>

              {/* Sort and search */}
              <div className="tcm-controls">
                <label htmlFor="tcm-sort" className="sr-only">Sort by</label>
                <select
                  id="tcm-sort"
                  className="tcm-sort-select"
                  value={sortKey}
                  onChange={(e) => setSortKey(e.target.value as SortKey)}
                >
                  <option value="name">Sort: Name</option>
                  <option value="students">Sort: Students</option>
                  <option value="activity">Sort: Last Activity</option>
                  <option value="assignments">Sort: Assignments</option>
                </select>

                {courses.length > 3 && (
                  <>
                    <label htmlFor="tcm-search" className="sr-only">Search classes</label>
                    <input
                      id="tcm-search"
                      type="text"
                      className="tcm-search-input"
                      placeholder="Search classes..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                  </>
                )}
              </div>
            </div>
          )}

          {filteredCourses.length > 0 ? (
            <div className="tcm-grid">
              {filteredCourses.map((course) => (
                <div key={course.id} className="tcm-card" onClick={() => navigate(`/courses/${course.id}`)}>
                  <div className="tcm-card-header">
                    <h4 className="tcm-card-name">{course.name}</h4>
                    <span className={`tcm-source-badge source-${course.source}`}>
                      {SOURCE_ICONS[course.source]}
                      {SOURCE_LABELS[course.source]}
                    </span>
                  </div>

                  {course.subject && (
                    <span className="tcm-subject-tag">{course.subject}</span>
                  )}

                  {course.description && (
                    <p className="tcm-card-desc">{course.description}</p>
                  )}

                  <div className="tcm-card-stats">
                    <div className="tcm-stat">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                        <circle cx="9" cy="7" r="4" />
                      </svg>
                      <span>{course.student_count} {course.student_count === 1 ? 'student' : 'students'}</span>
                    </div>
                    <div className="tcm-stat">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="9 11 12 14 22 4" />
                        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                      </svg>
                      <span>{course.assignment_count} {course.assignment_count === 1 ? 'assignment' : 'assignments'}</span>
                    </div>
                    <div className="tcm-stat">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                      </svg>
                      <span>{course.material_count} {course.material_count === 1 ? 'material' : 'materials'}</span>
                    </div>
                  </div>

                  <div className="tcm-card-footer">
                    <span className="tcm-last-activity">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10" />
                        <polyline points="12 6 12 12 16 14" />
                      </svg>
                      {formatRelativeDate(course.last_activity)}
                    </span>
                    <div className="tcm-card-actions" onClick={(e) => e.stopPropagation()}>
                      <button
                        className="tcm-action-btn"
                        title="View Course"
                        onClick={() => navigate(`/courses/${course.id}`)}
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                          <circle cx="12" cy="12" r="3" />
                        </svg>
                      </button>
                      <button
                        className="tcm-action-btn"
                        title="Add Material"
                        onClick={() => navigate(`/courses/${course.id}?tab=materials`)}
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                          <polyline points="14 2 14 8 20 8" />
                          <line x1="12" y1="18" x2="12" y2="12" />
                          <line x1="9" y1="15" x2="15" y2="15" />
                        </svg>
                      </button>
                      {course.source === 'google' && googleConnected && (
                        <button
                          className="tcm-action-btn tcm-sync-action"
                          title="Sync from Google"
                          onClick={handleSyncAndReload}
                          disabled={syncing}
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="23 4 23 10 17 10" />
                            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : courses.length > 0 ? (
            <EmptyState
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
              }
              title="No matching classes"
              description="Try adjusting your search or filter."
            />
          ) : (
            <EmptyState
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
                </svg>
              }
              title="No classes yet"
              description="Create your first class to start organizing materials and assignments."
              action={{ label: 'Create a Class', onClick: onCreateCourse }}
            />
          )}
        </>
      )}
    </section>
  );
}
