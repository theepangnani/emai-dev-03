import { useMemo, useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { messagesApi, inspirationApi } from '../api/client';
import { studyRequestsApi } from '../api/studyRequests';
import type { InspirationMessage } from '../api/client';
import { NotificationBell } from './NotificationBell';
import { AICreditsDisplay } from './AICreditsDisplay';
import { ThemeToggle } from './ThemeToggle';
import { KeyboardShortcutsModal } from './KeyboardShortcutsModal';
import { OnboardingTour, PARENT_TOUR_STEPS, STUDENT_TOUR_STEPS, TEACHER_TOUR_STEPS } from './OnboardingTour';
import { TutorialOverlay, triggerTutorial } from './tutorial/TutorialOverlay';
import { TUTORIAL_KEYS, PARENT_TUTORIAL_STEPS, STUDENT_TUTORIAL_STEPS, TEACHER_TUTORIAL_STEPS } from './tutorial/tutorialSteps';
import { SpeedDialFAB } from './SpeedDialFAB';
import { BugReportModal } from './BugReportModal';
import { JourneyWelcomeModal } from './JourneyWelcomeModal';
import { usePWAInstall } from '../hooks/usePWAInstall';
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
  /** @deprecated Use <PageNav> inside page content instead. Kept for backward compat. */
  showBackButton?: boolean;
  /** When provided, replaces the default welcome section. Receives inspiration data. */
  headerSlot?: (inspiration: InspirationData | null) => React.ReactNode;
}

// Module-level cache so inspiration persists across DashboardLayout remounts (page navigations)
let cachedInspiration: InspirationMessage | null = null;

// SVG icon component for nav items (Feather/Lucide style)
const NAV_SVG: Record<string, React.ReactNode> = {
  Home: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
      <polyline points="9 22 9 12 15 12 15 22"/>
    </svg>
  ),
  'My Kids': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
      <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
    </svg>
  ),
  Readiness: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 11l3 3L22 4"/>
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
    </svg>
  ),
  Classes: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
    </svg>
  ),
  Materials: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="16" y1="17" x2="8" y2="17"/>
    </svg>
  ),
  'Quiz History': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10"/>
      <line x1="12" y1="20" x2="12" y2="4"/>
      <line x1="6" y1="20" x2="6" y2="14"/>
    </svg>
  ),
  Study: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
    </svg>
  ),
  Timeline: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <polyline points="12 6 12 12 16 14"/>
    </svg>
  ),
  Tasks: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 11 12 14 22 4"/>
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
    </svg>
  ),
  Messages: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  ),
  'Teacher Comms': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
      <polyline points="22,6 12,13 2,6"/>
    </svg>
  ),
  Analytics: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 20H3"/>
      <path d="M18 20V10"/>
      <path d="M12 20V4"/>
      <path d="M6 20v-6"/>
    </svg>
  ),
  'AI Usage': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <path d="M12 6v6l4 2"/>
    </svg>
  ),
  'Customer DB': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
      <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
    </svg>
  ),
  Briefings: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="16" y1="17" x2="8" y2="17"/>
      <line x1="10" y1="9" x2="8" y2="9"/>
    </svg>
  ),
  'AI Tools': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a4 4 0 0 1 4 4c0 1.95-1.4 3.58-3.25 3.93L12 22"/>
      <path d="M12 2a4 4 0 0 0-4 4c0 1.95 1.4 3.58 3.25 3.93"/>
      <path d="M4.5 12.5L8 11l-1 4"/>
      <path d="M19.5 12.5L16 11l1 4"/>
    </svg>
  ),
  Help: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
      <line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  ),
  Waitlist: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
      <line x1="9" y1="10" x2="15" y2="10"/>
      <line x1="9" y1="14" x2="15" y2="14"/>
      <line x1="9" y1="18" x2="13" y2="18"/>
    </svg>
  ),
  'Survey Results': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 20V10"/>
      <path d="M12 20V4"/>
      <path d="M6 20v-6"/>
    </svg>
  ),
  'Report a Bug': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 2l1.88 1.88"/>
      <path d="M14.12 3.88L16 2"/>
      <path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1"/>
      <path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6"/>
      <path d="M12 20v-9"/>
      <path d="M6.53 9C4.6 8.8 3 7.1 3 5"/>
      <path d="M6 13H2"/>
      <path d="M3 21c0-2.1 1.7-3.9 3.8-4"/>
      <path d="M20.97 5c0 2.1-1.6 3.8-3.5 4"/>
      <path d="M22 13h-4"/>
      <path d="M17.2 17c2.1.1 3.8 1.9 3.8 4"/>
    </svg>
  ),
  'Install App': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="7 10 12 15 17 10"/>
      <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  ),
  'Report Cards': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
      <line x1="9" y1="10" x2="15" y2="10"/>
      <line x1="9" y1="14" x2="13" y2="14"/>
      <line x1="9" y1="18" x2="11" y2="18"/>
    </svg>
  ),
};

