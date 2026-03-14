import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { DashboardLayout } from '../../components/DashboardLayout';
import { activityApi, type ActivityItem } from '../../api/activity';
import { parentApi, type ChildSummary } from '../../api/parent';
import { CHILD_COLORS } from '../../components/parent/useParentDashboard';
import { formatRelativeTime } from '../../components/parent/RecentActivityPanel';
import './ActivityHistoryPage.css';

const ACTIVITY_TYPE_LABELS: Record<ActivityItem['activity_type'], string> = {
  course_created: 'Courses',
  task_created: 'Tasks',
  material_uploaded: 'Materials',
  task_completed: 'Completed',
  message_received: 'Messages',
  notification_received: 'Notifications',
  study_guide_generated: 'Study Guides',
};

const ICON_BG: Record<ActivityItem['activity_type'], string> = {
  course_created: '#4A90D9',
  task_created: '#34C759',
  material_uploaded: '#8B5CF6',
  task_completed: '#6B7280',
  message_received: '#F59E0B',
  notification_received: '#EF4444',
  study_guide_generated: '#10B981',
};

function getNavPath(item: ActivityItem): string | null {
  switch (item.activity_type) {
    case 'course_created': return '/courses';
    case 'task_created': return `/tasks/${item.resource_id}`;
    case 'material_uploaded': return `/course-materials/${item.resource_id}`;
    case 'task_completed': return `/tasks/${item.resource_id}`;
    case 'message_received': return '/messages';
    case 'study_guide_generated': return `/course-materials/${item.resource_id}?tab=guide`;
    default: return null;
  }
}

const PAGE_SIZE = 20;

export function ActivityHistoryPage() {
  const navigate = useNavigate();
  const [selectedChild, setSelectedChild] = useState<number | null>(null);
  const [selectedType, setSelectedType] = useState<ActivityItem['activity_type'] | 'all'>('all');
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const { data: children = [] } = useQuery<ChildSummary[]>({
    queryKey: ['parent', 'children'],
    queryFn: () => parentApi.getChildren(),
  });

  const { data: rawActivities = [], isLoading, isError } = useQuery<ActivityItem[]>({
    queryKey: ['activity', 'all', selectedChild],
    queryFn: () => activityApi.getRecent(selectedChild ?? undefined, 100),
  });

  const filtered = useMemo(() => {
    if (selectedType === 'all') return rawActivities;
    return rawActivities.filter(a => a.activity_type === selectedType);
  }, [rawActivities, selectedType]);

  const visible = filtered.slice(0, visibleCount);
  const hasMore = visibleCount < filtered.length;

  return (
    <DashboardLayout>
      <div className="ah-page">
        <div className="ah-header">
          <button className="ah-back-btn" onClick={() => navigate('/dashboard')} aria-label="Back to dashboard">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Dashboard
          </button>
          <h1 className="ah-title">Activity History</h1>
        </div>

        {/* Child filter chips */}
        {children.length > 1 && (
          <div className="ah-filter-row" role="group" aria-label="Filter by child">
            <button
              className={`ah-chip${selectedChild === null ? ' ah-chip-active' : ''}`}
              onClick={() => { setSelectedChild(null); setVisibleCount(PAGE_SIZE); }}
            >
              All Children
            </button>
            {children.map((child, i) => (
              <button
                key={child.student_id}
                className={`ah-chip${selectedChild === child.student_id ? ' ah-chip-active' : ''}`}
                style={selectedChild === child.student_id ? { background: CHILD_COLORS[i % CHILD_COLORS.length], borderColor: CHILD_COLORS[i % CHILD_COLORS.length], color: '#fff' } : {}}
                onClick={() => { setSelectedChild(child.student_id); setVisibleCount(PAGE_SIZE); }}
              >
                {child.full_name}
              </button>
            ))}
          </div>
        )}

        {/* Type filter chips */}
        <div className="ah-filter-row" role="group" aria-label="Filter by activity type">
          <button
            className={`ah-chip${selectedType === 'all' ? ' ah-chip-active' : ''}`}
            onClick={() => { setSelectedType('all'); setVisibleCount(PAGE_SIZE); }}
          >
            All Types
          </button>
          {(Object.entries(ACTIVITY_TYPE_LABELS) as [ActivityItem['activity_type'], string][]).map(([type, label]) => (
            <button
              key={type}
              className={`ah-chip${selectedType === type ? ' ah-chip-active' : ''}`}
              style={selectedType === type ? { background: ICON_BG[type], borderColor: ICON_BG[type], color: '#fff' } : {}}
              onClick={() => { setSelectedType(type); setVisibleCount(PAGE_SIZE); }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Activity list */}
        <div className="ah-list">
          {isLoading && (
            <div className="ah-state-msg">Loading activity...</div>
          )}
          {isError && (
            <div className="ah-state-msg ah-error">Unable to load activity history.</div>
          )}
          {!isLoading && !isError && filtered.length === 0 && (
            <div className="ah-state-msg">No activity found.</div>
          )}
          {!isLoading && !isError && visible.map((item, index) => {
            const path = getNavPath(item);
            const isClickable = path !== null;
            return (
              <div
                key={`${item.activity_type}-${item.resource_id}-${index}`}
                className={`ah-row${isClickable ? ' ah-row-clickable' : ''}`}
                onClick={() => isClickable && path && navigate(path)}
                role={isClickable ? 'link' : undefined}
              >
                <div className="ah-icon-circle" style={{ background: ICON_BG[item.activity_type] }} />
                <div className="ah-row-content">
                  <div className="ah-row-top">
                    <span className="ah-row-title">{item.title}</span>
                    <span className="ah-row-time">{formatRelativeTime(item.created_at)}</span>
                  </div>
                  <div className="ah-row-bottom">
                    <span className="ah-row-desc">{item.description}</span>
                    {item.student_name && !selectedChild && (
                      <span className="ah-child-badge" style={{ background: CHILD_COLORS[index % CHILD_COLORS.length] }}>
                        {item.student_name}
                      </span>
                    )}
                    <span className="ah-type-label">{ACTIVITY_TYPE_LABELS[item.activity_type]}</span>
                  </div>
                </div>
              </div>
            );
          })}
          {hasMore && (
            <button className="ah-load-more-btn" onClick={() => setVisibleCount(c => c + PAGE_SIZE)}>
              Load more ({filtered.length - visibleCount} remaining)
            </button>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

export default ActivityHistoryPage;
