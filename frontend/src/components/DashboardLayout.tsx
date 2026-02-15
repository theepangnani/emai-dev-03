import { useMemo, useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { messagesApi, inspirationApi } from '../api/client';
import type { InspirationMessage } from '../api/client';
import { NotificationBell } from './NotificationBell';
import { GlobalSearch } from './GlobalSearch';
import { ThemeToggle } from './ThemeToggle';
import { KeyboardShortcutsModal } from './KeyboardShortcutsModal';
import { OnboardingTour, PARENT_TOUR_STEPS, STUDENT_TOUR_STEPS, TEACHER_TOUR_STEPS } from './OnboardingTour';
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
  const { user, logout, switchRole } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [unreadCount, setUnreadCount] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [roleSwitcherOpen, setRoleSwitcherOpen] = useState(false);
  const roleSwitcherRef = useRef<HTMLDivElement>(null);
  const [inspiration, setInspiration] = useState<InspirationMessage | null>(null);
  const [showShortcuts, setShowShortcuts] = useState(false);

  const hasMultipleRoles = (user?.roles?.length ?? 0) > 1;

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
    if (user?.role === 'parent') {
      return [
        { label: 'Overview', path: '/dashboard' },
        { label: 'Child Profiles', path: '/my-kids' },
        { label: 'Tasks', path: '/tasks' },
        { label: 'Messages', path: '/messages' },
      ];
    }

    const items: Array<{ label: string; path: string }> = [
      { label: 'Dashboard', path: '/dashboard' },
      { label: 'Courses', path: '/courses' },
      { label: 'Course Materials', path: '/course-materials' },
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

  // Load inspirational message once per session
  useEffect(() => {
    inspirationApi.getRandom().then(setInspiration).catch(() => {});
  }, []);

  // Close menu when route changes
  useEffect(() => {
    // Menu close is intentionally synchronous here to provide immediate feedback on navigation
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMenuOpen(false);
  }, [location.pathname]);

  // Close role switcher on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (roleSwitcherRef.current && !roleSwitcherRef.current.contains(e.target as Node)) {
        setRoleSwitcherOpen(false);
      }
    };
    if (roleSwitcherOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [roleSwitcherOpen]);

  // Keyboard shortcuts: ? key opens legend
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') return;
      if (e.key === '?') {
        e.preventDefault();
        setShowShortcuts(true);
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, []);

  const handleNavClick = useCallback((path: string) => {
    navigate(path);
    setMenuOpen(false);
  }, [navigate]);

  const handleActionClick = useCallback((action: SidebarAction) => {
    action.onClick();
    setMenuOpen(false);
  }, []);

  const handleSwitchRole = useCallback(async (role: string) => {
    try {
      await switchRole(role);
      setRoleSwitcherOpen(false);
      navigate('/dashboard');
    } catch {
      // Silently fail
    }
  }, [switchRole, navigate]);

  return (
    <>
      {/* Skip to content link for keyboard users */}
      <a href="#main-content" className="skip-to-content">
        Skip to main content
      </a>

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
          <ThemeToggle />
          <NotificationBell />
          <div className="user-chip" ref={roleSwitcherRef}>
            <span className="user-name">{user?.full_name}</span>
            {hasMultipleRoles ? (
              <>
                <button
                  className="user-role role-switcher-trigger"
                  onClick={() => setRoleSwitcherOpen(!roleSwitcherOpen)}
                >
                  {user?.role} &#9662;
                </button>
                {roleSwitcherOpen && (
                  <div className="role-switcher-dropdown">
                    {user?.roles
                      .filter(r => r !== user?.role)
                      .map(r => (
                        <button
                          key={r}
                          className="role-switcher-option"
                          onClick={() => handleSwitchRole(r)}
                        >
                          Switch to {r}
                        </button>
                      ))}
                  </div>
                )}
              </>
            ) : (
              <span className="user-role">{user?.role}</span>
            )}
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

      <main id="main-content" className="dashboard-main-full" tabIndex={-1}>
        <div className="welcome-section">
          {inspiration ? (
            <>
              <h2 className="inspiration-text">"{inspiration.text}"</h2>
              {inspiration.author && (
                <p className="inspiration-author">— {inspiration.author}</p>
              )}
            </>
          ) : (
            <>
              <h2>Welcome back, {user?.full_name?.split(' ')[0]}!</h2>
              <p>{welcomeSubtitle || "Here's your overview"}</p>
            </>
          )}
        </div>

        {children}
      </main>

      <KeyboardShortcutsModal open={showShortcuts} onClose={() => setShowShortcuts(false)} />

      {user?.role === 'parent' && (
        <OnboardingTour steps={PARENT_TOUR_STEPS} storageKey="tour_completed_parent" />
      )}
      {user?.role === 'student' && (
        <OnboardingTour steps={STUDENT_TOUR_STEPS} storageKey="tour_completed_student" />
      )}
      {user?.role === 'teacher' && (
        <OnboardingTour steps={TEACHER_TOUR_STEPS} storageKey="tour_completed_teacher" />
      )}
      </div>
    </>
  );
}
