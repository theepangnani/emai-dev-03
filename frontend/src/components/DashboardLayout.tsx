import { useMemo, useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { messagesApi } from '../api/client';
import { NotificationBell } from './NotificationBell';
import { GlobalSearch } from './GlobalSearch';
import '../pages/Dashboard.css';

interface SidebarAction {
  label: string;
  onClick: () => void;
}

interface DashboardLayoutProps {
  children: React.ReactNode;
  welcomeSubtitle?: string;
  sidebarActions?: SidebarAction[];
}

export function DashboardLayout({ children, welcomeSubtitle, sidebarActions }: DashboardLayoutProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [unreadCount, setUnreadCount] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);

  const dashboardTitle = useMemo(() => {
    switch (user?.role) {
      case 'parent': return "Parent's Dashboard";
      case 'student': return "Student's Dashboard";
      case 'teacher': return "Teacher's Dashboard";
      case 'admin': return "Admin Dashboard";
      default: return 'Dashboard';
    }
  }, [user?.role]);

  const navItems = useMemo(() => {
    const items: Array<{ label: string; path: string }> = [
      { label: 'Dashboard', path: '/dashboard' },
      { label: 'Courses', path: '/courses' },
      { label: 'Study Guides', path: '/study-guides' },
      { label: 'Tasks', path: '/tasks' },
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

  // Close menu when route changes
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  const handleNavClick = useCallback((path: string) => {
    navigate(path);
    setMenuOpen(false);
  }, [navigate]);

  const handleActionClick = useCallback((action: SidebarAction) => {
    action.onClick();
    setMenuOpen(false);
  }, []);

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="header-left">
          <button
            className={`hamburger-btn${menuOpen ? ' open' : ''}`}
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle navigation"
          >
            <span />
            <span />
            <span />
          </button>
          <img src="/logo-icon.png" alt="ClassBridge" className="header-logo" onClick={() => navigate('/dashboard')} style={{ cursor: 'pointer' }} />
          <h1 className="logo" onClick={() => navigate('/dashboard')} style={{ cursor: 'pointer' }}>{dashboardTitle}</h1>
        </div>
        <GlobalSearch />
        <div className="header-right">
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

      {/* Slide-out menu overlay */}
      {menuOpen && <div className="menu-overlay" onClick={() => setMenuOpen(false)} />}

      <div className={`slide-menu${menuOpen ? ' open' : ''}`}>
        <div className="sidebar-title">Navigation</div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <button
              key={item.path}
              className={`sidebar-link${location.pathname === item.path ? ' active' : ''}`}
              onClick={() => handleNavClick(item.path)}
            >
              {item.label}
              {item.path === '/messages' && unreadCount > 0 && (
                <span className="sidebar-badge">{unreadCount}</span>
              )}
            </button>
          ))}
        </nav>
        {sidebarActions && sidebarActions.length > 0 && (
          <>
            <div className="sidebar-divider" />
            <div className="sidebar-title">Quick Actions</div>
            <div className="sidebar-nav">
              {sidebarActions.map((action, i) => (
                <button
                  key={i}
                  className="sidebar-action"
                  onClick={() => handleActionClick(action)}
                >
                  {action.label}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <main className="dashboard-main-full">
        <div className="welcome-section">
          <h2>Welcome back, {user?.full_name?.split(' ')[0]}!</h2>
          <p>{welcomeSubtitle || "Here's your overview"}</p>
        </div>

        {children}
      </main>
    </div>
  );
}
