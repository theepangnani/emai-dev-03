import { useMemo, useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
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
  icon?: string;
  onClick: () => void;
}

export interface InspirationData {
  text: string;
  author: string | null;
}

interface DashboardLayoutProps {
  children: React.ReactNode;
  welcomeSubtitle?: string;
  sidebarActions?: SidebarAction[];
  showBackButton?: boolean;
  /** When provided, replaces the default welcome section. Receives inspiration data. */
  headerSlot?: (inspiration: InspirationData | null) => React.ReactNode;
}

// Icon map for nav items (unicode emojis per project convention)
const NAV_ICONS: Record<string, string> = {
  'Home': '\u{1F3E0}',
  'My Kids': '\u{1F468}\u200D\u{1F469}\u200D\u{1F467}',
  'Courses': '\u{1F4DA}',
  'Class Materials': '\u{1F4DD}',
  'Quiz History': '\u{1F4CA}',
  'Tasks': '\u2705',
  'Messages': '\u{1F4AC}',
  'Help': '\u2753',
  'Dashboard': '\u{1F3E0}',
  'Teacher Comms': '\u{1F4E8}',
};

// Quick action icons — must match NAV_ICONS base icons for consistency
const QUICK_ACTION_ICONS: Record<string, string> = {
  '+ Class Material': '\u{1F4DD}',
  '+ Create Class Material': '\u{1F4DD}',
  '+ Task': '\u2705',
  '+ Child': '\u{1F476}',
  '+ Add Child': '\u{1F476}',
  '+ Course': '\u{1F4DA}',
  '+ Add Course': '\u{1F4DA}',
  '+ Create Study Material': '\u{1F4DD}',
};

export function DashboardLayout({ children, welcomeSubtitle, sidebarActions, showBackButton, headerSlot }: DashboardLayoutProps) {
  const { user, logout, switchRole, resendVerification } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [unreadCount, setUnreadCount] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [roleSwitcherOpen, setRoleSwitcherOpen] = useState(false);
  const roleSwitcherRef = useRef<HTMLDivElement>(null);
  const [inspiration, setInspiration] = useState<InspirationMessage | null>(null);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [quickActionsOpen, setQuickActionsOpen] = useState(false);
  const [verifyBannerDismissed, setVerifyBannerDismissed] = useState(false);
  const [resendStatus, setResendStatus] = useState<'idle' | 'sending' | 'sent'>('idle');

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
        { label: 'Home', path: '/dashboard' },
        { label: 'My Kids', path: '/my-kids' },
        { label: 'Tasks', path: '/tasks' },
        { label: 'Messages', path: '/messages' },
        { label: 'Help', path: '/help' },
      ];
    }

    const items: Array<{ label: string; path: string }> = [
      { label: 'Dashboard', path: '/dashboard' },
      { label: 'Courses', path: '/courses' },
      { label: 'Class Materials', path: '/course-materials' },
      { label: 'Quiz History', path: '/quiz-history' },
      { label: 'Tasks', path: '/tasks' },
      { label: 'Messages', path: '/messages' },
    ];

    if (user?.role === 'teacher') {
      items.push({ label: 'Teacher Comms', path: '/teacher-communications' });
    }

    items.push({ label: 'Help', path: '/help' });

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
    setQuickActionsOpen(false);
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

  // Build the full quick actions list for persistent sidebar (non-parent roles only)
  const persistentQuickActions = useMemo(() => {
    return sidebarActions || [];
  }, [sidebarActions]);

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

  const handleResendVerification = useCallback(async () => {
    setResendStatus('sending');
    try {
      await resendVerification();
      setResendStatus('sent');
    } catch {
      setResendStatus('idle');
    }
  }, [resendVerification]);

  const showVerifyBanner = user && !user.email_verified && !verifyBannerDismissed;

  return (
    <>
      {/* Skip to content link for keyboard users */}
      <a href="#main-content" className="skip-to-content">
        Skip to main content
      </a>

      <div className="dashboard">
        <header className="dashboard-header">
        <div className="header-left">
          {showBackButton && location.pathname !== '/dashboard' && (
            <button className="layout-back-button" onClick={() => navigate(-1)} aria-label="Go back">
              &larr;
            </button>
          )}
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

      {showVerifyBanner && (
        <div className="verify-email-banner">
          <span>Please verify your email address. Check your inbox for a verification link.</span>
          {resendStatus === 'idle' && (
            <button className="verify-email-banner__resend" onClick={handleResendVerification}>
              Resend email
            </button>
          )}
          {resendStatus === 'sending' && <span className="verify-email-banner__status">Sending...</span>}
          {resendStatus === 'sent' && <span className="verify-email-banner__status">Sent! Check your inbox.</span>}
          <button className="verify-email-banner__dismiss" onClick={() => setVerifyBannerDismissed(true)} aria-label="Dismiss">
            &times;
          </button>
        </div>
      )}

      {/* Slide-out menu overlay (mobile only, <768px) */}
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
              <span className="sidebar-link-icon">{NAV_ICONS[item.label] || ''}</span>
              <span className="sidebar-link-label">{item.label}</span>
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
                  <span className="sidebar-action-icon icon-with-plus">{action.icon || QUICK_ACTION_ICONS[action.label] || ''}</span>
                  <span className="sidebar-action-label">{action.label}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="dashboard-body">
        {/* Persistent sidebar (>=768px) */}
        <aside className="persistent-sidebar" aria-label="Main navigation">
          <nav className="persistent-sidebar-nav">
            {navItems.map((item) => (
              <button
                key={item.path}
                className={`ps-nav-item${location.pathname === item.path ? ' active' : ''}`}
                onClick={() => navigate(item.path)}
                title={item.label}
                aria-label={item.label}
              >
                <span className="ps-nav-icon">{NAV_ICONS[item.label] || ''}</span>
                {item.path === '/messages' && unreadCount > 0 && (
                  <span className="ps-nav-badge">{unreadCount}</span>
                )}
              </button>
            ))}
          </nav>

          {persistentQuickActions.length > 0 && (
            <>
              <div className="ps-divider" />
              <button
                className={`ps-fab-toggle${quickActionsOpen ? ' open' : ''}`}
                onClick={() => setQuickActionsOpen(p => !p)}
                title="Quick Actions"
                aria-label="Quick Actions"
              >
                <span className="ps-fab-icon">+</span>
              </button>
              {quickActionsOpen && (
                <div className="persistent-sidebar-actions">
                  {persistentQuickActions.map((action, i) => (
                    <button
                      key={i}
                      className="ps-action-item"
                      onClick={action.onClick}
                      title={action.label}
                      aria-label={action.label}
                    >
                      <span className="ps-action-icon icon-with-plus">{action.icon || QUICK_ACTION_ICONS[action.label] || ''}</span>
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </aside>

        <main id="main-content" className="dashboard-main-full" tabIndex={-1}>
        {headerSlot ? (
          headerSlot(inspiration ? { text: inspiration.text, author: inspiration.author } : null)
        ) : (
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
        )}

        {children}
      </main>
      </div>{/* end dashboard-body */}

      <footer className="dashboard-footer">
        <Link to="/privacy">Privacy Policy</Link>
        <span className="dashboard-footer-divider">|</span>
        <Link to="/terms">Terms of Service</Link>
        <span className="dashboard-footer-divider">|</span>
        <a href="mailto:support@classbridge.ca">Contact Us</a>
      </footer>

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
