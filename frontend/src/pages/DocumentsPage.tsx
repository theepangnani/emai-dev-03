import { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { documentsApi } from '../api/documents';
import type { DocumentItem } from '../api/documents';
import { parentApi } from '../api/client';
import type { ChildSummary } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { CHILD_COLORS } from '../components/parent/useParentDashboard';
import { COURSE_COLORS } from '../components/calendar/types';
import EmptyState from '../components/EmptyState';
import './DocumentsPage.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

type DocType = 'all' | 'document' | 'study_guide' | 'quiz' | 'flashcards';

const TYPE_TABS: { value: DocType; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'document', label: 'Documents' },
  { value: 'study_guide', label: 'Study Guides' },
  { value: 'quiz', label: 'Quizzes' },
  { value: 'flashcards', label: 'Flashcards' },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function typeIcon(type: string): React.ReactNode {
  switch (type) {
    case 'document':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
        </svg>
      );
    case 'study_guide':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        </svg>
      );
    case 'quiz':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      );
    case 'flashcards':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="2" y="5" width="20" height="14" rx="2" />
          <line x1="2" y1="10" x2="22" y2="10" />
        </svg>
      );
    default:
      return null;
  }
}

function typeLabel(type: string): string {
  switch (type) {
    case 'document': return 'Document';
    case 'study_guide': return 'Study Guide';
    case 'quiz': return 'Quiz';
    case 'flashcards': return 'Flashcards';
    default: return type;
  }
}

// Stable color assignment by course_id
function courseColor(courseId: number, knownCourseIds: number[]): string {
  const index = knownCourseIds.indexOf(courseId);
  return COURSE_COLORS[(index >= 0 ? index : courseId) % COURSE_COLORS.length];
}

// ---------------------------------------------------------------------------
// Skeleton loader
// ---------------------------------------------------------------------------

function DocumentCardSkeleton() {
  return (
    <div className="doc-card doc-card--skeleton" aria-hidden="true">
      <div className="doc-card__header">
        <div className="doc-card__course-badge skeleton-block" style={{ width: '80px', height: '20px' }} />
        <div className="skeleton-block" style={{ width: '60px', height: '20px' }} />
      </div>
      <div className="skeleton-block doc-card__title-skeleton" />
      <div className="doc-card__footer">
        <div className="skeleton-block" style={{ width: '90px', height: '14px' }} />
        <div className="skeleton-block" style={{ width: '70px', height: '28px', borderRadius: '6px' }} />
      </div>
    </div>
  );
}

