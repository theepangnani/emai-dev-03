import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { coursesApi, courseContentsApi, studyApi, googleApi } from '../api/client';
import type { CourseContentItem } from '../api/client';
import type { QuizHistoryStats } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import CreateStudyMaterialModal from '../components/CreateStudyMaterialModal';
import { useParentStudyTools } from '../components/parent/hooks/useParentStudyTools';
import { getCourseColor } from '../components/calendar/types';
import './StudyPage.css';

// ── Local Types ─────────────────────────────────────────────────────────────

interface CourseItem {
  id: number;
  name: string;
  description: string | null;
  subject: string | null;
  google_classroom_id?: string | null;
  classroom_type?: string | null;
  teacher_name?: string | null;
  is_private?: boolean;
}

type ContentTypeFilter = 'all' | 'study_guide' | 'quiz' | 'flashcards' | 'raw';

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function getTypeColor(type: string): string {
  switch (type) {
    case 'study_guide': return 'var(--color-accent)';
    case 'quiz': return '#f97316';
    case 'flashcards': return '#8b5cf6';
    default: return 'var(--color-ink-muted)';
  }
}

function ContentTypeIcon({ type, size = 20 }: { type: string; size?: number }) {
  const color = getTypeColor(type);
  if (type === 'study_guide') return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
    </svg>
  );
  if (type === 'quiz') return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17" strokeWidth="3"/>
    </svg>
  );
  if (type === 'flashcards') return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="2" y="6" width="20" height="14" rx="2"/><path d="M6 2h12a2 2 0 0 1 2 2v2H4V4a2 2 0 0 1 2-2z"/>
    </svg>
  );
  // default: document
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
    </svg>
  );
}

function getContentTypeLabel(contentType: string): string {
  switch (contentType) {
    case 'study_guide': return 'Study Guide';
    case 'quiz':        return 'Quiz';
    case 'flashcards':  return 'Flashcards';
    default:            return 'Document';
  }
}

function getDetailPath(item: CourseContentItem): string {
  return `/course-materials/${item.id}`;
}

// Has this raw doc had any AI materials generated from it?
// The CourseContentItem does not carry guide counts, so we use content_type itself —
// if it's not raw, it already has a generated type; if raw, show Generate.
function isRaw(item: CourseContentItem): boolean {
  return item.content_type === 'raw' || !item.content_type;
}

// ── Progress Ring Component ───────────────────────────────────────────────────

function ProgressRing({ score, size = 72, strokeWidth = 6 }: { score: number; size?: number; strokeWidth?: number }) {
  const r = (size - strokeWidth * 2) / 2;
  const circ = 2 * Math.PI * r;
  const filled = Math.max(0, Math.min(1, score / 100)) * circ;
  const cx = size / 2;
  const cy = size / 2;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--color-border)" strokeWidth={strokeWidth} />
      <circle
        cx={cx} cy={cy} r={r} fill="none"
        stroke="var(--color-accent)" strokeWidth={strokeWidth}
        strokeDasharray={`${filled} ${circ - filled}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${cx} ${cy})`}
        style={{ transition: 'stroke-dasharray 0.6s cubic-bezier(0.4,0,0.2,1)' }}
      />
      <text x={cx} y={cy} textAnchor="middle" dominantBaseline="central"
        style={{ fontSize: size * 0.22, fontWeight: 700, fill: 'var(--color-ink)', fontFamily: 'var(--font-display)' }}>
        {score}%
      </text>
    </svg>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────

