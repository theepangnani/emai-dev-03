import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { notificationsApi } from '../api/client';
import type { NotificationResponse } from '../api/client';
import './NotificationBell.css';

export function NotificationBell() {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [modalNotification, setModalNotification] = useState<NotificationResponse | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Poll unread count every 60 seconds
  useEffect(() => {
    loadUnreadCount();
    const interval = setInterval(loadUnreadCount, 60000);
    return () => clearInterval(interval);
  }, []);

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
      const data = await notificationsApi.list(0, 10);
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
                  className={`notification-item ${!n.read ? 'unread' : ''}`}
                  onClick={() => handleNotificationClick(n)}
                >
                  <span className="notification-icon">{getTypeIcon(n.type)}</span>
                  <div className="notification-content">
                    <p className="notification-title">{n.title}</p>
                    {n.content && (
                      <p className="notification-text">{n.content}</p>
                    )}
                    <span className="notification-time">{formatTime(n.created_at)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>

    {/* Notification Detail Modal - portaled to body to escape header stacking context */}
    {modalNotification && createPortal(
      <div className="modal-overlay" onClick={() => setModalNotification(null)}>
        <div className="notif-modal" onClick={(e) => e.stopPropagation()}>
          <div className="notif-modal-header">
            <span className="notif-modal-icon">{getTypeIcon(modalNotification.type)}</span>
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
          {modalNotification.link && (
            <div className="notif-modal-footer">
              <button
                className="notif-modal-action"
                onClick={() => {
                  setModalNotification(null);
                  navigate(modalNotification.link!);
                }}
              >
                Go to {modalNotification.link.replace('/', '')} &rarr;
              </button>
            </div>
          )}
        </div>
      </div>,
      document.body
    )}
    </>
  );
}
