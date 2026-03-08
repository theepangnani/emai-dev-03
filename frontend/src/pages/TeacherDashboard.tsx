import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { coursesApi, googleApi, invitesApi, messagesApi, assignmentsApi } from '../api/client';
import { useFeature } from '../hooks/useFeatureToggle';
import type { GoogleAccount, InviteResponse, ConversationSummary, AssignmentItem } from '../api/client';
import UploadMaterialWizard from '../components/UploadMaterialWizard';
import { useParentStudyTools } from '../components/parent/hooks/useParentStudyTools';
import { AILimitRequestModal } from '../components/AILimitRequestModal';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import type { InspirationData } from '../components/DashboardLayout';
import { useFocusTrap } from '../hooks/useFocusTrap';
import { isValidEmail } from '../utils/validation';
import { PageSkeleton } from '../components/Skeleton';
import EmptyState from '../components/EmptyState';
import { TeacherCourseManagement } from '../components/TeacherCourseManagement';
import './TeacherDashboard.css';
import './DashboardGrid.css';

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
  const gcEnabled = useFeature('google_classroom');
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

  // Sent invites state
  const [sentInvites, setSentInvites] = useState<InviteResponse[]>([]);
  const [resendingId, setResendingId] = useState<number | null>(null);
  const [_resentToastId, setResentToastId] = useState<number | null>(null);
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

  // Focus traps for modals (must be after state declarations they reference)
  const createCourseModalRef = useFocusTrap<HTMLDivElement>(showCreateModal, () => setShowCreateModal(false));
  const inviteParentModalRef = useFocusTrap<HTMLDivElement>(showInviteParentModal, () => setShowInviteParentModal(false));
  const announceModalRef = useFocusTrap<HTMLDivElement>(showAnnounceModal, () => setShowAnnounceModal(false));

  // Upload / study material generation (shared with Parent experience)
  const studyTools = useParentStudyTools({ selectedChildUserId: null, navigate });

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
      {syncMessage && (
        <div className={`sync-message ${syncMessage.includes('failed') ? 'sync-error' : 'sync-success'}`}>{syncMessage}</div>
      )}

      {/* ── 3-Section Dashboard Grid (#1417) ────────────── */}
      <div className="dashboard-redesign">
        {/* Section 1: Class Overview */}
        <section className="dash-section dash-section--primary">
          <div className="dash-section-header">
            <h3 className="dash-section-title"><span className="dash-section-title-icon" aria-hidden="true">&#128218;</span> Class Overview</h3>
          </div>
          <div className="dash-section-body">
            <TeacherCourseManagement key={courses.length} googleConnected={gcEnabled && googleConnected} onSync={handleSyncCourses} syncing={syncing} onCreateCourse={() => setShowCreateModal(true)} />
            {gcEnabled && googleConnected && (
              <div style={{ marginTop: 16 }}>
                <button className="collapse-toggle" onClick={() => setGoogleAccountsExpanded(v => !v)} style={{ fontSize: 13 }}>
                  <span className={`section-chevron${googleAccountsExpanded ? ' expanded' : ''}`}>&#9654;</span> Google Accounts ({googleAccounts.length})
                </button>
                {googleAccountsExpanded && googleAccounts.length > 0 && (
                  <div className="google-accounts-list" style={{ marginTop: 8 }}>
                    {googleAccounts.map((account) => (
                      <div key={account.id} className="google-account-row">
                        <div className="google-account-info">
                          <span className="google-account-email">{account.google_email}</span>
                          {account.is_primary && <span className="google-account-primary-badge">Primary</span>}
                        </div>
                        <div className="google-account-actions">
                          {!account.is_primary && <button className="text-btn" onClick={() => handleSetPrimary(account.id)}>Set Primary</button>}
                          <button className="text-btn danger" onClick={() => handleRemoveAccount(account.id)} disabled={removingAccountId === account.id}>{removingAccountId === account.id ? '...' : 'Remove'}</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        {/* Section 2: Pending Items */}
        <section className="dash-section dash-section--secondary">
          <div className="dash-section-header">
            <h3 className="dash-section-title"><span className="dash-section-title-icon" aria-hidden="true">&#128172;</span> Pending Items</h3>
            {unreadCount > 0 && <button className="dash-section-link" onClick={() => navigate('/messages')} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>{unreadCount} unread</button>}
          </div>
          <div className="dash-section-body">
            {recentConversations.length > 0 ? (
              <div className="teacher-activity-list">
                {recentConversations.map((conv) => (
                  <div key={conv.id} className="teacher-activity-item" onClick={() => navigate('/messages')}>
                    <div className="teacher-activity-item-info">
                      <span className="teacher-activity-item-name">{conv.other_participant_name}</span>
                      <span className="teacher-activity-item-preview">{conv.last_message_preview || 'No messages yet'}</span>
                    </div>
                    {conv.unread_count > 0 && <span className="teacher-activity-unread-badge">{conv.unread_count}</span>}
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState icon="&#128172;" title="No recent messages" description="Messages from parents will appear here." />
            )}
            {upcomingAssignments.length > 0 && (
              <>
                <hr style={{ border: 'none', borderTop: '1px solid var(--color-border)', margin: '12px 0' }} />
                <h4 style={{ margin: '0 0 8px', fontSize: 13, fontWeight: 600 }}>Upcoming Deadlines</h4>
                <div className="teacher-activity-list">
                  {upcomingAssignments.slice(0, 5).map((assignment) => (
                    <div key={assignment.id} className="teacher-activity-item" onClick={() => navigate('/courses')}>
                      <div className="teacher-activity-item-info">
                        <span className="teacher-activity-item-name">{assignment.title}</span>
                        <span className="teacher-activity-item-preview">{assignment.course_name}</span>
                      </div>
                      <span className="teacher-activity-item-time">{new Date(assignment.due_date!).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
            {sentInvites.length > 0 && (
              <>
                <hr style={{ border: 'none', borderTop: '1px solid var(--color-border)', margin: '12px 0' }} />
                <button className="collapse-toggle" onClick={() => setInvitesExpanded(!invitesExpanded)} style={{ fontSize: 13 }}>
                  <span className={`section-chevron${invitesExpanded ? ' expanded' : ''}`}>&#9654;</span> Sent Invites ({sentInvites.length})
                </button>
                {resendError && <div className="resend-error-toast">{resendError}</div>}
                {invitesExpanded && (
                  <div className="sent-invites-list" style={{ marginTop: 8 }}>
                    {sentInvites.map(inv => {
                      const cooling = isResendCoolingDown(inv);
                      const cooldownMins = cooling ? getResendCooldownMinutes(inv) : 0;
                      return (
                        <div key={inv.id} className="sent-invite-row">
                          <div className="sent-invite-info">
                            <span className="sent-invite-email">{inv.email}</span>
                            <span className={`sent-invite-status-badge status-${inv.status}`}>{inv.status}</span>
                          </div>
                          {inv.status === 'pending' && (
                            <button className="text-btn" disabled={resendingId === inv.id || !(!cooling)} onClick={() => handleResendInvite(inv.id)}>
                              {resendingId === inv.id ? '...' : cooling ? `${cooldownMins}m` : 'Resend'}
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </div>
        </section>

        {/* Section 3: Quick Actions */}
        <section className="dash-section dash-section--actions">
          <div className="dash-section-header">
            <h3 className="dash-section-title">Quick Actions</h3>
          </div>
          <div className="dash-quick-actions">
            <button className="dash-quick-action" onClick={() => setShowCreateModal(true)}><span className="dash-quick-action-icon">&#10133;</span> Create Class</button>
            <button className="dash-quick-action" onClick={() => navigate('/messages')}><span className="dash-quick-action-icon">&#128172;</span> Message Parents</button>
            <button className="dash-quick-action" onClick={() => setShowAnnounceModal(true)}><span className="dash-quick-action-icon">&#128227;</span> Announcements</button>
            <button className="dash-quick-action" onClick={() => setShowInviteParentModal(true)}><span className="dash-quick-action-icon">&#128101;</span> Invite Parents</button>
            <button className="dash-quick-action" onClick={() => studyTools.setShowStudyModal(true)}><span className="dash-quick-action-icon">&#128228;</span> Upload Material</button>
          </div>
        </section>
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
      {/* Upload / Study Material Modal — same experience as Parent */}
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
            navigate(guide.guide_type === 'quiz' ? `/study/quiz/${guide.id}` : guide.guide_type === 'flashcards' ? `/study/flashcards/${guide.id}` : `/study/guide/${guide.id}`);
          }
        }}
        onRegenerate={() => studyTools.handleGenerateFromModal({ title: studyTools.studyModalInitialTitle, content: studyTools.studyModalInitialContent, types: ['study_guide'], mode: 'text' })}
        onDismissDuplicate={() => studyTools.setDuplicateCheck(null)}
      />
      {/* Background generation status banner */}
      {studyTools.backgroundGeneration && (
        <div className={`td-generation-banner ${studyTools.backgroundGeneration.status}`}>
          {studyTools.backgroundGeneration.status === 'generating' && (
            <span><span className="td-gen-spinner" /> Generating {studyTools.backgroundGeneration.type}...</span>
          )}
          {studyTools.backgroundGeneration.status === 'success' && (
            <>
              <span>{studyTools.backgroundGeneration.type} ready!</span>
              <button className="td-gen-view-btn" onClick={() => { navigate('/course-materials'); studyTools.dismissBackgroundGeneration(); }}>View</button>
              <button className="td-gen-dismiss-btn" onClick={studyTools.dismissBackgroundGeneration}>&times;</button>
            </>
          )}
          {studyTools.backgroundGeneration.status === 'error' && (
            <>
              <span>Failed to generate {studyTools.backgroundGeneration.type}{studyTools.backgroundGeneration.error ? `: ${studyTools.backgroundGeneration.error}` : ''}</span>
              <button className="td-gen-dismiss-btn" onClick={studyTools.dismissBackgroundGeneration}>&times;</button>
            </>
          )}
        </div>
      )}
      <AILimitRequestModal
        open={studyTools.showLimitModal}
        onClose={() => studyTools.setShowLimitModal(false)}
      />
    </DashboardLayout>
  );
}