export function StudyPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  // ── State ──────────────────────────────────────────────────────────────────
  const [selectedCourseId, setSelectedCourseId] = useState<number | 'all'>('all');
  const [typeFilter, setTypeFilter] = useState<ContentTypeFilter>('all');

  const [courses, setCourses] = useState<CourseItem[]>([]);
  const [materials, setMaterials] = useState<CourseContentItem[]>([]);
  const [quizStats, setQuizStats] = useState<QuizHistoryStats | null>(null);
  const [materialCounts, setMaterialCounts] = useState<Record<number, number>>({});

  const [coursesLoading, setCoursesLoading] = useState(true);
  const [materialsLoading, setMaterialsLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [googleConnected, setGoogleConnected] = useState(false);

  // Upload modal wired through the shared hook (same as StudentDashboard)
  const studyTools = useParentStudyTools({ selectedChildUserId: null, navigate });

  // ── Data Loading ────────────────────────────────────────────────────────────

  const loadCourses = useCallback(async () => {
    setCoursesLoading(true);
    try {
      const data: CourseItem[] = await coursesApi.list();
      setCourses(data);
    } catch {
      // silently fail — empty state handles it
    } finally {
      setCoursesLoading(false);
    }
  }, []);

  const loadMaterials = useCallback(async (courseId: number | 'all') => {
    setMaterialsLoading(true);
    try {
      let data: CourseContentItem[];
      if (courseId === 'all') {
        data = await courseContentsApi.listAll({ include_archived: false });
      } else {
        data = await courseContentsApi.list(courseId);
      }
      setMaterials(data);

      // Build per-course count map when loading all materials
      if (courseId === 'all') {
        const counts: Record<number, number> = {};
        for (const m of data) {
          counts[m.course_id] = (counts[m.course_id] ?? 0) + 1;
        }
        setMaterialCounts(counts);
      }
    } catch {
      setMaterials([]);
    } finally {
      setMaterialsLoading(false);
    }
  }, []);

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const stats = await studyApi.getQuizStats();
      setQuizStats(stats);
    } catch {
      setQuizStats(null);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const checkGoogleStatus = useCallback(async () => {
    try {
      const status = await googleApi.getStatus();
      setGoogleConnected(status.connected);
    } catch {
      setGoogleConnected(false);
    }
  }, []);

  useEffect(() => {
    loadCourses();
    loadMaterials('all');
    loadStats();
    checkGoogleStatus();
  }, [loadCourses, loadMaterials, loadStats, checkGoogleStatus]);

  // Re-fetch materials when selected course changes
  useEffect(() => {
    loadMaterials(selectedCourseId);
    setTypeFilter('all');
  }, [selectedCourseId, loadMaterials]);

  // ── Derived ─────────────────────────────────────────────────────────────────

  const allCourseIds = useMemo(() => courses.map(c => c.id), [courses]);

  const filteredMaterials = useMemo(() => {
    if (typeFilter === 'all') return materials;
    if (typeFilter === 'raw') return materials.filter(m => isRaw(m));
    return materials.filter(m => m.content_type === typeFilter);
  }, [materials, typeFilter]);

  // Count materials per type for filter pills
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = { all: materials.length };
    for (const m of materials) {
      const t = isRaw(m) ? 'raw' : m.content_type;
      counts[t] = (counts[t] ?? 0) + 1;
    }
    return counts;
  }, [materials]);

  const selectedCourse = useMemo(
    () => (selectedCourseId === 'all' ? null : courses.find(c => c.id === selectedCourseId) ?? null),
    [selectedCourseId, courses]
  );

  // ── Handlers ─────────────────────────────────────────────────────────────────

  const handleSyncGoogle = async () => {
    if (!googleConnected) {
      window.location.href = '/api/google/connect';
      return;
    }
    setSyncing(true);
    setSyncError(null);
    try {
      await googleApi.syncCourses();
      await loadCourses();
      await loadMaterials(selectedCourseId);
    } catch {
      setSyncError('Sync failed — please try again');
    } finally {
      setSyncing(false);
    }
  };

  const handleCreateCourse = () => {
    navigate('/courses?create=true');
  };

  const handleMaterialClick = (item: CourseContentItem) => {
    navigate(getDetailPath(item));
  };

  const handleStudy = (item: CourseContentItem, e: React.MouseEvent) => {
    e.stopPropagation();
    navigate(getDetailPath(item));
  };

  const handleGenerate = (item: CourseContentItem, e: React.MouseEvent) => {
    e.stopPropagation();
    navigate(`${getDetailPath(item)}#guide`);
  };

  const handleUploadForCourse = () => {
    studyTools.setShowStudyModal(true);
  };

  // After modal closes, refresh materials
  const handleModalClose = () => {
    studyTools.resetStudyModal();
    // Reload after short delay to pick up newly uploaded material
    setTimeout(() => loadMaterials(selectedCourseId), 800);
  };

  // ── Render Helpers ───────────────────────────────────────────────────────────

  function renderCourseList() {
    if (coursesLoading) {
      return (
        <div className="study-course-skeleton">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="skeleton" style={{ height: 36, borderRadius: 8, marginBottom: 4 }} />
          ))}
        </div>
      );
    }

    return (
      <>
        {/* "All" pseudo-course */}
        <button
          className={`study-course-item${selectedCourseId === 'all' ? ' active' : ''}`}
          onClick={() => setSelectedCourseId('all')}
          style={selectedCourseId === 'all' ? { borderLeftColor: 'var(--color-accent)' } : {}}
        >
          <span className="study-course-name">All Materials</span>
          <span className="study-course-count">{Object.values(materialCounts).reduce((a, b) => a + b, 0)}</span>
        </button>

        {courses.length === 0 && (
          <p className="study-empty-sidebar-text">No courses yet</p>
        )}

        {courses.map((course) => {
          const color = getCourseColor(course.id, allCourseIds);
          const count = materialCounts[course.id] ?? 0;
          const isActive = selectedCourseId === course.id;
          return (
            <button
              key={course.id}
              className={`study-course-item${isActive ? ' active' : ''}`}
              onClick={() => setSelectedCourseId(course.id)}
              style={isActive ? { borderLeftColor: color } : {}}
            >
              <span
                className="study-course-dot"
                style={{ background: color }}
                aria-hidden="true"
              />
              <span className="study-course-name" title={course.name}>{course.name}</span>
              {count > 0 && <span className="study-course-count">{count}</span>}
            </button>
          );
        })}

        {/* My Materials separator */}
        {courses.length > 0 && (
          <button
            className={`study-course-item study-my-materials${selectedCourseId === 'all' ? '' : ''}`}
            onClick={() => setSelectedCourseId('all')}
          >
            <span className="study-course-name">My Materials</span>
          </button>
        )}
      </>
    );
  }

  function renderProgressSection() {
    if (statsLoading) return <div className="skeleton" style={{ height: 90, borderRadius: 12 }} />;
    if (!quizStats || quizStats.total_attempts === 0) {
      return (
        <div className="study-progress-empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--color-border)" strokeWidth="1.5">
            <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17" strokeWidth="2.5"/>
          </svg>
          <span>Take a quiz to track your progress</span>
        </div>
      );
    }
    const trendIcon = quizStats.recent_trend === 'improving' ? '↑' : quizStats.recent_trend === 'declining' ? '↓' : '→';
    const trendColor = quizStats.recent_trend === 'improving' ? 'var(--color-success)' : quizStats.recent_trend === 'declining' ? 'var(--color-danger)' : 'var(--color-ink-muted)';
    return (
      <div className="study-progress-ring-layout">
        <ProgressRing score={quizStats.average_score} />
        <div className="study-progress-details">
          <div className="study-progress-row">
            <span className="study-progress-detail-label">Best</span>
            <span className="study-progress-detail-value" style={{ color: 'var(--color-success)' }}>{quizStats.best_score}%</span>
          </div>
          <div className="study-progress-row">
            <span className="study-progress-detail-label">Quizzes</span>
            <span className="study-progress-detail-value">{quizStats.total_attempts} <span style={{ fontSize: 11, color: trendColor }}>{trendIcon}</span></span>
          </div>
        </div>
      </div>
    );
  }

  function renderTypeFilters() {
    const filters: { key: ContentTypeFilter; label: string }[] = [
      { key: 'all',         label: `All ${typeCounts.all > 0 ? typeCounts.all : ''}` },
      { key: 'study_guide', label: `Study Guides${typeCounts.study_guide ? ` ${typeCounts.study_guide}` : ''}` },
      { key: 'quiz',        label: `Quizzes${typeCounts.quiz ? ` ${typeCounts.quiz}` : ''}` },
      { key: 'flashcards',  label: `Flashcards${typeCounts.flashcards ? ` ${typeCounts.flashcards}` : ''}` },
    ];

    // Only show filters that have items (always show 'all')
    const visibleFilters = filters.filter(f => f.key === 'all' || (typeCounts[f.key] ?? 0) > 0);

    return (
      <div className="study-type-filters" role="group" aria-label="Filter by type">
        {visibleFilters.map(f => (
          <button
            key={f.key}
            className={`study-filter-pill${typeFilter === f.key ? ' active' : ''}`}
            onClick={() => setTypeFilter(f.key)}
          >
            {f.label.trim()}
          </button>
        ))}
      </div>
    );
  }

  function renderMaterialCard(item: CourseContentItem) {
    const raw = isRaw(item);

    return (
      <div
        key={item.id}
        className="study-material-card"
        data-type={item.content_type || 'raw'}
        onClick={() => handleMaterialClick(item)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleMaterialClick(item); } }}
        aria-label={`${item.title} — ${getContentTypeLabel(item.content_type)}`}
      >
        <span className="study-material-icon">
          <ContentTypeIcon type={item.content_type} size={20} />
        </span>
        <div className="study-material-info">
          <span className="study-material-title">{item.title}</span>
          <span className="study-material-meta">
            <span className={`study-type-badge study-type-${item.content_type || 'raw'}`}>
              {getContentTypeLabel(item.content_type)}
            </span>
            {item.course_name && selectedCourseId === 'all' && (
              <span className="study-material-course">{item.course_name}</span>
            )}
          </span>
        </div>
        <span className="study-material-date">{formatDate(item.created_at)}</span>
        <div className="study-material-actions" onClick={e => e.stopPropagation()}>
          <button
            className="study-action-btn primary"
            onClick={(e) => handleStudy(item, e)}
            title="Open material"
          >
            Study
          </button>
          {raw && (
            <button
              className="study-action-btn secondary"
              onClick={(e) => handleGenerate(item, e)}
              title="Generate AI study tools from this document"
            >
              Generate
            </button>
          )}
        </div>
      </div>
    );
  }

  function renderMaterialsPanel() {
    const panelTitle = selectedCourse
      ? `Materials — ${selectedCourse.name}`
      : 'All Materials';

    return (
      <div className="study-materials-panel">
        <div className="study-materials-header">
          <h2 className="study-materials-title">{panelTitle}</h2>
        </div>

        {/* Continue studying shortcut */}
        {selectedCourseId === 'all' && typeFilter === 'all' && filteredMaterials.length > 0 && (
          <div className="study-continue-row">
            <span className="study-continue-label">Continue</span>
            <div className="study-continue-items">
              {filteredMaterials.slice(0, 2).map(item => (
                <button
                  key={item.id}
                  className="study-continue-chip"
                  onClick={() => navigate(getDetailPath(item))}
                >
                  <ContentTypeIcon type={item.content_type} size={14} />
                  <span>{item.title.length > 20 ? item.title.slice(0, 20) + '\u2026' : item.title}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {renderTypeFilters()}

        {materialsLoading ? (
          <div className="study-materials-loading">
            {[1, 2, 3].map(i => (
              <div key={i} className="skeleton" style={{ height: 76, borderRadius: 10, marginBottom: 8 }} />
            ))}
          </div>
        ) : filteredMaterials.length === 0 ? (
          <div className="study-materials-empty">
            <span className="study-empty-icon">{'\u{1F4DA}'}</span>
            <p className="study-empty-title">
              {materials.length === 0
                ? selectedCourse
                  ? `No materials for ${selectedCourse.name} yet`
                  : 'No materials yet'
                : `No ${typeFilter !== 'all' ? typeFilter.replace('_', ' ') + 's' : 'materials'} found`}
            </p>
            <p className="study-empty-desc">
              {materials.length === 0
                ? 'Upload a document to get started — then generate study guides, quizzes, and flashcards.'
                : 'Try a different filter or upload a new document.'}
            </p>
            <button
              className="study-empty-cta"
              onClick={handleUploadForCourse}
            >
              + Upload Document
            </button>
          </div>
        ) : (
          <div className="study-materials-list">
            {filteredMaterials.map(item => renderMaterialCard(item))}
          </div>
        )}

        {/* Bottom upload CTA */}
        {!materialsLoading && filteredMaterials.length > 0 && (
          <div className="study-upload-cta-row">
            <button
              className="study-upload-cta-btn"
              onClick={handleUploadForCourse}
            >
              + Upload{selectedCourse ? ` for ${selectedCourse.name}` : ' Document'}
            </button>
          </div>
        )}
      </div>
    );
  }

  // ── Main Render ───────────────────────────────────────────────────────────────

  return (
    <DashboardLayout>
      <div className="study-page">

        {/* ── Page Header ─────────────────────────────────── */}
        <div className="study-page-header">
          <div className="study-page-header-left">
            <h1 className="study-page-title">Study</h1>
            <p className="study-page-subtitle">
              {user?.full_name ? `Your learning hub, ${user.full_name.split(' ')[0]}` : 'Your learning hub'}
            </p>
          </div>
          <button
            className="study-upload-btn"
            onClick={handleUploadForCourse}
          >
            <span aria-hidden="true">+</span> Upload Material
          </button>
        </div>

        {syncError && (
          <div className="study-sync-error" role="alert">
            {syncError}
            <button onClick={() => setSyncError(null)} className="study-sync-error-dismiss">&times;</button>
          </div>
        )}

        {/* ── Two-Column Layout ────────────────────────────── */}
        <div className="study-layout">

          {/* LEFT: Courses Panel */}
          <aside className="study-courses-panel" aria-label="Classes">
            <div className="study-panel-section">
              <h2 className="study-panel-label">CLASSES</h2>
              <div className="study-course-list" role="listbox" aria-label="Select a class">
                {renderCourseList()}
              </div>
            </div>

            <div className="study-panel-actions">
              <button
                className="study-sidebar-btn"
                onClick={handleCreateCourse}
                title="Create a new course"
              >
                + New Course
              </button>
              <button
                className="study-sidebar-btn"
                onClick={handleSyncGoogle}
                disabled={syncing}
                title={googleConnected ? 'Sync with Google Classroom' : 'Connect Google Classroom'}
              >
                {syncing ? (
                  <><span className="study-spin" aria-hidden="true" /> Syncing...</>
                ) : googleConnected ? (
                  <>{'\u{1F504}'} Sync Google</>
                ) : (
                  <>{'\u{1F4E1}'} Connect Google</>
                )}
              </button>
            </div>

            {/* My Progress */}
            <div className="study-panel-section study-progress">
              <h2 className="study-panel-label">MY PROGRESS</h2>
              {renderProgressSection()}
              {quizStats && quizStats.total_attempts > 0 && (
                <button
                  className="study-progress-history-btn"
                  onClick={() => navigate('/quiz-history')}
                >
                  View History
                </button>
              )}
            </div>
          </aside>

          {/* RIGHT: Materials Panel */}
          <main
            className="study-materials-wrapper"
            style={selectedCourse
              ? { '--course-accent': getCourseColor(selectedCourse.id, allCourseIds) } as React.CSSProperties
              : {}
            }
            aria-label="Study materials"
          >
            {renderMaterialsPanel()}
          </main>

        </div>
      </div>

      {/* ── Upload Modal ──────────────────────────────────────────── */}
      <CreateStudyMaterialModal
        open={studyTools.showStudyModal}
        onClose={handleModalClose}
        onGenerate={studyTools.handleGenerateFromModal}
        isGenerating={studyTools.isGenerating}
        courses={courses.map(c => ({ id: c.id, name: c.name }))}
        selectedCourseId={selectedCourseId !== 'all' ? selectedCourseId : undefined}
        onCourseChange={(id) => {
          if (id !== '') setSelectedCourseId(id);
        }}
        duplicateCheck={studyTools.duplicateCheck}
        onViewExisting={() => {
          const guide = studyTools.duplicateCheck?.existing_guide;
          if (guide) {
            studyTools.resetStudyModal();
            navigate(
              guide.guide_type === 'quiz'
                ? `/study/quiz/${guide.id}`
                : guide.guide_type === 'flashcards'
                ? `/study/flashcards/${guide.id}`
                : `/study/guide/${guide.id}`
            );
          }
        }}
        onRegenerate={() =>
          studyTools.handleGenerateFromModal({
            title: studyTools.studyModalInitialTitle,
            content: studyTools.studyModalInitialContent,
            types: ['study_guide'],
            mode: 'text',
          })
        }
        onDismissDuplicate={() => studyTools.setDuplicateCheck(null)}
        showParentNote={false}
      />

      {/* ── Background generation banner ─────────────────────────── */}
      {studyTools.backgroundGeneration && (
        <div className={`sd-generation-banner ${studyTools.backgroundGeneration.status}`}>
          {studyTools.backgroundGeneration.status === 'generating' && (
            <span>
              <span className="sd-gen-spinner" />
              {' '}Generating {studyTools.backgroundGeneration.type}...
            </span>
          )}
          {studyTools.backgroundGeneration.status === 'success' && (
            <>
              <span>{studyTools.backgroundGeneration.type} ready!</span>
              <button
                className="sd-gen-view-btn"
                onClick={() => {
                  navigate('/course-materials');
                  studyTools.dismissBackgroundGeneration();
                }}
              >
                View
              </button>
              <button className="sd-gen-dismiss-btn" onClick={studyTools.dismissBackgroundGeneration}>&times;</button>
            </>
          )}
          {studyTools.backgroundGeneration.status === 'error' && (
            <>
              <span>Failed to generate {studyTools.backgroundGeneration.type}</span>
              <button className="sd-gen-dismiss-btn" onClick={studyTools.dismissBackgroundGeneration}>&times;</button>
            </>
          )}
        </div>
      )}
    </DashboardLayout>
  );
}

export default StudyPage;
