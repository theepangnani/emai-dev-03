import { useMemo, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { messagesApi } from '../api/client';
import { NotificationBell } from './NotificationBell';
import '../pages/Dashboard.css';

interface DashboardLayoutProps {
  children: React.ReactNode;
  welcomeSubtitle?: string;
}

export function DashboardLayout({ children, welcomeSubtitle }: DashboardLayoutProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [unreadCount, setUnreadCount] = useState(0);

  const navItems = useMemo(() => {
    const items = [
      { label: 'Dashboard', path: '/dashboard' },
      { label: 'Messages', path: '/messages' },
    ];

    if (user?.role === 'teacher') {
      items.push({ label: 'Teacher Comms', path: '/teacher-communications' });
    }

    return items;
  }, [user?.role]);

  useEffect(() => {
    const loadUnreadCount = async () => {
      try {
        const data = await messagesApi.getUnreadCount();
        setUnreadCount(data.total_unread);
      } catch {
        // Silently fail
      }
    };

    loadUnreadCount();
    const interval = setInterval(loadUnreadCount, 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="header-left">
          <img src="/logo-icon.png" alt="ClassBridge" className="header-logo" onClick={() => navigate('/dashboard')} style={{ cursor: 'pointer' }} />
          <h1 className="logo" onClick={() => navigate('/dashboard')} style={{ cursor: 'pointer' }}>ClassBridge</h1>
        </div>
        <div className="header-right">
          <button onClick={() => navigate('/messages')} className="messages-button">
            Messages
            {unreadCount > 0 && <span className="unread-badge">{unreadCount}</span>}
          </button>
          {user?.role === 'teacher' && (
            <button onClick={() => navigate('/teacher-communications')} className="messages-button secondary">
              Teacher Comms
            </button>
          )}
          <NotificationBell />
          <div className="user-chip">
            <span className="user-name">{user?.full_name}</span>
            <span className="user-role">{user?.role}</span>
          </div>
          <button onClick={logout} className="logout-button">
            Sign Out
          </button>
        </div>
      </header>

      <div className="dashboard-body">
        <aside className="dashboard-sidebar">
          <div className="sidebar-title">Navigation</div>
          <nav className="sidebar-nav">
            {navItems.map((item) => (
              <button
                key={item.path}
                className="sidebar-link"
                onClick={() => navigate(item.path)}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div className="sidebar-footer">
            <div className="sidebar-stat">
              <span>Unread</span>
              <strong>{unreadCount}</strong>
            </div>
          </div>
        </aside>

        <main className="dashboard-main">
          <div className="welcome-section">
            <h2>Welcome back, {user?.full_name?.split(' ')[0]}!</h2>
            <p>{welcomeSubtitle || "Here's your overview"}</p>
          </div>

          {children}
        </main>
      </div>
    </div>
  );
}
