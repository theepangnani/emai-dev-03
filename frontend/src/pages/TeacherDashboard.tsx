import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { coursesApi, googleApi, invitesApi } from '../api/client';
import type { GoogleAccount, InviteResponse } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageSkeleton } from '../components/Skeleton';
import './TeacherDashboard.css';

interface Course {
  id: number;
  name: string;
  description: string | null;
  subject: string | null;
  google_classroom_id: string | null;
}

export function TeacherDashboard() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState<Course[]>([]);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

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

  // Pending invites state
  const [pendingInvites, setPendingInvites] = useState<InviteResponse[]>([]);
  const [resendingId, setResendingId] = useState<number | null>(null);

  // Course search
  const [courseSearch, setCourseSearch] = useState('');

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
        setPendingInvites(invitesData.value.filter(i => !i.accepted_at && new Date(i.expires_at) > new Date()));
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
    try {
      await googleApi.syncCourses();
      // Reload courses after sync
      const coursesData = await coursesApi.teachingList();
      setCourses(coursesData);
    } catch {
      // Sync failed
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
      setCreateError(err.response?.data?.detail || 'Failed to create course');
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
    try {
      const updated = await invitesApi.resend(inviteId);
      setPendingInvites(prev => prev.map(i => i.id === inviteId ? updated : i));
    } catch { /* ignore */ }
    setResendingId(null);
  };

  const closeInviteParentModal = () => {
    setShowInviteParentModal(false);
    setInviteParentEmail('');
    setInviteError('');
    setInviteSuccess('');
  };

  const handleInviteParent = async () => {
    if (!inviteParentEmail.trim()) return;
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
          <h3>Courses</h3>
          <p className="card-value">{courses.length}</p>
          <p className="card-label">Courses teaching</p>
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
              {syncing ? 'Syncing...' : 'Sync Courses'}
            </button>
          )}
        </div>
      </div>

      <div className="dashboard-sections">
        <section className="section teacher-courses-section">
          <div className="section-header">
            <h3>Your Courses</h3>
            <button className="create-custom-btn" onClick={() => setShowCreateModal(true)}>
              + Create Course
            </button>
          </div>
          {courses.length > 3 && (
            <input
              type="text"
              className="courses-search-input"
              placeholder="Search courses by name or subject..."
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
                <div key={course.id} className="teacher-course-card">
                  <h4>{course.name}</h4>
                  {course.subject && <span className="course-subject-tag">{course.subject}</span>}
                  {course.description && (
                    <p className="course-desc">{course.description}</p>
                  )}
                  {course.google_classroom_id && (
                    <span className="google-badge">Google Classroom</span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <p>No courses yet</p>
              <small>
                Create a course manually{googleConnected
                  ? ' or click "Sync Courses" to import from Google Classroom'
                  : ' or connect Google Classroom to sync your courses'}
              </small>
              <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', marginTop: '12px' }}>
                <button className="connect-button" onClick={() => setShowCreateModal(true)}>
                  + Create Course
                </button>
                {googleConnected && (
                  <button className="connect-button" onClick={handleSyncCourses} disabled={syncing}>
                    {syncing ? 'Syncing...' : 'Sync Courses'}
                  </button>
                )}
              </div>
            </div>
          )}
        </section>

        {/* Pending Invites Section */}
        {pendingInvites.length > 0 && (
          <section className="section">
            <div className="section-header">
              <h3>Pending Invites</h3>
            </div>
            <div className="pending-invites-list">
              {pendingInvites.map(inv => (
                <div key={inv.id} className="pending-invite-row">
                  <span className="pending-invite-email">{inv.email}</span>
                  <span className="pending-invite-type">{inv.invite_type}</span>
                  <button
                    className="text-btn"
                    disabled={resendingId === inv.id}
                    onClick={() => handleResendInvite(inv.id)}
                  >
                    {resendingId === inv.id ? 'Sending...' : 'Resend'}
                  </button>
                </div>
              ))}
            </div>
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
                <small>Connect your Google account to sync courses from Google Classroom</small>
              </div>
            )}
          </section>
        )}
      </div>

      {/* Create Course Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={closeCreateModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Create Course</h2>
            <div className="modal-form">
              <label>
                Course Name *
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
                  placeholder="Brief description of the course..."
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
                {createLoading ? 'Creating...' : 'Create Course'}
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
    </DashboardLayout>
  );
}
