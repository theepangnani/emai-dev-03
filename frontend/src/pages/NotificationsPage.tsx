import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { notificationsApi } from '../api/client';
import type { NotificationResponse } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { ListSkeleton } from '../components/Skeleton';
import EmptyState from '../components/EmptyState';
import './NotificationsPage.css';

type FilterTab = 'all' | 'unread' | 'read';

const TYPE_GROUPS: { key: string; label: string; types: string[] }[] = [
  { key: 'tasks', label: 'Tasks & Assignments', types: ['assignment_due', 'task_due', 'project_due', 'assessment_upcoming'] },
  { key: 'messages', label: 'Messages', types: ['message', 'link_request', 'parent_request'] },
  { key: 'study', label: 'Study Tools', types: ['study_guide_created', 'material_uploaded'] },
  { key: 'system', label: 'System', types: ['system', 'grade_posted'] },
];

const getTypeIcon = (type: string) => {
  switch (type) {
    case 'assignment_due': return '\uD83D\uDCDD';
    case 'grade_posted': return '\uD83D\uDCCA';
    case 'message': return '\uD83D\uDCAC';
    case 'system': return '\u2699\uFE0F';
    case 'task_due': return '\u2705';
    case 'link_request': return '\uD83D\uDD17';
    case 'material_uploaded': return '\uD83D\uDCE4';
    case 'study_guide_created': return '\uD83D\uDCDA';
    case 'parent_request': return '\uD83D\uDC68\u200D\uD83D\uDC69\u200D\uD83D\uDC67';
    case 'assessment_upcoming': return '\uD83D\uDCCB';
    case 'project_due': return '\uD83C\uDFAF';
    default: return '\uD83D\uDD14';
  }
};

const formatTime = (dateString: string) => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

export function NotificationsPage() {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterTab, setFilterTab] = useState<FilterTab>('all');

  useEffect(() => {
    loadNotifications();
  }, []);

  const loadNotifications = async () => {
    setLoading(true);
    try {
      const data = await notificationsApi.list(0, 50, false);
      setNotifications(data);
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllAsRead();
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch {
      // Silently fail
    }
  };

  const handleClick = async (notification: NotificationResponse) => {
    if (!notification.read) {
      try {
        await notificationsApi.markAsRead(notification.id);
        setNotifications(prev => prev.map(n => n.id === notification.id ? { ...n, read: true } : n));
      } catch {
        // Silently fail
      }
    }
    if (notification.link) {
      navigate(notification.link);
    }
  };

  const filtered = useMemo(() => {
    if (filterTab === 'unread') return notifications.filter(n => !n.read);
    if (filterTab === 'read') return notifications.filter(n => n.read);
    return notifications;
  }, [notifications, filterTab]);

  const unreadCount = notifications.filter(n => !n.read).length;

  // Group filtered notifications by type category
  const grouped = useMemo(() => {
    const result: { key: string; label: string; items: NotificationResponse[] }[] = [];
    const assigned = new Set<number>();

    for (const group of TYPE_GROUPS) {
      const items = filtered.filter(n => group.types.includes(n.type) && !assigned.has(n.id));
      if (items.length > 0) {
        items.forEach(n => assigned.add(n.id));
        result.push({ key: group.key, label: group.label, items });
      }
    }

    // Catch any uncategorized
    const remaining = filtered.filter(n => !assigned.has(n.id));
    if (remaining.length > 0) {
      result.push({ key: 'other', label: 'Other', items: remaining });
    }

    return result;
  }, [filtered]);

  return (
    <DashboardLayout welcomeSubtitle="Your notifications" showBackButton>
      <div className="notif-page">
        <div className="notif-page-header">
          <h3>Notifications</h3>
          {unreadCount > 0 && (
            <button className="notif-mark-all" onClick={handleMarkAllRead}>
              Mark all as read
            </button>
          )}
        </div>

        <div className="notif-tabs">
          {(['all', 'unread', 'read'] as FilterTab[]).map(tab => (
            <button
              key={tab}
              className={`notif-tab${filterTab === tab ? ' active' : ''}`}
              onClick={() => setFilterTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
              {tab === 'unread' && unreadCount > 0 && (
                <span className="notif-tab-count">{unreadCount}</span>
              )}
            </button>
          ))}
        </div>

        {loading ? (
          <ListSkeleton rows={6} />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={'\u2713'}
            title="You're all caught up!"
            className="notif-empty"
          />
        ) : (
          <div className="notif-groups">
            {grouped.map(group => (
              <div key={group.key} className="notif-group">
                <h4 className="notif-group-label">{group.label}</h4>
                <div className="notif-list">
                  {group.items.map(n => (
                    <div
                      key={n.id}
                      className={`notif-card${!n.read ? ' unread' : ''}${n.link ? ' clickable' : ''}`}
                      onClick={() => handleClick(n)}
                    >
                      <span className="notif-card-icon">{getTypeIcon(n.type)}</span>
                      <div className="notif-card-body">
                        <p className="notif-card-title">{n.title}</p>
                        {n.content && <p className="notif-card-text">{n.content}</p>}
                      </div>
                      <span className="notif-card-time">{formatTime(n.created_at)}</span>
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