function SkeletonGrid() {
  return (
    <div className="doc-grid">
      {Array.from({ length: 8 }).map((_, i) => (
        <DocumentCardSkeleton key={i} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Document Card
// ---------------------------------------------------------------------------

interface DocumentCardProps {
  item: DocumentItem;
  onOpen: (item: DocumentItem) => void;
  courseColor: string;
}

function DocumentCard({ item, onOpen, courseColor: color }: DocumentCardProps) {
  return (
    <div className="doc-card" onClick={() => onOpen(item)} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(item); } }}>
      <div className="doc-card__header">
        <span className="doc-card__course-badge" style={{ backgroundColor: color + '22', color }}>
          {item.course_name}
        </span>
        <span className={`doc-card__type-chip doc-card__type-chip--${item.type}`}>
          {typeIcon(item.type)}
          {typeLabel(item.type)}
        </span>
      </div>

      <h3 className="doc-card__title">{item.title}</h3>

      {item.child_name && (
        <p className="doc-card__child">{item.child_name}</p>
      )}

      <div className="doc-card__ai-flags">
        {item.has_study_guide && (
          <span className="doc-card__ai-flag" title="Has Study Guide">SG</span>
        )}
        {item.has_quiz && (
          <span className="doc-card__ai-flag" title="Has Quiz">Q</span>
        )}
        {item.has_flashcards && (
          <span className="doc-card__ai-flag" title="Has Flashcards">FC</span>
        )}
      </div>

      <div className="doc-card__footer">
        <span className="doc-card__date">{formatDate(item.created_at)}</span>
        <button className="doc-card__open-btn" onClick={(e) => { e.stopPropagation(); onOpen(item); }}>
          Open
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function DocumentsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const isParent = user?.role === 'parent';
  const isTeacher = user?.role === 'teacher';

  // Filters
  const [search, setSearch] = useState(() => searchParams.get('q') || '');
  const [debouncedSearch, setDebouncedSearch] = useState(search);
  const [activeType, setActiveType] = useState<DocType>(() => {
    const t = searchParams.get('type') as DocType | null;
    return t && ['document', 'study_guide', 'quiz', 'flashcards'].includes(t) ? t : 'all';
  });
  const [selectedChildId, setSelectedChildId] = useState<number | null>(() => {
    const stored = searchParams.get('child') || localStorage.getItem('last_selected_child');
    return stored ? Number(stored) : null;
  });
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(() => {
    const c = searchParams.get('course');
    return c ? Number(c) : null;
  });

  // Children list (parents only)
  const [children, setChildren] = useState<ChildSummary[]>([]);

  // Debounce search input — 300ms
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [search]);

  // Load children for parents
  useEffect(() => {
    if (isParent) {
      parentApi.getChildren().then((kids) => {
        setChildren(kids);
        // Auto-select first child if none stored
        if (!selectedChildId && kids.length === 1) {
          const first = kids[0];
          setSelectedChildId(first.student_id);
          try { localStorage.setItem('last_selected_child', String(first.student_id)); } catch { /* ignore */ }
        }
      }).catch(() => {});
    }
  }, [isParent]);

  // Sync URL params
  useEffect(() => {
    const params: Record<string, string> = {};
    if (debouncedSearch) params.q = debouncedSearch;
    if (activeType !== 'all') params.type = activeType;
    if (selectedChildId) params.child = String(selectedChildId);
    if (selectedCourseId) params.course = String(selectedCourseId);
    setSearchParams(params, { replace: true });
  }, [debouncedSearch, activeType, selectedChildId, selectedCourseId]);

  // Query params for the API
  const queryParams = useMemo(() => ({
    search: debouncedSearch || undefined,
    type: activeType !== 'all' ? activeType : undefined,
    child_id: isParent && selectedChildId ? selectedChildId : undefined,
    course_id: selectedCourseId || undefined,
    limit: 200,
    offset: 0,
  }), [debouncedSearch, activeType, selectedChildId, selectedCourseId, isParent]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['documents', queryParams],
    queryFn: () => documentsApi.list(queryParams),
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  // Build sorted, unique list of course IDs for color assignment
  const knownCourseIds = useMemo(() => {
    const ids = [...new Set(items.map((i) => i.course_id))].sort((a, b) => a - b);
    return ids;
  }, [items]);

  // Unique courses for the filter dropdown
  const courseOptions = useMemo(() => {
    const seen = new Map<number, string>();
    for (const item of items) {
      if (!seen.has(item.course_id)) seen.set(item.course_id, item.course_name);
    }
    return Array.from(seen.entries()).map(([id, name]) => ({ id, name }));
  }, [items]);

  const handleOpen = (item: DocumentItem) => {
    if (item.type === 'document') {
      navigate(`/course-materials/${item.id}`);
    } else if (item.type === 'study_guide') {
      navigate(`/study/guide/${item.id}`);
    } else if (item.type === 'quiz') {
      navigate(`/study/quiz/${item.id}`);
    } else if (item.type === 'flashcards') {
      navigate(`/study/flashcards/${item.id}`);
    }
  };

  const handleChildSelect = (studentId: number | null) => {
    setSelectedChildId(studentId);
    if (studentId) {
      try { localStorage.setItem('last_selected_child', String(studentId)); } catch { /* ignore */ }
    }
  };

  return (
    <DashboardLayout>
      <div className="documents-page">
        <div className="documents-page__header">
          <h1 className="documents-page__title">Documents</h1>
          {total > 0 && (
            <span className="documents-page__count">{total} item{total !== 1 ? 's' : ''}</span>
          )}
        </div>

        {/* Child selector pills — parents only */}
        {isParent && children.length > 0 && (
          <div className="documents-child-selector" role="group" aria-label="Filter by child">
            <button
              className={`child-pill${selectedChildId === null ? ' child-pill--active' : ''}`}
              onClick={() => handleChildSelect(null)}
            >
              All Children
            </button>
            {children.map((child, idx) => {
              const color = CHILD_COLORS[idx % CHILD_COLORS.length];
              const isActive = selectedChildId === child.student_id;
              return (
                <button
                  key={child.student_id}
                  className={`child-pill${isActive ? ' child-pill--active' : ''}`}
                  style={isActive ? { borderColor: color, backgroundColor: color, color: '#fff' } : { borderColor: color + '66' }}
                  onClick={() => handleChildSelect(child.student_id)}
                >
                  <span className="child-pill__dot" style={{ backgroundColor: color }} />
                  {child.full_name}
                </button>
              );
            })}
          </div>
        )}

        {/* Filter bar */}
        <div className="documents-filter-bar">
          <div className="documents-search-wrap">
            <svg className="documents-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              className="documents-search"
              type="search"
              placeholder="Search documents..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search documents"
            />
          </div>

          <select
            className="documents-course-select"
            value={selectedCourseId ?? ''}
            onChange={(e) => setSelectedCourseId(e.target.value ? Number(e.target.value) : null)}
            aria-label="Filter by course"
          >
            <option value="">All Courses</option>
            {courseOptions.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        {/* Type tabs */}
        <div className="documents-type-tabs" role="tablist" aria-label="Filter by type">
          {TYPE_TABS.map((tab) => (
            <button
              key={tab.value}
              role="tab"
              aria-selected={activeType === tab.value}
              className={`doc-type-tab${activeType === tab.value ? ' doc-type-tab--active' : ''}`}
              onClick={() => setActiveType(tab.value)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        {isLoading && <SkeletonGrid />}

        {isError && (
          <div className="documents-error" role="alert">
            Failed to load documents. Please try again.
          </div>
        )}

        {!isLoading && !isError && items.length === 0 && (
          <EmptyState
            title="No documents found"
            description={
              debouncedSearch || activeType !== 'all'
                ? 'Try clearing your filters or search term.'
                : isParent
                  ? 'No course materials have been uploaded for your children yet.'
                  : isTeacher
                    ? 'No course materials have been added to your courses yet.'
                    : 'No course materials have been added to your courses yet.'
            }
          />
        )}

        {!isLoading && !isError && items.length > 0 && (
          <div className="doc-grid">
            {items.map((item) => (
              <DocumentCard
                key={`${item.type}-${item.id}`}
                item={item}
                onOpen={handleOpen}
                courseColor={courseColor(item.course_id, knownCourseIds)}
              />
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
