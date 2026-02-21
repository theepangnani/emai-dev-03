import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { coursesApi, googleApi, invitesApi } from '../api/client';
import type { GoogleAccount, InviteResponse } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { isValidEmail } from '../utils/validation';
import { PageSkeleton } from '../components/Skeleton';
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
  const [courses, setCourses] = useState<Course[]>([]);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');

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
  const [resentToastId, setResentToastId] = useState<number | null>(null);
  const [invitesExpanded, setInvitesExpanded] = useState(true);
  const [resendError, setResendError] = useState<string | null>(null);

  // Course search
  const [courseSearch, setCourseSearch] = useState('');

  // Announcement modal state
  const [showAnnounceModal, setShowAnnounceModal] = useState(false);
  const [announceCourseId, setAnnounceCourseId] = useState<number | ''>('');
  const [announceSubject, setAnnounceSubject] = useState('');
  const [announceBody, setAnnounceBody] = useState('');
  const [announceSending, setAnnounceSending] = useState(false);
  const [announceError, setAnnounceError] = useState('');
  const [announceSuccess, setAnnounceSuccess] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [coursesData, googleStatus, accountsData, invitesData] = await Promise.allSettled([
        coursesApi.teachingList(),
        googleApi.getStatus(),
        googleApi.getTeacherAccounts(),
        invitesApi.listSent(),
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

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Your classroom overview">
        <PageSkeleton />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle="Your classroom overview">
      <div className="dashboard-grid">
        <div className="dashboard-card">
          <div className="card-icon">📚</div>
          <h3>Classes</h3>
          <p className="card-value">{courses.length}</p>
          <p className="card-label">Classes teaching</p>
        </div>

        <div className="dashboard-card clickable" onClick={() => navigate('/messages')}>
          <div className="card-icon">💬</div>
          <h3>Messages</h3>
          <p className="card-value">View</p>
          <p className="card-label">Parent messages</p>
        </div>

        <div className="dashboard-card clickable" onClick={() => navigate('/teacher-communications')}>
          <div className="card-icon">📧</div>
          <h3>Communications</h3>
          <p className="card-value">View</p>
          <p className="card-label">Email monitoring</p>
        </div>

        <div className="dashboard-card clickable" onClick={() => setShowAnnounceModal(true)}>
          <div className="card-icon">📢</div>
          <h3>Announcement</h3>
          <p className="card-value">Send</p>
          <p className="card-label">Notify all parents</p>
        </div>

        <div className="dashboard-card clickable" onClick={() => setShowInviteParentModal(true)}>
          <div className="card-icon">👨‍👩‍👧</div>
          <h3>Invite Parent</h3>
          <p className="card-value">Invite</p>
          <p className="card-label">Connect families</p>
        </div>

        <div className="dashboard-card">
          <div className="card-icon">🔗</div>
          <h3>Google Classroom</h3>
          <p className="card-value">{googleConnected ? 'Connected' : 'Not Connected'}</p>
          {!googleConnected ? (
            <button className="connect-button" onClick={handleConnectGoogle}>
              Connect
            </button>
          ) : (
            <button className="connect-button" onClick={handleSyncCourses} disabled={syncing}>
              {syncing ? 'Syncing...' : 'Sync Classes'}
            </button>
          )}
        </div>
      </div>

      <div className="dashboard-sections">
        <section className="section teacher-courses-section">
          <div className="section-header">
            <h3>Your Classes</h3>
            <div className="section-header-actions">
              {googleConnected && (
                <button className="sync-btn" onClick={handleSyncCourses} disabled={syncing}>
                  {syncing ? 'Syncing...' : 'Sync Classes'}
                </button>
              )}
              <button className="create-custom-btn" onClick={() => setShowCreateModal(true)}>
                + Create Class
              </button>
            </div>
          </div>
          {syncMessage && (
            <div className={`sync-message ${syncMessage.includes('failed') ? 'sync-error' : 'sync-success'}`}>
              {syncMessage}
            </div>
          )}
          {courses.length > 3 && (
            <input
              type="text"
              className="courses-search-input"
              placeholder="Search classes by name or subject..."
              value={courseSearch}
              onChange={(e) => setCourseSearch(e.target.value)}
              style={{ marginBottom: 16 }}
            />
          )}
          {courses.length > 0 ? (
            <div className="teacher-courses-grid">
              {courses.filter(c =>
                !courseSearch ||
                c.name.toLowerCase().includes(courseSearch.toLowerCase()) ||
                (c.subject && c.subject.toLowerCase().includes(courseSearch.toLowerCase()))
              ).map((course) => (
                <div key={course.id} className="teacher-course-card" onClick={() => navigate(`/courses/${course.id}`)}>
                  <div className="course-card-header">
                    <h4>{course.name}</h4>
                    <span className={`course-source-badge ${course.google_classroom_id ? 'source-google' : 'source-manual'}`}>
                      {course.google_classroom_id ? 'Google Classroom' : 'Manual'}
                    </span>
                  </div>
                  {course.subject && <span className="course-subject-tag">{course.subject}</span>}
                  {course.description && (
                    <p className="course-desc">{course.description}</p>
                  )}
                  <div className="course-card-footer">
                    <span className="course-student-count">
                      {course.student_count} {course.student_count === 1 ? 'student' : 'students'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <p>No classes yet</p>
              <small>
                Create a class manually{googleConnected
                  ? ' or click "Sync Classes" to import from Google Classroom'
                  : ' or connect Google Classroom to sync your classes'}
              </small>
              <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', marginTop: '12px' }}>
                <button className="connect-button" onClick={() => setShowCreateModal(true)}>
                  + Create Class
                </button>
                {googleConnected && (
                  <button className="connect-button" onClick={handleSyncCourses} disabled={syncing}>
                    {syncing ? 'Syncing...' : 'Sync Classes'}
                  </button>
                )}
              </div>
            </div>
          )}
        </section>

        {/* Sent Invites Section */}
        {sentInvites.length > 0 && (
          <section className="section sent-invites-section">
            <div className="section-header section-header-collapsible" onClick={() => setInvitesExpanded(!invitesExpanded)}>
              <h3>
                <span className={`collapse-arrow ${invitesExpanded ? 'expanded' : ''}`}>&#9654;</span>
                {' '}Sent Invites ({sentInvites.length})
              </h3>
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

        {/* Google Accounts Section */}
        {googleConnected && (
          <section className="section teacher-google-accounts-section">
            <div className="section-header">
              <h3>Google Accounts</h3>
              <button className="create-custom-btn" onClick={handleAddGoogleAccount}>
                + Add Account
              </button>
            </div>
            {googleAccounts.length > 0 ? (
              <div className="google-accounts-list">
                {googleAccounts.map((account) => (
                  <div key={account.id} className="google-account-row">
                    <div className="google-account-info">
                      <span className="google-account-email">{account.google_email}</span>
                      {account.display_name && (
                        <span className="google-account-name">{account.display_name}</span>
                      )}
                      {account.account_label && (
                        <span className="google-account-label">{account.account_label}</span>
                      )}
                      {account.is_primary && (
                        <span className="google-account-primary-badge">Primary</span>
                      )}
                      {account.last_sync_at && (
                        <span className="google-account-sync">
                          Last synced: {new Date(account.last_sync_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    <div className="google-account-actions">
                      {!account.is_primary && (
                        <button
                          className="text-btn"
                          onClick={() => handleSetPrimary(account.id)}
                          title="Set as primary"
                        >
                          Set Primary
                        </button>
                      )}
                      <button
                        className="text-btn danger"
                        onClick={() => handleRemoveAccount(account.id)}
                        disabled={removingAccountId === account.id}
                        title="Remove account"
                      >
                        {removingAccountId === account.id ? 'Removing...' : 'Remove'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <p>No Google accounts linked yet</p>
                <small>Connect your Google account to sync classes from Google Classroom</small>
              </div>
            )}
          </section>
        )}
      </div>

      {/* Create Course Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={closeCreateModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
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
          <div className="modal" onClick={(e) => e.stopPropagation()}>
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
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Send Announcement</h2>
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
                onClick={handleSendAnnouncement}
                disabled={announceSending || !announceCourseId || !announceSubject.trim() || !announceBody.trim()}
              >
                {announceSending ? 'Sending...' : 'Send Announcement'}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
