import { useState, useEffect, useMemo } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { googleApi, coursesApi, assignmentsApi, studyApi } from '../api/client';
import { useFeature } from '../hooks/useFeatureToggle';
import { notificationsApi, type NotificationResponse } from '../api/notifications';
import { tasksApi, type TaskItem } from '../api/tasks';
import { invitesApi } from '../api/invites';
import type { StudyGuide } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageSkeleton } from '../components/Skeleton';
import { FAQErrorHint } from '../components/FAQErrorHint';
import { extractFaqCode } from '../utils/faqUtils';
import { useFocusTrap } from '../hooks/useFocusTrap';
import UploadMaterialWizard from '../components/UploadMaterialWizard';
import { useParentStudyTools } from '../components/parent/hooks/useParentStudyTools';
import { AILimitRequestModal } from '../components/AILimitRequestModal';
import { useAuth } from '../context/AuthContext';
import { logger } from '../utils/logger';
import EmptyState from '../components/EmptyState';
import { StreakMilestone } from '../components/StreakMilestone';
import { ContinueStudying } from '../components/ContinueStudying';
import { StreakHistory } from '../components/StreakHistory';
import { XpDashboardSection } from '../components/xp/XpDashboardSection';
import { AssessmentCountdown } from '../components/AssessmentCountdown';
import { gradesApi } from '../api/grades';
import { studyRequestsApi, type StudyRequestData } from '../api/studyRequests';
import { StudyRequestCard } from '../components/StudyRequestCard';
import type { ChildGradeSummary } from '../api/grades';
import { GenerationSpinner } from '../components/GenerationSpinner';
import { ReportBugLink } from '../components/ReportBugLink';

import { QuizOfTheDay } from '../components/QuizOfTheDay';

import { StudyTimeSuggestions } from '../components/StudyTimeSuggestions';

import './StudentDashboard.css';
import './DashboardGrid.css';

function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrowStart = new Date(todayStart);
  tomorrowStart.setDate(tomorrowStart.getDate() + 1);
  const dayAfterTomorrow = new Date(todayStart);
  dayAfterTomorrow.setDate(dayAfterTomorrow.getDate() + 2);

  if (date < todayStart) return 'Overdue';
  if (date < tomorrowStart) {
    return `Today${date.getHours() ? ` at ${date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}` : ''}`;
  }
  if (date < dayAfterTomorrow) return 'Tomorrow';
  return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
}

interface Course {
  id: number;
  name: string;
  subject?: string;
  google_classroom_id?: string;
}

interface Assignment {
  id: number;
  title: string;
  description: string | null;
  course_id: number;
  course_name?: string | null;
  due_date: string | null;
}

type UrgencyTier = 'overdue' | 'today' | 'week' | 'later';

interface TimelineItem {
  id: string;
  title: string;
  dueDate: string | null;
  type: 'assignment' | 'task';
  urgency: UrgencyTier;
  courseName?: string;
  sourceId: number;
  priority?: string;
}

function getUrgencyTier(dueDate: string | null): UrgencyTier {
  if (!dueDate) return 'later';
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const todayEnd = new Date(todayStart);
  todayEnd.setDate(todayEnd.getDate() + 1);
  const weekEnd = new Date(todayStart);
  weekEnd.setDate(weekEnd.getDate() + 7);
  const due = new Date(dueDate);
  if (due < todayStart) return 'overdue';
  if (due < todayEnd) return 'today';
  if (due < weekEnd) return 'week';
  return 'later';
}

