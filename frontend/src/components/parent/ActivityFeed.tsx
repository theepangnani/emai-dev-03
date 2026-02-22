import { useState, useMemo } from 'react';
import type { CourseMaterial } from './StudentDetailPanel';

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffHours = diffMs / (1000 * 60 * 60);

  if (diffHours < 1) return 'Just now';
  if (diffHours < 24) return `${Math.floor(diffHours)} hour${Math.floor(diffHours) !== 1 ? 's' : ''} ago`;
  if (diffHours < 48) return 'Yesterday';
  return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function typeIcon(contentType: string): string {
  switch (contentType) {
    case 'assignment': return '\u{1F4DD}';
    case 'announcement': return '\u{1F4E2}';
    case 'topic': return '\u{1F4C1}';
    default: return '\u{1F4C4}';
  }
}

interface ActivityFeedProps {
  courseMaterials: CourseMaterial[];
  onViewMaterial: (mat: CourseMaterial) => void;
  onViewAllMaterials: () => void;
}

export function ActivityFeed({ courseMaterials, onViewMaterial, onViewAllMaterials }: ActivityFeedProps) {
  const [collapsed, setCollapsed] = useState(false);

  const recentItems = useMemo(() => {
    return [...courseMaterials]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 10);
  }, [courseMaterials]);

  return (
    <div className="pd-feed-container">
      <button
        className="pd-feed-header"
        onClick={() => setCollapsed(prev => !prev)}
        type="button"
        aria-expanded={!collapsed}
        aria-label={`Recent Activity (${recentItems.length} items)`}
      >
        <span className="pd-feed-header-left">
          <span className={`pd-feed-chevron ${collapsed ? '' : 'open'}`} aria-hidden="true">&#9656;</span>
          <span className="pd-feed-title">Recent Activity</span>
          {recentItems.length > 0 && (
            <span className="pd-feed-count">{recentItems.length}</span>
          )}
          {collapsed && recentItems.length > 0 && (
            <span className="pd-feed-preview">
              {recentItems[0].title}
            </span>
          )}
        </span>
      </button>

      {!collapsed && (
        <div className="pd-feed-body">
          {recentItems.length === 0 ? (
            <p className="pd-feed-empty">No recent activity</p>
          ) : (
            <>
              <div className="pd-feed-list">
                {recentItems.map(item => (
                  <button
                    key={item.id}
                    className="pd-feed-item"
                    onClick={() => onViewMaterial(item)}
                    type="button"
                  >
                    <span className="pd-feed-item-icon" aria-hidden="true">{typeIcon(item.content_type)}</span>
                    <span className="pd-feed-item-info">
                      <span className="pd-feed-item-title">{item.title}</span>
                      {item.course_name && (
                        <span className="pd-feed-item-course">{item.course_name}</span>
                      )}
                    </span>
                    <span className="pd-feed-item-time">{relativeTime(item.created_at)}</span>
                  </button>
                ))}
              </div>
              <button className="pd-feed-view-all" onClick={onViewAllMaterials} type="button">
                View All Materials
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
