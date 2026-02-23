import { useState, useRef, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { dateKey } from '../components/calendar/types';
import CreateStudyMaterialModal from '../components/CreateStudyMaterialModal';
import { AlertBanner } from '../components/parent/AlertBanner';
import { StudentDetailPanel } from '../components/parent/StudentDetailPanel';
import { ActivityFeed } from '../components/parent/ActivityFeed';
import { ComingUpTimeline } from '../components/parent/ComingUpTimeline';
import { AddActionButton } from '../components/AddActionButton';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { TodaysFocusHeader } from '../components/parent/TodaysFocusHeader';
import { useParentDashboard, CHILD_COLORS } from '../components/parent/useParentDashboard';
import { useFocusTrap } from '../hooks/useFocusTrap';
import './ParentDashboard.css';

/** Section-specific skeleton that matches the Parent Dashboard layout. */
function DashboardSkeleton() {
  return (
    <div className="pd-skeleton" aria-busy="true" aria-label="Loading dashboard">
      {/* Today's Focus skeleton */}
      <div className="pd-skeleton-focus">
        <div className="skeleton pd-skeleton-headline" />
        <div className="pd-skeleton-tags">
          <div className="skeleton pd-skeleton-tag" />
          <div className="skeleton pd-skeleton-tag" />
          <div className="skeleton pd-skeleton-tag" style={{ width: 100 }} />
        </div>
      </div>

      {/* Child selector skeleton */}
      <div className="pd-skeleton-child-selector">
        <div className="skeleton pd-skeleton-pill" />
        <div className="skeleton pd-skeleton-pill" />
        <div className="skeleton pd-skeleton-pill" style={{ width: 100 }} />
      </div>

      {/* Timeline skeleton */}
      <div className="pd-skeleton-timeline">
        { [70, 55, 80, 60].map((w, i) => (
          <div className="pd-skeleton-timeline-item" key={i}>
            <div className="skeleton pd-skeleton-timeline-dot" />
            <div className="pd-skeleton-timeline-content">
              <div className="skeleton pd-skeleton-timeline-row" style={{ width: `${w}%` }} />
              <div className="skeleton pd-skeleton-timeline-row-sm" style={{ width: `${w - 20}%` }} />
            </div>
          </div>
        ))}
      </div>

      {/* Detail panel skeleton */}
      <div className="pd-skeleton-detail">
        <div className="skeleton pd-skeleton-detail-header" />
        <div className="skeleton pd-skeleton-detail-row" />
        <div className="skeleton pd-skeleton-detail-row" style={{ width: '50%' }} />
      </div>
    </div>
  );
}

export function ParentDashboard() {
  const pd = useParentDashboard();
  const [tipDismissed, setTipDismissed] = useState(false);
  const [comingUpDismissed, setComingUpDismissed] = useState(false);
  const childTabsRef = useRef<HTMLDivElement>(null);

  // Arrow key navigation for child selector tabs (ARIA tab pattern)
  const handleChildTabKeyDown = useCallback((e: React.KeyboardEvent, index: number) => {
    const tabs = childTabsRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    if (!tabs || tabs.length === 0) return;
    let nextIndex = -1;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      nextIndex = (index + 1) % tabs.length;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      nextIndex = (index - 1 + tabs.length) % tabs.length;
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextIndex = 0;
    } else if (e.key === 'End') {
      e.preventDefault();
      nextIndex = tabs.length - 1;
    }
    if (nextIndex >= 0) {
      tabs[nextIndex].focus();
      pd.handleChildTabClick(pd.children[nextIndex].student_id);
    }
  }, [pd]);

  // Focus traps for modals
  const linkModalRef = useFocusTrap<HTMLDivElement>(!!pd.showLinkModal, pd.closeLinkModal);
  const inviteModalRef = useFocusTrap<HTMLDivElement>(!!pd.showInviteModal, pd.closeInviteModal);
  const editChildModalRef = useFocusTrap<HTMLDivElement>(!!pd.showEditChildModal, pd.closeEditChildModal);
  const dayModalRef = useFocusTrap<HTMLDivElement>(!!pd.dayModalDate, pd.closeDayModal);
  const taskDetailModalRef = useFocusTrap<HTMLDivElement>(!!pd.taskDetailModal, () => pd.setTaskDetailModal(null));

  // Today's Focus header builder
  const renderHeaderSlot = pd.children.length > 0
    ? TodaysFocusHeader({
        children: pd.children,
        selectedChild: pd.selectedChild,
        selectedChildFirstName: pd.selectedChildFirstName,
        taskCounts: pd.taskCounts,
        pendingInviteCount: pd.pendingInvites.length,
        perChildOverdue: pd.perChildOverdue,
        collapsed: pd.focusCollapsed,
        onToggleCollapse: () => pd.setFocusCollapsed(prev => !prev),
        onNavigate: (path) => pd.navigate(path),
      })
    : undefined;

  if (pd.loading) {
    return (
      <DashboardLayout welcomeSubtitle="At-a-glance monitoring, calendar, and quick actions">
        <DashboardSkeleton />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      welcomeSubtitle="At-a-glance monitoring, calendar, and quick actions"
      headerSlot={renderHeaderSlot}
    >
      {pd.dashboardError ? (
        <div className="no-children-state">
          <h3>Unable to Load Dashboard</h3>
          <p>Something went wrong while loading your dashboard. Please try refreshing the page.</p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '20px' }}>
            <button className="link-child-btn" onClick={() => window.location.reload()}>Refresh Page</button>
          </div>
        </div>
      ) : pd.children.length === 0 ? (
        <div className="pd-onboard-container">
          <h2 className="pd-onboard-title">Welcome to ClassBridge!</h2>
          <p className="pd-onboard-subtitle">Your education command center starts here.</p>

          <div className="pd-onboard-steps" role="list" aria-label="Setup steps">
            <div className="pd-onboard-card pd-onboard-card-active" role="listitem" style={{ animationDelay: '0ms' }}>
              <span className="pd-onboard-card-step">Step 1</span>
              <span className="pd-onboard-card-icon" aria-hidden="true">👨‍👩‍👧</span>
              <span className="pd-onboard-card-title">Add Your Child</span>
              <span className="pd-onboard-card-desc">Create a profile or link an existing student account</span>
            </div>
            <div className="pd-onboard-card pd-onboard-card-future" role="listitem" style={{ animationDelay: '100ms' }}>
              <span className="pd-onboard-card-step">Step 2</span>
              <span className="pd-onboard-card-icon" aria-hidden="true">🏫</span>
              <span className="pd-onboard-card-title">Connect School</span>
              <span className="pd-onboard-card-desc">Import classes from Google Classroom automatically</span>
            </div>
            <div className="pd-onboard-card pd-onboard-card-future" role="listitem" style={{ animationDelay: '200ms' }}>
              <span className="pd-onboard-card-step">Step 3</span>
              <span className="pd-onboard-card-icon" aria-hidden="true">📚</span>
              <span className="pd-onboard-card-title">Explore Tools</span>
              <span className="pd-onboard-card-desc">Study guides, tasks &amp; tracking for your child</span>
            </div>
          </div>

          <button className="pd-onboard-cta" onClick={() => pd.setShowLinkModal(true)}>
            Get Started &mdash; Add Your First Child
          </button>
        </div>
      ) : (
        <>
          {/* Child Filter */}
          <div className="pd-child-selector" role="tablist" aria-label="Select child" ref={childTabsRef}>
            {pd.children.map((child, index) => {
              const isSelected = pd.selectedChild === child.student_id;
              const overdueCount = pd.childOverdueCounts.get(child.student_id) ?? 0;
              return (
                <button
                  key={child.student_id}
                  role="tab"
                  aria-selected={isSelected}
                  tabIndex={isSelected || (pd.selectedChild === null && index === 0) ? 0 : -1}
                  className={`pd-child-tab ${isSelected ? 'active' : ''}`}
                  onClick={() => pd.handleChildTabClick(child.student_id)}
                  onKeyDown={(e) => handleChildTabKeyDown(e, index)}
                >
                  <span className="pd-child-color-dot" aria-hidden="true" style={{ backgroundColor: CHILD_COLORS[index % CHILD_COLORS.length] }} />
                  {child.full_name}
                  {child.grade_level != null && <span className="pd-grade-badge">Grade {child.grade_level}</span>}
                  {overdueCount > 0 && <span className="pd-overdue-badge" aria-label={`${overdueCount} overdue`}>{overdueCount}</span>}
                </button>
              );
            })}
            <AddActionButton actions={[
              { icon: '\u{1F4DD}', label: 'Upload Documents', onClick: () => pd.setShowStudyModal(true) },
              { icon: '\u2705', label: 'Create Task', onClick: () => pd.setShowCreateTaskModal(true) },
            ]} />
          </div>

          <AlertBanner
            pendingInvites={pd.pendingInvites.map(i => ({ id: i.id, email: i.email }))}
            onResendInvite={pd.handleResendInvite}
            resendingId={pd.resendingId}
          />

          {pd.backgroundGeneration && (
            <div className={`pd-generation-banner ${pd.backgroundGeneration.status}`}>
              {pd.backgroundGeneration.status === 'generating' && (
                <>
                  <span className="pd-gen-spinner" />
                  <span>Generating {pd.backgroundGeneration.type}...</span>
                </>
              )}
              {pd.backgroundGeneration.status === 'success' && (
                <>
                  <span>{pd.backgroundGeneration.type} ready!</span>
                  <button className="pd-gen-view-btn" onClick={() => { pd.navigate('/course-materials'); pd.dismissBackgroundGeneration(); }}>
                    View
                  </button>
                  <button className="pd-gen-dismiss-btn" onClick={pd.dismissBackgroundGeneration}>&times;</button>
                </>
              )}
              {pd.backgroundGeneration.status === 'error' && (
                <>
                  <span>Failed to generate {pd.backgroundGeneration.type}</span>
                  <button className="pd-gen-dismiss-btn" onClick={pd.dismissBackgroundGeneration}>&times;</button>
                </>
              )}
            </div>
          )}

          {/* Coming Up Timeline */}
          {!comingUpDismissed && (
            <ComingUpTimeline
              calendarAssignments={pd.calendarAssignments}
              filteredTasks={pd.filteredTasks}
              selectedChild={pd.selectedChild}
              onToggleTask={pd.handleToggleTask}
              onNavigateStudy={pd.handleOneClickStudy}
              onDismiss={() => setComingUpDismissed(true)}
            />
          )}

          {!tipDismissed && pd.courseMaterials.length === 0 && (
            <div className="pd-onboard-tip" role="status">
              <span className="pd-onboard-tip-icon" aria-hidden="true">💡</span>
              <span className="pd-onboard-tip-text">Upload class materials to generate AI study guides for your child</span>
              <button className="pd-onboard-tip-action" onClick={() => pd.setShowStudyModal(true)}>Upload Now</button>
              <button className="pd-onboard-tip-dismiss" onClick={() => setTipDismissed(true)} aria-label="Dismiss tip">&times;</button>
            </div>
          )}

          <StudentDetailPanel
            selectedChildName={pd.selectedChild ? (pd.children.find(c => c.student_id === pd.selectedChild)?.full_name ?? null) : null}
            courseMaterials={pd.courseMaterials}
            tasks={pd.filteredTasks}
            collapsed={pd.detailPanelCollapsed}
            onToggleCollapsed={() => pd.setDetailPanelCollapsed(v => !v)}
            onViewMaterial={(mat) => pd.navigate(`/course-materials/${mat.id}`)}
            onToggleTask={pd.handleToggleTask}
            onTaskClick={(task) => pd.setTaskDetailModal(task)}
            onViewAllTasks={() => pd.navigate('/tasks', { state: { selectedChild: pd.selectedChildUserId } })}
            onViewAllMaterials={() => pd.navigate('/course-materials', { state: { selectedChild: pd.selectedChildUserId } })}
          />

          <ActivityFeed
            courseMaterials={pd.courseMaterials}
            onViewMaterial={(mat) => pd.navigate(`/course-materials/${mat.id}`)}
            onViewAllMaterials={() => pd.navigate('/course-materials')}
          />

          {/* Calendar moved to Tasks page */}
        </>
      )}

      {/* ============================================
          Modals
          ============================================ */}

      {/* Link Child Modal */}
      {pd.showLinkModal && (
        <div className="modal-overlay" onClick={pd.closeLinkModal}>
          <div className="modal modal-lg" role="dialog" aria-modal="true" aria-label="Add Child" ref={linkModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Add Child</h2>

            <div className="link-tabs" role="tablist" aria-label="Add child method">
              <button role="tab" aria-selected={pd.linkTab === 'create'} className={`link-tab ${pd.linkTab === 'create' ? 'active' : ''}`} onClick={() => { pd.setLinkTab('create'); pd.setLinkError(''); }}>Create New</button>
              <button role="tab" aria-selected={pd.linkTab === 'email'} className={`link-tab ${pd.linkTab === 'email' ? 'active' : ''}`} onClick={() => { pd.setLinkTab('email'); pd.setLinkError(''); }}>Link by Email</button>
              <button role="tab" aria-selected={pd.linkTab === 'google'} className={`link-tab ${pd.linkTab === 'google' ? 'active' : ''}`} onClick={() => { pd.setLinkTab('google'); pd.setLinkError(''); }}>Google Classroom</button>
            </div>

            {pd.linkTab === 'create' && (
              <>
                {pd.createChildInviteLink ? (
                  <div className="modal-form">
                    <div className="invite-success-box">
                      <p style={{ margin: '0 0 8px', fontWeight: 600 }}>Child added successfully!</p>
                      <p style={{ margin: '0 0 8px', fontSize: 14 }}>Share this link with your child so they can set their password and log in:</p>
                      <div className="invite-link-container">
                        <span className="invite-link">{pd.createChildInviteLink}</span>
                        <button className="copy-link-btn" onClick={() => navigator.clipboard.writeText(pd.createChildInviteLink)}>Copy</button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="modal-desc">Add your child with just their name. Email is optional.</p>
                    <div className="modal-form">
                      <label>Child's Name *<input type="text" value={pd.createChildName} onChange={(e) => pd.setCreateChildName(e.target.value)} placeholder="e.g. Alex Smith" disabled={pd.createChildLoading} onKeyDown={(e) => e.key === 'Enter' && pd.handleCreateChild()} /></label>
                      <label>Email (optional)<input type="email" value={pd.createChildEmail} onChange={(e) => { pd.setCreateChildEmail(e.target.value); pd.setCreateChildError(''); }} placeholder="child@example.com" disabled={pd.createChildLoading} /></label>
                      <label>Relationship
                        <select value={pd.createChildRelationship} onChange={(e) => pd.setCreateChildRelationship(e.target.value)} disabled={pd.createChildLoading}>
                          <option value="mother">Mother</option><option value="father">Father</option><option value="guardian">Guardian</option><option value="other">Other</option>
                        </select>
                      </label>
                      {pd.createChildError && <p className="link-error">{pd.createChildError}</p>}
                    </div>
                  </>
                )}
                <div className="modal-actions">
                  <button className="cancel-btn" onClick={pd.closeLinkModal} disabled={pd.createChildLoading}>{pd.createChildInviteLink ? 'Close' : 'Cancel'}</button>
                  {!pd.createChildInviteLink && (
                    <button className="generate-btn" onClick={pd.handleCreateChild} disabled={pd.createChildLoading || !pd.createChildName.trim()}>
                      {pd.createChildLoading ? 'Creating...' : 'Add Child'}
                    </button>
                  )}
                </div>
              </>
            )}

            {pd.linkTab === 'email' && (
              <>
                {pd.linkInviteLink ? (
                  <div className="modal-form">
                    <div className="invite-success-box">
                      <p style={{ margin: '0 0 8px', fontWeight: 600 }}>Child linked successfully!</p>
                      <p style={{ margin: '0 0 8px', fontSize: 14 }}>A new student account was created. Share this link with your child so they can set their password and log in:</p>
                      <div className="invite-link-container">
                        <span className="invite-link">{pd.linkInviteLink}</span>
                        <button className="copy-link-btn" onClick={() => navigator.clipboard.writeText(pd.linkInviteLink)}>Copy</button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="modal-desc">Enter your child's email to link or create their account.</p>
                    <div className="modal-form">
                      <label>Child's Name<input type="text" value={pd.linkName} onChange={(e) => pd.setLinkName(e.target.value)} placeholder="e.g. Alex Smith" disabled={pd.linkLoading} /></label>
                      <label>Student Email<input type="email" value={pd.linkEmail} onChange={(e) => { pd.setLinkEmail(e.target.value); pd.setLinkError(''); }} placeholder="child@school.edu" disabled={pd.linkLoading} onKeyDown={(e) => e.key === 'Enter' && pd.handleLinkChild()} /></label>
                      <label>Relationship
                        <select value={pd.linkRelationship} onChange={(e) => pd.setLinkRelationship(e.target.value)} disabled={pd.linkLoading}>
                          <option value="mother">Mother</option><option value="father">Father</option><option value="guardian">Guardian</option><option value="other">Other</option>
                        </select>
                      </label>
                      {pd.linkError && <p className="link-error">{pd.linkError}</p>}
                    </div>
                  </>
                )}
                <div className="modal-actions">
                  <button className="cancel-btn" onClick={pd.closeLinkModal} disabled={pd.linkLoading}>{pd.linkInviteLink ? 'Close' : 'Cancel'}</button>
                  {!pd.linkInviteLink && (
                    <button className="generate-btn" onClick={pd.handleLinkChild} disabled={pd.linkLoading || !pd.linkEmail.trim()}>
                      {pd.linkLoading ? 'Linking...' : 'Link Child'}
                    </button>
                  )}
                </div>
              </>
            )}

            {pd.linkTab === 'google' && (
              <>
                {!pd.googleConnected && pd.discoveryState === 'idle' && (
                  <div className="pd-google-connect-prompt">
                    <div className="pd-google-icon">🔗</div>
                    <h3>Connect Google Account</h3>
                    <p>Sign in with your Google account to automatically discover your children's student accounts from Google Classroom.</p>
                    <button className="pd-google-connect-btn" onClick={pd.handleConnectGoogle}>Connect Google Account</button>
                    {pd.linkError && <p className="link-error">{pd.linkError}</p>}
                  </div>
                )}
                {((pd.googleConnected && pd.discoveryState === 'idle') || pd.discoveryState === 'discovering') && (
                  <div className="pd-discovery-loading">
                    <div className="pd-loading-spinner-large" />
                    <p>Searching Google Classroom courses for student accounts...</p>
                  </div>
                )}
                {pd.discoveryState === 'results' && (
                  <div className="discovery-results">
                    {pd.bulkLinkSuccess > 0 && (
                      <div className="invite-success-box" style={{ marginBottom: 12 }}>
                        <p style={{ margin: 0, fontWeight: 600 }}>Successfully linked {pd.bulkLinkSuccess} child{pd.bulkLinkSuccess !== 1 ? 'ren' : ''}!</p>
                      </div>
                    )}
                    {pd.discoveredChildren.every(c => c.already_linked) ? (
                      <p className="modal-desc">All {pd.discoveredChildren.length} discovered student{pd.discoveredChildren.length !== 1 ? 's' : ''} are linked to your account.</p>
                    ) : (
                      <p className="modal-desc">Found {pd.discoveredChildren.length} student{pd.discoveredChildren.length !== 1 ? 's' : ''} across {pd.coursesSearched} class{pd.coursesSearched !== 1 ? 'es' : ''}. Select the children you want to link:</p>
                    )}
                    <div className="discovered-list">
                      {pd.discoveredChildren.map((child) => (
                        <label key={child.user_id} className={`discovered-item ${child.already_linked ? 'disabled' : ''}`}>
                          <input type="checkbox" checked={pd.selectedDiscovered.has(child.user_id)} onChange={() => pd.toggleDiscovered(child.user_id)} disabled={child.already_linked} />
                          <div className="discovered-info">
                            <span className="discovered-name">{child.full_name}</span>
                            <span className="discovered-email">{child.email}</span>
                            <span className="discovered-courses">{child.google_courses.join(', ')}</span>
                            {child.already_linked && <span className="discovered-linked-badge">Already linked</span>}
                          </div>
                        </label>
                      ))}
                    </div>
                    {pd.linkError && <p className="link-error">{pd.linkError}</p>}
                    <div className="modal-actions" style={{ justifyContent: 'space-between' }}>
                      <button className="cancel-btn" style={{ fontSize: '13px' }} onClick={async () => { try { await (await import('../api/client')).googleApi.disconnect(); pd.setGoogleConnected(false); pd.setDiscoveryState('idle'); pd.setDiscoveredChildren([]); pd.setBulkLinkSuccess(0); } catch { pd.setLinkError('Failed to disconnect Google account'); } }}>Disconnect Google</button>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button className="cancel-btn" onClick={pd.closeLinkModal} disabled={pd.bulkLinking}>Done</button>
                        {!pd.discoveredChildren.every(c => c.already_linked) && (
                          <button className="generate-btn" onClick={pd.handleBulkLink} disabled={pd.bulkLinking || pd.selectedDiscovered.size === 0}>
                            {pd.bulkLinking ? 'Linking...' : `Link ${pd.selectedDiscovered.size} Selected`}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )}
                {pd.discoveryState === 'no_results' && (
                  <div className="pd-google-connect-prompt">
                    <div className="pd-google-icon">📭</div>
                    <h3>No Matching Students Found</h3>
                    <p>We searched {pd.coursesSearched} Google Classroom class{pd.coursesSearched !== 1 ? 'es' : ''} but didn't find any matching student accounts.</p>
                    <button className="pd-link-tab-switch" onClick={() => { pd.setLinkTab('email'); pd.setDiscoveryState('idle'); }}>Try linking by email instead</button>
                    <div className="modal-actions">
                      <button className="cancel-btn" onClick={pd.closeLinkModal}>Close</button>
                      <button className="generate-btn" onClick={pd.triggerDiscovery}>Search Again</button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Invite Student Modal */}
      {pd.showInviteModal && (
        <div className="modal-overlay" onClick={pd.closeInviteModal}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Invite Student" ref={inviteModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Invite Student</h2>
            <p className="modal-desc">Send an email invite to create a new student account linked to yours.</p>
            <div className="modal-form">
              <label>Student Email<input type="email" value={pd.inviteEmail} onChange={(e) => { pd.setInviteEmail(e.target.value); pd.setInviteError(''); pd.setInviteSuccess(''); }} placeholder="child@example.com" disabled={pd.inviteLoading} onKeyDown={(e) => e.key === 'Enter' && pd.handleInviteStudent()} /></label>
              <label>Relationship
                <select value={pd.inviteRelationship} onChange={(e) => pd.setInviteRelationship(e.target.value)} disabled={pd.inviteLoading}>
                  <option value="mother">Mother</option><option value="father">Father</option><option value="guardian">Guardian</option><option value="other">Other</option>
                </select>
              </label>
              {pd.inviteError && <p className="link-error">{pd.inviteError}</p>}
              {pd.inviteSuccess && (
                <div className="invite-success-box">
                  <p className="link-success">Invite created!</p>
                  <p className="invite-link-label">Share this link with your child:</p>
                  <div className="invite-link-container">
                    <code className="invite-link">{pd.inviteSuccess.split('\n')[1]}</code>
                    <button className="copy-link-btn" onClick={() => { navigator.clipboard.writeText(pd.inviteSuccess.split('\n')[1]); alert('Link copied!'); }}>Copy</button>
                  </div>
                </div>
              )}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={pd.closeInviteModal} disabled={pd.inviteLoading}>Close</button>
              <button className="generate-btn" onClick={pd.handleInviteStudent} disabled={pd.inviteLoading || !pd.inviteEmail.trim() || !!pd.inviteSuccess}>
                {pd.inviteLoading ? 'Creating...' : 'Create Invite'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Child Modal */}
      {pd.showEditChildModal && pd.editChild && (
        <div className="modal-overlay" onClick={pd.closeEditChildModal}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Edit Child" ref={editChildModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Edit Child</h2>
            <p className="modal-desc">Update {pd.editChild.full_name}'s profile information.</p>
            <div className="modal-form">
              <label>Name<input type="text" value={pd.editChildName} onChange={(e) => pd.setEditChildName(e.target.value)} placeholder="Child's name" disabled={pd.editChildLoading} onKeyDown={(e) => e.key === 'Enter' && pd.handleEditChild()} /></label>
              <label>Email<input type="email" value={pd.editChildEmail} onChange={(e) => pd.setEditChildEmail(e.target.value)} placeholder="child@example.com" disabled={pd.editChildLoading} onKeyDown={(e) => e.key === 'Enter' && pd.handleEditChild()} /></label>
              <label>Grade Level
                <select value={pd.editChildGrade} onChange={(e) => pd.setEditChildGrade(e.target.value)} disabled={pd.editChildLoading}>
                  <option value="">Not set</option>
                  {Array.from({ length: 13 }, (_, i) => (<option key={i} value={String(i)}>{i === 0 ? 'Kindergarten' : `Grade ${i}`}</option>))}
                </select>
              </label>
              <label>School<input type="text" value={pd.editChildSchool} onChange={(e) => pd.setEditChildSchool(e.target.value)} placeholder="e.g., Lincoln Elementary" disabled={pd.editChildLoading} /></label>
              <div className="collapsible-section">
                <button type="button" className="collapsible-toggle" onClick={() => pd.setEditChildOptionalOpen(!pd.editChildOptionalOpen)}>
                  <span className={`collapsible-arrow ${pd.editChildOptionalOpen ? 'open' : ''}`}>&#9656;</span>
                  Additional Details
                </button>
                {pd.editChildOptionalOpen && (
                  <div className="collapsible-content">
                    <label>Date of Birth<input type="date" value={pd.editChildDob} onChange={(e) => pd.setEditChildDob(e.target.value)} disabled={pd.editChildLoading} /></label>
                    <label>Phone<input type="tel" value={pd.editChildPhone} onChange={(e) => pd.setEditChildPhone(e.target.value)} placeholder="e.g., 555-123-4567" disabled={pd.editChildLoading} /></label>
                    <label>Address<input type="text" value={pd.editChildAddress} onChange={(e) => pd.setEditChildAddress(e.target.value)} placeholder="Street address" disabled={pd.editChildLoading} /></label>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      <label>City<input type="text" value={pd.editChildCity} onChange={(e) => pd.setEditChildCity(e.target.value)} placeholder="City" disabled={pd.editChildLoading} /></label>
                      <label>Province<input type="text" value={pd.editChildProvince} onChange={(e) => pd.setEditChildProvince(e.target.value)} placeholder="Province" disabled={pd.editChildLoading} /></label>
                    </div>
                    <label>Postal Code<input type="text" value={pd.editChildPostal} onChange={(e) => pd.setEditChildPostal(e.target.value)} placeholder="e.g., A1B 2C3" disabled={pd.editChildLoading} /></label>
                    <label>Notes<textarea value={pd.editChildNotes} onChange={(e) => pd.setEditChildNotes(e.target.value)} placeholder="Any additional notes about your child..." disabled={pd.editChildLoading} rows={3} /></label>
                  </div>
                )}
              </div>
              {pd.editChildError && <p className="link-error">{pd.editChildError}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={pd.closeEditChildModal} disabled={pd.editChildLoading}>Cancel</button>
              <button className="generate-btn" onClick={pd.handleEditChild} disabled={pd.editChildLoading || !pd.editChildName.trim()}>
                {pd.editChildLoading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Day Detail Modal */}
      {pd.dayModalDate && (
        <div className="modal-overlay" onClick={pd.closeDayModal}>
          <div className="modal modal-lg" role="dialog" aria-modal="true" aria-label={`Day detail: ${pd.dayModalDate.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}`} ref={dayModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>{pd.dayModalDate.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</h2>

            {(() => {
              const dk = dateKey(pd.dayModalDate);
              const dayAssigns = pd.calendarAssignments.filter(a => dateKey(a.dueDate) === dk && a.itemType !== 'task');
              return dayAssigns.length > 0 ? (
                <div className="pd-day-modal-section">
                  <div className="pd-day-modal-section-title">Assignments</div>
                  <div className="pd-day-modal-list">
                    {dayAssigns.map(a => (
                      <div key={a.id} className="pd-day-modal-item">
                        <span className="cal-entry-dot" style={{ background: a.courseColor }} />
                        <div className="pd-day-modal-item-info">
                          <span className="pd-day-modal-item-title">{a.title}</span>
                          <span className="pd-day-modal-item-meta">{a.courseName}{a.childName ? ` \u2022 ${a.childName}` : ''}</span>
                        </div>
                        <div className="pd-day-modal-item-actions">
                          {a.courseId > 0 && <button className="pd-day-modal-action-btn" onClick={() => { pd.closeDayModal(); pd.handleGoToCourse(a.courseId); }}>Class</button>}
                          <button className="pd-day-modal-study-btn" disabled={pd.generatingStudyId === a.id} onClick={() => { pd.closeDayModal(); pd.handleOneClickStudy(a); }}>{pd.generatingStudyId === a.id ? 'Checking...' : 'Study'}</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null;
            })()}

            <div className="pd-day-modal-section">
              <div className="pd-day-modal-section-title">Tasks</div>
              <div className="pd-day-modal-list">
                {pd.dayTasks.length === 0 && <div className="pd-day-modal-empty">No tasks for this day</div>}
                {pd.dayTasks.map(task => {
                  const isExpanded = pd.expandedTaskId === task.id;
                  const priorityClass = task.priority || 'medium';
                  return (
                    <div key={task.id} className={`pd-task-sticky-note ${priorityClass}${task.is_completed ? ' completed' : ''}`} onClick={() => pd.setExpandedTaskId(prev => prev === task.id ? null : task.id)}>
                      <div className="pd-task-sticky-header">
                        <input type="checkbox" checked={task.is_completed} onChange={(e) => { e.stopPropagation(); pd.handleToggleTask(task); }} className="pd-task-checkbox" />
                        <div className="pd-task-sticky-body">
                          <span className={`pd-task-sticky-title${task.is_completed ? ' completed' : ''}`}>{task.title}</span>
                          <span className="pd-task-sticky-meta">
                            <span className={`pd-task-priority-badge ${priorityClass}`} aria-label={`Priority: ${priorityClass}`}>{priorityClass === 'high' ? '\u25B2 ' : priorityClass === 'low' ? '\u25BC ' : '\u25CF '}{priorityClass}</span>
                            {task.assignee_name && <span className="pd-task-sticky-assignee">&rarr; {task.assignee_name}</span>}
                          </span>
                        </div>
                        <button className="pd-task-delete-btn" onClick={(e) => { e.stopPropagation(); pd.handleDeleteTask(task.id); }} title="Archive task" aria-label="Delete this task">&times;</button>
                      </div>
                      {isExpanded && (
                        <div className="pd-task-sticky-detail">
                          {task.description && <p className="pd-task-sticky-desc">{task.description}</p>}
                          <div className="pd-task-sticky-detail-row">
                            {task.due_date && <span>Due: {new Date(task.due_date).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>}
                            {task.creator_name && <span>Created by: {task.creator_name}</span>}
                            {task.category && <span>Category: {task.category}</span>}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              <div className="pd-day-modal-add-task">
                <input type="text" value={pd.newTaskTitle} onChange={(e) => pd.setNewTaskTitle(e.target.value)} placeholder="Add a task..." onKeyDown={(e) => e.key === 'Enter' && pd.handleCreateDayTask()} disabled={pd.newTaskCreating} />
                <button onClick={pd.handleCreateDayTask} disabled={pd.newTaskCreating || !pd.newTaskTitle.trim()} className="generate-btn">
                  {pd.newTaskCreating ? '...' : 'Add'}
                </button>
              </div>
            </div>

            <div className="modal-actions">
              <button className="cancel-btn" onClick={pd.closeDayModal}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Task Detail Modal */}
      {pd.taskDetailModal && (
        <div className="modal-overlay" onClick={() => pd.setTaskDetailModal(null)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label={`Task: ${pd.taskDetailModal.title}`} ref={taskDetailModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>{pd.taskDetailModal.title}</h2>
            <div className="pd-task-detail-modal-body">
              {pd.taskDetailModal.description && <p className="pd-task-detail-desc">{pd.taskDetailModal.description}</p>}
              <div className="pd-task-detail-fields">
                <div className="pd-task-detail-row"><span className="pd-task-detail-label">Status</span><span className={`sdp-task-badge ${pd.taskDetailModal.is_completed ? 'completed' : 'pending'}`}>{pd.taskDetailModal.is_completed ? 'Completed' : 'Pending'}</span></div>
                {pd.taskDetailModal.due_date && <div className="pd-task-detail-row"><span className="pd-task-detail-label">Due Date</span><span>{new Date(pd.taskDetailModal.due_date).toLocaleDateString(undefined, { weekday: 'short', month: 'long', day: 'numeric', year: 'numeric' })}</span></div>}
                {pd.taskDetailModal.priority && <div className="pd-task-detail-row"><span className="pd-task-detail-label">Priority</span><span className={`pd-task-priority-badge ${pd.taskDetailModal.priority}`}>{pd.taskDetailModal.priority}</span></div>}
                {pd.taskDetailModal.assignee_name && <div className="pd-task-detail-row"><span className="pd-task-detail-label">Assigned To</span><span>{pd.taskDetailModal.assignee_name}</span></div>}
                {pd.taskDetailModal.creator_name && <div className="pd-task-detail-row"><span className="pd-task-detail-label">Created By</span><span>{pd.taskDetailModal.creator_name}</span></div>}
                {pd.taskDetailModal.course_name && <div className="pd-task-detail-row"><span className="pd-task-detail-label">Class</span><span>{pd.taskDetailModal.course_name}</span></div>}
                {pd.taskDetailModal.category && <div className="pd-task-detail-row"><span className="pd-task-detail-label">Category</span><span>{pd.taskDetailModal.category}</span></div>}
              </div>
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => pd.setTaskDetailModal(null)}>Close</button>
              <button className="generate-btn view-details-btn" onClick={() => { pd.setTaskDetailModal(null); pd.navigate(`/tasks/${pd.taskDetailModal!.id}`); }}>View Details</button>
              <button className="generate-btn" onClick={() => { pd.handleToggleTask(pd.taskDetailModal!); pd.setTaskDetailModal({ ...pd.taskDetailModal!, is_completed: !pd.taskDetailModal!.is_completed }); }}>
                {pd.taskDetailModal.is_completed ? 'Mark Incomplete' : 'Mark Complete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Study Tools Modal */}
      <CreateStudyMaterialModal
        open={pd.showStudyModal}
        onClose={pd.resetStudyModal}
        onGenerate={pd.handleGenerateFromModal}
        isGenerating={pd.isGenerating}
        initialTitle={pd.studyModalInitialTitle}
        initialContent={pd.studyModalInitialContent}
        duplicateCheck={pd.duplicateCheck}
        onViewExisting={() => {
          const guide = pd.duplicateCheck?.existing_guide;
          if (guide) { pd.resetStudyModal(); pd.navigate(guide.guide_type === 'quiz' ? `/study/quiz/${guide.id}` : guide.guide_type === 'flashcards' ? `/study/flashcards/${guide.id}` : `/study/guide/${guide.id}`); }
        }}
        onRegenerate={() => pd.handleGenerateFromModal({ title: pd.studyModalInitialTitle, content: pd.studyModalInitialContent, types: ['study_guide'], mode: 'text' })}
        onDismissDuplicate={() => pd.setDuplicateCheck(null)}
      />
      <CreateTaskModal
        open={pd.showCreateTaskModal}
        onClose={() => pd.setShowCreateTaskModal(false)}
        onCreated={() => { pd.setShowCreateTaskModal(false); pd.loadDashboard(); }}
      />
      {pd.confirmModal}
    </DashboardLayout>
  );
}
