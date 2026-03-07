import { useState, useCallback, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { activityApi, type ActivityItem } from '../../api/activity';
import { CHILD_COLORS } from './useParentDashboard';
import './RecentActivityPanel.css';

/* ── Props ──────────────────────────────────────────────── */

interface RecentActivityPanelProps {
  selectedChild: number | null; // null = all children
  navigate: (path: string) => void;
}

/* ── Relative time helper ───────────────────────────────── */

export function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  const diffHr = Math.floor(diffMs / 3_600_000);
  const diffDay = Math.floor(diffMs / 86_400_000);

  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 2) return 'yesterday';
  if (diffDay < 7) return `${diffDay}d ago`;

  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[date.getMonth()]} ${date.getDate()}`;
}

/* ── Icon mapping ───────────────────────────────────────── */

const ICON_CONFIG: Record<ActivityItem['activity_type'], { bg: string; icon: ReactNode }> = {
  course_created: {
    bg: '#4A90D9',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      </svg>
    ),
  },
  task_created: {
    bg: '#34C759',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
        <line x1="12" y1="8" x2="12" y2="16" />
        <line x1="8" y1="12" x2="16" y2="12" />
      </svg>
    ),
  },
  material_uploaded: {
    bg: '#8B5CF6',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
  },
  task_completed: {
    bg: '#6B7280',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
        <polyline points="22 4 12 14.01 9 11.01" />
      </svg>
    ),
  },
  message_received: {
    bg: '#F59E0B',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
      </svg>
    ),
  },
  notification_received: {
    bg: '#EF4444',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
    ),
  },
};

/* ── Navigation mapping ─────────────────────────────────── */

function getNavigationPath(item: ActivityItem): string | null {
  switch (item.activity_type) {
    case 'course_created': return '/courses';
    case 'task_created': return `/tasks/${item.resource_id}`;
    case 'material_uploaded': return `/course-materials/${item.resource_id}`;
    case 'task_completed': return `/tasks/${item.resource_id}`;
    case 'message_received': return '/messages';
    case 'notification_received': return null;
    default: return null;
  }
}

/* ── Component ──────────────────────────────────────────── */

export function RecentActivityPanel({ selectedChild, navigate }: RecentActivityPanelProps) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('pd-activity-collapsed');
      if (saved !== null) return saved === '1';
    } catch { /* ignore */ }
    return true; // collapsed by default
  });

  const toggleCollapsed = useCallback(() => {
    setCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem('pd-activity-collapsed', next ? '1' : '0'); } catch { /* ignore */ }
      return next;
    });
  }, []);

  const { data: activities, isLoading, isError, refetch } = useQuery({
    queryKey: ['activity', 'recent', selectedChild],
    queryFn: () => activityApi.getRecent(selectedChild ?? undefined),
  });

  const handleRowClick = useCallback((item: ActivityItem) => {
    const path = getNavigationPath(item);
    if (path) navigate(path);
  }, [navigate]);

  return (
    <section className="pd-activity-panel" aria-label="Recent activity">
      {/* Header */}
      <div
        className="pd-activity-header"
        onClick={toggleCollapsed}
        role="button"
        tabIndex={0}
        aria-expanded={!collapsed}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleCollapsed(); } }}
      >
        <div className="pd-activity-header-left">
          <h3 className="pd-activity-heading">Recent Activity</h3>
          {activities && activities.length > 0 && (
            <span className="pd-activity-count-badge">{activities.length}</span>
          )}
        </div>
        <svg
          className={`pd-activity-chevron${collapsed ? ' pd-activity-collapsed' : ''}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {/* Body */}
      <div className={`pd-activity-body${collapsed ? ' pd-activity-body-collapsed' : ''}`} data-testid="activity-body">
        <div className="pd-activity-list">
          {/* Loading skeleton */}
          {isLoading && (
            <>
              {[0, 1, 2].map(i => (
                <div key={i} className="pd-activity-skeleton-row" data-testid="activity-skeleton">
                  <div className="pd-activity-skeleton-circle" />
                  <div className="pd-activity-skeleton-lines">
                    <div className="pd-activity-skeleton-line" />
                    <div className="pd-activity-skeleton-line" />
                  </div>
                </div>
              ))}
            </>
          )}

          {/* Error state */}
          {isError && !isLoading && (
            <div className="pd-activity-error">
              <span>Unable to load activity</span>
              <button className="pd-activity-retry-btn" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          )}

          {/* Empty state */}
          {!isLoading && !isError && activities && activities.length === 0 && (
            <div className="pd-activity-empty">No recent activity</div>
          )}

          {/* Activity rows */}
          {!isLoading && !isError && activities && activities.map((item, index) => {
            const config = ICON_CONFIG[item.activity_type];
            const path = getNavigationPath(item);
            const isClickable = path !== null;

            return (
              <div
                key={`${item.activity_type}-${item.resource_id}-${index}`}
                className={`pd-activity-row${!isClickable ? ' pd-activity-row-no-click' : ''}`}
                onClick={() => isClickable && handleRowClick(item)}
                role={isClickable ? 'link' : undefined}
                data-testid="activity-row"
              >
                <div
                  className="pd-activity-icon-circle"
                  style={{ background: config?.bg ?? '#6B7280' }}
                  data-testid={`activity-icon-${item.activity_type}`}
                >
                  {config?.icon}
                </div>
                <div className="pd-activity-content">
                  <div className="pd-activity-title-row">
                    <span className="pd-activity-title">{item.title}</span>
                    <span className="pd-activity-time">{formatRelativeTime(item.created_at)}</span>
                  </div>
                  <div className="pd-activity-desc-row">
                    <span className="pd-activity-description">{item.description}</span>
                    {!selectedChild && item.student_name && (
                      <span
                        className="pd-activity-child-badge"
                        style={{ background: CHILD_COLORS[index % CHILD_COLORS.length] }}
                        data-testid="activity-child-badge"
                      >
                        {item.student_name}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export default RecentActivityPanel;
