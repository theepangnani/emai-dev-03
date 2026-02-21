import { useState, useEffect, useRef, useMemo } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { googleApi, coursesApi, assignmentsApi, studyApi } from '../api/client';
import { invitesApi } from '../api/invites';
import type { StudyGuide, SupportedFormats, DuplicateCheckResponse } from '../api/client';
import { StudyToolsButton } from '../components/StudyToolsButton';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageSkeleton } from '../components/Skeleton';
import { FAQErrorHint } from '../components/FAQErrorHint';
import { extractFaqCode } from '../utils/faqUtils';
import { useConfirm } from '../components/ConfirmModal';
import { useAuth } from '../context/AuthContext';
import type { InspirationData } from '../components/DashboardLayout';
import { logger } from '../utils/logger';
import './StudentDashboard.css';

const MAX_FILE_SIZE_MB = 100;

interface Course {
  id: number;
  name: string;
  google_classroom_id?: string;
}

interface Assignment {
  id: number;
  title: string;
  description: string | null;
  course_id: number;
  due_date: string | null;
}

export function StudentDashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [initialLoading, setInitialLoading] = useState(true);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [courses, setCourses] = useState<Course[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [studyGuides, setStudyGuides] = useState<StudyGuide[]>([]);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [faqCode, setFaqCode] = useState<string | null>(null);

  // Custom study material modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [customTitle, setCustomTitle] = useState('');
  const [customContent, setCustomContent] = useState('');
  const [customType, setCustomType] = useState<'study_guide' | 'quiz' | 'flashcards'>('study_guide');
  const [isGenerating, setIsGenerating] = useState(false);

  // File upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadMode, setUploadMode] = useState<'text' | 'file'>('text');
  const [isDragging, setIsDragging] = useState(false);
  const [supportedFormats, setSupportedFormats] = useState<SupportedFormats | null>(null);
  const [courseFilter, setCourseFilter] = useState<number | ''>('');
  const [duplicateCheck, setDuplicateCheck] = useState<DuplicateCheckResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { confirm, confirmModal } = useConfirm();

  // Invite teacher state
  const [showInviteTeacherModal, setShowInviteTeacherModal] = useState(false);
  const [inviteTeacherEmail, setInviteTeacherEmail] = useState('');
  const [inviteTeacherLoading, setInviteTeacherLoading] = useState(false);
  const [inviteTeacherMsg, setInviteTeacherMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const justRegistered = searchParams.get('just_registered') === 'true';

  const { user } = useAuth();
  const [focusDismissed, setFocusDismissed] = useState(false);

  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    const firstName = user?.full_name?.split(' ')[0] || 'there';
    if (hour < 12) return `Good morning, ${firstName}!`;
    if (hour < 17) return `Good afternoon, ${firstName}!`;
    return `Good evening, ${firstName}!`;
  }, [user?.full_name]);

  const urgencyCounts = useMemo(() => {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const todayEnd = new Date(todayStart);
    todayEnd.setDate(todayEnd.getDate() + 1);
    const weekEnd = new Date(todayStart);
    weekEnd.setDate(weekEnd.getDate() + 7);

    let overdue = 0;
    let dueToday = 0;
    let upcoming = 0;

    for (const a of assignments) {
      if (!a.due_date) continue;
      const due = new Date(a.due_date);
      if (due < todayStart) overdue++;
      else if (due < todayEnd) dueToday++;
      else if (due < weekEnd) upcoming++;
    }
    return { overdue, dueToday, upcoming };
  }, [assignments]);

  type UrgencyTier = 'overdue' | 'today' | 'week' | 'later';

  const getUrgencyTier = (dueDate: string | null): UrgencyTier => {
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
  };

  const groupedAssignments = useMemo(() => {
    const groups: Record<UrgencyTier, Assignment[]> = {
      overdue: [], today: [], week: [], later: [],
    };
    for (const a of assignments) {
      groups[getUrgencyTier(a.due_date)].push(a);
    }
    // Sort within each group by due date (nearest first)
    for (const tier of Object.keys(groups) as UrgencyTier[]) {
      groups[tier].sort((a, b) => {
        if (!a.due_date) return 1;
        if (!b.due_date) return -1;
        return new Date(a.due_date).getTime() - new Date(b.due_date).getTime();
      });
    }
    return groups;
  }, [assignments]);

  const dueThisWeekCount = groupedAssignments.overdue.length + groupedAssignments.today.length + groupedAssignments.week.length;

  const TIER_LABELS: Record<UrgencyTier, string> = {
    overdue: 'Overdue', today: 'Due Today', week: 'This Week', later: 'Later',
  };

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
      setStatusMessage({ type: 'success', text: 'Google Classroom connected successfully!' });
      // Auto-sync courses after Google connection
      googleApi.syncCourses().then((result) => {
        setStatusMessage({ type: 'success', text: result.message || 'Classes synced!' });
        loadCourses();
        loadAssignments();
      }).catch(() => {});
      // Clear the param but keep just_registered if present
      const newParams: Record<string, string> = {};
      if (searchParams.get('just_registered')) newParams.just_registered = 'true';
      setSearchParams(newParams);
    } else if (error) {
      setStatusMessage({ type: 'error', text: `Connection failed: ${error}` });
      setFaqCode('GOOGLE_SYNC_FAILED');
      setSearchParams({});
    }

    Promise.all([checkGoogleStatus(), loadCourses(), loadAssignments(), loadStudyGuides()])
      .finally(() => setInitialLoading(false));
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

  const loadStudyGuides = async (filterCourseId?: number) => {
    try {
      const params: { course_id?: number } = {};
      if (filterCourseId) params.course_id = filterCourseId;
      const data = await studyApi.listGuides(params);
      setStudyGuides(data);
    } catch {
      // Study guides not loaded
    }
  };

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
    try {
      await googleApi.disconnect();
      setGoogleConnected(false);
      setStatusMessage({ type: 'success', text: 'Google Classroom disconnected' });
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to disconnect Google Classroom' });
    }
  };

  const handleSyncCourses = async () => {
    setIsSyncing(true);
    setStatusMessage(null);
    try {
      const result = await googleApi.syncCourses();
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

  useEffect(() => {
    if (statusMessage) {
      const timer = setTimeout(() => { setStatusMessage(null); setFaqCode(null); }, 5000);
      return () => clearTimeout(timer);
    }
  }, [statusMessage]);

  useEffect(() => {
    if (showCreateModal && !supportedFormats) {
      studyApi.getSupportedFormats().then(setSupportedFormats).catch(() => {});
    }
  }, [showCreateModal, supportedFormats]);

  const handleFileSelect = (file: File) => {
    const fileSizeMB = file.size / (1024 * 1024);
    logger.info('File selected for upload', { filename: file.name, sizeMB: fileSizeMB.toFixed(2) });

    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      logger.warn('File too large', { filename: file.name, sizeMB: fileSizeMB.toFixed(2), maxMB: MAX_FILE_SIZE_MB });
      setStatusMessage({ type: 'error', text: `File size exceeds ${MAX_FILE_SIZE_MB} MB limit` });
      return;
    }
    setSelectedFile(file);
    setUploadMode('file');
    if (!customTitle) {
      const baseName = file.name.replace(/\.[^/.]+$/, '');
      setCustomTitle(baseName);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const clearFileSelection = () => {
    setSelectedFile(null);
    setUploadMode('text');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const resetModal = () => {
    setShowCreateModal(false);
    setCustomTitle('');
    setCustomContent('');
    setSelectedFile(null);
    setUploadMode('text');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleCreateCustom = async () => {
    if (uploadMode === 'file') {
      if (!selectedFile) {
        setStatusMessage({ type: 'error', text: 'Please select a file to upload' });
        return;
      }
    } else {
      if (!customContent.trim()) {
        setStatusMessage({ type: 'error', text: 'Please enter some content' });
        return;
      }
    }

    if (!duplicateCheck) {
      const ok = await confirm({
        title: 'Generate Study Material',
        message: `Generate ${customType.replace('_', ' ')}? This will use AI credits.`,
        confirmLabel: 'Generate',
      });
      if (!ok) return;
    }

    logger.info('Generating study material', {
      mode: uploadMode,
      type: customType,
      filename: selectedFile?.name,
      contentLength: customContent.length,
    });

    // Check for duplicates before generating (skip for file uploads)
    if (uploadMode === 'text' && !duplicateCheck) {
      try {
        const dupResult = await studyApi.checkDuplicate({
          title: customTitle || undefined,
          guide_type: customType,
        });
        if (dupResult.exists) {
          setDuplicateCheck(dupResult);
          return;
        }
      } catch {
        // Continue with generation if check fails
      }
    }
    setDuplicateCheck(null);

    setIsGenerating(true);
    try {
      let result;
      const regenerateId = duplicateCheck?.existing_guide?.id;

      if (uploadMode === 'file' && selectedFile) {
        result = await studyApi.generateFromFile({
          file: selectedFile,
          title: customTitle || undefined,
          guide_type: customType,
          num_questions: 5,
          num_cards: 10,
        });
      } else {
        if (customType === 'quiz') {
          result = await studyApi.generateQuiz({
            topic: customTitle || 'Custom Quiz',
            content: customContent,
            num_questions: 5,
            regenerate_from_id: regenerateId,
          });
        } else if (customType === 'flashcards') {
          result = await studyApi.generateFlashcards({
            topic: customTitle || 'Custom Flashcards',
            content: customContent,
            num_cards: 10,
            regenerate_from_id: regenerateId,
          });
        } else {
          result = await studyApi.generateGuide({
            title: customTitle || 'Custom Study Guide',
            content: customContent,
            regenerate_from_id: regenerateId,
          });
        }
      }

      logger.info('Study material generated successfully', { id: result.id, type: customType });

      if (customType === 'quiz') {
        navigate(`/study/quiz/${result.id}`);
      } else if (customType === 'flashcards') {
        navigate(`/study/flashcards/${result.id}`);
      } else {
        navigate(`/study/guide/${result.id}`);
      }

      resetModal();
    } catch (err) {
      logger.logError(err, 'Failed to generate study material', { mode: uploadMode, type: customType });
      setStatusMessage({ type: 'error', text: 'Failed to generate study material' });
    } finally {
      setIsGenerating(false);
    }
  };

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

  const renderHeaderSlot = (inspiration: InspirationData | null) => {
    if (focusDismissed) return null;

    const { overdue, dueToday, upcoming } = urgencyCounts;
    const allClear = overdue === 0 && dueToday === 0 && upcoming === 0;

    return (
      <div className="student-focus-header">
        <div className="student-focus-main">
          <div className="student-focus-greeting">{greeting}</div>
          {allClear ? (
            <div className="student-focus-status all-clear">
              <span className="student-focus-icon">{'\u2705'}</span>
              <span>All caught up! Keep up the great work.</span>
            </div>
          ) : (
            <div className="student-focus-status">
              <span className="student-focus-icon">{overdue > 0 ? '\u{1F525}' : '\u{1F4CB}'}</span>
              <div className="student-focus-items">
                {overdue > 0 && (
                  <button type="button" className="student-focus-tag overdue" onClick={() => navigate('/tasks?due=overdue')}>{overdue} overdue</button>
                )}
                {dueToday > 0 && (
                  <button type="button" className="student-focus-tag today" onClick={() => navigate('/tasks?due=today')}>{dueToday} due today</button>
                )}
                {upcoming > 0 && (
                  <button type="button" className="student-focus-tag upcoming" onClick={() => navigate('/tasks?due=week')}>{upcoming} this week</button>
                )}
              </div>
            </div>
          )}
        </div>
        {inspiration && (
          <div className="student-focus-inspiration">
            <span className="student-focus-quote">"{inspiration.text}"</span>
            {inspiration.author && (
              <span className="student-focus-author"> — {inspiration.author}</span>
            )}
          </div>
        )}
        <button
          className="student-focus-close"
          onClick={() => setFocusDismissed(true)}
          aria-label="Dismiss"
        >
          {'\u00D7'}
        </button>
      </div>
    );
  };

  if (initialLoading) {
    return (
      <DashboardLayout welcomeSubtitle="Here's your learning overview">
        <PageSkeleton />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle="Here's your learning overview" headerSlot={renderHeaderSlot}>
      {statusMessage && (
        <div className={`status-message status-${statusMessage.type}`}>
          {statusMessage.text}
          <FAQErrorHint faqCode={faqCode} />
        </div>
      )}

      {!googleConnected && (
        <div className={`onboarding-banner ${justRegistered ? 'welcome' : 'standard'}`}>
          <div className="onboarding-icon">🔗</div>
          <div className="onboarding-text">
            <strong className="onboarding-title">
              {justRegistered ? 'Welcome! Connect your Google Classroom' : 'Connect Google Classroom'}
            </strong>
            <p className="onboarding-subtitle">
              {justRegistered
                ? 'Your parent invited you to EMAI. Connect Google Classroom so they can see your classes and teachers.'
                : 'Connect your Google Classroom so your parent can see your classes and track your progress.'}
            </p>
          </div>
          <button
            className="connect-button onboarding-action"
            onClick={handleConnectGoogle}
            disabled={isConnecting}
          >
            {isConnecting ? 'Connecting...' : 'Connect Now'}
          </button>
        </div>
      )}

      <div className="dashboard-grid">
        <div className="dashboard-card">
          <div className="card-icon">📚</div>
          <h3>Classes</h3>
          <p className="card-value">{courses.length || '--'}</p>
          <p className="card-label">Active classes</p>
        </div>

        <div className="dashboard-card">
          <div className="card-icon">📝</div>
          <h3>Assignments</h3>
          <p className="card-value">{assignments.length || '--'}</p>
          <p className="card-label">Total assignments</p>
        </div>

        <div className="dashboard-card">
          <div className="card-icon">📖</div>
          <h3>Study Materials</h3>
          <p className="card-value">{studyGuides.length || '--'}</p>
          <p className="card-label">Guides, quizzes & flashcards</p>
        </div>

        <div className="dashboard-card streak-card">
          <div className="card-icon">🔥</div>
          <h3>Study Streak</h3>
          <p className="card-value">{calculateStreak(studyGuides)}</p>
          <p className="card-label">{calculateStreak(studyGuides) === 1 ? 'day' : 'days'} in a row</p>
        </div>

        <div className="dashboard-card">
          <div className="card-icon">🔗</div>
          <h3>Google Classroom</h3>
          <p className="card-value">{googleConnected ? 'Connected' : 'Not Connected'}</p>
          {googleConnected ? (
            <div className="card-buttons">
              <button className="connect-button" onClick={handleSyncCourses} disabled={isSyncing}>
                {isSyncing ? 'Syncing...' : 'Sync Classes'}
              </button>
              <button className="disconnect-button" onClick={handleDisconnectGoogle}>
                Disconnect
              </button>
            </div>
          ) : (
            <button className="connect-button" onClick={handleConnectGoogle} disabled={isConnecting}>
              {isConnecting ? 'Connecting...' : 'Connect'}
            </button>
          )}
        </div>
      </div>

      <div className="dashboard-sections">
        <section className="section">
          <h3>Your Assignments</h3>
          {assignments.length > 0 ? (
            <>
              {dueThisWeekCount > 0 && (
                <div className="student-assignments-summary">
                  <span className="student-due-week-count">{dueThisWeekCount} due this week</span>
                </div>
              )}
              <ul className="assignments-list">
                {(['overdue', 'today', 'week', 'later'] as UrgencyTier[]).map(tier => {
                  const items = groupedAssignments[tier];
                  if (items.length === 0) return null;
                  return (
                    <li key={tier} className="student-assignment-group">
                      <div className={`student-assignment-group-header ${tier}`}>
                        {TIER_LABELS[tier]} ({items.length})
                      </div>
                      <ul className="student-assignment-group-list">
                        {items.map((assignment) => (
                          <li key={assignment.id} className="assignment-item">
                            <div className="assignment-info">
                              <span className="assignment-title">{assignment.title}</span>
                              <span className={`student-due-badge ${tier}`}>
                                {assignment.due_date
                                  ? new Date(assignment.due_date).toLocaleDateString()
                                  : 'No due date'}
                              </span>
                            </div>
                            <StudyToolsButton assignmentId={assignment.id} assignmentTitle={assignment.title} />
                          </li>
                        ))}
                      </ul>
                    </li>
                  );
                })}
              </ul>
            </>
          ) : (
            <div className="empty-state">
              <p>No assignments yet</p>
              <small>Sync your Google Classroom to see assignments</small>
            </div>
          )}
        </section>

        <section className="section">
          <div className="section-header">
            <h3>Your Study Materials</h3>
            <button className="create-custom-btn" onClick={() => setShowCreateModal(true)}>
              + Create Custom
            </button>
          </div>
          {courses.length > 0 && (
            <div className="course-filter">
              <select
                value={courseFilter}
                onChange={(e) => {
                  const val = e.target.value ? Number(e.target.value) : '';
                  setCourseFilter(val);
                  loadStudyGuides(val || undefined);
                }}
              >
                <option value="">All Classes</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
          )}
          {studyGuides.length > 0 ? (
            <ul className="study-guides-list">
              {studyGuides.map((guide) => (
                <li key={guide.id} className="study-guide-item">
                  <Link
                    to={
                      guide.guide_type === 'quiz'
                        ? `/study/quiz/${guide.id}`
                        : guide.guide_type === 'flashcards'
                        ? `/study/flashcards/${guide.id}`
                        : `/study/guide/${guide.id}`
                    }
                    className="study-guide-link"
                  >
                    <span className="guide-icon">
                      {guide.guide_type === 'quiz' ? '?' : guide.guide_type === 'flashcards' ? '🃏' : '📖'}
                    </span>
                    <span className="guide-title">{guide.title}</span>
                    {guide.version > 1 && (
                      <span className="version-badge">v{guide.version}</span>
                    )}
                    <span className="guide-date">
                      {new Date(guide.created_at).toLocaleDateString()}
                    </span>
                  </Link>
                  {courses.length > 0 && (
                    <select
                      className="inline-course-select"
                      title="Assign to class"
                      value={guide.course_id ?? ''}
                      onClick={(e) => e.preventDefault()}
                      onChange={async (e) => {
                        e.preventDefault();
                        const newCourseId = e.target.value === '' ? null : parseInt(e.target.value);
                        try {
                          await studyApi.updateGuide(guide.id, { course_id: newCourseId });
                          setStudyGuides(prev => prev.map(g => g.id === guide.id ? { ...g, course_id: newCourseId } : g));
                        } catch { /* ignore */ }
                      }}
                    >
                      <option value="">No class</option>
                      {courses.map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  )}
                  <button
                    className="delete-guide-btn"
                    title="Delete"
                    onClick={async (e) => {
                      e.preventDefault();
                      await studyApi.deleteGuide(guide.id);
                      setStudyGuides(prev => prev.filter(g => g.id !== guide.id));
                    }}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty-state">
              <p>No study materials yet</p>
              <small>Click "Create Custom" to generate class materials from any content</small>
            </div>
          )}
        </section>

        <section className="section">
          <div className="section-header">
            <h3>Your Classes</h3>
            <button className="create-custom-btn" onClick={() => { setInviteTeacherMsg(null); setInviteTeacherEmail(''); setShowInviteTeacherModal(true); }}>
              + Invite Teacher
            </button>
          </div>
          {courses.length > 0 ? (
            <ul className="courses-list">
              {courses.map((course) => (
                <li key={course.id} className="course-item">
                  <span className="course-name">{course.name}</span>
                  {course.google_classroom_id && (
                    <span className="google-badge">Google</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty-state">
              <p>No classes yet</p>
              <small>Connect Google Classroom to sync your classes</small>
            </div>
          )}
        </section>
      </div>

      {/* Create Custom Study Material Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => resetModal()}>
          <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
            <h2>Create Study Material</h2>

            <div className="mode-toggle">
              <button
                className={`mode-btn ${uploadMode === 'text' ? 'active' : ''}`}
                onClick={() => setUploadMode('text')}
                disabled={isGenerating}
              >
                Paste Text
              </button>
              <button
                className={`mode-btn ${uploadMode === 'file' ? 'active' : ''}`}
                onClick={() => setUploadMode('file')}
                disabled={isGenerating}
              >
                Upload File
              </button>
            </div>

            <div className="modal-form">
              <label>
                Title (optional)
                <input
                  type="text"
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                  placeholder="e.g., Chapter 5 Review"
                  disabled={isGenerating}
                />
              </label>

              {uploadMode === 'text' ? (
                <label>
                  Content to study
                  <textarea
                    value={customContent}
                    onChange={(e) => setCustomContent(e.target.value)}
                    placeholder="Paste your notes, textbook content, or any material you want to study..."
                    rows={8}
                    disabled={isGenerating}
                  />
                </label>
              ) : (
                <div className="file-upload-section">
                  <input
                    ref={fileInputRef}
                    type="file"
                    onChange={handleFileInputChange}
                    accept=".pdf,.docx,.doc,.txt,.md,.xlsx,.xls,.csv,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.webp,.zip"
                    style={{ display: 'none' }}
                    disabled={isGenerating}
                  />

                  <div
                    className={`drop-zone ${isDragging ? 'dragging' : ''} ${selectedFile ? 'has-file' : ''}`}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => !isGenerating && fileInputRef.current?.click()}
                  >
                    {selectedFile ? (
                      <div className="selected-file">
                        <span className="file-icon">📄</span>
                        <div className="file-info">
                          <span className="file-name">{selectedFile.name}</span>
                          <span className="file-size">
                            {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                          </span>
                        </div>
                        <button
                          className="clear-file-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            clearFileSelection();
                          }}
                          disabled={isGenerating}
                        >
                          x
                        </button>
                      </div>
                    ) : (
                      <div className="drop-zone-content">
                        <span className="upload-icon">📁</span>
                        <p>Drag & drop a file here, or click to browse</p>
                        <small>
                          Supports: PDF, Word, Excel, PowerPoint, Images, Text, ZIP
                          <br />
                          Max size: {MAX_FILE_SIZE_MB} MB
                        </small>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <label>
                Generate as
                <select
                  value={customType}
                  onChange={(e) => setCustomType(e.target.value as 'study_guide' | 'quiz' | 'flashcards')}
                  disabled={isGenerating}
                >
                  <option value="study_guide">Study Guide</option>
                  <option value="quiz">Practice Quiz</option>
                  <option value="flashcards">Flashcards</option>
                </select>
              </label>
            </div>

            {duplicateCheck && duplicateCheck.exists && (
              <div className="duplicate-warning">
                <p>{duplicateCheck.message}</p>
                <div className="duplicate-actions">
                  <button
                    className="generate-btn"
                    onClick={() => {
                      const guide = duplicateCheck.existing_guide!;
                      resetModal();
                      navigate(
                        guide.guide_type === 'quiz' ? `/study/quiz/${guide.id}`
                          : guide.guide_type === 'flashcards' ? `/study/flashcards/${guide.id}`
                          : `/study/guide/${guide.id}`
                      );
                    }}
                  >
                    View Existing
                  </button>
                  <button className="generate-btn" onClick={handleCreateCustom}>
                    Regenerate (New Version)
                  </button>
                  <button className="cancel-btn" onClick={() => setDuplicateCheck(null)}>
                    Cancel
                  </button>
                </div>
              </div>
            )}

            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => { resetModal(); setDuplicateCheck(null); }} disabled={isGenerating}>
                Cancel
              </button>
              <button
                className="generate-btn"
                onClick={handleCreateCustom}
                disabled={isGenerating || (uploadMode === 'file' ? !selectedFile : !customContent.trim())}
              >
                {isGenerating ? 'Generating...' : 'Generate'}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Invite Teacher Modal */}
      {showInviteTeacherModal && (
        <div className="modal-overlay" onClick={() => setShowInviteTeacherModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
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
      {confirmModal}
    </DashboardLayout>
  );
}