export function StudentDashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const gcEnabled = useFeature('google_classroom');

  const [initialLoading, setInitialLoading] = useState(true);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  // lastSynced state removed — no longer displayed in unified quick actions
  const [courses, setCourses] = useState<Course[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [studyGuides, setStudyGuides] = useState<StudyGuide[]>([]);
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [pendingStudyRequests, setPendingStudyRequests] = useState<StudyRequestData[]>([]);
  const [faqCode, setFaqCode] = useState<string | null>(null);

  // Upload / study material generation (shared with Parent experience)
  const studyTools = useParentStudyTools({ selectedChildUserId: null, navigate });

  // Create course modal
  const [showCreateCourseModal, setShowCreateCourseModal] = useState(false);
  const [newCourseName, setNewCourseName] = useState('');
  const [newCourseSubject, setNewCourseSubject] = useState('');
  const [isCreatingCourse, setIsCreatingCourse] = useState(false);

  // Classroom type selection for Google sync (#550)
  const [showClassroomTypeModal, setShowClassroomTypeModal] = useState(false);
  const [classroomType, setClassroomType] = useState<'school' | 'private'>('school');

  // Invite teacher state
  const [gradeSummary, setGradeSummary] = useState<ChildGradeSummary | null>(null);

  const [showInviteTeacherModal, setShowInviteTeacherModal] = useState(false);
  const [inviteTeacherEmail, setInviteTeacherEmail] = useState('');
  const [inviteTeacherLoading, setInviteTeacherLoading] = useState(false);
  const [inviteTeacherMsg, setInviteTeacherMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const createCourseModalRef = useFocusTrap<HTMLDivElement>(showCreateCourseModal, () => setShowCreateCourseModal(false));
  const inviteTeacherModalRef = useFocusTrap<HTMLDivElement>(showInviteTeacherModal, () => setShowInviteTeacherModal(false));
  const classroomTypeModalRef = useFocusTrap<HTMLDivElement>(showClassroomTypeModal, () => setShowClassroomTypeModal(false));


  const { user } = useAuth();
  const [onboardingDismissed, setOnboardingDismissed] = useState(() =>
    localStorage.getItem('student-upload-onboarding-dismissed') === 'true'
  );

  const [myDayCollapsed, setMyDayCollapsed] = useState(() => {
    try { const v = localStorage.getItem('sd-myday-collapsed'); return v !== null ? v === '1' : true; } catch { return true; }
  });
  const [materialsCollapsed, setMaterialsCollapsed] = useState(() => {
    try { const v = localStorage.getItem('sd-materials-collapsed'); return v !== null ? v === '1' : true; } catch { return true; }
  });

  const toggleMyDay = () => setMyDayCollapsed(prev => { const next = !prev; try { localStorage.setItem('sd-myday-collapsed', next ? '1' : '0'); } catch { /* ignore */ } return next; });
  const toggleMaterials = () => setMaterialsCollapsed(prev => { const next = !prev; try { localStorage.setItem('sd-materials-collapsed', next ? '1' : '0'); } catch { /* ignore */ } return next; });

  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    const firstName = user?.full_name?.split(' ')[0] || 'there';
    if (hour < 12) return `Good morning, ${firstName}`;
    if (hour < 17) return `Good afternoon, ${firstName}`;
    return `Good evening, ${firstName}`;
  }, [user?.full_name]);

  const calculateStreak = (guides: StudyGuide[]): number => {
    if (!guides.length) return 0;
    const uniqueDates = Array.from(
      new Set(guides.map(g => new Date(g.created_at).toDateString()))
    ).sort((a, b) => new Date(b).getTime() - new Date(a).getTime());
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    let streak = 0;
    for (let i = 0; i < uniqueDates.length; i++) {
      const expected = new Date(today);
      expected.setDate(expected.getDate() - i);
      if (new Date(uniqueDates[i]).toDateString() !== expected.toDateString()) break;
      streak++;
    }
    return streak;
  };

  // Build unified timeline from assignments + tasks
  const timelineItems = useMemo(() => {
    const items: TimelineItem[] = [];

    for (const a of assignments) {
      items.push({
        id: `assignment-${a.id}`,
        title: a.title,
        dueDate: a.due_date,
        type: 'assignment',
        urgency: getUrgencyTier(a.due_date),
        courseName: a.course_name ?? undefined,
        sourceId: a.id,
      });
    }

    for (const t of tasks) {
      if (t.is_completed) continue;
      items.push({
        id: `task-${t.id}`,
        title: t.title,
        dueDate: t.due_date,
        type: 'task',
        urgency: getUrgencyTier(t.due_date),
        courseName: t.course_name ?? undefined,
        sourceId: t.id,
        priority: t.priority || undefined,
      });
    }

    // Sort: overdue first, then today, week, later. Within each tier, nearest due first
    const tierOrder: Record<UrgencyTier, number> = { overdue: 0, today: 1, week: 2, later: 3 };
    items.sort((a, b) => {
      const tierDiff = tierOrder[a.urgency] - tierOrder[b.urgency];
      if (tierDiff !== 0) return tierDiff;
      if (!a.dueDate) return 1;
      if (!b.dueDate) return -1;
      return new Date(a.dueDate).getTime() - new Date(b.dueDate).getTime();
    });

    return items;
  }, [assignments, tasks]);

  const urgencyCounts = useMemo(() => {
    let overdue = 0;
    let dueToday = 0;
    let upcoming = 0;
    for (const item of timelineItems) {
      if (item.urgency === 'overdue') overdue++;
      else if (item.urgency === 'today') dueToday++;
      else if (item.urgency === 'week') upcoming++;
    }
    return { overdue, dueToday, upcoming };
  }, [timelineItems]);

  // Actionable notifications (unread, from parents/teachers)
  const actionableNotifications = useMemo(() => {
    return notifications.filter(n =>
      !n.read && (
        n.type === 'parent_request' ||
        n.type === 'assessment_upcoming' ||
        n.type === 'assignment_due' ||
        n.type === 'task_due' ||
        (n.requires_ack && !n.acked_at)
      )
    ).slice(0, 5);
  }, [notifications]);

  const streak = useMemo(() => calculateStreak(studyGuides), [studyGuides]);

  // ── Data Loading ──────────────────────────────────────────────
  useEffect(() => {
    const checkGoogleStatus = async () => {
      try {
        const status = await googleApi.getStatus();
        setGoogleConnected(status.connected);
      } catch {
        setGoogleConnected(false);
      }
    };

    const connected = searchParams.get('google_connected');
    const error = searchParams.get('error');

    if (connected === 'true') {
      setGoogleConnected(true);
      setStatusMessage({ type: 'success', text: 'Google Classroom connected! Choose your classroom type to sync.' });
      // Show classroom type selector before first sync (#550)
      setShowClassroomTypeModal(true);
      const newParams: Record<string, string> = {};
      if (searchParams.get('just_registered')) newParams.just_registered = 'true';
      setSearchParams(newParams);
    } else if (error) {
      setStatusMessage({ type: 'error', text: `Connection failed: ${error}` });
      setFaqCode('GOOGLE_SYNC_FAILED');
      setSearchParams({});
    }

    Promise.all([
      checkGoogleStatus(),
      loadCourses(),
      loadAssignments(),
      loadStudyGuides(),
      loadTasks(),
      loadNotifications(),
      loadGradeSummary(),
      loadStudyRequests(),
    ]).finally(() => setInitialLoading(false));
  }, [searchParams, setSearchParams]);

  const loadCourses = async () => {
    try {
      const data = await coursesApi.list();
      setCourses(data);
      logger.debug('Courses loaded', { count: data.length });
    } catch (err) {
      logger.logError(err, 'Failed to load courses', { component: 'StudentDashboard' });
    }
  };

  const loadAssignments = async () => {
    try {
      const data = await assignmentsApi.list();
      setAssignments(data);
    } catch {
      // Assignments not loaded
    }
  };

  const loadStudyGuides = async () => {
    try {
      const data = await studyApi.listGuides({});
      setStudyGuides(data);
    } catch {
      // Study guides not loaded
    }
  };

  const loadTasks = async () => {
    try {
      const data = await tasksApi.list({ is_completed: false });
      setTasks(data);
    } catch {
      // Tasks not loaded
    }
  };

  const loadNotifications = async () => {
    try {
      const data = await notificationsApi.list(0, 20, true);
      setNotifications(data);
    } catch {
      // Notifications not loaded
    }
  };

  const loadStudyRequests = async () => {
    try {
      const data = await studyRequestsApi.list();
      setPendingStudyRequests(data.filter(sr => sr.status === 'pending'));
    } catch {
      // Study requests not loaded
    }
  };

  const loadGradeSummary = async () => {
    try {
      const data = await gradesApi.summary();
      if (data.children.length > 0) {
        setGradeSummary(data.children[0]);
      }
    } catch {
      // Grades not loaded — not critical
    }
  };

  // ── Google Actions ────────────────────────────────────────────
  const handleConnectGoogle = async () => {
    try {
      const { authorization_url } = await googleApi.getConnectUrl();
      window.location.href = authorization_url;
    } catch (err) {
      setStatusMessage({ type: 'error', text: 'Failed to initiate Google connection' });
      setFaqCode(extractFaqCode(err));
    }
  };

  const handleDisconnectGoogle = async () => {
    setDisconnecting(true);
    try {
      await googleApi.disconnect();
      setGoogleConnected(false);
      setStatusMessage({ type: 'success', text: 'Google Classroom disconnected' });
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to disconnect Google Classroom' });
    } finally {
      setDisconnecting(false);
    }
  };

  const handleSyncCourses = async (overrideType?: 'school' | 'private') => {
    setIsSyncing(true);
    setStatusMessage(null);
    try {
      const result = await googleApi.syncCourses(overrideType || classroomType);
      setStatusMessage({ type: 'success', text: result.message || 'Classes synced successfully' });
      loadCourses();
      loadAssignments();
    } catch (err) {
      setStatusMessage({ type: 'error', text: 'Failed to sync classes' });
      setFaqCode(extractFaqCode(err));
    } finally {
      setIsSyncing(false);
    }
  };

  /** Show classroom type chooser before first sync (#550) */
  const handleSyncWithTypeChoice = () => {
    setShowClassroomTypeModal(true);
  };

  /** User confirmed classroom type; proceed with sync */
  const handleConfirmClassroomType = () => {
    setShowClassroomTypeModal(false);
    handleSyncCourses(classroomType);
  };

  // ── Status message auto-dismiss ───────────────────────────────
  useEffect(() => {
    if (statusMessage) {
      const timer = setTimeout(() => { setStatusMessage(null); setFaqCode(null); }, 5000);
      return () => clearTimeout(timer);
    }
  }, [statusMessage]);

  // ── Create Course ─────────────────────────────────────────────
  const handleCreateCourse = async () => {
    if (!newCourseName.trim()) return;
    setIsCreatingCourse(true);
    try {
      await coursesApi.create({
        name: newCourseName.trim(),
        subject: newCourseSubject.trim() || undefined,
      });
      setStatusMessage({ type: 'success', text: `Class "${newCourseName}" created!` });
      setShowCreateCourseModal(false);
      setNewCourseName('');
      setNewCourseSubject('');
      loadCourses();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to create course' });
    } finally {
      setIsCreatingCourse(false);
    }
  };

  // ── Invite Teacher ────────────────────────────────────────────
  const handleInviteTeacher = async () => {
    if (!inviteTeacherEmail.trim()) return;
    setInviteTeacherLoading(true);
    setInviteTeacherMsg(null);
    try {
      const result = await invitesApi.inviteTeacher(inviteTeacherEmail.trim());
      if (result.action === 'message_sent') {
        setInviteTeacherMsg({ type: 'success', text: result.message || 'Message sent to teacher!' });
      } else {
        setInviteTeacherMsg({ type: 'success', text: 'Invite sent! Your teacher will receive an email.' });
      }
      setInviteTeacherEmail('');
    } catch (err: any) {
      setInviteTeacherMsg({ type: 'error', text: err.response?.data?.detail || 'Failed to invite teacher' });
    } finally {
      setInviteTeacherLoading(false);
    }
  };

  // ── Notification Actions ──────────────────────────────────────
  const handleNotificationClick = async (n: NotificationResponse) => {
    try {
      await notificationsApi.markAsRead(n.id);
      setNotifications(prev => prev.filter(x => x.id !== n.id));
    } catch { /* ignore */ }
    if (n.link) navigate(n.link);
  };

  const handleDismissNotification = async (e: React.MouseEvent, n: NotificationResponse) => {
    e.stopPropagation();
    try {
      if (n.requires_ack) {
        await notificationsApi.ack(n.id);
      } else {
        await notificationsApi.markAsRead(n.id);
      }
      setNotifications(prev => prev.filter(x => x.id !== n.id));
    } catch { /* ignore */ }
  };

  // ── Icon helpers ──────────────────────────────────────────────
  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'parent_request': return '\u{1F4E9}';
      case 'assessment_upcoming': return '\u{1F4DD}';
      case 'assignment_due': return '\u{1F4DA}';
      case 'task_due': return '\u2705';
      default: return '\u{1F514}';
    }
  };

  const getNotificationLabel = (type: string) => {
    switch (type) {
      case 'parent_request': return 'From Parent';
      case 'assessment_upcoming': return 'From Teacher';
      case 'assignment_due': return 'Due Soon';
      case 'task_due': return 'Task Due';
      default: return 'Alert';
    }
  };

  // ── Render ────────────────────────────────────────────────────
  if (initialLoading) {
    return (
      <DashboardLayout welcomeSubtitle="Here's your learning overview">
        <PageSkeleton />
      </DashboardLayout>
    );
  }

  const { overdue, dueToday, upcoming } = urgencyCounts;
  const allClear = overdue === 0 && dueToday === 0 && upcoming === 0;
  const recentGuides = studyGuides.slice(0, 5);

  return (
    <DashboardLayout welcomeSubtitle="Here's your learning overview">
      {statusMessage && (
        <div className={`status-message status-${statusMessage.type}`}>
          {statusMessage.text}
          <FAQErrorHint faqCode={faqCode} />
          {statusMessage.type === 'error' && <ReportBugLink errorMessage={statusMessage.text} />}
        </div>
      )}

      {/* ── Hero Section ─────────────────────────────────── */}
      <section className="sd-hero">
        <div className="sd-hero-text">
          <h1 className="sd-greeting">{greeting}</h1>
          {allClear ? (
            <p className="sd-hero-subtitle sd-all-clear">You're all caught up. Keep it going!</p>
          ) : (
            <p className="sd-hero-subtitle">
              {overdue > 0 && <Link to="/tasks?due=overdue" className="sd-urgency-pill overdue">{overdue} overdue</Link>}
              {dueToday > 0 && <Link to="/tasks?due=today" className="sd-urgency-pill today">{dueToday} due today</Link>}
              {upcoming > 0 && <Link to="/tasks?due=week" className="sd-urgency-pill week">{upcoming} this week</Link>}
            </p>
          )}
        </div>
        <div className="sd-hero-stats">
          {streak > 0 && (
            <Link to="/tasks" className="sd-stat-chip streak sd-stat-chip--link" style={{ textDecoration: 'none' }}>
              <span className="sd-stat-icon">{'\u{1F525}'}</span>
              <span>{streak} day{streak !== 1 ? 's' : ''}</span>
            </Link>
          )}
          <StreakMilestone streak={streak} />
          <StreakHistory studyGuides={studyGuides} />
          {gradeSummary && gradeSummary.courses.length > 0 && (
            <Link to="/grades" className="sd-stat-chip grade" style={{ textDecoration: 'none' }}>
              <span className="sd-stat-icon">{'\u{1F4CA}'}</span>
              <span>{gradeSummary.overall_average}% ({gradeSummary.letter_grade})</span>
            </Link>
          )}
          <Link to="/courses" className="sd-stat-chip sd-stat-chip--link" style={{ textDecoration: 'none' }}>
            <span className="sd-stat-icon">{'\u{1F4DA}'}</span>
            <span>{courses.length} class{courses.length !== 1 ? 'es' : ''}</span>
          </Link>
          <Link to="/course-materials" className="sd-stat-chip sd-stat-chip--link" style={{ textDecoration: 'none' }}>
            <span className="sd-stat-icon">{'\u{1F4DD}'}</span>
            <span>{studyGuides.length} material{studyGuides.length !== 1 ? 's' : ''}</span>
          </Link>
        </div>
      </section>

      {/* ── XP Progress ────────────────────────────────── */}
      <XpDashboardSection />

      {/* ── Quiz of the Day (#2225) ────────────────────── */}
      <QuizOfTheDay />
      {/* ── Best Study Times ─────────────────────────── */}
      <StudyTimeSuggestions />

      {/* ── Assessment Countdown ──────────────────────── */}
      <AssessmentCountdown />

      {/* ── Notification Alerts ──────────────────────────── */}
      {actionableNotifications.length > 0 && (
        <section className="sd-alerts">
          <h2 className="sd-section-label">Needs Your Attention</h2>
          <div className="sd-alerts-list">
            {actionableNotifications.map(n => (
              <div
                key={n.id}
                className={`sd-alert-card ${n.type}`}
                onClick={() => handleNotificationClick(n)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter') handleNotificationClick(n); }}
              >
                <span className="sd-alert-icon">{getNotificationIcon(n.type)}</span>
                <div className="sd-alert-body">
                  <span className="sd-alert-label">{getNotificationLabel(n.type)}</span>
                  <span className="sd-alert-title">{n.title}</span>
                </div>
                <button
                  className="sd-alert-dismiss"
                  onClick={(e) => handleDismissNotification(e, n)}
                  aria-label="Dismiss"
                >{'\u00D7'}</button>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Study Requests from Parent ──────────────────── */}
      <StudyRequestCard requests={pendingStudyRequests} onUpdate={loadStudyRequests} />

      {/* ── Onboarding Tip ───────────────────────────────── */}
      {!onboardingDismissed && studyGuides.length < 3 && (
        <div className="sd-onboarding">
          <div className="sd-onboarding-content">
            <h3>How to add your class materials</h3>
            <ol>
              <li>Download materials from Google Classroom, TeachAssist, or Edsby</li>
              <li>Upload them here using the upload action below</li>
              <li>ClassBridge generates study guides, quizzes, and flashcards automatically</li>
            </ol>
          </div>
          <button
            className="sd-onboarding-dismiss"
            onClick={() => {
              localStorage.setItem('student-upload-onboarding-dismissed', 'true');
              setOnboardingDismissed(true);
            }}
          >Got it</button>
        </div>
      )}

      {/* ── Continue Studying ─────────────────────────────── */}
      <ContinueStudying studyGuides={studyGuides} courses={courses} />

      {/* ── 3-Section Dashboard Grid (#1416) ────────────── */}
      <div className="dashboard-redesign">
        {/* Section 1: My Day */}
        <section className="dash-section dash-section--primary">
          <div className="dash-section-header dash-section-header--collapsible" onClick={toggleMyDay} role="button" tabIndex={0} aria-expanded={!myDayCollapsed} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleMyDay(); } }}>
            <h3 className="dash-section-title">
              <span className="dash-section-title-icon" aria-hidden="true">&#128197;</span>
              My Day
            </h3>
            <div className="dash-section-header-right">
              <Link to="/tasks" className="dash-section-link" onClick={e => e.stopPropagation()}>All tasks</Link>
              <svg className={`dash-section-chevron${myDayCollapsed ? ' dash-section-chevron--collapsed' : ''}`} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg>
            </div>
          </div>
          <div className={`dash-section-body${myDayCollapsed ? ' dash-section-body--collapsed' : ''}`}>
            {timelineItems.length > 0 ? (
              <div className="sd-timeline">
                {timelineItems.slice(0, 8).map(item => (
                  <div
                    key={item.id}
                    className={`sd-timeline-item ${item.urgency}`}
                    onClick={() => { if (item.type === 'task') navigate(`/tasks/${item.sourceId}`); }}
                    role={item.type === 'task' ? 'button' : undefined}
                    tabIndex={item.type === 'task' ? 0 : undefined}
                  >
                    <div className="sd-timeline-dot" />
                    <div className="sd-timeline-content">
                      <span className="sd-timeline-title">{item.title}</span>
                      <div className="sd-timeline-meta">
                        {item.dueDate && <span className={`sd-timeline-date ${item.urgency}`}>{formatRelativeDate(item.dueDate)}</span>}
                        {item.courseName && <span className="sd-timeline-course">{item.courseName}</span>}
                        <span className={`sd-timeline-type ${item.type}`}>{item.type === 'assignment' ? 'Assignment' : 'Task'}</span>
                      </div>
                    </div>
                  </div>
                ))}
                {timelineItems.length > 8 && <Link to="/tasks" className="sd-timeline-more">+{timelineItems.length - 8} more items</Link>}
              </div>
            ) : (
              <EmptyState icon={'\u{1F389}'} title="Nothing coming up" description="You're all clear!" className="sd-empty" />
            )}
            <hr style={{ border: 'none', borderTop: '1px solid var(--color-border)', margin: '16px 0' }} />
            <div className="sd-panel-header" style={{ marginBottom: 8 }}>
              <h4 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Your Courses</h4>
              <div className="sd-courses-actions">
                {googleConnected && <button className="sd-text-btn" onClick={handleSyncWithTypeChoice} disabled={isSyncing}>{isSyncing ? 'Syncing...' : 'Sync'}</button>}
                {googleConnected && <button className="sd-text-btn danger" onClick={handleDisconnectGoogle} disabled={disconnecting}>{disconnecting ? '...' : 'Disconnect'}</button>}
                <button className="sd-text-btn" onClick={() => { setInviteTeacherMsg(null); setInviteTeacherEmail(''); setShowInviteTeacherModal(true); }}>Invite Teacher</button>
              </div>
            </div>
            {courses.length > 0 ? (
              <div className="sd-course-chips">
                {courses.map(course => {
                  const courseGrade = gradeSummary?.courses.find(c => c.course_id === course.id);
                  return (
                    <Link key={course.id} to="/courses" className="sd-course-chip">
                      <span className="sd-course-name">{course.name}</span>
                      {course.google_classroom_id && <span className="sd-google-tag">Google</span>}
                      {courseGrade && <span className={`sd-grade-tag sd-grade-${courseGrade.color}`}>{courseGrade.letter_grade}</span>}
                    </Link>
                  );
                })}
                <button className="sd-course-chip add" onClick={() => setShowCreateCourseModal(true)}>+ Add Class</button>
              </div>
            ) : (
              <EmptyState title="No classes yet" description={gcEnabled ? "Create a class or connect Google Classroom." : "Create a class to get started."} variant="compact" className="sd-empty"
                actions={[{ label: 'Create Class', onClick: () => setShowCreateCourseModal(true) }, ...(gcEnabled && !googleConnected ? [{ label: 'Connect Classroom', onClick: handleConnectGoogle, variant: 'secondary' as const }] : [])]} />
            )}
          </div>
        </section>

        {/* Section 2: Study Materials */}
        <section className="dash-section dash-section--secondary">
          <div className="dash-section-header dash-section-header--collapsible" onClick={toggleMaterials} role="button" tabIndex={0} aria-expanded={!materialsCollapsed} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleMaterials(); } }}>
            <h3 className="dash-section-title">
              <span className="dash-section-title-icon" aria-hidden="true">&#128221;</span>
              Study Materials
            </h3>
            <div className="dash-section-header-right">
              <Link to="/course-materials" className="dash-section-link" onClick={e => e.stopPropagation()}>See all</Link>
              <svg className={`dash-section-chevron${materialsCollapsed ? ' dash-section-chevron--collapsed' : ''}`} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg>
            </div>
          </div>
          <div className={`dash-section-body${materialsCollapsed ? ' dash-section-body--collapsed' : ''}`}>
            {recentGuides.length > 0 ? (
              <div className="sd-materials-list">
                {recentGuides.map(guide => (
                  <Link key={guide.id} to={guide.course_content_id ? `/course-materials/${guide.course_content_id}?tab=${{ quiz: 'quiz', flashcards: 'flashcards', study_guide: 'guide', mind_map: 'mindmap' }[guide.guide_type] || 'guide'}` : guide.guide_type === 'quiz' ? `/study/quiz/${guide.id}` : guide.guide_type === 'flashcards' ? `/study/flashcards/${guide.id}` : `/study/guide/${guide.id}`} className="sd-material-row">
                    <span className="sd-material-icon">{guide.guide_type === 'quiz' ? '\u{2753}' : guide.guide_type === 'flashcards' ? '\u{1F0CF}' : '\u{1F4D6}'}</span>
                    <div className="sd-material-info">
                      <span className="sd-material-title">{guide.title}</span>
                      <span className="sd-material-meta">{guide.guide_type.replace('_', ' ')}{guide.version > 1 && ` \u00B7 v${guide.version}`}</span>
                    </div>
                    <span className="sd-material-date">{new Date(guide.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}</span>
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState icon={'\u{1F4DD}'} title="No study materials yet" description="Upload class materials or paste your notes to generate study guides."
                action={{ label: 'Upload Class Material', onClick: () => studyTools.setShowStudyModal(true) }} className="sd-empty" />
            )}
          </div>
        </section>

        {/* Section 3: Quick Actions */}
        <section className="dash-section dash-section--actions">
          <div className="dash-section-header">
            <h3 className="dash-section-title">Quick Actions</h3>
          </div>
          <div className="dash-quick-actions">
            <button className="dash-quick-action" onClick={() => navigate('/study/session')}>
              <span className="dash-quick-action-icon">&#9202;</span>
              Study Session
            </button>
            <button className="dash-quick-action" onClick={() => navigate('/course-materials')}>
              <span className="dash-quick-action-icon">&#128214;</span>
              View Study Guides
            </button>
            <button className="dash-quick-action" onClick={() => studyTools.setShowStudyModal(true)}>
              <span className="dash-quick-action-icon">&#128228;</span>
              Upload Class Materials
            </button>
            <button className="dash-quick-action" onClick={() => navigate('/tasks')}>
              <span className="dash-quick-action-icon">&#9989;</span>
              Create Tasks
            </button>
            <button className="dash-quick-action" onClick={() => navigate('/messages')}>
              <span className="dash-quick-action-icon">&#128172;</span>
              Send Message
            </button>
          </div>
        </section>
      </div>

      {/* ── Upload / Study Material Modal — same experience as Parent ── */}
      <UploadMaterialWizard
        open={studyTools.showStudyModal}
        onClose={studyTools.resetStudyModal}
        onGenerate={studyTools.handleGenerateFromModal}
        isGenerating={studyTools.isGenerating}
        courses={courses.map(c => ({ id: c.id, name: c.name }))}
        duplicateCheck={studyTools.duplicateCheck}
        onViewExisting={() => {
          const guide = studyTools.duplicateCheck?.existing_guide;
          if (guide) {
            studyTools.resetStudyModal();
            if (guide.course_content_id) {
              const tabMap: Record<string, string> = { quiz: 'quiz', flashcards: 'flashcards', study_guide: 'guide', mind_map: 'mindmap' };
              navigate(`/course-materials/${guide.course_content_id}?tab=${tabMap[guide.guide_type] || 'guide'}`);
            } else if (guide.guide_type === 'quiz') navigate(`/study/quiz/${guide.id}`);
            else if (guide.guide_type === 'flashcards') navigate(`/study/flashcards/${guide.id}`);
            else navigate(`/study/guide/${guide.id}`);
          }
        }}
        onRegenerate={() => studyTools.handleGenerateFromModal({ title: studyTools.studyModalInitialTitle, content: studyTools.studyModalInitialContent, types: ['study_guide'], mode: 'text' })}
        onDismissDuplicate={() => studyTools.setDuplicateCheck(null)}
        showParentNote={false}
      />
      {/* Background generation status banner */}
      {studyTools.backgroundGeneration && (
        <div className={`sd-generation-banner ${studyTools.backgroundGeneration.status}`}>
          {studyTools.backgroundGeneration.status === 'generating' && (
            <span><GenerationSpinner size="sm" /> Generating {studyTools.backgroundGeneration.type}...</span>
          )}
          {studyTools.backgroundGeneration.status === 'success' && (
            <>
              <span>{studyTools.backgroundGeneration.type} ready!</span>
              <button className="sd-gen-view-btn" onClick={() => { navigate(studyTools.getBackgroundGenerationRoute()); studyTools.dismissBackgroundGeneration(); }}>View</button>
              <button className="sd-gen-dismiss-btn" onClick={studyTools.dismissBackgroundGeneration}>&times;</button>
            </>
          )}
          {studyTools.backgroundGeneration.status === 'error' && (
            <>
              <span>Failed to generate {studyTools.backgroundGeneration.type}{studyTools.backgroundGeneration.error ? `: ${studyTools.backgroundGeneration.error}` : ''}</span>
              <button className="sd-gen-dismiss-btn" onClick={studyTools.dismissBackgroundGeneration}>&times;</button>
            </>
          )}
        </div>
      )}

      {/* ── Create Class Modal ──────────────────────────── */}
      {showCreateCourseModal && (
        <div className="modal-overlay" onClick={() => setShowCreateCourseModal(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Create a Class" ref={createCourseModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Create a Class</h2>
            <p className="modal-desc">Add a class or subject to organize your materials.</p>
            <div className="modal-form">
              <label>
                Class Name *
                <input
                  type="text"
                  value={newCourseName}
                  onChange={(e) => setNewCourseName(e.target.value)}
                  placeholder="e.g., Grade 10 Math"
                  disabled={isCreatingCourse}
                  onKeyDown={(e) => e.key === 'Enter' && handleCreateCourse()}
                />
              </label>
              <label>
                Subject (optional)
                <input
                  type="text"
                  value={newCourseSubject}
                  onChange={(e) => setNewCourseSubject(e.target.value)}
                  placeholder="e.g., Mathematics"
                  disabled={isCreatingCourse}
                />
              </label>
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowCreateCourseModal(false)} disabled={isCreatingCourse}>Cancel</button>
              <button className="generate-btn" onClick={handleCreateCourse} disabled={isCreatingCourse || !newCourseName.trim()}>
                {isCreatingCourse ? 'Creating...' : 'Create Class'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Classroom Type Modal (#550) ───────────────────── */}
      {showClassroomTypeModal && (
        <div className="modal-overlay" onClick={() => setShowClassroomTypeModal(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Choose Classroom Type" ref={classroomTypeModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Classroom Type</h2>
            <p className="modal-desc">What type of Google Classroom is this?</p>
            <div className="modal-form">
              <label className={`sd-classroom-type-option${classroomType === 'school' ? ' selected' : ''}`}>
                <input
                  type="radio"
                  name="classroomType"
                  value="school"
                  checked={classroomType === 'school'}
                  onChange={() => setClassroomType('school')}
                />
                <div>
                  <strong>School Classroom</strong>
                  <small>You can view assignments but ClassBridge cannot download school documents.</small>
                </div>
              </label>
              <label className={`sd-classroom-type-option${classroomType === 'private' ? ' selected' : ''}`}>
                <input
                  type="radio"
                  name="classroomType"
                  value="private"
                  checked={classroomType === 'private'}
                  onChange={() => setClassroomType('private')}
                />
                <div>
                  <strong>Private Classroom (Tutor)</strong>
                  <small>Full access to all materials and downloads.</small>
                </div>
              </label>
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowClassroomTypeModal(false)}>Cancel</button>
              <button className="generate-btn" onClick={handleConfirmClassroomType} disabled={isSyncing}>
                {isSyncing ? 'Syncing...' : 'Sync Classes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Invite Teacher Modal ─────────────────────────── */}
      {showInviteTeacherModal && (
        <div className="modal-overlay" onClick={() => setShowInviteTeacherModal(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Invite a Teacher" ref={inviteTeacherModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Invite a Teacher</h2>
            <p className="modal-desc">Enter your teacher's email address. If they don't have an account, they'll receive an invitation.</p>
            <div className="modal-form">
              <label>
                Teacher Email *
                <input
                  type="email"
                  value={inviteTeacherEmail}
                  onChange={(e) => setInviteTeacherEmail(e.target.value)}
                  placeholder="teacher@example.com"
                  disabled={inviteTeacherLoading}
                  onKeyDown={(e) => e.key === 'Enter' && handleInviteTeacher()}
                />
              </label>
              {inviteTeacherMsg && (
                <p className={inviteTeacherMsg.type === 'error' ? 'link-error' : 'link-success'}>
                  {inviteTeacherMsg.text}
                </p>
              )}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowInviteTeacherModal(false)} disabled={inviteTeacherLoading}>Close</button>
              <button className="generate-btn" onClick={handleInviteTeacher} disabled={inviteTeacherLoading || !inviteTeacherEmail.trim()}>
                {inviteTeacherLoading ? 'Sending...' : 'Send Invite'}
              </button>
            </div>
          </div>
        </div>
      )}
      <AILimitRequestModal
        open={studyTools.showLimitModal}
        onClose={() => studyTools.setShowLimitModal(false)}
      />
    </DashboardLayout>
  );
}
