import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { parentApi, googleApi, invitesApi } from '../api/client';
import type { ChildSummary, ChildOverview, DiscoveredChild } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import './ParentDashboard.css';

type LinkTab = 'email' | 'google';
type DiscoveryState = 'idle' | 'discovering' | 'results' | 'no_results';
type SyncState = 'idle' | 'syncing' | 'done' | 'error';

export function ParentDashboard() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChild, setSelectedChild] = useState<number | null>(null);
  const [childOverview, setChildOverview] = useState<ChildOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [overviewLoading, setOverviewLoading] = useState(false);

  // Link child modal state
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [linkTab, setLinkTab] = useState<LinkTab>('email');
  const [linkEmail, setLinkEmail] = useState('');
  const [linkRelationship, setLinkRelationship] = useState('guardian');
  const [linkError, setLinkError] = useState('');
  const [linkLoading, setLinkLoading] = useState(false);

  // Invite student modal state
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRelationship, setInviteRelationship] = useState('guardian');
  const [inviteError, setInviteError] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteSuccess, setInviteSuccess] = useState('');

  // Google discovery state
  const [discoveryState, setDiscoveryState] = useState<DiscoveryState>('idle');
  const [discoveredChildren, setDiscoveredChildren] = useState<DiscoveredChild[]>([]);
  const [selectedDiscovered, setSelectedDiscovered] = useState<Set<number>>(new Set());
  const [googleConnected, setGoogleConnected] = useState(false);
  const [coursesSearched, setCoursesSearched] = useState(0);
  const [bulkLinking, setBulkLinking] = useState(false);

  // Child sync state
  const [syncState, setSyncState] = useState<SyncState>('idle');
  const [syncMessage, setSyncMessage] = useState('');

  // Check for OAuth callback and pending action on mount
  useEffect(() => {
    const connected = searchParams.get('google_connected');
    const pendingAction = localStorage.getItem('pendingAction');

    if (connected === 'true' && pendingAction === 'discover_children') {
      localStorage.removeItem('pendingAction');
      setSearchParams({});
      setShowLinkModal(true);
      setLinkTab('google');
      setGoogleConnected(true);
      // Trigger discovery after a tick
      setTimeout(() => triggerDiscovery(), 100);
    } else if (connected === 'true') {
      setSearchParams({});
      setGoogleConnected(true);
    }

    loadChildren();
    checkGoogleStatus();
  }, []);

  useEffect(() => {
    if (selectedChild) {
      loadChildOverview(selectedChild);
    }
  }, [selectedChild]);

  const checkGoogleStatus = async () => {
    try {
      const status = await googleApi.getStatus();
      setGoogleConnected(status.connected);
    } catch {
      // ignore
    }
  };

  const loadChildren = async () => {
    try {
      const data = await parentApi.getChildren();
      setChildren(data);
      if (data.length > 0) {
        setSelectedChild(data[0].student_id);
      }
    } catch {
      // Failed to load children
    } finally {
      setLoading(false);
    }
  };

  const loadChildOverview = async (studentId: number) => {
    setOverviewLoading(true);
    try {
      const data = await parentApi.getChildOverview(studentId);
      setChildOverview(data);
    } catch {
      setChildOverview(null);
    } finally {
      setOverviewLoading(false);
    }
  };

  const handleLinkChild = async () => {
    if (!linkEmail.trim()) return;
    setLinkError('');
    setLinkLoading(true);
    try {
      await parentApi.linkChild(linkEmail.trim(), linkRelationship);
      closeLinkModal();
      await loadChildren();
    } catch (err: any) {
      setLinkError(err.response?.data?.detail || 'Failed to link child');
    } finally {
      setLinkLoading(false);
    }
  };

  const handleInviteStudent = async () => {
    if (!inviteEmail.trim()) return;
    setInviteError('');
    setInviteSuccess('');
    setInviteLoading(true);
    try {
      await invitesApi.create({
        email: inviteEmail.trim(),
        invite_type: 'student',
        metadata: { relationship_type: inviteRelationship },
      });
      setInviteSuccess(`Invite sent to ${inviteEmail.trim()}`);
      setInviteEmail('');
    } catch (err: any) {
      setInviteError(err.response?.data?.detail || 'Failed to send invite');
    } finally {
      setInviteLoading(false);
    }
  };

  const closeInviteModal = () => {
    setShowInviteModal(false);
    setInviteEmail('');
    setInviteRelationship('guardian');
    setInviteError('');
    setInviteSuccess('');
  };

  const handleConnectGoogle = async () => {
    try {
      localStorage.setItem('pendingAction', 'discover_children');
      const { authorization_url } = await googleApi.getConnectUrl();
      window.location.href = authorization_url;
    } catch {
      setLinkError('Failed to initiate Google connection');
      localStorage.removeItem('pendingAction');
    }
  };

  const triggerDiscovery = async () => {
    setDiscoveryState('discovering');
    setDiscoveredChildren([]);
    setSelectedDiscovered(new Set());
    setLinkError('');
    try {
      const data = await parentApi.discoverViaGoogle();
      setGoogleConnected(data.google_connected);
      setCoursesSearched(data.courses_searched);
      if (data.discovered.length > 0) {
        setDiscoveredChildren(data.discovered);
        // Pre-select children not already linked
        const preSelected = new Set(
          data.discovered.filter(c => !c.already_linked).map(c => c.user_id)
        );
        setSelectedDiscovered(preSelected);
        setDiscoveryState('results');
      } else {
        setDiscoveryState('no_results');
      }
    } catch (err: any) {
      setLinkError(err.response?.data?.detail || 'Failed to search Google Classroom');
      setDiscoveryState('idle');
    }
  };

  const handleBulkLink = async () => {
    if (selectedDiscovered.size === 0) return;
    setBulkLinking(true);
    setLinkError('');
    try {
      await parentApi.linkChildrenBulk(Array.from(selectedDiscovered));
      closeLinkModal();
      await loadChildren();
    } catch (err: any) {
      setLinkError(err.response?.data?.detail || 'Failed to link selected children');
    } finally {
      setBulkLinking(false);
    }
  };

  const toggleDiscovered = (userId: number) => {
    setSelectedDiscovered(prev => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });
  };

  const closeLinkModal = () => {
    setShowLinkModal(false);
    setLinkTab('email');
    setLinkEmail('');
    setLinkRelationship('guardian');
    setLinkError('');
    setDiscoveryState('idle');
    setDiscoveredChildren([]);
    setSelectedDiscovered(new Set());
  };

  const handleSyncChildCourses = async () => {
    if (!selectedChild) return;
    setSyncState('syncing');
    setSyncMessage('');
    try {
      const result = await parentApi.syncChildCourses(selectedChild);
      setSyncMessage(result.message);
      setSyncState('done');
      loadChildOverview(selectedChild);
      setTimeout(() => { setSyncState('idle'); setSyncMessage(''); }, 4000);
    } catch (err: any) {
      setSyncMessage(err.response?.data?.detail || 'Failed to sync courses');
      setSyncState('error');
      setTimeout(() => { setSyncState('idle'); setSyncMessage(''); }, 4000);
    }
  };

  const upcomingAssignments = childOverview?.assignments
    .filter(a => a.due_date && new Date(a.due_date) >= new Date())
    .sort((a, b) => new Date(a.due_date!).getTime() - new Date(b.due_date!).getTime())
    .slice(0, 10) || [];

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Monitor your child's progress">
        <div className="loading-state">Loading...</div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle="Monitor your child's progress">
      <div className="dashboard-grid">
        <div className="dashboard-card">
          <div className="card-icon">👨‍👩‍👧‍👦</div>
          <h3>Children</h3>
          <p className="card-value">{children.length}</p>
          <p className="card-label">Linked students</p>
        </div>

        <div className="dashboard-card">
          <div className="card-icon">📝</div>
          <h3>Assignments</h3>
          <p className="card-value">{childOverview?.assignments.length || '--'}</p>
          <p className="card-label">Total assignments</p>
        </div>

        <div className="dashboard-card">
          <div className="card-icon">📚</div>
          <h3>Courses</h3>
          <p className="card-value">{childOverview?.courses.length || '--'}</p>
          <p className="card-label">Enrolled courses</p>
        </div>

        <div className="dashboard-card clickable" onClick={() => navigate('/messages')}>
          <div className="card-icon">💬</div>
          <h3>Messages</h3>
          <p className="card-value">View</p>
          <p className="card-label">Message teachers</p>
        </div>
      </div>

      {children.length === 0 ? (
        <div className="no-children-state">
          <h3>No Children Linked</h3>
          <p>Link your child's student account to monitor their progress.</p>
          <button className="link-child-btn" onClick={() => setShowLinkModal(true)}>
            + Link Child
          </button>
          <button className="link-child-btn" onClick={() => setShowInviteModal(true)} style={{ marginTop: 8 }}>
            + Invite Student
          </button>
        </div>
      ) : (
        <>
          <div className="link-child-header">
            <button className="link-child-btn-small" onClick={() => setShowLinkModal(true)}>
              + Link Another Child
            </button>
            <button className="link-child-btn-small" onClick={() => setShowInviteModal(true)}>
              + Invite Student
            </button>
          </div>

          {children.length > 1 && (
            <div className="child-selector">
              {children.map((child) => (
                <button
                  key={child.student_id}
                  className={`child-tab ${selectedChild === child.student_id ? 'active' : ''}`}
                  onClick={() => setSelectedChild(child.student_id)}
                >
                  {child.full_name}
                  {child.relationship_type && (
                    <span className="relationship-badge">{child.relationship_type}</span>
                  )}
                  {child.grade_level && <span className="grade-badge">Grade {child.grade_level}</span>}
                </button>
              ))}
            </div>
          )}

          {overviewLoading ? (
            <div className="loading-state">Loading child data...</div>
          ) : childOverview ? (
            <div className="dashboard-sections">
              <section className="section">
                <h3>{childOverview.full_name}'s Upcoming Assignments</h3>
                {upcomingAssignments.length > 0 ? (
                  <ul className="assignments-list">
                    {upcomingAssignments.map((assignment) => (
                      <li key={assignment.id} className="assignment-item">
                        <div className="assignment-info">
                          <span className="assignment-title">{assignment.title}</span>
                          {assignment.due_date && (
                            <span className="assignment-due">
                              Due: {new Date(assignment.due_date).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="empty-state">
                    <p>No upcoming assignments</p>
                  </div>
                )}
              </section>

              <section className="section">
                <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3>{childOverview.full_name}'s Courses</h3>
                  {childOverview.google_connected && (
                    <button
                      className="link-child-btn-small"
                      onClick={handleSyncChildCourses}
                      disabled={syncState === 'syncing'}
                    >
                      {syncState === 'syncing' ? 'Syncing...' : 'Sync Courses'}
                    </button>
                  )}
                </div>
                {syncMessage && (
                  <div className={`status-message status-${syncState === 'error' ? 'error' : 'success'}`} style={{ marginBottom: 8 }}>
                    {syncMessage}
                  </div>
                )}
                {!childOverview.google_connected && (
                  <div className="google-warning">
                    Your child hasn't connected Google Classroom yet. Ask them to sign in and connect it from their dashboard.
                  </div>
                )}
                {childOverview.courses.length > 0 ? (
                  <ul className="courses-list">
                    {childOverview.courses.map((course) => (
                      <li key={course.id} className="course-item">
                        <span className="course-name">{course.name}</span>
                        {course.teacher_name && (
                          <span className="course-subject teacher">
                            Teacher: {course.teacher_name}
                          </span>
                        )}
                        {course.subject && (
                          <span className="course-subject">{course.subject}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="empty-state">
                    <p>No courses enrolled</p>
                  </div>
                )}
              </section>

              <section className="section">
                <h3>Study Materials</h3>
                <div className="study-count-card">
                  <span className="study-count">{childOverview.study_guides_count}</span>
                  <span className="study-label">study materials created</span>
                </div>
              </section>
            </div>
          ) : null}
        </>
      )}

      {/* Link Child Modal */}
      {showLinkModal && (
        <div className="modal-overlay" onClick={closeLinkModal}>
          <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
            <h2>Link Child Account</h2>

            {/* Tabs */}
            <div className="link-tabs">
              <button
                className={`link-tab ${linkTab === 'email' ? 'active' : ''}`}
                onClick={() => { setLinkTab('email'); setLinkError(''); }}
              >
                By Email
              </button>
              <button
                className={`link-tab ${linkTab === 'google' ? 'active' : ''}`}
                onClick={() => { setLinkTab('google'); setLinkError(''); }}
              >
                Via Google Classroom
              </button>
            </div>

            {/* Email Tab */}
            {linkTab === 'email' && (
              <>
                <p className="modal-desc">Enter your child's student email address to link their account.</p>
                <div className="modal-form">
                  <label>
                    Student Email
                    <input
                      type="email"
                      value={linkEmail}
                      onChange={(e) => { setLinkEmail(e.target.value); setLinkError(''); }}
                      placeholder="child@school.edu"
                      disabled={linkLoading}
                      onKeyDown={(e) => e.key === 'Enter' && handleLinkChild()}
                    />
                  </label>
                  <label>
                    Relationship
                    <select
                      value={linkRelationship}
                      onChange={(e) => setLinkRelationship(e.target.value)}
                      disabled={linkLoading}
                    >
                      <option value="mother">Mother</option>
                      <option value="father">Father</option>
                      <option value="guardian">Guardian</option>
                      <option value="other">Other</option>
                    </select>
                  </label>
                  {linkError && <p className="link-error">{linkError}</p>}
                </div>
                <div className="modal-actions">
                  <button className="cancel-btn" onClick={closeLinkModal} disabled={linkLoading}>
                    Cancel
                  </button>
                  <button className="generate-btn" onClick={handleLinkChild} disabled={linkLoading || !linkEmail.trim()}>
                    {linkLoading ? 'Linking...' : 'Link Child'}
                  </button>
                </div>
              </>
            )}

            {/* Google Tab */}
            {linkTab === 'google' && (
              <>
                {!googleConnected && discoveryState === 'idle' && (
                  <div className="google-connect-prompt">
                    <div className="google-icon">🔗</div>
                    <h3>Connect Google Account</h3>
                    <p>Sign in with your Google account to automatically discover your children's student accounts from Google Classroom.</p>
                    <button className="google-connect-btn" onClick={handleConnectGoogle}>
                      Connect Google Account
                    </button>
                    {linkError && <p className="link-error">{linkError}</p>}
                  </div>
                )}

                {googleConnected && discoveryState === 'idle' && (
                  <div className="google-connect-prompt">
                    <div className="google-icon">✓</div>
                    <h3>Google Account Connected</h3>
                    <p>Search your Google Classroom courses to find your children's student accounts.</p>
                    <button className="google-connect-btn" onClick={triggerDiscovery}>
                      Search Google Classroom
                    </button>
                    {linkError && <p className="link-error">{linkError}</p>}
                  </div>
                )}

                {discoveryState === 'discovering' && (
                  <div className="discovery-loading">
                    <div className="loading-spinner-large" />
                    <p>Searching Google Classroom courses for student accounts...</p>
                  </div>
                )}

                {discoveryState === 'results' && (
                  <div className="discovery-results">
                    <p className="modal-desc">
                      Found {discoveredChildren.length} student{discoveredChildren.length !== 1 ? 's' : ''} across {coursesSearched} course{coursesSearched !== 1 ? 's' : ''}. Select the children you want to link:
                    </p>
                    <div className="discovered-list">
                      {discoveredChildren.map((child) => (
                        <label
                          key={child.user_id}
                          className={`discovered-item ${child.already_linked ? 'disabled' : ''}`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedDiscovered.has(child.user_id)}
                            onChange={() => toggleDiscovered(child.user_id)}
                            disabled={child.already_linked}
                          />
                          <div className="discovered-info">
                            <span className="discovered-name">{child.full_name}</span>
                            <span className="discovered-email">{child.email}</span>
                            <span className="discovered-courses">
                              {child.google_courses.join(', ')}
                            </span>
                            {child.already_linked && (
                              <span className="discovered-linked-badge">Already linked</span>
                            )}
                          </div>
                        </label>
                      ))}
                    </div>
                    {linkError && <p className="link-error">{linkError}</p>}
                    <div className="modal-actions">
                      <button className="cancel-btn" onClick={closeLinkModal} disabled={bulkLinking}>
                        Cancel
                      </button>
                      <button
                        className="generate-btn"
                        onClick={handleBulkLink}
                        disabled={bulkLinking || selectedDiscovered.size === 0}
                      >
                        {bulkLinking ? 'Linking...' : `Link ${selectedDiscovered.size} Selected`}
                      </button>
                    </div>
                  </div>
                )}

                {discoveryState === 'no_results' && (
                  <div className="google-connect-prompt">
                    <div className="google-icon">📭</div>
                    <h3>No Matching Students Found</h3>
                    <p>
                      We searched {coursesSearched} Google Classroom course{coursesSearched !== 1 ? 's' : ''} but didn't find any matching student accounts.
                      Your child may need to register an account first, or you can link them by email.
                    </p>
                    <button className="link-tab-switch" onClick={() => { setLinkTab('email'); setDiscoveryState('idle'); }}>
                      Try linking by email instead
                    </button>
                    <div className="modal-actions" style={{ marginTop: 16 }}>
                      <button className="cancel-btn" onClick={closeLinkModal}>Close</button>
                      <button className="generate-btn" onClick={triggerDiscovery}>Search Again</button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
      {/* Invite Student Modal */}
      {showInviteModal && (
        <div className="modal-overlay" onClick={closeInviteModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Invite Student</h2>
            <p className="modal-desc">
              Send an email invite to create a new student account linked to yours.
            </p>
            <div className="modal-form">
              <label>
                Student Email
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => { setInviteEmail(e.target.value); setInviteError(''); setInviteSuccess(''); }}
                  placeholder="child@example.com"
                  disabled={inviteLoading}
                  onKeyDown={(e) => e.key === 'Enter' && handleInviteStudent()}
                />
              </label>
              <label>
                Relationship
                <select
                  value={inviteRelationship}
                  onChange={(e) => setInviteRelationship(e.target.value)}
                  disabled={inviteLoading}
                >
                  <option value="mother">Mother</option>
                  <option value="father">Father</option>
                  <option value="guardian">Guardian</option>
                  <option value="other">Other</option>
                </select>
              </label>
              {inviteError && <p className="link-error">{inviteError}</p>}
              {inviteSuccess && <p className="link-success">{inviteSuccess}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={closeInviteModal} disabled={inviteLoading}>
                Close
              </button>
              <button className="generate-btn" onClick={handleInviteStudent} disabled={inviteLoading || !inviteEmail.trim()}>
                {inviteLoading ? 'Sending...' : 'Send Invite'}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
