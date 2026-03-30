import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, Link } from 'react-router-dom';
import { notificationsApi } from '../api/client';
import type { NotificationResponse } from '../api/client';
import { usePageVisible } from '../hooks/usePageVisible';
import './NotificationBell.css';

export function NotificationBell() {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [modalNotification, setModalNotification] = useState<NotificationResponse | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const isVisible = usePageVisible();

  // Poll unread count every 60 seconds (only when page is visible)
  useEffect(() => {
    if (!isVisible) return;
    loadUnreadCount();
    const interval = setInterval(loadUnreadCount, 60000);
    return () => clearInterval(interval);
  }, [isVisible]);

  // Close modal on Escape key
  useEffect(() => {
    if (!modalNotification) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setModalNotification(null);
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [modalNotification]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const loadUnreadCount = async () => {
    try {
      const data = await notificationsApi.getUnreadCount();
      setUnreadCount(data.count);
    } catch {
      // Silently fail
    }
  };

  const loadNotifications = async () => {
    setLoading(true);
    try {
      const data = await notificationsApi.list(0, 10, true);
      setNotifications(data);
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
    }
  };

  const toggleDropdown = () => {
    if (!isOpen) {
      loadNotifications();
    }
    setIsOpen(!isOpen);
  };

  const handleNotificationClick = async (notification: NotificationResponse) => {
    if (!notification.read) {
      try {
        await notificationsApi.markAsRead(notification.id);
        setUnreadCount((prev) => Math.max(0, prev - 1));
      } catch {
        // Silently fail
      }
    }

    // Remove from panel and open detail modal
    setNotifications((prev) => prev.filter((n) => n.id !== notification.id));
    setIsOpen(false);
    setModalNotification(notification);
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllAsRead();
      setUnreadCount(0);
      setNotifications([]);
    } catch {
      // Silently fail
    }
  };

  const handleAcknowledge = async (notificationOrNull?: NotificationResponse | null) => {
    const target = notificationOrNull ?? modalNotification;
    if (!target) return;
    try {
      const updated = await notificationsApi.ack(target.id);
      // Update in both modal and dropdown list
      if (modalNotification && modalNotification.id === target.id) {
        setModalNotification(updated);
      }
      setNotifications((prev) =>
        prev.map((n) => (n.id === target.id ? updated : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      // Silently fail
    }
  };

  const handleSuppress = async (notificationOrNull?: NotificationResponse | null) => {
    const target = notificationOrNull ?? modalNotification;
    if (!target) return;
    try {
      await notificationsApi.suppress(target.id);
      if (modalNotification && modalNotification.id === target.id) {
        setModalNotification(null);
      }
      // Remove from dropdown list
      setNotifications((prev) => prev.filter((n) => n.id !== target.id));
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      // Silently fail
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
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'assignment_due': return '📝';
      case 'grade_posted': return '📊';
      case 'message': return '💬';
      case 'system': return '⚙️';
      case 'task_due': return '✅';
      case 'link_request': return '🔗';
      case 'material_uploaded': return '📤';
      case 'study_guide_created': return '📚';
      case 'parent_request': return '👨‍👩‍👧';
      case 'assessment_upcoming': return '📋';
      case 'project_due': return '🎯';
      default: return '🔔';
    }
  };

  return (
    <>
    <div className="notification-bell" ref={dropdownRef}>
      <button className="bell-button" onClick={toggleDropdown} aria-label="Notifications">
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unreadCount > 0 && (
          <span className="bell-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>
        )}
      </button>

      {isOpen && (
        <div className="notification-dropdown">
          <div className="dropdown-header">
            <h3>Notifications</h3>
            {unreadCount > 0 && (
              <button className="mark-all-btn" onClick={handleMarkAllRead}>
                Mark all read
              </button>
            )}
          </div>

          <div className="dropdown-body">
            {loading ? (
              <div className="dropdown-empty">Loading...</div>
            ) : notifications.length === 0 ? (
              <div className="dropdown-empty">No notifications</div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  className={`notification-item ${!n.read ? 'unread' : ''} ${n.requires_ack && !n.acked_at ? 'requires-ack' : ''} ${n.acked_at ? 'acknowledged' : ''}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleNotificationClick(n)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleNotificationClick(n); } }}
                >
                  <span className="notification-icon" aria-hidden="true">{getTypeIcon(n.type)}</span>
                  <div className="notification-content">
                    <div className="notification-title-row">
                      <p className="notification-title">{n.title}</p>
                      {n.requires_ack && !n.acked_at && (
                        <span className="ack-badge">ACK</span>
                      )}
                    </div>
                    {n.content && (
                      <p className="notification-text">{n.content}</p>
                    )}
                    <div className="notification-meta-row">
                      <span className="notification-time">{formatTime(n.created_at)}</span>
                      <div className="notification-inline-actions" onClick={(e) => e.stopPropagation()}>
                        {n.requires_ack && !n.acked_at && (
                          <button
                            className="inline-ack-btn"
                            onClick={() => handleAcknowledge(n)}
                            title="Acknowledge"
                            aria-label="Acknowledge notification"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                          </button>
                        )}
                        {n.source_type && (
                          <button
                            className="inline-suppress-btn"
                            onClick={() => handleSuppress(n)}
                            title="Silence future reminders"
                            aria-label="Silence notification"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                              <line x1="1" y1="1" x2="23" y2="23" />
                            </svg>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
            <div className="notif-dropdown-footer">
              <Link to="/notifications" className="notif-view-all" onClick={() => setIsOpen(false)}>
                View All Notifications
              </Link>
              <Link to="/settings/notifications" className="notif-preferences-link" onClick={() => setIsOpen(false)}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 4, verticalAlign: 'middle' }}>
                  <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
                Preferences
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>

    {/* Notification Detail Modal - portaled to body to escape header stacking context */}
    {modalNotification && createPortal(
      <div className="modal-overlay" onClick={() => setModalNotification(null)}>
        <div className="notif-modal" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
          <div className="notif-modal-header">
            <span className="notif-modal-icon" aria-hidden="true">{getTypeIcon(modalNotification.type)}</span>
            <h3>{modalNotification.title}</h3>
            <button className="modal-close" onClick={() => setModalNotification(null)}>
              &times;
            </button>
          </div>
          <div className="notif-modal-body">
            {modalNotification.content && (
              <p className="notif-modal-content">{modalNotification.content}</p>
            )}
            <span className="notif-modal-time">{formatTime(modalNotification.created_at)}</span>
          </div>
          <div className="notif-modal-footer">
            {modalNotification.requires_ack && !modalNotification.acked_at && (
              <button className="notif-modal-ack-btn" onClick={() => handleAcknowledge()}>
                Acknowledge
              </button>
            )}
            {modalNotification.source_type && (
              <button className="notif-modal-silence-btn" onClick={() => handleSuppress()}>
                Silence
              </button>
            )}
            {modalNotification.link && (
              <button
                className="notif-modal-action"
                onClick={() => {
                  setModalNotification(null);
                  navigate(modalNotification.link!);
                }}
              >
                Go to {modalNotification.link.replace('/', '')} &rarr;
              </button>
            )}
          </div>
        </div>
      </div>,
      document.body
    )}
    </>
  );
}
