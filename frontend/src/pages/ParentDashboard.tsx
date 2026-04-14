import { useState, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { dateKey } from '../components/calendar/types';
import UploadMaterialWizard from '../components/UploadMaterialWizard';
import { AlertBanner } from '../components/parent/AlertBanner';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { TodaysFocusHeader } from '../components/parent/TodaysFocusHeader';
import { useParentDashboard } from '../components/parent/useParentDashboard';
import { RoleQuickActions } from '../components/RoleQuickActions';
import type { QuickAction } from '../components/RoleQuickActions';
import { useFocusTrap } from '../hooks/useFocusTrap';
import { GoogleClassroomPrompt } from '../components/GoogleClassroomPrompt';
import { useFeature } from '../hooks/useFeatureToggle';
import { SetupChecklist } from '../components/SetupChecklist';
import { RecentActivityPanel } from '../components/parent/RecentActivityPanel';
import { HelpStudyMenu } from '../components/study/HelpStudyMenu';
import { ChildSelectorTabs } from '../components/ChildSelectorTabs';
import { SectionPanel } from '../components/SectionPanel';
import { GenerationSpinner } from '../components/GenerationSpinner';
import { AssessmentCountdown } from '../components/AssessmentCountdown';
import { ReportBugLink } from '../components/ReportBugLink';
import { JourneyNudgeBanner } from '../components/JourneyNudgeBanner';
import { GettingStartedWidget } from '../components/GettingStartedWidget';
import './ParentDashboard.css';
import './DashboardGrid.css';

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

// localStorage key for section collapse states
const SECTION_STATES_KEY = 'pd-section-states';
const VIEW_MODE_KEY = 'pd-view-mode';
const VIEW_MODE_VERSION_KEY = 'pd-view-mode-v';
const VIEW_MODE_VERSION = 2; // bump to force-reset all users to simplified

interface SectionStates {
  comingUp: boolean;
  studentDetail: boolean;
  activityFeed?: boolean; // deprecated — kept for localStorage compat
}

function loadSectionStates(): SectionStates {
  try {
    const saved = localStorage.getItem(SECTION_STATES_KEY);
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  // First-time defaults: all panels collapsed
  return { comingUp: false, studentDetail: false, activityFeed: false };
}

function saveSectionStates(states: SectionStates) {
  try { localStorage.setItem(SECTION_STATES_KEY, JSON.stringify(states)); } catch { /* ignore */ }
}

function loadViewMode(): 'simplified' | 'full' {
  try {
    const ver = localStorage.getItem(VIEW_MODE_VERSION_KEY);
    if (ver !== String(VIEW_MODE_VERSION)) {
      localStorage.setItem(VIEW_MODE_KEY, 'simplified');
      localStorage.setItem(VIEW_MODE_VERSION_KEY, String(VIEW_MODE_VERSION));
      return 'simplified';
    }
    const saved = localStorage.getItem(VIEW_MODE_KEY);
    if (saved === 'simplified' || saved === 'full') return saved;
  } catch { /* ignore */ }
  return 'simplified';
}

export function ParentDashboard() {
  const pd = useParentDashboard();
  const gcEnabled = useFeature('google_classroom');
  const [tipDismissed, setTipDismissed] = useState(false);
  const [tasksCollapsed, setTasksCollapsed] = useState(() => loadViewMode() === 'simplified');
  const [activityCollapsed, setActivityCollapsed] = useState(() => loadViewMode() === 'simplified');
  const [showHelpStudyMenu, setShowHelpStudyMenu] = useState(false);
  // Collapsible section states (#832) — sectionStates retained for simplified/full toggle
  const [, setSectionStates] = useState<SectionStates>(loadSectionStates);
  const [viewMode, setViewMode] = useState<'simplified' | 'full'>(loadViewMode);

  const handleToggleViewMode = useCallback(() => {
    setViewMode(prev => {
      const next = prev === 'full' ? 'simplified' : 'full';
      try { localStorage.setItem(VIEW_MODE_KEY, next); } catch { /* ignore */ }
      setTasksCollapsed(next === 'simplified');
      setActivityCollapsed(next === 'simplified');
      if (next === 'simplified') {
        const collapsed: SectionStates = { comingUp: false, studentDetail: false };
        setSectionStates(collapsed);
        saveSectionStates(collapsed);
      } else {
        const expanded: SectionStates = { comingUp: true, studentDetail: true };
        setSectionStates(expanded);
        saveSectionStates(expanded);
      }
      return next;
    });
  }, []);

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
      <JourneyNudgeBanner pageName="dashboard" />
      {pd.dashboardError ? (
        <div className="no-children-state">
          <h3>Unable to Load Dashboard</h3>
          <p>Something went wrong while loading your dashboard. Please try refreshing the page.</p>
          <ReportBugLink errorMessage="Unable to load dashboard" />
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
            {gcEnabled && (
            <div className="pd-onboard-card pd-onboard-card-future" role="listitem" style={{ animationDelay: '100ms' }}>
              <span className="pd-onboard-card-step">Step 2</span>
              <span className="pd-onboard-card-icon" aria-hidden="true">🏫</span>
              <span className="pd-onboard-card-title">Connect School</span>
              <span className="pd-onboard-card-desc">Import classes from Google Classroom automatically</span>
            </div>
            )}
            <div className="pd-onboard-card pd-onboard-card-future" role="listitem" style={{ animationDelay: gcEnabled ? '200ms' : '100ms' }}>
              <span className="pd-onboard-card-step">{gcEnabled ? 'Step 3' : 'Step 2'}</span>
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
          {/* Onboarding Setup Checklist (#869) */}
          <SetupChecklist />

          {/* Getting Started progress widget (#2610) */}
          <GettingStartedWidget
            completedStepIds={[
              ...(pd.children.length > 0 ? ['add_child'] : []),
              ...(pd.courseMaterials.length > 0 ? ['upload_material'] : []),
            ]}
          />

          {/* Above-grid elements */}
          <div className="dash-above-grid">
            {/* View Mode Toggle (#832) */}
          <div className="pd-view-toggle-row">
            <button
              className="pd-view-toggle"
              onClick={handleToggleViewMode}
              aria-label={viewMode === 'full' ? 'Switch to simplified view' : 'Switch to full view'}
              type="button"
            >
              <span className={`pd-view-toggle-option ${viewMode === 'simplified' ? 'active' : ''}`}>Simplified</span>
              <span className={`pd-view-toggle-option ${viewMode === 'full' ? 'active' : ''}`}>Full</span>
            </button>
          </div>

          {/* Child Filter (#830) */}
          <ChildSelectorTabs
            children={pd.children}
            selectedChild={pd.selectedChild}
            onSelectChild={(id) => {
              if (id === null) { pd.handleAllChildrenClick(); } else { pd.handleChildTabClick(id); }
              setTasksCollapsed(false);
              setActivityCollapsed(false);
              if (viewMode === 'simplified') { setViewMode('full'); try { localStorage.setItem(VIEW_MODE_KEY, 'full'); } catch { /* ignore */ } }
            }}
            childOverdueCounts={pd.childOverdueCounts}
          />

          <AlertBanner
            pendingInvites={pd.pendingInvites.map(i => ({ id: i.id, email: i.email }))}
            onResendInvite={pd.handleResendInvite}
            resendingId={pd.resendingId}
          />

          {pd.backgroundGeneration && (
            <div className={`pd-generation-banner ${pd.backgroundGeneration.status}`}>
              {pd.backgroundGeneration.status === 'generating' && (
                <>
                  <GenerationSpinner size="sm" />
                  <span>{pd.backgroundGeneration.type === 'Material' ? 'Uploading material...' : `Generating ${pd.backgroundGeneration.type}...`}</span>
                </>
              )}
              {pd.backgroundGeneration.status === 'success' && (
                <>
                  <span>{pd.backgroundGeneration.type === 'Material' ? 'Material uploaded!' : `${pd.backgroundGeneration.type} ready!`}</span>
                  <button className="pd-gen-view-btn" onClick={() => { pd.navigate(pd.getBackgroundGenerationRoute()); pd.dismissBackgroundGeneration(); }}>
                    View
                  </button>
                  <button className="pd-gen-dismiss-btn" onClick={pd.dismissBackgroundGeneration}>&times;</button>
                </>
              )}
              {pd.backgroundGeneration.status === 'error' && (
                <>
                  <span>{pd.backgroundGeneration.type === 'Material' ? 'Upload failed' : `Failed to generate ${pd.backgroundGeneration.type}`}{pd.backgroundGeneration.error ? `: ${pd.backgroundGeneration.error}` : ''}</span>
                  <button className="pd-gen-dismiss-btn" onClick={pd.dismissBackgroundGeneration}>&times;</button>
                </>
              )}
            </div>
          )}

          {/* Google Classroom connection prompt when selected child has 0 courses (#874) */}
          {(() => {
            const selectedChildData = pd.selectedChild
              ? pd.children.find(c => c.student_id === pd.selectedChild)
              : null;
            if (selectedChildData && selectedChildData.course_count === 0) {
              return (
                <GoogleClassroomPrompt
                  childName={selectedChildData.full_name}
                  childStudentId={selectedChildData.student_id}
                  onAddManually={() => pd.navigate('/courses')}
                />
              );
            }
            return null;
          })()}

          {/* Quick Action Bar (#837 unified) */}
          <RoleQuickActions
            actions={[
              {
                icon: (
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                  </svg>
                ),
                label: 'View Class Materials',
                onClick: () => pd.navigate('/course-materials'),
              },
              {
                icon: (
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                ),
                label: 'Upload Class Material',
                onClick: () => pd.setShowStudyModal(true),
              },
              {
                icon: (
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M9 9a3 3 0 015.12 1.5c0 2-3 2-3 4" />
                    <circle cx="12" cy="18" r="0.5" fill="currentColor" />
                  </svg>
                ),
                label: 'Help My Kid',
                onClick: () => setShowHelpStudyMenu(true),
              },
              ...(pd.selectedChild ? [{
                icon: (
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
                  </svg>
                ),
                label: `Teach ${pd.selectedChildFirstName || 'Child'}`,
                onClick: () => pd.navigate(`/flash-tutor?mode=parent_teaching&child_id=${pd.selectedChild}`),
              }] : []) as QuickAction[],
              {
                icon: (
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M9 11l3 3L22 4" />
                    <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
                  </svg>
                ),
                label: 'Quiz History',
                onClick: () => pd.navigate('/quiz-history'),
              },
              {
                icon: (
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M16 21v-2a4 4 0 00-4-4H5a4 4 0 00-4-4v2" />
                    <circle cx="8.5" cy="7" r="4" />
                    <line x1="20" y1="8" x2="20" y2="14" />
                    <line x1="23" y1="11" x2="17" y2="11" />
                  </svg>
                ),
                label: 'Add Child',
                onClick: () => pd.setShowLinkModal(true),
              },
              {
                icon: (
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                ),
                label: 'Export Data',
                onClick: () => pd.navigate('/settings/data-export'),
              },
              {
                icon: (
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
                  </svg>
                ),
                label: 'Account Settings',
                onClick: () => pd.navigate('/settings/account'),
              },
            ] satisfies QuickAction[]}
            maxVisible={3}
          />

          {!tipDismissed && pd.courseMaterials.length === 0 && (
              <div className="pd-onboard-tip" role="status">
                <span className="pd-onboard-tip-icon" aria-hidden="true">💡</span>
                <span className="pd-onboard-tip-text">Upload class materials to generate AI study guides for your child</span>
                <button className="pd-onboard-tip-action" onClick={() => pd.setShowStudyModal(true)}>Upload Now</button>
                <button className="pd-onboard-tip-dismiss" onClick={() => setTipDismissed(true)} aria-label="Dismiss tip">&times;</button>
              </div>
            )}
          </div>

          {/* ── Assessment Countdown ──────────────────────── */}
          <AssessmentCountdown />

          {/* 3-Section Dashboard Grid (#1415) */}
          <div className="dashboard-redesign">
            <SectionPanel
              title="Tasks Overview"
              icon="&#9728;&#65039;"
              count={pd.taskCounts.overdue + pd.taskCounts.dueToday + pd.taskCounts.upcoming}
              collapsed={tasksCollapsed}
              onToggle={() => setTasksCollapsed(c => !c)}
              headerRight={<a href="/tasks" className="dash-section-link" onClick={e => e.stopPropagation()}>All tasks</a>}
              className="dash-section--primary"
            >
                  {(pd.taskCounts.overdue > 0 || pd.taskCounts.dueToday > 0 || pd.taskCounts.upcoming > 0) && (
                    <div className="pd-task-status-pills" style={{ marginTop: 12 }}>
                      {pd.taskCounts.overdue > 0 && <button className="pd-status-pill pd-status-pill-overdue" onClick={() => pd.navigate('/tasks?due=overdue')}>{pd.taskCounts.overdue} overdue</button>}
                      {pd.taskCounts.dueToday > 0 && <button className="pd-status-pill pd-status-pill-today" onClick={() => pd.navigate('/tasks?due=today')}>{pd.taskCounts.dueToday} due today</button>}
                      {pd.taskCounts.upcoming > 0 && <button className="pd-status-pill pd-status-pill-upcoming" onClick={() => pd.navigate('/tasks?due=upcoming')}>{pd.taskCounts.upcoming} next 3 days</button>}
                    </div>
                  )}
                  {(() => {
                    const activeTasks = pd.filteredTasks.filter(t => !t.is_completed && !t.archived_at);
                    const topTasks = activeTasks.slice(0, 5);
                    if (topTasks.length === 0) return <p className="dash-empty-hint">No active tasks</p>;
                    return (
                      <div className="dash-task-list">
                        {topTasks.map(t => (
                          <div key={t.id} className="dash-task-row" onClick={() => pd.navigate(`/tasks/${t.id}`)} role="button" tabIndex={0} onKeyDown={e => { if (e.key === 'Enter') pd.navigate(`/tasks/${t.id}`); }}>
                            <span className={`task-priority-dot ${t.priority || 'medium'}`} />
                            <span className="dash-task-title">{t.title}</span>
                            {t.due_date && <span className="dash-task-due">{new Date(t.due_date.length === 10 ? t.due_date + 'T00:00:00' : t.due_date).toLocaleDateString()}</span>}
                          </div>
                        ))}
                      </div>
                    );
                  })()}
            </SectionPanel>

            <section className="dash-section dash-section--secondary">
              <RecentActivityPanel selectedChild={pd.selectedChild} navigate={pd.navigate} collapsed={activityCollapsed} onToggle={() => setActivityCollapsed(c => !c)} />
            </section>

            <section className="dash-section dash-section--actions">
              <div className="dash-section-header">
                <h3 className="dash-section-title">Quick Actions</h3>
              </div>
              <div className="dash-quick-actions">
                <button className="dash-quick-action" onClick={() => pd.navigate('/ai-tools')}><span className="dash-quick-action-icon">💡</span> Help My Kid</button>
                <button className="dash-quick-action" onClick={() => pd.navigate('/courses')}><span className="dash-quick-action-icon">📚</span> View Classes</button>
                <button className="dash-quick-action" onClick={() => pd.navigate('/courses?create=1')}><span className="dash-quick-action-icon">➕</span> Create Class</button>
                <button className="dash-quick-action" onClick={() => pd.setShowCreateTaskModal(true)}><span className="dash-quick-action-icon">✅</span> Create Task</button>
              </div>
            </section>
          </div>
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
              {gcEnabled && <button role="tab" aria-selected={pd.linkTab === 'google'} className={`link-tab ${pd.linkTab === 'google' ? 'active' : ''}`} onClick={() => { pd.setLinkTab('google'); pd.setLinkError(''); }}>Google Classroom</button>}
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
                    <div className="pd-google-icon" aria-hidden="true">🔗</div>
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
                    <div className="pd-google-icon" aria-hidden="true">📭</div>
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
                    <label>Interests / Hobbies
                      <div className="interests-tag-input" style={{ marginTop: 4 }}>
                        <div className="interests-tags">
                          {pd.editChildInterests.map((interest: string, i: number) => (
                            <span key={i} className="interest-tag">
                              {interest}
                              <button type="button" className="interest-tag-remove" onClick={() => pd.setEditChildInterests(pd.editChildInterests.filter((_: string, idx: number) => idx !== i))}>&times;</button>
                            </span>
                          ))}
                          {pd.editChildInterests.length < 10 && (
                            <input
                              type="text"
                              className="interest-input"
                              value={pd.editChildInterestInput}
                              onChange={e => pd.setEditChildInterestInput(e.target.value)}
                              onKeyDown={e => {
                                if (e.key === 'Enter') {
                                  e.preventDefault();
                                  const v = pd.editChildInterestInput.trim().toLowerCase();
                                  if (v && v.length <= 50 && !pd.editChildInterests.includes(v)) {
                                    pd.setEditChildInterests([...pd.editChildInterests, v]);
                                    pd.setEditChildInterestInput('');
                                  }
                                } else if (e.key === 'Backspace' && !pd.editChildInterestInput && pd.editChildInterests.length > 0) {
                                  pd.setEditChildInterests(pd.editChildInterests.slice(0, -1));
                                }
                              }}
                              placeholder={pd.editChildInterests.length === 0 ? 'Type an interest and press Enter...' : ''}
                              maxLength={50}
                              disabled={pd.editChildLoading}
                            />
                          )}
                        </div>
                      </div>
                      <span style={{ fontSize: 11, color: '#6b7280' }}>{pd.editChildInterests.length}/10 - AI will use these to personalize study materials</span>
                    </label>
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
                <label htmlFor="pd-day-add-task" className="sr-only">Add a task</label>
                <input id="pd-day-add-task" type="text" value={pd.newTaskTitle} onChange={(e) => pd.setNewTaskTitle(e.target.value)} placeholder="Add a task..." onKeyDown={(e) => e.key === 'Enter' && pd.handleCreateDayTask()} disabled={pd.newTaskCreating} />
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
                {pd.taskDetailModal.due_date && <div className="pd-task-detail-row"><span className="pd-task-detail-label">Due Date</span><span>{new Date(pd.taskDetailModal.due_date.includes('T') ? pd.taskDetailModal.due_date : pd.taskDetailModal.due_date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'long', day: 'numeric', year: 'numeric' })}</span></div>}
                {pd.taskDetailModal.priority && <div className="pd-task-detail-row"><span className="pd-task-detail-label">Priority</span><span className={`pd-task-priority-badge ${pd.taskDetailModal.priority}`}>{pd.taskDetailModal.priority === 'high' ? '\u25B2 ' : pd.taskDetailModal.priority === 'low' ? '\u25BC ' : '\u25CF '}{pd.taskDetailModal.priority}</span></div>}
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
      <UploadMaterialWizard
        open={pd.showStudyModal}
        onClose={() => { pd.resetStudyModal(); pd.resetWizardChild(); }}
        onGenerate={pd.handleGenerateFromModal}
        isGenerating={pd.isGenerating}
        initialTitle={pd.studyModalInitialTitle}
        initialContent={pd.studyModalInitialContent}
        childName={(pd.wizardChildFirstName ?? pd.selectedChildFirstName) ?? undefined}
        children={pd.children.map(c => ({ id: c.student_id, name: c.full_name }))}
        onChildChange={(studentId) => pd.selectChildForWizard(studentId)}
        courses={pd.childCoursesForWizard}
        selectedCourseId={pd.childCoursesForWizard?.length === 1 ? pd.childCoursesForWizard[0].id : ''}
      />
      <CreateTaskModal
        open={pd.showCreateTaskModal}
        onClose={() => pd.setShowCreateTaskModal(false)}
        onCreated={() => { pd.setShowCreateTaskModal(false); pd.loadDashboard(); }}
      />
      {pd.confirmModal}
      {showHelpStudyMenu && pd.selectedChild != null && (
        <HelpStudyMenu
          studentId={pd.selectedChild}
          onClose={() => setShowHelpStudyMenu(false)}
        />
      )}
      {showHelpStudyMenu && pd.selectedChild == null && pd.children.length > 0 && (
        <HelpStudyMenu
          studentId={pd.children[0].student_id}
          onClose={() => setShowHelpStudyMenu(false)}
        />
      )}
    </DashboardLayout>
  );
}
