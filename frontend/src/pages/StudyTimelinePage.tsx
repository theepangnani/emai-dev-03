import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import { PageSkeleton } from '../components/Skeleton';
import { activityApi, type TimelineEntry } from '../api/activity';
import { coursesApi } from '../api/courses';
import { ReportBugLink } from '../components/ReportBugLink';
import './StudyTimelinePage.css';

const TYPE_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  upload: { label: 'Upload', color: '#2563eb', icon: 'U' },
  study_guide: { label: 'Study Guide', color: '#10b981', icon: 'S' },
  quiz: { label: 'Quiz', color: '#7c3aed', icon: 'Q' },
  badge: { label: 'Badge', color: '#d97706', icon: 'B' },
  level_up: { label: 'Level Up', color: '#ea580c', icon: 'L' },
};

const DAYS_OPTIONS = [
  { value: 7, label: 'Last 7 days' },
  { value: 14, label: 'Last 14 days' },
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
  { value: 365, label: 'Last year' },
];

const PAGE_SIZE = 50;

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

function groupByDate(items: TimelineEntry[]): Map<string, TimelineEntry[]> {
  const groups = new Map<string, TimelineEntry[]>();
  for (const item of items) {
    const dateKey = new Date(item.date).toLocaleDateString();
    const existing = groups.get(dateKey) || [];
    existing.push(item);
    groups.set(dateKey, existing);
  }
  return groups;
}

export function StudyTimelinePage() {
  const [days, setDays] = useState(30);
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [courseFilter, setCourseFilter] = useState<number | ''>('');
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const { data, isLoading, error } = useQuery({
    queryKey: ['study-timeline', days, typeFilter, courseFilter],
    queryFn: () =>
      activityApi.getTimeline({
        days,
        type: typeFilter || undefined,
        course_id: courseFilter || undefined,
        limit: 500,
        offset: 0,
      }),
  });

  const { data: courses = [] } = useQuery({
    queryKey: ['courses-list'],
    queryFn: () => coursesApi.list(),
  });

  const handleLoadMore = useCallback(() => {
    setVisibleCount((c) => c + PAGE_SIZE);
  }, []);

  const items = data?.items ?? [];
  const visible = items.slice(0, visibleCount);
  const hasMore = visibleCount < items.length;
  const grouped = groupByDate(visible);

  return (
    <DashboardLayout>
      <div className="st-page">
        <PageNav
          items={[
            { label: 'Home', to: '/dashboard' },
            { label: 'Study Timeline' },
          ]}
        />

        <h2 className="st-title">Study Timeline</h2>

        {/* Filters */}
        <div className="st-filters">
          <select
            className="st-select"
            value={days}
            onChange={(e) => {
              setDays(Number(e.target.value));
              setVisibleCount(PAGE_SIZE);
            }}
            aria-label="Date range"
          >
            {DAYS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <select
            className="st-select"
            value={courseFilter}
            onChange={(e) => {
              setCourseFilter(e.target.value ? Number(e.target.value) : '');
              setVisibleCount(PAGE_SIZE);
            }}
            aria-label="Filter by course"
          >
            <option value="">All Courses</option>
            {courses.map((c: { id: number; name: string }) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>

          <div className="st-type-chips" role="group" aria-label="Filter by activity type">
            <button
              className={`st-chip${!typeFilter ? ' st-chip-active' : ''}`}
              onClick={() => {
                setTypeFilter('');
                setVisibleCount(PAGE_SIZE);
              }}
            >
              All
            </button>
            {Object.entries(TYPE_CONFIG).map(([type, cfg]) => (
              <button
                key={type}
                className={`st-chip${typeFilter === type ? ' st-chip-active' : ''}`}
                style={
                  typeFilter === type
                    ? { background: cfg.color, borderColor: cfg.color, color: '#fff' }
                    : {}
                }
                onClick={() => {
                  setTypeFilter(typeFilter === type ? '' : type);
                  setVisibleCount(PAGE_SIZE);
                }}
              >
                {cfg.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        {isLoading && <PageSkeleton />}
        {error && (
          <div className="st-error">Failed to load timeline. Please try again.<ReportBugLink errorMessage="Failed to load timeline" /></div>
        )}

        {!isLoading && !error && items.length === 0 && (
          <div className="st-empty">
            <h3>No activity yet</h3>
            <p>Start studying to see your activity timeline here!</p>
          </div>
        )}

        {!isLoading && !error && items.length > 0 && (
          <div className="st-timeline">
            {Array.from(grouped.entries()).map(([dateKey, entries]) => (
              <div key={dateKey} className="st-day-group">
                <div className="st-day-label">{formatDate(entries[0].date)}</div>
                <div className="st-day-entries">
                  {entries.map((entry, idx) => {
                    const cfg = TYPE_CONFIG[entry.type] || TYPE_CONFIG.upload;
                    return (
                      <div key={`${entry.type}-${entry.date}-${idx}`} className="st-entry">
                        <div className="st-entry-line" />
                        <div
                          className="st-entry-icon"
                          style={{ background: cfg.color }}
                          aria-label={cfg.label}
                        >
                          {cfg.icon}
                        </div>
                        <div className="st-entry-body">
                          <div className="st-entry-top">
                            <span className="st-entry-title">{entry.title}</span>
                            <span className="st-entry-time">{formatTime(entry.date)}</span>
                          </div>
                          <div className="st-entry-bottom">
                            {entry.course && (
                              <span className="st-entry-course">{entry.course}</span>
                            )}
                            {entry.xp != null && (
                              <span className="st-entry-xp">+{entry.xp} XP</span>
                            )}
                            {entry.score != null && (
                              <span className="st-entry-score">{entry.score}%</span>
                            )}
                            <span
                              className="st-entry-type-label"
                              style={{ color: cfg.color }}
                            >
                              {cfg.label}
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}

            {hasMore && (
              <button className="st-load-more" onClick={handleLoadMore} type="button">
                Load more ({items.length - visibleCount} remaining)
              </button>
            )}

            <div className="st-count">
              Showing {visible.length} of {data?.total ?? 0} activities
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

export default StudyTimelinePage;