const NavIcon = ({ name }: { name: string }) => {
  const icon = NAV_SVG[name];
  if (!icon) return <span aria-hidden="true">{name[0]}</span>;
  return <span aria-hidden="true">{icon}</span>;
};

// Quick action SVG icons — maps sidebar action labels to nav SVGs
const QUICK_ACTION_SVG: Record<string, React.ReactNode> = {
  '+ Class Material': NAV_SVG.Materials,
  '+ Course Material': NAV_SVG.Materials, // legacy fallback
  '+ Create Class Material': NAV_SVG.Materials,
  '+ Task': NAV_SVG.Tasks,
  '+ Child': NAV_SVG['My Kids'],
  '+ Add Child': NAV_SVG['My Kids'],
  '+ Class': NAV_SVG.Classes,
  '+ Add Class': NAV_SVG.Classes,
  '+ Create Study Material': NAV_SVG.Materials,
  'Create Task': NAV_SVG.Tasks,
};

export function DashboardLayout({ children, welcomeSubtitle, sidebarActions, headerSlot }: DashboardLayoutProps) {
  const { user, logout, switchRole, resendVerification } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [unreadCount, setUnreadCount] = useState(0);
  const [pendingStudyCount, setPendingStudyCount] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [roleSwitcherOpen, setRoleSwitcherOpen] = useState(false);
  const roleSwitcherRef = useRef<HTMLDivElement>(null);
  const [inspiration, setInspiration] = useState<InspirationMessage | null>(cachedInspiration);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [quickActionsOpen, setQuickActionsOpen] = useState(false);
  const [verifyBannerDismissed, setVerifyBannerDismissed] = useState(false);
  const [resendStatus, setResendStatus] = useState<'idle' | 'sending' | 'sent'>('idle');
  const [reconnecting, setReconnecting] = useState(false);
  const [bugReportOpen, setBugReportOpen] = useState(false);
  const { canInstall, installApp } = usePWAInstall();

  useEffect(() => {
    let safetyTimer: ReturnType<typeof setTimeout> | null = null;
    const onReconnecting = () => {
      setReconnecting(true);
      // Safety timeout: auto-dismiss after 45s in case events are lost (#2623)
      if (safetyTimer) clearTimeout(safetyTimer);
      safetyTimer = setTimeout(() => setReconnecting(false), 45_000);
    };
    const onReconnected = () => {
      setReconnecting(false);
      if (safetyTimer) { clearTimeout(safetyTimer); safetyTimer = null; }
    };
    window.addEventListener('api:reconnecting', onReconnecting);
    window.addEventListener('api:reconnected', onReconnected);
    return () => {
      window.removeEventListener('api:reconnecting', onReconnecting);
      window.removeEventListener('api:reconnected', onReconnected);
      if (safetyTimer) clearTimeout(safetyTimer);
    };
  }, []);

  // WCAG 2.4.2 — update document title on route change
  useEffect(() => {
    const PAGE_TITLES: Record<string, string> = {
      '/dashboard': 'Home',
      '/my-kids': 'My Kids',
      '/school-report-cards': 'Report Cards',
      '/analytics': 'Analytics',
      '/tasks': 'Tasks',
      '/messages': 'Messages',
      '/help': 'Help',
      '/study': 'Study',
      '/courses': 'Classes',
      '/course-materials': 'Materials',
      '/teacher-communications': 'Teacher Comms',
      '/admin/waitlist': 'Waitlist',
      '/admin/survey': 'Survey Results',
      '/admin/ai-usage': 'AI Usage',
      '/admin/audit-log': 'Audit Log',
      '/admin/inspiration': 'Inspiration',
      '/admin/faq': 'Manage FAQ',
      '/notifications': 'Notifications',
      '/link-requests': 'Link Requests',
      '/quiz-history': 'Quiz History',
      '/settings/emails': 'Email Settings',
      '/settings/notifications': 'Notification Preferences',
      '/settings/account': 'Account Settings',
      '/settings/data-export': 'Data Export',
      '/settings/calendar-import': 'Calendar Import',
      '/faq': 'FAQ',
      '/ai-tools': 'AI Tools',
      '/activity': 'Activity History',
      '/activity/timeline': 'Timeline',
      '/grades': 'Grades',
      '/xp/history': 'XP History',
      '/xp/badges': 'Badges',
      '/report-card': 'Report Card',
      '/wallet': 'Wallet',
      '/parent-briefing-notes': 'Briefing Notes',
      '/readiness-check': 'Readiness Check',
    };
    const title = PAGE_TITLES[location.pathname] || 'ClassBridge';
    document.title = title === 'ClassBridge' ? title : `${title} — ClassBridge`;
  }, [location.pathname]);

  // WCAG 2.4.3 — move focus to main content on route change
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    const mainEl = document.getElementById('main-content');
    if (mainEl) {
      mainEl.focus({ preventScroll: false });
    }
  }, [location.pathname]);

  const hasMultipleRoles = (user?.roles?.length ?? 0) > 1;

  const navItems = useMemo(() => {
    if (user?.role === 'parent') {
      return [
        { label: 'Home', path: '/dashboard' },
        { label: 'My Kids', path: '/my-kids' },
        { label: 'Report Cards', path: '/school-report-cards' },
        { label: 'Analytics', path: '/analytics' },
        { label: 'Tasks', path: '/tasks' },
        { label: 'Messages', path: '/messages' },
        { label: 'Help', path: '/help' },
      ];
    }

    if (user?.role === 'student') {
      return [
        { label: 'Home', path: '/dashboard' },
        { label: 'Study', path: '/study' },
        { label: 'Report Cards', path: '/school-report-cards' },
        { label: 'Analytics', path: '/analytics' },
        { label: 'Timeline', path: '/activity/timeline' },
        { label: 'Tasks', path: '/tasks' },
        { label: 'Messages', path: '/messages' },
        { label: 'Help', path: '/help' },
      ];
    }

    const items: Array<{ label: string; path: string }> = [
      { label: 'Home', path: '/dashboard' },
      { label: 'Classes', path: '/courses' },
      { label: 'Materials', path: '/course-materials' },
    ];

    items.push(
      { label: 'Tasks', path: '/tasks' },
      { label: 'Messages', path: '/messages' },
    );

    if (user?.role === 'teacher') {
      items.push({ label: 'Teacher Comms', path: '/teacher-communications' });
    }

    if (user?.role === 'admin') {
      items.push({ label: 'Analytics', path: '/analytics' });
      items.push({ label: 'Waitlist', path: '/admin/waitlist' });
      items.push({ label: 'Survey Results', path: '/admin/survey' });
      items.push({ label: 'AI Usage', path: '/admin/ai-usage' });
      items.push({ label: 'Customer DB', path: '/admin/contacts' });
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

  // Load pending study request count for students
  useEffect(() => {
    if (user?.role !== 'student') return;
    const loadPending = async () => {
      try {
        const count = await studyRequestsApi.pendingCount();
        setPendingStudyCount(count);
      } catch {
        // Silently fail
      }
    };
    loadPending();
    const interval = setInterval(loadPending, 60000);
    return () => clearInterval(interval);
  }, [user?.role]);

  // Load inspirational message once per session (cached across remounts)
  useEffect(() => {
    if (cachedInspiration) return;
    inspirationApi.getRandom().then((msg) => {
      cachedInspiration = msg;
      setInspiration(msg);
    }).catch(() => {});
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

  // Keyboard shortcuts: ? key opens legend, Ctrl+K / Cmd+K opens chatbot
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      // Ctrl+K / Cmd+K → open chatbot (search)
      if (e.key === 'k' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent('open-help-chat'));
        return;
      }
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

  // Shared nav-item renderer to deduplicate slide-out and persistent sidebar (#3144)
  const renderNavItems = (opts: {
    classPrefix: 'sidebar' | 'ps-nav';
    onNavigate: (path: string) => void;
    isActive: (path: string) => boolean;
    showTitleAttr?: boolean;
  }) => {
    const { classPrefix, onNavigate, isActive, showTitleAttr } = opts;
    const itemClass = classPrefix === 'sidebar' ? 'sidebar-link' : 'ps-nav-item';
    const iconClass = classPrefix === 'sidebar' ? 'sidebar-link-icon' : 'ps-nav-icon';
    const labelClass = classPrefix === 'sidebar' ? 'sidebar-link-label' : 'ps-nav-label';
    const badgeClass = classPrefix === 'sidebar' ? 'sidebar-badge' : 'ps-nav-badge';

    return navItems.map((item) => {
      const active = isActive(item.path);
      return (
        <button
          key={item.path}
          className={`${itemClass}${active ? ' active' : ''}`}
          onClick={() => onNavigate(item.path)}
          aria-current={active ? 'page' : undefined}
          {...(showTitleAttr ? { title: item.label, 'aria-label': item.label } : {})}
        >
          <span className={iconClass}><NavIcon name={item.label} /></span>
          <span className={labelClass}>{item.label}</span>
          {item.path === '/messages' && unreadCount > 0 && (
            <span className={badgeClass}>{unreadCount}</span>
          )}
          {item.path === '/dashboard' && user?.role === 'student' && pendingStudyCount > 0 && (
            <span className={badgeClass}>{pendingStudyCount}</span>
          )}
        </button>
      );
    });
  };

  return (
    <>
      {/* Skip to content link for keyboard users */}
      <a href="#main-content" className="skip-to-content">
        Skip to main content
      </a>

      <div className="dashboard">
        <div
          role="alert"
          aria-live="assertive"
          style={{
            position: 'fixed', top: 0, left: 0, right: 0, zIndex: 9999,
            background: 'var(--color-warning)', color: 'var(--color-surface)', textAlign: 'center',
            padding: reconnecting ? '8px 16px' : '0', fontSize: '14px', fontWeight: 500,
          }}
        >
          {reconnecting && 'Reconnecting to server…'}
        </div>
        <header className="dashboard-header">
          <div className="header-left">
            <button
              className={`hamburger-btn${menuOpen ? ' open' : ''}`}
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="Toggle navigation"
              aria-expanded={menuOpen}
            >
              <span />
              <span />
              <span />
            </button>
            <img src="/classbridge-logo-v6.png" alt="ClassBridge" className="header-logo" onClick={() => navigate('/dashboard')} style={{ cursor: 'pointer' }} />
          </div>
          <div className="header-right">
            <AICreditsDisplay />
            <ThemeToggle />
            <NotificationBell />
            <div className="user-chip" ref={roleSwitcherRef}>
              <span className="user-name">{user?.full_name}</span>
              {hasMultipleRoles ? (
                <>
                  <button
                    className="user-role role-switcher-trigger"
                    onClick={() => setRoleSwitcherOpen(!roleSwitcherOpen)}
                    aria-expanded={roleSwitcherOpen}
                    aria-haspopup="true"
                  >
                    {user?.role} &#9662;
                  </button>
                  {roleSwitcherOpen && (
                    <div
                      className="role-switcher-dropdown"
                      role="menu"
                      onKeyDown={(e) => {
                        if (e.key === 'Escape') {
                          setRoleSwitcherOpen(false);
                          return;
                        }
                        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                          e.preventDefault();
                          const items = Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>('[role="menuitem"]'));
                          const idx = items.indexOf(document.activeElement as HTMLButtonElement);
                          const next = e.key === 'ArrowDown'
                            ? items[(idx + 1) % items.length]
                            : items[(idx - 1 + items.length) % items.length];
                          next?.focus();
                        }
                      }}
                    >
                      {user?.roles
                        .filter(r => r !== user?.role)
                        .map(r => (
                          <button
                            key={r}
                            className="role-switcher-option"
                            role="menuitem"
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
            {user?.role === 'student' && (
              <Link to="/settings/emails" className="email-settings-link">
                Email Settings
              </Link>
            )}
            <button onClick={logout} className="logout-button">
              Sign Out
            </button>
          </div>
        </header>

      {showVerifyBanner && (
        <div className="verify-email-banner" role="status" aria-live="polite">
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
          {renderNavItems({
            classPrefix: 'sidebar',
            onNavigate: handleNavClick,
            isActive: (path) => location.pathname === path,
          })}
          <button
            className="sidebar-link"
            onClick={() => {
              setMenuOpen(false);
              setBugReportOpen(true);
            }}
          >
            <span className="sidebar-link-icon"><NavIcon name="Report a Bug" /></span>
            <span className="sidebar-link-label">Report a Bug</span>
          </button>
          <button
            className="sidebar-link"
            onClick={() => {
              setMenuOpen(false);
              const key = user?.role === 'student' ? TUTORIAL_KEYS.STUDENT_DASHBOARD
                : user?.role === 'teacher' ? TUTORIAL_KEYS.TEACHER_DASHBOARD
                : TUTORIAL_KEYS.PARENT_DASHBOARD;
              triggerTutorial(key);
            }}
          >
            <span className="sidebar-link-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
            </span>
            <span className="sidebar-link-label">Show Tutorial</span>
          </button>
          {canInstall && (
            <button
              className="sidebar-link"
              onClick={() => {
                setMenuOpen(false);
                installApp();
              }}
            >
              <span className="sidebar-link-icon"><NavIcon name="Install App" /></span>
              <span className="sidebar-link-label">Install App</span>
            </button>
          )}
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
                  <span className="sidebar-action-icon icon-with-plus">{QUICK_ACTION_SVG[action.label] || <NavIcon name={action.label} />}</span>
                  <span className="sidebar-action-label">{action.label}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="dashboard-body" aria-hidden={menuOpen || undefined}>
        {/* Persistent sidebar (>=768px) */}
        <aside
          className="persistent-sidebar"
          aria-label="Main navigation"
        >
          <nav className="persistent-sidebar-nav">
            {renderNavItems({
              classPrefix: 'ps-nav',
              onNavigate: navigate,
              isActive: (path) => location.pathname === path || (path !== '/dashboard' && location.pathname.startsWith(path)),
              showTitleAttr: true,
            })}
            <button
              className="ps-nav-item"
              onClick={() => setBugReportOpen(true)}
              title="Report a Bug"
              aria-label="Report a Bug"
            >
              <span className="ps-nav-icon"><NavIcon name="Report a Bug" /></span>
              <span className="ps-nav-label">Report a Bug</span>
            </button>
            {canInstall && (
              <button
                className="ps-nav-item"
                onClick={() => installApp()}
                title="Install App"
                aria-label="Install App"
              >
                <span className="ps-nav-icon"><NavIcon name="Install App" /></span>
                <span className="ps-nav-label">Install App</span>
              </button>
            )}
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
                <span className="ps-fab-icon">
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                    <path d="M9 3v12M3 9h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </span>
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
                      <span className="ps-action-icon icon-with-plus">{QUICK_ACTION_SVG[action.label] || <NavIcon name={action.label} />}</span>
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
              {inspiration && (
                <div className="welcome-inspiration">
                  <h2 className="inspiration-text">"{inspiration.text}"</h2>
                  {inspiration.author && (
                    <p className="inspiration-author">— {inspiration.author}</p>
                  )}
                </div>
              )}
              <div className={`welcome-fallback${inspiration ? ' has-inspiration' : ''}`}>
                <h2>Welcome back, {user?.full_name?.split(' ')[0]}!</h2>
                <p>{welcomeSubtitle || "Here's your overview"}</p>
              </div>
            </div>
          )}

          {location.pathname === '/dashboard' && (
            <div className="dashboard-date-bar">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
              <span>{new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</span>
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
        <Link to="/faq">FAQ</Link>
        <span className="dashboard-footer-divider">|</span>
        <a href="mailto:support@classbridge.ca">Contact Us</a>
      </footer>

      {/* Mobile bottom tab bar (<768px) */}
      <nav className="mobile-tab-bar" aria-label="Mobile navigation">
        {navItems.slice(0, 5).map((item) => (
          <button
            key={item.path}
            className={`mobile-tab-item${location.pathname === item.path || (item.path !== '/dashboard' && location.pathname.startsWith(item.path)) ? ' active' : ''}`}
            onClick={() => navigate(item.path)}
            aria-label={item.label}
            aria-current={location.pathname === item.path || (item.path !== '/dashboard' && location.pathname.startsWith(item.path)) ? 'page' : undefined}
          >
            <span className="mobile-tab-icon">
              <NavIcon name={item.label} />
              {item.path === '/messages' && unreadCount > 0 && (
                <span className="mobile-tab-badge">{unreadCount}</span>
              )}
              {item.path === '/dashboard' && user?.role === 'student' && pendingStudyCount > 0 && (
                <span className="mobile-tab-badge">{pendingStudyCount}</span>
              )}
            </span>
            <span className="mobile-tab-label">{item.label}</span>
          </button>
        ))}
      </nav>

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

      {/* Backend-persisted tutorial overlay (#1210) */}
      {user?.role === 'parent' && (
        <TutorialOverlay tutorialKey={TUTORIAL_KEYS.PARENT_DASHBOARD} steps={PARENT_TUTORIAL_STEPS} />
      )}
      {user?.role === 'student' && (
        <TutorialOverlay tutorialKey={TUTORIAL_KEYS.STUDENT_DASHBOARD} steps={STUDENT_TUTORIAL_STEPS} />
      )}
      {user?.role === 'teacher' && (
        <TutorialOverlay tutorialKey={TUTORIAL_KEYS.TEACHER_DASHBOARD} steps={TEACHER_TUTORIAL_STEPS} />
      )}

      <BugReportModal open={bugReportOpen} onClose={() => setBugReportOpen(false)} />
      <JourneyWelcomeModal />
      <SpeedDialFAB />
      </div>
    </>
  );
}
