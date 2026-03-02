import { useState, useEffect, useMemo } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { googleApi, coursesApi, assignmentsApi, studyApi, studentApi } from '../api/client';
import type { StudyActivityResponse } from '../api/client';
import { notificationsApi, type NotificationResponse } from '../api/notifications';
import { tasksApi, type TaskItem } from '../api/tasks';
import { invitesApi } from '../api/invites';
import type { StudyGuide } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageSkeleton } from '../components/Skeleton';
import { FAQErrorHint } from '../components/FAQErrorHint';
import { extractFaqCode } from '../utils/faqUtils';
import { useFocusTrap } from '../hooks/useFocusTrap';
import CreateStudyMaterialModal from '../components/CreateStudyMaterialModal';
import { useParentStudyTools } from '../components/parent/hooks/useParentStudyTools';
import { useAuth } from '../context/AuthContext';
import { logger } from '../utils/logger';
import EmptyState from '../components/EmptyState';
import { RoleQuickActions } from '../components/RoleQuickActions';
import type { QuickAction } from '../components/RoleQuickActions';
import { StreakMilestone } from '../components/StreakMilestone';
import { ContinueStudying } from '../components/ContinueStudying';
import { StreakHistory } from '../components/StreakHistory';
import { gradesApi } from '../api/grades';
import type { ChildGradeSummary, ClassroomGradeItem } from '../api/grades';
import { submissionsApi } from '../api/submissions';
import type { SubmissionResponse } from '../api/submissions';
import { SubmitAssignmentModal } from '../components/SubmitAssignmentModal';
import { quizAssignmentsApi } from '../api/quizAssignments';
import type { QuizAssignmentResponse } from '../api/quizAssignments';
import { mockExamsApi } from '../api/mockExams';
import type { MockExamAssignment } from '../api/mockExams';
import './StudentDashboard.css';

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

  const [initialLoading, setInitialLoading] = useState(true);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  // lastSynced state removed — no longer displayed in unified quick actions
  const [courses, setCourses] = useState<Course[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [studyGuides, setStudyGuides] = useState<StudyGuide[]>([]);
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
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

  // Backend streak data (#834)
  const [backendStreak, setBackendStreak] = useState<StudyActivityResponse | null>(null);

  // Assignment submission modal (#839)
  const [submitModalAssignment, setSubmitModalAssignment] = useState<Assignment | null>(null);
  const [submissionsMap, setSubmissionsMap] = useState<Map<number, SubmissionResponse>>(new Map());

  // Assigned quizzes from parents (#664)
  const [assignedQuizzes, setAssignedQuizzes] = useState<QuizAssignmentResponse[]>([]);

  // Assigned mock exams (#667)
  const [assignedExams, setAssignedExams] = useState<MockExamAssignment[]>([]);

  // Invite teacher state
  const [gradeSummary, setGradeSummary] = useState<ChildGradeSummary | null>(null);
  const [recentGrades, setRecentGrades] = useState<ClassroomGradeItem[]>([]);

  const [showInviteTeacherModal, setShowInviteTeacherModal] = useState(false);
  const [inviteTeacherEmail, setInviteTeacherEmail] = useState('');
  const [inviteTeacherLoading, setInviteTeacherLoading] = useState(false);
  const [inviteTeacherMsg, setInviteTeacherMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const createCourseModalRef = useFocusTrap<HTMLDivElement>(showCreateCourseModal, () => setShowCreateCourseModal(false));
  const inviteTeacherModalRef = useFocusTrap<HTMLDivElement>(showInviteTeacherModal, () => setShowInviteTeacherModal(false));
  const classroomTypeModalRef = useFocusTrap<HTMLDivElement>(showClassroomTypeModal, () => setShowClassroomTypeModal(false));

  const justRegistered = searchParams.get('just_registered') === 'true';

  const { user } = useAuth();
  const [onboardingDismissed, setOnboardingDismissed] = useState(() =>
    localStorage.getItem('student-upload-onboarding-dismissed') === 'true'
  );

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

  // Use backend streak if available, fall back to locally computed streak
  const displayStreak = backendStreak ? backendStreak.study_streak_days : streak;

  // Is streak at risk? — last study date was yesterday (streak hasn't been continued today)
  const streakAtRisk = useMemo(() => {
    if (!backendStreak?.last_study_date) return false;
    const lastDate = new Date(backendStreak.last_study_date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    return lastDate.getTime() === yesterday.getTime() && (backendStreak.study_streak_days ?? 0) >= 2;
  }, [backendStreak]);

  // Spaced repetition: study guides not accessed in 3+ days (#834)
  const dueForReview = useMemo(() => {
    const threeDaysAgo = new Date();
    threeDaysAgo.setDate(threeDaysAgo.getDate() - 3);
    return studyGuides
      .filter(g => new Date(g.created_at) < threeDaysAgo)
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
      .slice(0, 3);
  }, [studyGuides]);

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
      loadRecentGrades(),
      loadBackendStreak(),
      loadAssignedQuizzes(),
      loadAssignedExams(),
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
      // Load existing submissions in background (best effort)
      loadSubmissions(data).catch(() => { /* ignore */ });
    } catch {
      // Assignments not loaded
    }
  };

  const loadSubmissions = async (assignmentList: Assignment[]) => {
    if (!assignmentList.length) return;
    const map = new Map<number, SubmissionResponse>();
    await Promise.all(
      assignmentList.map(async (a) => {
        try {
          const sub = await submissionsApi.getSubmission(a.id);
          map.set(a.id, sub);
        } catch {
          // 404 means no submission yet — that's fine
        }
      })
    );
    setSubmissionsMap(map);
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

  const loadRecentGrades = async () => {
    try {
      const data = await gradesApi.getGrades();
      setRecentGrades(data.slice(0, 5));
    } catch {
      // Google not connected or grades unavailable — hide section gracefully
    }
  };

  const loadBackendStreak = async () => {
    try {
      const data = await studentApi.getStreak();
      setBackendStreak(data);
    } catch {
      // Streak not loaded — not critical (student may not have a profile yet)
    }
  };

  const loadAssignedQuizzes = async () => {
    try {
      const data = await quizAssignmentsApi.list({ status: 'assigned' });
      // Also include in_progress
      const inProgress = await quizAssignmentsApi.list({ status: 'in_progress' });
      setAssignedQuizzes([...data, ...inProgress]);
    } catch {
      // Not critical — student may not have a profile or any assignments yet
    }
  };

  const loadAssignedExams = async () => {
    try {
      const data = await mockExamsApi.list() as MockExamAssignment[];
      // Show only assigned or in_progress
      setAssignedExams(data.filter(e => e.status !== 'completed'));
    } catch {
      // Not critical
    }
  };

  // ── Google Actions ────────────────────────────────────────────
  const handleConnectGoogle = async () => {
    setIsConnecting(true);
    try {
      const { authorization_url } = await googleApi.getConnectUrl();
      window.location.href = authorization_url;
    } catch (err) {
      setStatusMessage({ type: 'error', text: 'Failed to initiate Google connection' });
      setFaqCode(extractFaqCode(err));
      setIsConnecting(false);
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
      setStatusMessage({ type: 'success', text: `Course "${newCourseName}" created!` });
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
          {displayStreak > 0 && (
            <div className="sd-stat-chip streak">
              <span className="sd-stat-icon">{'\u{1F525}'}</span>
              <span>{displayStreak} day{displayStreak !== 1 ? 's' : ''}</span>
            </div>
          )}
          <StreakMilestone streak={displayStreak} />
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

      {/* ── Assigned Quizzes (#664) ──────────────────────── */}
      {assignedQuizzes.length > 0 && (
        <section className="sd-assigned-quizzes">
          <h2 className="sd-section-label">Assigned Quizzes</h2>
          <div className="sd-assigned-quizzes-list">
            {assignedQuizzes.map(qa => {
              const difficultyClass = qa.difficulty === 'easy' ? 'easy' : qa.difficulty === 'hard' ? 'hard' : 'medium';
              const difficultyLabel = qa.difficulty.charAt(0).toUpperCase() + qa.difficulty.slice(1);
              return (
                <div key={qa.id} className="sd-assigned-quiz-card">
                  <div className="sd-aq-meta">
                    <span className={`sd-aq-difficulty-badge ${difficultyClass}`}>{difficultyLabel}</span>
                    {qa.due_date && (
                      <span className="sd-aq-due">
                        Due: {new Date(qa.due_date + 'T00:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                      </span>
                    )}
                  </div>
                  <p className="sd-aq-title">{qa.study_guide_title || 'Quiz'}</p>
                  {qa.course_name && <p className="sd-aq-course">{qa.course_name}</p>}
                  {qa.note && <p className="sd-aq-note">"{qa.note}"</p>}
                  <button
                    className="sd-aq-start-btn"
                    onClick={() => navigate(`/study/quiz/${qa.study_guide_id}?assignment=${qa.id}`)}
                    type="button"
                  >
                    Start Quiz
                  </button>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Assigned Mock Exams (#667) ───────────────────── */}
      {assignedExams.length > 0 && (
        <section className="sd-assigned-quizzes">
          <h2 className="sd-section-label">Assigned Exams</h2>
          <div className="sd-assigned-quizzes-list">
            {assignedExams.map(exam => (
              <div key={exam.id} className="sd-assigned-quiz-card">
                <div className="sd-aq-meta">
                  <span className="sd-aq-difficulty-badge medium">
                    {exam.num_questions} questions
                  </span>
                  {exam.time_limit_minutes != null && (
                    <span className="sd-aq-difficulty-badge" style={{ background: '#e0e7ff', color: '#4338ca' }}>
                      {exam.time_limit_minutes} min
                    </span>
                  )}
                  {exam.due_date && (
                    <span className="sd-aq-due">
                      Due: {new Date(exam.due_date + 'T00:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                    </span>
                  )}
                </div>
                <p className="sd-aq-title">{exam.exam_title || 'Mock Exam'}</p>
                {exam.course_name && <p className="sd-aq-course">{exam.course_name}</p>}
                <button
                  className="sd-aq-start-btn"
                  onClick={() => navigate(`/exams/${exam.id}`)}
                  type="button"
                >
                  {exam.status === 'in_progress' ? 'Continue Exam' : 'Start Exam'}
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

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

      {/* ── Google Classroom Banner ──────────────────────── */}
      {!googleConnected && (
        <div className={`sd-google-banner ${justRegistered ? 'welcome' : ''}`}>
          <div className="sd-google-icon">{'\u{1F517}'}</div>
          <div className="sd-google-text">
            <strong>
              {justRegistered ? 'Welcome! Connect your Google Classroom' : 'Connect Google Classroom'}
            </strong>
            <p>
              {justRegistered
                ? 'Your parent invited you to ClassBridge. Connect Google Classroom so they can see your classes and teachers.'
                : 'Sync your classes and assignments automatically.'}
            </p>
          </div>
          <button className="sd-google-btn" onClick={handleConnectGoogle} disabled={isConnecting}>
            {isConnecting ? 'Connecting...' : 'Connect Now'}
          </button>
        </div>
      )}

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

      {/* ── Quick Actions (#837 unified) ────────────────── */}
      <RoleQuickActions
        actions={[
          {
            icon: (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            ),
            label: 'Course Material',
            onClick: () => studyTools.setShowStudyModal(true),
          },
          {
            icon: (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                <line x1="12" y1="6" x2="12" y2="14" />
                <line x1="8" y1="10" x2="16" y2="10" />
              </svg>
            ),
            label: 'New Course',
            onClick: () => setShowCreateCourseModal(true),
          },
          {
            icon: (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
            ),
            label: 'Study Guide',
            onClick: () => studyTools.setShowStudyModal(true),
          },
          googleConnected ? {
            icon: (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="23 4 23 10 17 10" />
                <polyline points="1 20 1 14 7 14" />
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
              </svg>
            ),
            label: isSyncing ? 'Syncing...' : 'Sync Classes',
            onClick: handleSyncWithTypeChoice,
            disabled: isSyncing,
          } : {
            icon: (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
              </svg>
            ),
            label: 'Connect Classroom',
            onClick: handleConnectGoogle,
            disabled: isConnecting,
          },
        ] satisfies QuickAction[]}
        maxVisible={4}
      />

      {/* ── Streak At Risk Banner (#834) ─────────────────── */}
      {streakAtRisk && (
        <div className="sd-streak-at-risk" role="alert">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <span>
            <strong>Keep it up!</strong> Study today to maintain your {displayStreak}-day streak.
          </span>
        </div>
      )}

      {/* ── Continue Studying ─────────────────────────────── */}
      <ContinueStudying studyGuides={studyGuides} courses={courses} />

      {/* ── Due for Review (Spaced Repetition) (#834) ─────── */}
      {dueForReview.length > 0 && (
        <section className="sd-due-review">
          <div className="sd-panel-header">
            <div className="sd-review-title-row">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 6 12 12 16 14"/>
              </svg>
              <h2>Due for Review</h2>
            </div>
            <Link to="/course-materials" className="sd-see-all">See all</Link>
          </div>
          <div className="sd-review-list">
            {dueForReview.map(guide => (
              <Link
                key={guide.id}
                to={
                  guide.guide_type === 'quiz'
                    ? `/study/quiz/${guide.id}`
                    : guide.guide_type === 'flashcards'
                    ? `/study/flashcards/${guide.id}`
                    : `/study/guide/${guide.id}`
                }
                className="sd-review-card"
              >
                <div className="sd-review-card-info">
                  <span className="sd-review-icon">
                    {guide.guide_type === 'quiz' ? '\u{2753}' : guide.guide_type === 'flashcards' ? '\u{1F0CF}' : '\u{1F4D6}'}
                  </span>
                  <div>
                    <div className="sd-review-title">{guide.title}</div>
                    <div className="sd-review-meta">
                      {guide.guide_type.replace('_', ' ')}
                      {' \u00B7 '}
                      Last created {Math.floor((Date.now() - new Date(guide.created_at).getTime()) / 86400000)}d ago
                    </div>
                  </div>
                </div>
                <span className="sd-review-btn">Review Now</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* ── Main Content Grid ────────────────────────────── */}
      <div className="sd-main-grid">
        {/* Coming Up */}
        <section className="sd-panel sd-coming-up">
          <div className="sd-panel-header">
            <h2>Coming Up</h2>
            <Link to="/tasks" className="sd-see-all">All tasks</Link>
          </div>
          {timelineItems.length > 0 ? (
            <div className="sd-timeline">
              {timelineItems.slice(0, 8).map(item => {
                const submission = item.type === 'assignment' ? submissionsMap.get(item.sourceId) : undefined;
                const isSubmitted = submission && (submission.status === 'submitted' || submission.status === 'graded' || submission.status === 'returned');
                const sourceAssignment = item.type === 'assignment' ? assignments.find(a => a.id === item.sourceId) : undefined;
                return (
                  <div
                    key={item.id}
                    className={`sd-timeline-item ${item.urgency}`}
                    onClick={() => {
                      if (item.type === 'task') navigate(`/tasks/${item.sourceId}`);
                    }}
                    role={item.type === 'task' ? 'button' : undefined}
                    tabIndex={item.type === 'task' ? 0 : undefined}
                  >
                    <div className="sd-timeline-dot" />
                    <div className="sd-timeline-content">
                      <span className="sd-timeline-title">{item.title}</span>
                      <div className="sd-timeline-meta">
                        {item.dueDate && (
                          <span className={`sd-timeline-date ${item.urgency}`}>
                            {formatRelativeDate(item.dueDate)}
                          </span>
                        )}
                        {item.courseName && (
                          <span className="sd-timeline-course">{item.courseName}</span>
                        )}
                        <span className={`sd-timeline-type ${item.type}`}>
                          {item.type === 'assignment' ? 'Assignment' : 'Task'}
                        </span>
                      </div>
                    </div>
                    {item.type === 'assignment' && (
                      <div className="sd-timeline-submit">
                        {isSubmitted ? (
                          <span className="sd-submitted-badge">
                            {submission?.status === 'graded' ? 'Graded' : 'Submitted'}
                          </span>
                        ) : (
                          <button
                            className="sd-submit-btn"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (sourceAssignment) setSubmitModalAssignment(sourceAssignment);
                            }}
                            aria-label={`Submit ${item.title}`}
                          >
                            Submit
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
              {timelineItems.length > 8 && (
                <Link to="/tasks" className="sd-timeline-more">
                  +{timelineItems.length - 8} more items
                </Link>
              )}
            </div>
          ) : (
            <EmptyState
              icon={'\u{1F389}'}
              title="Nothing coming up"
              description="You're all clear! Create a course or upload materials to get started."
              className="sd-empty"
            />
          )}
        </section>

        {/* Recent Study Materials */}
        <section className="sd-panel sd-materials">
          <div className="sd-panel-header">
            <h2>Study Materials</h2>
            <Link to="/course-materials" className="sd-see-all">See all</Link>
          </div>
          {recentGuides.length > 0 ? (
            <div className="sd-materials-list">
              {recentGuides.map(guide => (
                <Link
                  key={guide.id}
                  to={
                    guide.guide_type === 'quiz'
                      ? `/study/quiz/${guide.id}`
                      : guide.guide_type === 'flashcards'
                      ? `/study/flashcards/${guide.id}`
                      : `/study/guide/${guide.id}`
                  }
                  className="sd-material-row"
                >
                  <span className="sd-material-icon">
                    {guide.guide_type === 'quiz' ? '\u{2753}' : guide.guide_type === 'flashcards' ? '\u{1F0CF}' : '\u{1F4D6}'}
                  </span>
                  <div className="sd-material-info">
                    <span className="sd-material-title">{guide.title}</span>
                    <span className="sd-material-meta">
                      {guide.guide_type.replace('_', ' ')}
                      {guide.version > 1 && ` \u00B7 v${guide.version}`}
                    </span>
                  </div>
                  <span className="sd-material-date">
                    {new Date(guide.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                  </span>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={'\u{1F4DD}'}
              title="No study materials yet"
              description="Upload class materials or paste your notes to generate study guides."
              action={{ label: 'Create Study Material', onClick: () => studyTools.setShowStudyModal(true) }}
              className="sd-empty"
            />
          )}
        </section>
      </div>

      {/* ── Recent Grades (#838) ─────────────────────────── */}
      {recentGrades.length > 0 && (
        <section className="sd-panel sd-recent-grades">
          <div className="sd-panel-header">
            <h2>Recent Grades</h2>
            <Link to="/grades" className="sd-see-all">View All</Link>
          </div>
          <div className="sd-grades-list">
            {recentGrades.map((g, idx) => {
              const pct = g.percentage;
              const chipColor = pct >= 80 ? 'green' : pct >= 60 ? 'amber' : 'red';
              return (
                <div key={idx} className="sd-grade-row">
                  <div className="sd-grade-row-info">
                    <span className="sd-grade-assignment">{g.assignment_title}</span>
                    <span className="sd-grade-course">{g.course_name}</span>
                  </div>
                  <span className={`sd-grade-chip sd-grade-chip--${chipColor}`}>
                    {g.grade}/{g.max_grade} &mdash; {pct}%
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Courses Section ──────────────────────────────── */}
      <section className="sd-panel sd-courses">
        <div className="sd-panel-header">
          <h2>Your Courses</h2>
          <div className="sd-courses-actions">
            {googleConnected && (
              <button className="sd-text-btn" onClick={handleSyncWithTypeChoice} disabled={isSyncing}>
                {isSyncing ? 'Syncing...' : 'Sync'}
              </button>
            )}
            {googleConnected && (
              <button className="sd-text-btn danger" onClick={handleDisconnectGoogle} disabled={disconnecting}>
                {disconnecting ? '...' : 'Disconnect'}
              </button>
            )}
            <button className="sd-text-btn" onClick={() => { setInviteTeacherMsg(null); setInviteTeacherEmail(''); setShowInviteTeacherModal(true); }}>
              Invite Teacher
            </button>
          </div>
        </div>
        {courses.length > 0 ? (
          <div className="sd-course-chips">
            {courses.map(course => {
              const courseGrade = gradeSummary?.courses.find(c => c.course_id === course.id);
              return (
                <Link key={course.id} to={`/courses`} className="sd-course-chip">
                  <span className="sd-course-name">{course.name}</span>
                  {course.google_classroom_id && <span className="sd-google-tag">Google</span>}
                  {courseGrade && (
                    <span className={`sd-grade-tag sd-grade-${courseGrade.color}`}>
                      {courseGrade.letter_grade}
                    </span>
                  )}
                </Link>
              );
            })}
            <button className="sd-course-chip add" onClick={() => setShowCreateCourseModal(true)}>
              + Add Course
            </button>
          </div>
        ) : (
          <EmptyState
            title="No courses yet"
            description="Create a course or connect Google Classroom to get started."
            variant="compact"
            className="sd-empty"
            actions={[
              { label: 'Create Course', onClick: () => setShowCreateCourseModal(true) },
              ...(!googleConnected ? [{ label: 'Connect Classroom', onClick: handleConnectGoogle, variant: 'secondary' as const }] : []),
            ]}
          />
        )}
      </section>

      {/* ── Upload / Study Material Modal — same experience as Parent ── */}
      <CreateStudyMaterialModal
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
            navigate(guide.guide_type === 'quiz' ? `/study/quiz/${guide.id}` : guide.guide_type === 'flashcards' ? `/study/flashcards/${guide.id}` : `/study/guide/${guide.id}`);
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
            <span><span className="sd-gen-spinner" /> Generating {studyTools.backgroundGeneration.type}...</span>
          )}
          {studyTools.backgroundGeneration.status === 'success' && (
            <>
              <span>{studyTools.backgroundGeneration.type} ready!</span>
              <button className="sd-gen-view-btn" onClick={() => { navigate('/course-materials'); studyTools.dismissBackgroundGeneration(); }}>View</button>
              <button className="sd-gen-dismiss-btn" onClick={studyTools.dismissBackgroundGeneration}>&times;</button>
            </>
          )}
          {studyTools.backgroundGeneration.status === 'error' && (
            <>
              <span>Failed to generate {studyTools.backgroundGeneration.type}</span>
              <button className="sd-gen-dismiss-btn" onClick={studyTools.dismissBackgroundGeneration}>&times;</button>
            </>
          )}
        </div>
      )}

      {/* ── Create Course Modal ──────────────────────────── */}
      {showCreateCourseModal && (
        <div className="modal-overlay" onClick={() => setShowCreateCourseModal(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Create a Course" ref={createCourseModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Create a Course</h2>
            <p className="modal-desc">Add a course or subject to organize your materials.</p>
            <div className="modal-form">
              <label>
                Course Name *
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
                {isCreatingCourse ? 'Creating...' : 'Create Course'}
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

      {/* ── Submit Assignment Modal (#839) ────────────────── */}
      {submitModalAssignment && (
        <SubmitAssignmentModal
          assignmentId={submitModalAssignment.id}
          assignmentTitle={submitModalAssignment.title}
          dueDate={submitModalAssignment.due_date}
          existingSubmission={submissionsMap.get(submitModalAssignment.id) ?? null}
          onSubmitted={(sub) => {
            setSubmissionsMap(prev => {
              const next = new Map(prev);
              next.set(submitModalAssignment.id, sub);
              return next;
            });
          }}
          onClose={() => setSubmitModalAssignment(null)}
        />
      )}
    </DashboardLayout>
  );
}
