import { useState, useEffect } from 'react';
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
          <h1 className="logo" onClick={() => navigate('/dashboard')} style={{ cursor: 'pointer' }}>EMAI</h1>
        </div>
        <div className="header-right">
          <button onClick={() => navigate('/messages')} className="messages-button">
            Messages
            {unreadCount > 0 && <span className="unread-badge">{unreadCount}</span>}
          </button>
          <button onClick={() => navigate('/teacher-communications')} className="messages-button">
            Teacher Comms
          </button>
          <NotificationBell />
          <span className="user-name">{user?.full_name}</span>
          <span className="user-role">{user?.role}</span>
          <button onClick={logout} className="logout-button">
            Sign Out
          </button>
        </div>
      </header>

      <main className="dashboard-main">
        <div className="welcome-section">
          <h2>Welcome back, {user?.full_name?.split(' ')[0]}!</h2>
          <p>{welcomeSubtitle || "Here's your overview"}</p>
        </div>

        {children}
      </main>
    </div>
  );
}
