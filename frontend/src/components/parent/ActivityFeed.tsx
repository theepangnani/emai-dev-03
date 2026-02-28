import { useMemo } from 'react';
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
  const recentItems = useMemo(() => {
    return [...courseMaterials]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 10);
  }, [courseMaterials]);

  return (
    <div className="pd-feed-container">
      <div className="pd-feed-body">
        {recentItems.length === 0 ? (
          <p className="pd-feed-empty">Activity will appear here as you upload materials and complete tasks.</p>
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
    </div>
  );
}
