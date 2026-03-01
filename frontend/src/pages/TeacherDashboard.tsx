import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { coursesApi, googleApi, invitesApi, messagesApi, assignmentsApi, courseContentsApi } from '../api/client';
import type { GoogleAccount, InviteResponse, ConversationSummary, AssignmentItem } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import type { InspirationData } from '../components/DashboardLayout';
import { useFocusTrap } from '../hooks/useFocusTrap';
import { isValidEmail } from '../utils/validation';
import { PageSkeleton } from '../components/Skeleton';
import EmptyState from '../components/EmptyState';
import { RoleQuickActions } from '../components/RoleQuickActions';
import type { QuickAction } from '../components/RoleQuickActions';
import { TeacherCourseManagement } from '../components/TeacherCourseManagement';
import { GoogleCalendarSync } from '../components/GoogleCalendarSync';
import './TeacherDashboard.css';

interface Course {
  id: number;
  name: string;
  description: string | null;
  subject: string | null;
  google_classroom_id: string | null;
  student_count: number;
}

export function TeacherDashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [courses, setCourses] = useState<Course[]>([]);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');

  // Activity summary state
  const [unreadCount, setUnreadCount] = useState(0);
  const [recentConversations, setRecentConversations] = useState<ConversationSummary[]>([]);
  const [upcomingAssignments, setUpcomingAssignments] = useState<AssignmentItem[]>([]);
  const [focusDismissed, setFocusDismissed] = useState(false);

  // Create course modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [courseName, setCourseName] = useState('');
  const [courseSubject, setCourseSubject] = useState('');
  const [courseDescription, setCourseDescription] = useState('');
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState('');

  // Invite parent modal state
  const [showInviteParentModal, setShowInviteParentModal] = useState(false);
  const [inviteParentEmail, setInviteParentEmail] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteError, setInviteError] = useState('');
  const [inviteSuccess, setInviteSuccess] = useState('');

  // Google accounts state
  const [googleAccounts, setGoogleAccounts] = useState<GoogleAccount[]>([]);
  const [removingAccountId, setRemovingAccountId] = useState<number | null>(null);
  const [editingLabelId, setEditingLabelId] = useState<number | null>(null);
  const [editingLabelValue, setEditingLabelValue] = useState('');
  const [savingLabelId, setSavingLabelId] = useState<number | null>(null);

  // Sent invites state
  const [sentInvites, setSentInvites] = useState<InviteResponse[]>([]);
  const [resendingId, setResendingId] = useState<number | null>(null);
  const [resentToastId, setResentToastId] = useState<number | null>(null);
  const [invitesExpanded, setInvitesExpanded] = useState(true);
  const [googleAccountsExpanded, setGoogleAccountsExpanded] = useState(true);
  const [resendError, setResendError] = useState<string | null>(null);
  // Announcement modal state
  const [showAnnounceModal, setShowAnnounceModal] = useState(false);
  const [announceCourseId, setAnnounceCourseId] = useState<number | ''>('');
  const [announceSubject, setAnnounceSubject] = useState('');
  const [announceBody, setAnnounceBody] = useState('');
  const [announceSending, setAnnounceSending] = useState(false);
  const [announceError, setAnnounceError] = useState('');
  const [announceSuccess, setAnnounceSuccess] = useState('');
  const [announcePreview, setAnnouncePreview] = useState(false);

  // Upload material modal state
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadCourseId, setUploadCourseId] = useState<number | ''>('');
  const [uploadType, setUploadType] = useState('notes');
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadDescription, setUploadDescription] = useState('');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDragging, setUploadDragging] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');

  // Focus traps for modals (must be after state declarations they reference)
  const createCourseModalRef = useFocusTrap<HTMLDivElement>(showCreateModal, () => setShowCreateModal(false));
  const inviteParentModalRef = useFocusTrap<HTMLDivElement>(showInviteParentModal, () => setShowInviteParentModal(false));
  const announceModalRef = useFocusTrap<HTMLDivElement>(showAnnounceModal, () => setShowAnnounceModal(false));
  const uploadModalRef = useFocusTrap<HTMLDivElement>(showUploadModal, () => setShowUploadModal(false));

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [coursesData, googleStatus, accountsData, invitesData, unreadData, conversationsData, assignmentsData] = await Promise.allSettled([
        coursesApi.teachingList(),
        googleApi.getStatus(),
        googleApi.getTeacherAccounts(),
        invitesApi.listSent(),
        messagesApi.getUnreadCount(),
        messagesApi.listConversations({ limit: 3 }),
        assignmentsApi.list(),
      ]);

      if (coursesData.status === 'fulfilled') {
        setCourses(coursesData.value);
      }
      if (googleStatus.status === 'fulfilled') {
        setGoogleConnected(googleStatus.value.connected);
      }
      if (accountsData.status === 'fulfilled') {
        setGoogleAccounts(accountsData.value);
      }
      if (invitesData.status === 'fulfilled') {
        setSentInvites(invitesData.value);
      }
      if (unreadData.status === 'fulfilled') {
        setUnreadCount(unreadData.value.total_unread);
      }
      if (conversationsData.status === 'fulfilled') {
        setRecentConversations(conversationsData.value.slice(0, 3));
      }
      if (assignmentsData.status === 'fulfilled') {
        const now = new Date();
        const sevenDays = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
        const upcoming = assignmentsData.value
          .filter((a: AssignmentItem) => a.due_date && new Date(a.due_date) >= now && new Date(a.due_date) <= sevenDays)
          .sort((a: AssignmentItem, b: AssignmentItem) => new Date(a.due_date!).getTime() - new Date(b.due_date!).getTime());
        setUpcomingAssignments(upcoming);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleConnectGoogle = async () => {
    try {
      const { authorization_url } = await googleApi.getConnectUrl();
      window.location.href = authorization_url;
    } catch {
      // Failed to connect
    }
  };

  const handleSyncCourses = async () => {
    setSyncing(true);
    setSyncMessage('');
    try {
      const result = await googleApi.syncCourses();
      // Reload courses after sync
      const coursesData = await coursesApi.teachingList();
      setCourses(coursesData);
      setSyncMessage(result.message || 'Sync complete');
      setTimeout(() => setSyncMessage(''), 5000);
    } catch {
      setSyncMessage('Sync failed. Please try again.');
      setTimeout(() => setSyncMessage(''), 5000);
    } finally {
      setSyncing(false);
    }
  };

  const closeCreateModal = () => {
    setShowCreateModal(false);
    setCourseName('');
    setCourseSubject('');
    setCourseDescription('');
    setCreateError('');
  };

  const handleCreateCourse = async () => {
    if (!courseName.trim()) return;
    setCreateLoading(true);
    setCreateError('');
    try {
      await coursesApi.create({
        name: courseName.trim(),
        description: courseDescription.trim() || undefined,
        subject: courseSubject.trim() || undefined,
      });
      closeCreateModal();
      const coursesData = await coursesApi.teachingList();
      setCourses(coursesData);
    } catch (err: any) {
      setCreateError(err.response?.data?.detail || 'Failed to create class');
    } finally {
      setCreateLoading(false);
    }
  };

  const handleAddGoogleAccount = async () => {
    try {
      const { authorization_url } = await googleApi.getConnectUrl(true);
      window.location.href = authorization_url;
    } catch {
      // Failed to start add-account flow
    }
  };

  const handleRemoveAccount = async (accountId: number) => {
    setRemovingAccountId(accountId);
    try {
      await googleApi.removeTeacherAccount(accountId);
      setGoogleAccounts(prev => prev.filter(a => a.id !== accountId));
    } catch {
      // Failed to remove
    } finally {
      setRemovingAccountId(null);
    }
  };

  const handleSetPrimary = async (accountId: number) => {
    try {
      await googleApi.updateTeacherAccount(accountId, undefined, true);
      setGoogleAccounts(prev => prev.map(a => ({ ...a, is_primary: a.id === accountId })));
    } catch {
      // Failed to set primary
    }
  };

  const handleStartEditLabel = (account: GoogleAccount) => {
    setEditingLabelId(account.id);
    setEditingLabelValue(account.account_label ?? '');
  };

  const handleSaveLabel = async (accountId: number) => {
    setSavingLabelId(accountId);
    try {
      await googleApi.updateTeacherAccount(accountId, editingLabelValue.trim() || undefined);
      setGoogleAccounts(prev =>
        prev.map(a => a.id === accountId ? { ...a, account_label: editingLabelValue.trim() || null } : a)
      );
      setEditingLabelId(null);
    } catch {
      // Failed to save label
    } finally {
      setSavingLabelId(null);
    }
  };

  const handleCancelEditLabel = () => {
    setEditingLabelId(null);
    setEditingLabelValue('');
  };

  const handleResendInvite = async (inviteId: number) => {
    setResendingId(inviteId);
    setResendError(null);
    try {
      const updated = await invitesApi.resend(inviteId);
      setSentInvites(prev => prev.map(i => i.id === inviteId ? updated : i));
      setResentToastId(inviteId);
      setTimeout(() => setResentToastId(null), 3000);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 429 && detail) {
        setResendError(detail);
        setTimeout(() => setResendError(null), 5000);
      }
    }
    setResendingId(null);
  };

  const isResendCoolingDown = (invite: InviteResponse): boolean => {
    if (!invite.last_resent_at) return false;
    const lastResent = new Date(invite.last_resent_at).getTime();
    const oneHour = 60 * 60 * 1000;
    return Date.now() - lastResent < oneHour;
  };

  const getResendCooldownMinutes = (invite: InviteResponse): number => {
    if (!invite.last_resent_at) return 0;
    const lastResent = new Date(invite.last_resent_at).getTime();
    const oneHour = 60 * 60 * 1000;
    const remaining = oneHour - (Date.now() - lastResent);
    return Math.max(0, Math.ceil(remaining / 60000));
  };

  const closeInviteParentModal = () => {
    setShowInviteParentModal(false);
    setInviteParentEmail('');
    setInviteError('');
    setInviteSuccess('');
  };

  const handleInviteParent = async () => {
    if (!inviteParentEmail.trim()) return;
    if (!isValidEmail(inviteParentEmail.trim())) {
      setInviteError('Please enter a valid email address');
      return;
    }
    setInviteLoading(true);
    setInviteError('');
    setInviteSuccess('');
    try {
      const result = await invitesApi.inviteParent(inviteParentEmail.trim());
      if (result.action === 'message_sent') {
        setInviteSuccess(result.message || `Message sent to ${result.recipient_name}`);
      } else {
        setInviteSuccess(`Invitation sent to ${inviteParentEmail.trim()}`);
      }
      setInviteParentEmail('');
    } catch (err: any) {
      setInviteError(err.response?.data?.detail || 'Failed to send invitation');
    } finally {
      setInviteLoading(false);
    }
  };

  const closeAnnounceModal = () => {
    setShowAnnounceModal(false);
    setAnnounceCourseId('');
    setAnnounceSubject('');
    setAnnounceBody('');
    setAnnounceError('');
    setAnnounceSuccess('');
    setAnnouncePreview(false);
  };

  const handleSendAnnouncement = async () => {
    if (!announceCourseId || !announceSubject.trim() || !announceBody.trim()) return;
    setAnnounceSending(true);
    setAnnounceError('');
    setAnnounceSuccess('');
    try {
      const result = await coursesApi.announce(announceCourseId as number, announceSubject.trim(), announceBody.trim());
      setAnnounceSuccess(`Sent to ${result.recipient_count} parent${result.recipient_count !== 1 ? 's' : ''} (${result.email_count} email${result.email_count !== 1 ? 's' : ''})`);
      setAnnounceSubject('');
      setAnnounceBody('');
    } catch (err: any) {
      setAnnounceError(err.response?.data?.detail || 'Failed to send announcement');
    } finally {
      setAnnounceSending(false);
    }
  };

  const closeUploadModal = () => {
    setShowUploadModal(false);
    setUploadCourseId('');
    setUploadType('notes');
    setUploadTitle('');
    setUploadDescription('');
    setUploadFile(null);
    setUploadError('');
    setUploadSuccess('');
    setUploadDragging(false);
  };

  const handleUploadMaterial = async () => {
    if (!uploadCourseId || !uploadFile) return;
    setUploadLoading(true);
    setUploadError('');
    setUploadSuccess('');
    try {
      await courseContentsApi.uploadFile(
        uploadFile,
        uploadCourseId as number,
        uploadTitle.trim() || undefined,
        uploadType,
      );
      setUploadSuccess('Material uploaded successfully!');
      setUploadFile(null);
      setUploadTitle('');
      setUploadDescription('');
      setTimeout(() => {
        closeUploadModal();
      }, 1500);
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || 'Failed to upload material');
    } finally {
      setUploadLoading(false);
    }
  };

  const handleUploadDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setUploadDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      setUploadFile(file);
      if (!uploadTitle.trim()) setUploadTitle(file.name.replace(/\.[^/.]+$/, ''));
    }
  };

  const handleUploadFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadFile(file);
      if (!uploadTitle.trim()) setUploadTitle(file.name.replace(/\.[^/.]+$/, ''));
    }
  };

  const firstName = user?.full_name?.split(' ')[0] ?? '';

  const renderHeaderSlot = (inspiration: InspirationData | null) => {
    if (focusDismissed) return null;

    const greeting = new Date().getHours() < 12 ? 'Good morning' : new Date().getHours() < 17 ? 'Good afternoon' : 'Good evening';

    return (
      <div className="teacher-focus-header">
        <div className="teacher-focus-main">
          <span className="teacher-focus-icon">{unreadCount > 0 ? (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12" /><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" /></svg>
          ) : (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></svg>
          )}</span>
          <div>
            <div className="teacher-focus-title">
              {greeting}, {firstName}!
              {unreadCount > 0 && ` You have ${unreadCount} unread message${unreadCount !== 1 ? 's' : ''}.`}
              {unreadCount === 0 && ' Your inbox is clear.'}
            </div>
            <div className="teacher-focus-badges">
              {unreadCount > 0 && (
                <button type="button" className="teacher-focus-badge messages" onClick={() => navigate('/messages')}>
                  {unreadCount} unread
                </button>
              )}
              {upcomingAssignments.length > 0 && (
                <button type="button" className="teacher-focus-badge deadlines" onClick={() => navigate('/courses')}>
                  {upcomingAssignments.length} deadline{upcomingAssignments.length !== 1 ? 's' : ''} this week
                </button>
              )}
              {courses.length > 0 && (
                <span className="teacher-focus-badge classes">
                  {courses.reduce((sum, c) => sum + c.student_count, 0)} students
                </span>
              )}
            </div>
          </div>
        </div>
        {inspiration && (
          <div className="teacher-focus-inspiration">
            <span className="teacher-focus-quote">"{inspiration.text}"</span>
            {inspiration.author && <span className="teacher-focus-author"> — {inspiration.author}</span>}
          </div>
        )}
        <button className="teacher-focus-close" onClick={() => setFocusDismissed(true)} aria-label="Dismiss">{'\u00D7'}</button>
      </div>
    );
  };

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Your classroom overview">
        <PageSkeleton />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle="Your classroom overview" headerSlot={renderHeaderSlot}>
      {/* Quick Actions (#837 unified) */}
      <RoleQuickActions
        actions={[
          {
            icon: (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
            ),
            label: 'My Classes',
            onClick: () => navigate('/courses'),
          },
          {
            icon: (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            ),
            label: 'Messages',
            onClick: () => navigate('/messages'),
            badge: unreadCount > 0 ? unreadCount : undefined,
          },
          {
            icon: (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 17H2a3 3 0 0 0 3-3V9a7 7 0 0 1 14 0v5a3 3 0 0 0 3 3z" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
            ),
            label: 'Announcements',
            onClick: () => setShowAnnounceModal(true),
          },
          {
            icon: (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
              </svg>
            ),
            label: googleConnected ? 'Sync Classes' : 'Google Classroom',
            onClick: googleConnected ? handleSyncCourses : handleConnectGoogle,
            disabled: syncing,
          },
          {
            icon: (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="8.5" cy="7" r="4" />
                <line x1="20" y1="8" x2="20" y2="14" />
                <line x1="23" y1="11" x2="17" y2="11" />
              </svg>
            ),
            label: 'Invite Parents',
            onClick: () => setShowInviteParentModal(true),
          },
          {
            icon: (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            ),
            label: 'Course Material',
            onClick: () => setShowUploadModal(true),
          },
        ] satisfies QuickAction[]}
        maxVisible={4}
      />

      {/* Activity Summary */}
      <div className="teacher-activity-summary">
        <div className="teacher-activity-card">
          <div className="teacher-activity-card-header">
            <h4>Recent Messages</h4>
            {recentConversations.length > 0 && (
              <button className="teacher-activity-view-all" onClick={() => navigate('/messages')}>View All</button>
            )}
          </div>
          {recentConversations.length > 0 ? (
            <div className="teacher-activity-list">
              {recentConversations.map((conv) => (
                <div key={conv.id} className="teacher-activity-item" onClick={() => navigate('/messages')}>
                  <div className="teacher-activity-item-info">
                    <span className="teacher-activity-item-name">{conv.other_participant_name}</span>
                    <span className="teacher-activity-item-preview">{conv.last_message_preview || 'No messages yet'}</span>
                  </div>
                  <div className="teacher-activity-item-meta">
                    {conv.unread_count > 0 && (
                      <span className="teacher-activity-unread-badge">{conv.unread_count}</span>
                    )}
                    {conv.last_message_at && (
                      <span className="teacher-activity-item-time">
                        {new Date(conv.last_message_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="20" x2="12" y2="10" /><line x1="18" y1="20" x2="18" y2="4" /><line x1="6" y1="20" x2="6" y2="16" /></svg>}
              title="No recent activity"
              description="Activity will appear here as students interact with your classes."
            />
          )}
        </div>

        <div className="teacher-activity-card">
          <div className="teacher-activity-card-header">
            <h4>Upcoming Deadlines</h4>
            {upcomingAssignments.length > 0 && (
              <span className="teacher-activity-subtitle">Next 7 days</span>
            )}
          </div>
          {upcomingAssignments.length > 0 ? (
            <div className="teacher-activity-list">
              {upcomingAssignments.slice(0, 5).map((assignment) => (
                <div key={assignment.id} className="teacher-activity-item" onClick={() => navigate(`/courses`)}>
                  <div className="teacher-activity-item-info">
                    <span className="teacher-activity-item-name">{assignment.title}</span>
                    <span className="teacher-activity-item-preview">{assignment.course_name}</span>
                  </div>
                  <span className="teacher-activity-item-time">
                    {new Date(assignment.due_date!).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>}
              title="No upcoming deadlines"
              description="All caught up!"
            />
          )}
        </div>
      </div>

      <div className="dashboard-sections">
        {/* Course Management Section (#947) */}
        <TeacherCourseManagement
          key={courses.length}
          googleConnected={googleConnected}
          onSync={handleSyncCourses}
          syncing={syncing}
          onCreateCourse={() => setShowCreateModal(true)}
        />

        {syncMessage && (
          <div className={`sync-message ${syncMessage.includes('failed') ? 'sync-error' : 'sync-success'}`} style={{ gridColumn: '1 / -1' }}>
            {syncMessage}
          </div>
        )}

        {/* Sent Invites Section */}
        {sentInvites.length > 0 && (
          <section className="section sent-invites-section">
            <div className="section-header">
              <button className="collapse-toggle" onClick={() => setInvitesExpanded(!invitesExpanded)}>
                <span className={`section-chevron${invitesExpanded ? ' expanded' : ''}`}>&#9654;</span>
                <h3>Sent Invites ({sentInvites.length})</h3>
              </button>
            </div>
            {resendError && (
              <div className="resend-error-toast">{resendError}</div>
            )}
            {invitesExpanded && (
              <div className="sent-invites-list">
                {sentInvites.map(inv => {
                  const cooling = isResendCoolingDown(inv);
                  const cooldownMins = cooling ? getResendCooldownMinutes(inv) : 0;
                  const canResend = inv.status === 'pending' && !cooling;
                  return (
                    <div key={inv.id} className="sent-invite-row">
                      <div className="sent-invite-info">
                        <span className="sent-invite-email">{inv.email}</span>
                        <span className={`sent-invite-type-badge badge-${inv.invite_type}`}>{inv.invite_type}</span>
                        <span className={`sent-invite-status-badge status-${inv.status}`}>{inv.status}</span>
                      </div>
                      <div className="sent-invite-meta">
                        <span className="sent-invite-date">
                          Sent {new Date(inv.created_at).toLocaleDateString()}
                        </span>
                        {inv.status === 'pending' && (
                          <div className="sent-invite-actions">
                            {resentToastId === inv.id ? (
                              <span className="resent-toast">Resent!</span>
                            ) : (
                              <button
                                className="text-btn"
                                disabled={resendingId === inv.id || !canResend}
                                onClick={() => handleResendInvite(inv.id)}
                                title={cooling ? `Wait ${cooldownMins} min before resending` : 'Resend invite'}
                              >
                                {resendingId === inv.id
                                  ? 'Sending...'
                                  : cooling
                                    ? `Wait ${cooldownMins}m`
                                    : 'Resend'}
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        )}

        {/* Google Calendar Sync Section */}
        {googleConnected && (
          <section className="section teacher-google-calendar-section">
            <GoogleCalendarSync googleConnected={googleConnected} />
          </section>
        )}

        {/* Google Accounts Section — show when connected or when accounts already exist */}
        {(googleConnected || googleAccounts.length > 0) && (
          <section className="section teacher-google-accounts-section">
            <div className="section-header">
              <button className="collapse-toggle" onClick={() => setGoogleAccountsExpanded(v => !v)}>
                <span className={`section-chevron${googleAccountsExpanded ? ' expanded' : ''}`}>&#9654;</span>
                <h3>Connected Google Accounts ({googleAccounts.length})</h3>
              </button>
              <button className="create-custom-btn" onClick={handleAddGoogleAccount}>
                + Connect Another Account
              </button>
            </div>
            {googleAccountsExpanded && googleAccounts.length > 0 ? (
              <div className="google-accounts-list">
                {googleAccounts.map((account) => (
                  <div key={account.id} className="google-account-row">
                    <div className="google-account-info">
                      {/* Primary indicator dot */}
                      <span
                        className={`google-account-primary-dot${account.is_primary ? ' is-primary' : ''}`}
                        title={account.is_primary ? 'Primary account' : 'Secondary account'}
                      />
                      <div className="google-account-identity">
                        <span className="google-account-email">{account.google_email}</span>
                        {account.display_name && (
                          <span className="google-account-name">{account.display_name}</span>
                        )}
                      </div>
                      {account.is_primary && (
                        <span className="google-account-primary-badge">Primary</span>
                      )}
                      {/* Inline label editing */}
                      {editingLabelId === account.id ? (
                        <span className="google-account-label-edit">
                          <input
                            type="text"
                            className="google-account-label-input"
                            value={editingLabelValue}
                            onChange={(e) => setEditingLabelValue(e.target.value)}
                            placeholder="e.g. School Account"
                            maxLength={100}
                            autoFocus
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleSaveLabel(account.id);
                              if (e.key === 'Escape') handleCancelEditLabel();
                            }}
                          />
                          <button
                            className="text-btn"
                            onClick={() => handleSaveLabel(account.id)}
                            disabled={savingLabelId === account.id}
                          >
                            {savingLabelId === account.id ? 'Saving...' : 'Save'}
                          </button>
                          <button className="text-btn" onClick={handleCancelEditLabel}>
                            Cancel
                          </button>
                        </span>
                      ) : (
                        <button
                          className={`google-account-label-btn${account.account_label ? ' has-label' : ''}`}
                          onClick={() => handleStartEditLabel(account)}
                          title="Click to edit label"
                        >
                          {account.account_label || 'Add label'}
                        </button>
                      )}
                      {account.last_sync_at && (
                        <span className="google-account-sync">
                          Synced {new Date(account.last_sync_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    <div className="google-account-actions">
                      {!account.is_primary && (
                        <button
                          className="text-btn"
                          onClick={() => handleSetPrimary(account.id)}
                          title="Set as primary account"
                        >
                          Set Primary
                        </button>
                      )}
                      <button
                        className="text-btn danger"
                        onClick={() => handleRemoveAccount(account.id)}
                        disabled={removingAccountId === account.id}
                        title="Remove this Google account"
                      >
                        {removingAccountId === account.id ? 'Removing...' : 'Remove'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : googleAccountsExpanded ? (
              <EmptyState
                icon={<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" /></svg>}
                title="No Google accounts linked yet"
                description="Connect your Google account to sync classes from Google Classroom."
              />
            ) : null}
          </section>
        )}
      </div>

      {/* Create Course Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={closeCreateModal}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Create Class" ref={createCourseModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Create Class</h2>
            <div className="modal-form">
              <label>
                Class Name *
                <input
                  type="text"
                  value={courseName}
                  onChange={(e) => { setCourseName(e.target.value); setCreateError(''); }}
                  placeholder="e.g. Algebra I"
                  disabled={createLoading}
                  onKeyDown={(e) => e.key === 'Enter' && handleCreateCourse()}
                />
              </label>
              <label>
                Subject
                <input
                  type="text"
                  value={courseSubject}
                  onChange={(e) => setCourseSubject(e.target.value)}
                  placeholder="e.g. Mathematics"
                  disabled={createLoading}
                />
              </label>
              <label>
                Description
                <textarea
                  value={courseDescription}
                  onChange={(e) => setCourseDescription(e.target.value)}
                  placeholder="Brief description of the class..."
                  rows={3}
                  disabled={createLoading}
                />
              </label>
              {createError && <p className="link-error">{createError}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={closeCreateModal} disabled={createLoading}>
                Cancel
              </button>
              <button
                className="generate-btn"
                onClick={handleCreateCourse}
                disabled={createLoading || !courseName.trim()}
              >
                {createLoading ? 'Creating...' : 'Create Class'}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Invite Parent Modal */}
      {showInviteParentModal && (
        <div className="modal-overlay" onClick={closeInviteParentModal}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Invite Parent" ref={inviteParentModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Invite Parent</h2>
            <p className="modal-desc">
              Send an email invitation to a parent to join ClassBridge.
            </p>
            <div className="modal-form">
              <label>
                Parent Email *
                <input
                  type="email"
                  value={inviteParentEmail}
                  onChange={(e) => { setInviteParentEmail(e.target.value); setInviteError(''); setInviteSuccess(''); }}
                  placeholder="parent@example.com"
                  disabled={inviteLoading}
                  onKeyDown={(e) => e.key === 'Enter' && handleInviteParent()}
                />
              </label>
              {inviteError && <p className="link-error">{inviteError}</p>}
              {inviteSuccess && <p className="link-success">{inviteSuccess}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={closeInviteParentModal} disabled={inviteLoading}>
                {inviteSuccess ? 'Close' : 'Cancel'}
              </button>
              <button
                className="generate-btn"
                onClick={handleInviteParent}
                disabled={inviteLoading || !inviteParentEmail.trim()}
              >
                {inviteLoading ? 'Sending...' : 'Send Invitation'}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Announcement Modal */}
      {showAnnounceModal && (
        <div className="modal-overlay" onClick={closeAnnounceModal}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Send Announcement" ref={announceModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>{announcePreview ? 'Preview Announcement' : 'Send Announcement'}</h2>
            {!announcePreview ? (
              <>
                <p className="modal-desc">
                  Send a message to all parents of students in a class.
                </p>
                <div className="modal-form">
                  <label>
                    Class *
                    <select
                      value={announceCourseId}
                      onChange={(e) => { setAnnounceCourseId(e.target.value ? Number(e.target.value) : ''); setAnnounceError(''); }}
                      disabled={announceSending}
                    >
                      <option value="">Select a class...</option>
                      {courses.map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Subject *
                    <input
                      type="text"
                      value={announceSubject}
                      onChange={(e) => { setAnnounceSubject(e.target.value); setAnnounceError(''); }}
                      placeholder="e.g., Upcoming field trip"
                      disabled={announceSending}
                    />
                  </label>
                  <label>
                    Message *
                    <textarea
                      value={announceBody}
                      onChange={(e) => { setAnnounceBody(e.target.value); setAnnounceError(''); }}
                      placeholder="Write your announcement..."
                      rows={5}
                      disabled={announceSending}
                    />
                  </label>
                  {announceError && <p className="link-error">{announceError}</p>}
                  {announceSuccess && <p className="link-success">{announceSuccess}</p>}
                </div>
                <div className="modal-actions">
                  <button className="cancel-btn" onClick={closeAnnounceModal} disabled={announceSending}>
                    {announceSuccess ? 'Close' : 'Cancel'}
                  </button>
                  <button
                    className="generate-btn"
                    onClick={() => setAnnouncePreview(true)}
                    disabled={announceSending || !announceCourseId || !announceSubject.trim() || !announceBody.trim()}
                  >
                    Send Announcement
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="announce-preview">
                  <div className="announce-preview-field">
                    <span className="announce-preview-label">Class</span>
                    <span className="announce-preview-value">{courses.find(c => c.id === announceCourseId)?.name}</span>
                  </div>
                  <div className="announce-preview-field">
                    <span className="announce-preview-label">Recipients</span>
                    <span className="announce-preview-value">
                      {(() => {
                        const selectedCourse = courses.find(c => c.id === announceCourseId);
                        const count = selectedCourse?.student_count ?? 0;
                        return `${count} student${count !== 1 ? 's' : ''} (parents will be notified)`;
                      })()}
                    </span>
                  </div>
                  <div className="announce-preview-field">
                    <span className="announce-preview-label">Subject</span>
                    <span className="announce-preview-value announce-preview-subject">{announceSubject}</span>
                  </div>
                  <div className="announce-preview-field">
                    <span className="announce-preview-label">Message</span>
                    <div className="announce-preview-body">{announceBody}</div>
                  </div>
                </div>
                {announceError && <p className="link-error">{announceError}</p>}
                {announceSuccess && <p className="link-success">{announceSuccess}</p>}
                <div className="modal-actions">
                  {announceSuccess ? (
                    <button className="cancel-btn" onClick={closeAnnounceModal}>
                      Close
                    </button>
                  ) : (
                    <>
                      <button className="cancel-btn" onClick={() => setAnnouncePreview(false)} disabled={announceSending}>
                        Edit
                      </button>
                      <button
                        className="generate-btn"
                        onClick={handleSendAnnouncement}
                        disabled={announceSending}
                      >
                        {announceSending ? 'Sending...' : 'Confirm Send'}
                      </button>
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
      {/* Upload Material Modal */}
      {showUploadModal && (
        <div className="modal-overlay" onClick={closeUploadModal}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Upload Material" ref={uploadModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Upload Material</h2>
            <p className="modal-desc">
              Upload class notes, tests, or other materials to a course.
            </p>
            <div className="modal-form">
              <label>
                Course *
                <select
                  value={uploadCourseId}
                  onChange={(e) => { setUploadCourseId(e.target.value ? Number(e.target.value) : ''); setUploadError(''); }}
                  disabled={uploadLoading}
                >
                  <option value="">Select a class...</option>
                  {courses.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </label>
              <label>
                Material Type *
                <select
                  value={uploadType}
                  onChange={(e) => setUploadType(e.target.value)}
                  disabled={uploadLoading}
                >
                  <option value="notes">Class Notes</option>
                  <option value="test">Test / Quiz</option>
                  <option value="lab">Lab / Project</option>
                  <option value="assignment">Assignment</option>
                </select>
              </label>
              <label>
                Title
                <input
                  type="text"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  placeholder="e.g., Chapter 5 Notes"
                  disabled={uploadLoading}
                />
              </label>
              <label>
                Description
                <textarea
                  value={uploadDescription}
                  onChange={(e) => setUploadDescription(e.target.value)}
                  placeholder="Optional description..."
                  rows={2}
                  disabled={uploadLoading}
                />
              </label>
              <div
                className={`upload-drop-zone${uploadDragging ? ' dragging' : ''}${uploadFile ? ' has-file' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setUploadDragging(true); }}
                onDragLeave={() => setUploadDragging(false)}
                onDrop={handleUploadDrop}
                onClick={() => document.getElementById('teacher-upload-input')?.click()}
              >
                {uploadFile ? (
                  <div className="upload-file-info">
                    <span className="upload-file-name">{uploadFile.name}</span>
                    <span className="upload-file-size">({(uploadFile.size / 1024).toFixed(0)} KB)</span>
                    <button
                      type="button"
                      className="upload-file-remove"
                      onClick={(e) => { e.stopPropagation(); setUploadFile(null); }}
                    >
                      {'\u00D7'}
                    </button>
                  </div>
                ) : (
                  <div className="upload-drop-prompt">
                    <span className="upload-drop-icon">
                      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" /></svg>
                    </span>
                    <span>Drag & drop a file here, or click to browse</span>
                  </div>
                )}
                <input
                  id="teacher-upload-input"
                  type="file"
                  style={{ display: 'none' }}
                  onChange={handleUploadFileChange}
                  disabled={uploadLoading}
                />
              </div>
              {uploadError && <p className="link-error">{uploadError}</p>}
              {uploadSuccess && <p className="link-success">{uploadSuccess}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={closeUploadModal} disabled={uploadLoading}>
                {uploadSuccess ? 'Close' : 'Cancel'}
              </button>
              <button
                className="generate-btn"
                onClick={handleUploadMaterial}
                disabled={uploadLoading || !uploadCourseId || !uploadFile}
              >
                {uploadLoading ? 'Uploading...' : 'Upload'}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
