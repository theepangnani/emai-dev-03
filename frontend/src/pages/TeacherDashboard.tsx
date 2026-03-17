import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { coursesApi, googleApi, invitesApi, messagesApi, assignmentsApi } from '../api/client';
import { useFeature } from '../hooks/useFeatureToggle';
import type { GoogleAccount, InviteResponse, AssignmentItem } from '../api/client';
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
import { SearchableSelect, MultiSearchableSelect } from '../components/SearchableSelect';
import type { SearchableOption } from '../components/SearchableSelect';
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
  const [overdueCount, setOverdueCount] = useState(0);

  // Create course modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [courseName, setCourseName] = useState('');
  const [courseSubject, setCourseSubject] = useState('');
  const [courseDescription, setCourseDescription] = useState('');
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState('');
  const [selectedTeacher, setSelectedTeacher] = useState<SearchableOption | null>(null);
  const [selectedStudents, setSelectedStudents] = useState<SearchableOption[]>([]);
  const [showCreateTeacher, setShowCreateTeacher] = useState(false);
  const [newTeacherName, setNewTeacherName] = useState('');
  const [newTeacherEmail, setNewTeacherEmail] = useState('');

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
  const [googleAccountsExpanded, setGoogleAccountsExpanded] = useState(true);
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
      const [coursesData, googleStatus, accountsData, invitesData, unreadData, assignmentsData] = await Promise.allSettled([
        coursesApi.teachingList(),
        googleApi.getStatus(),
        googleApi.getTeacherAccounts(),
        invitesApi.listSent(),
        messagesApi.getUnreadCount(),
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
      if (assignmentsData.status === 'fulfilled') {
        const now = new Date();
        const overdue = assignmentsData.value.filter((a: AssignmentItem) => a.due_date && new Date(a.due_date) < now);
        setOverdueCount(overdue.length);
      }
    } finally {
      setLoading(false);
    }
  };

  // handleConnectGoogle removed — unused after dashboard redesign

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
    setSelectedTeacher(null);
    setSelectedStudents([]);
    setShowCreateTeacher(false);
    setNewTeacherName('');
    setNewTeacherEmail('');
  };

  const handleSearchTeachers = async (q: string): Promise<SearchableOption[]> => {
    const results = await coursesApi.searchTeachers(q);
    return results.map(t => ({
      id: t.id,
      label: t.name,
      sublabel: t.email || (t.is_shadow ? 'Shadow teacher' : undefined),
    }));
  };

  const handleSearchStudents = async (q: string): Promise<SearchableOption[]> => {
    const results = await coursesApi.searchStudents(q);
    return results.map(s => ({
      id: s.id,
      label: s.name,
      sublabel: s.email,
    }));
  };

  const handleCreateCourse = async () => {
    if (!courseName.trim()) return;
    if (!selectedTeacher && !showCreateTeacher) {
      setCreateError('A teacher is required');
      return;
    }
    if (showCreateTeacher && !newTeacherName.trim()) {
      setCreateError('Teacher name is required');
      return;
    }
    if (newTeacherEmail && !isValidEmail(newTeacherEmail.trim())) {
      setCreateError('Please enter a valid teacher email');
      return;
    }
    setCreateLoading(true);
    setCreateError('');
    try {
      const data: Parameters<typeof coursesApi.create>[0] = {
        name: courseName.trim(),
        description: courseDescription.trim() || undefined,
        subject: courseSubject.trim() || undefined,
        student_ids: selectedStudents.map(s => s.id),
      };
      if (selectedTeacher) {
        data.teacher_id = selectedTeacher.id;
      } else if (showCreateTeacher) {
        data.new_teacher_name = newTeacherName.trim();
        data.new_teacher_email = newTeacherEmail.trim() || undefined;
      }
      await coursesApi.create(data);
      closeCreateModal();
      const coursesData = await coursesApi.teachingList();
      setCourses(coursesData);
    } catch (err: any) {
      setCreateError(err.response?.data?.detail || 'Failed to create class');
    } finally {
      setCreateLoading(false);
    }
  };

  // handleAddGoogleAccount removed — unused after dashboard redesign

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
    const greeting = new Date().getHours() < 12 ? 'Good morning' : new Date().getHours() < 17 ? 'Good afternoon' : 'Good evening';
    const totalStudents = courses.reduce((sum, c) => sum + c.student_count, 0);

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
            </div>
            <div className="teacher-focus-badges">
              <span className="teacher-focus-badge classes">
                {courses.length} classes · {totalStudents} students · {unreadCount} messages
              </span>
            </div>
          </div>
        </div>
        {inspiration && (
          <div className="teacher-focus-inspiration">
            <span className="teacher-focus-quote">"{inspiration.text}"</span>
            {inspiration.author && <span className="teacher-focus-author"> — {inspiration.author}</span>}
          </div>
        )}
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
        {/* Section 1: Student Alerts */}
        <section className="dash-section dash-section--primary">
          <div className="dash-section-header">
            <h3 className="dash-section-title"><span className="dash-section-title-icon" aria-hidden="true">&#128680;</span> Student Alerts</h3>
          </div>
          <div className="dash-section-body">
            {overdueCount === 0 && unreadCount === 0 && sentInvites.filter(i => i.status === 'pending').length === 0 ? (
              <EmptyState icon="&#10003;" title="All clear! No urgent items." description="" />
            ) : (
              <div className="teacher-activity-list">
                {overdueCount > 0 && (
                  <div className="teacher-activity-item" onClick={() => navigate('/courses')} style={{ cursor: 'pointer' }}>
                    <div className="teacher-activity-item-info">
                      <span className="teacher-activity-item-name">{overdueCount} overdue assignment{overdueCount !== 1 ? 's' : ''}</span>
                    </div>
                  </div>
                )}
                {unreadCount > 0 && (
                  <div className="teacher-activity-item" onClick={() => navigate('/messages')} style={{ cursor: 'pointer' }}>
                    <div className="teacher-activity-item-info">
                      <span className="teacher-activity-item-name">{unreadCount} new parent message{unreadCount !== 1 ? 's' : ''}</span>
                    </div>
                  </div>
                )}
                {sentInvites.filter(i => i.status === 'pending').length > 0 && (
                  <div className="teacher-activity-item" onClick={() => navigate('/messages')} style={{ cursor: 'pointer' }}>
                    <div className="teacher-activity-item-info">
                      <span className="teacher-activity-item-name">{sentInvites.filter(i => i.status === 'pending').length} pending invite{sentInvites.filter(i => i.status === 'pending').length !== 1 ? 's' : ''}</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        {/* Section 2: My Classes */}
        <section className="dash-section dash-section--secondary">
          <div className="dash-section-header">
            <h3 className="dash-section-title"><span className="dash-section-title-icon" aria-hidden="true">&#128218;</span> My Classes</h3>
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

        {/* Section 3: Quick Actions */}
        <section className="dash-section dash-section--actions">
          <div className="dash-section-header">
            <h3 className="dash-section-title">Quick Actions</h3>
          </div>
          <div className="dash-quick-actions">
            <button className="dash-quick-action" onClick={() => navigate('/courses')}><span className="dash-quick-action-icon">&#10133;</span> Create Assignment</button>
            <button className="dash-quick-action" onClick={() => navigate('/messages')}><span className="dash-quick-action-icon">&#128172;</span> Send Message</button>
            <button className="dash-quick-action" onClick={() => studyTools.setShowStudyModal(true)}><span className="dash-quick-action-icon">&#128228;</span> Upload Material</button>
            <button className="dash-quick-action" onClick={() => handleSyncCourses()}><span className="dash-quick-action-icon">&#128259;</span> Sync Classroom</button>
            <button className="dash-quick-action" onClick={() => setShowInviteParentModal(true)}><span className="dash-quick-action-icon">&#128101;</span> Invite Parents</button>
          </div>
        </section>
      </div>

      {/* Create Course Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={closeCreateModal}>
          <div className="modal modal-lg" role="dialog" aria-modal="true" aria-label="Create Class" ref={createCourseModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Create Class</h2>
            <p className="modal-desc">Set up a new class with students and a teacher.</p>
            <div className="modal-form">
              <label>
                Class Name *
                <input
                  type="text"
                  value={courseName}
                  onChange={(e) => { setCourseName(e.target.value); setCreateError(''); }}
                  placeholder="e.g. Algebra I"
                  disabled={createLoading}
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
                  rows={2}
                  disabled={createLoading}
                />
              </label>

              <label>
                Teacher *
              </label>
              {!showCreateTeacher ? (
                <SearchableSelect
                  placeholder="Search for a teacher by name or email..."
                  onSearch={handleSearchTeachers}
                  onSelect={(opt) => { setSelectedTeacher(opt); setCreateError(''); }}
                  selected={selectedTeacher}
                  onClear={() => setSelectedTeacher(null)}
                  disabled={createLoading}
                  createAction={{ label: '+ Create New Teacher', onClick: () => { setSelectedTeacher(null); setShowCreateTeacher(true); } }}
                />
              ) : (
                <div className="create-teacher-inline">
                  <div className="create-teacher-inline__header">
                    <h4>New Teacher</h4>
                    <button type="button" className="create-teacher-inline__cancel" onClick={() => { setShowCreateTeacher(false); setNewTeacherName(''); setNewTeacherEmail(''); }}>
                      Back to search
                    </button>
                  </div>
                  <label>
                    Name *
                    <input
                      type="text"
                      value={newTeacherName}
                      onChange={(e) => { setNewTeacherName(e.target.value); setCreateError(''); }}
                      placeholder="e.g. Ms. Johnson"
                      disabled={createLoading}
                    />
                  </label>
                  <label>
                    Email (optional)
                    <input
                      type="email"
                      value={newTeacherEmail}
                      onChange={(e) => setNewTeacherEmail(e.target.value)}
                      placeholder="teacher@school.com"
                      disabled={createLoading}
                    />
                  </label>
                  <p className="shadow-note">
                    {newTeacherEmail ? 'An invitation will be sent to join ClassBridge as a teacher.' : 'No email = shadow teacher (can be invited later).'}
                  </p>
                </div>
              )}

              <label>
                Students <span style={{ fontWeight: 400, fontSize: '0.8rem', color: '#6b7280' }}>(optional — students can enroll later)</span>
              </label>
              <MultiSearchableSelect
                placeholder="Search students by name or email..."
                onSearch={handleSearchStudents}
                selected={selectedStudents}
                onAdd={(opt) => { setSelectedStudents(prev => [...prev, opt]); setCreateError(''); }}
                onRemove={(id) => setSelectedStudents(prev => prev.filter(s => s.id !== id))}
                disabled={createLoading}
              />

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
            navigate(guide.guide_type === 'quiz' ? `/study/quiz/${guide.id}` : guide.guide_type === 'flashcards' ? `/study/flashcards/${guide.id}` : guide.course_content_id ? `/course-materials/${guide.course_content_id}?tab=guide` : `/study/guide/${guide.id}`);
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
              <button className="td-gen-view-btn" onClick={() => { navigate(studyTools.backgroundGeneration?.resultId ? `/course-materials/${studyTools.backgroundGeneration.resultId}` : '/course-materials'); studyTools.dismissBackgroundGeneration(); }}>View</button>
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
