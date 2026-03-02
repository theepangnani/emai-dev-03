import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import { CopyPasteImporter } from '../components/CopyPasteImporter';
import { ScreenshotImporter } from '../components/ScreenshotImporter';
import { EmailForwardSetup } from '../components/EmailForwardSetup';
import { ICSImporter } from '../components/ICSImporter';
import { CSVImporter } from '../components/CSVImporter';
import { ImportReviewWizard } from '../components/ImportReviewWizard';
import { classroomImportApi, ImportSessionListItem } from '../api/classroomImport';
import { useAuth } from '../context/AuthContext';
import './ClassroomImportPage.css';

type Pathway = 'copypaste' | 'screenshot' | 'email' | 'ics' | 'csv';

const PATHWAY_LABELS: Record<Pathway, string> = {
  copypaste: 'Copy & Paste',
  screenshot: 'Screenshot / Photo',
  email: 'Email Forward',
  ics: 'Calendar Import',
  csv: 'CSV Import',
};

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function statusLabel(status: string): string {
  switch (status) {
    case 'processing': return 'Processing';
    case 'ready_for_review': return 'Ready for Review';
    case 'imported': return 'Imported';
    case 'failed': return 'Failed';
    default: return status;
  }
}

function statusClass(status: string): string {
  switch (status) {
    case 'processing': return 'ci-status-processing';
    case 'ready_for_review': return 'ci-status-review';
    case 'imported': return 'ci-status-imported';
    case 'failed': return 'ci-status-failed';
    default: return '';
  }
}

/* ---------- Inline SVG icons (24x24, stroke-based) ---------- */

function ClipboardIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
    </svg>
  );
}

function CameraIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
      <circle cx="12" cy="13" r="4" />
    </svg>
  );
}

function MailIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <polyline points="22,6 12,13 2,6" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

function TableIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <line x1="3" y1="9" x2="21" y2="9" />
      <line x1="3" y1="15" x2="21" y2="15" />
      <line x1="9" y1="3" x2="9" y2="21" />
      <line x1="15" y1="3" x2="15" y2="21" />
    </svg>
  );
}

function GoogleIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 8v8" />
      <path d="M8 12h8" />
    </svg>
  );
}

function sourceIcon(source: string) {
  switch (source) {
    case 'copypaste': return <ClipboardIcon />;
    case 'screenshot': return <CameraIcon />;
    case 'email': return <MailIcon />;
    case 'ics': return <CalendarIcon />;
    case 'csv': return <TableIcon />;
    default: return <ClipboardIcon />;
  }
}

function sourceLabel(source: string): string {
  switch (source) {
    case 'copypaste': return 'Copy & Paste';
    case 'screenshot': return 'Screenshot';
    case 'email': return 'Email Forward';
    case 'ics': return 'Calendar';
    case 'csv': return 'CSV';
    default: return source;
  }
}

export function ClassroomImportPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [activePathway, setActivePathway] = useState<Pathway | null>(null);
  const [reviewSessionId, setReviewSessionId] = useState<number | null>(null);
  const [recentSessions, setRecentSessions] = useState<ImportSessionListItem[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState('');

  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    setSessionsError('');
    try {
      const data = await classroomImportApi.listSessions();
      setRecentSessions(data);
    } catch {
      setSessionsError('Failed to load recent imports.');
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const handleSessionCreated = (sessionId: number) => {
    setReviewSessionId(sessionId);
  };

  const handleReviewComplete = () => {
    setReviewSessionId(null);
    setActivePathway(null);
    loadSessions();
  };

  const handleReviewCancel = () => {
    setReviewSessionId(null);
    loadSessions();
  };

  // -- Full-screen review wizard --
  if (reviewSessionId !== null) {
    return (
      <DashboardLayout welcomeSubtitle="Review imported data">
        <div className="ci-page">
          <ImportReviewWizard
            sessionId={reviewSessionId}
            onComplete={handleReviewComplete}
            onCancel={handleReviewCancel}
          />
        </div>
      </DashboardLayout>
    );
  }

  // -- Active pathway view --
  if (activePathway) {
    return (
      <DashboardLayout welcomeSubtitle="Import classroom data">
        <div className="ci-page">
          <PageNav
            items={[
              { label: 'Dashboard', to: '/dashboard' },
              { label: 'Import Data', to: '/import' },
              { label: PATHWAY_LABELS[activePathway] },
            ]}
          />
          <button
            className="ci-back-link"
            onClick={() => setActivePathway(null)}
            type="button"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M15 18l-6-6 6-6" />
            </svg>
            Back to all methods
          </button>

          <div className="ci-importer-container">
            {activePathway === 'copypaste' && (
              <CopyPasteImporter onSessionCreated={handleSessionCreated} />
            )}
            {activePathway === 'screenshot' && (
              <ScreenshotImporter onSessionCreated={handleSessionCreated} />
            )}
            {activePathway === 'email' && (
              <EmailForwardSetup onSessionCreated={handleSessionCreated} />
            )}
            {activePathway === 'ics' && (
              <ICSImporter onSessionCreated={handleSessionCreated} />
            )}
            {activePathway === 'csv' && (
              <CSVImporter onSessionCreated={handleSessionCreated} />
            )}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  // -- Hub view (default) --
  return (
    <DashboardLayout welcomeSubtitle="Import classroom data">
      <div className="ci-page">
        <PageNav
          items={[
            { label: 'Dashboard', to: '/dashboard' },
            { label: 'Import Data' },
          ]}
        />

        {/* Page header */}
        <div className="ci-header">
          <h2 className="ci-title">Import Classroom Data</h2>
          <p className="ci-subtitle">
            Can't connect to your school's Google Classroom directly? Use one of
            these methods to bring your data into ClassBridge.
          </p>
        </div>

        {/* Pathway cards grid */}
        <div className="ci-cards-grid">
          {/* Card 1: Copy & Paste */}
          <button
            className="ci-card"
            onClick={() => setActivePathway('copypaste')}
            type="button"
          >
            <div className="ci-card-icon ci-card-icon-clipboard">
              <ClipboardIcon />
            </div>
            <div className="ci-card-body">
              <h3 className="ci-card-title">Copy &amp; Paste</h3>
              <p className="ci-card-desc">
                Copy text from Google Classroom and paste it here
              </p>
              <p className="ci-card-hint">
                Fastest method — works from any browser
              </p>
            </div>
            <span className="ci-card-action">Get Started</span>
          </button>

          {/* Card 2: Screenshot / Photo */}
          <button
            className="ci-card"
            onClick={() => setActivePathway('screenshot')}
            type="button"
          >
            <div className="ci-card-icon ci-card-icon-camera">
              <CameraIcon />
            </div>
            <div className="ci-card-body">
              <h3 className="ci-card-title">Screenshot / Photo</h3>
              <p className="ci-card-desc">
                Upload screenshots or photos of Google Classroom
              </p>
              <p className="ci-card-hint">
                AI reads your screenshots automatically
              </p>
            </div>
            <span className="ci-card-action">Get Started</span>
          </button>

          {/* Card 3: Email Forward */}
          <button
            className="ci-card"
            onClick={() => setActivePathway('email')}
            type="button"
          >
            <div className="ci-card-icon ci-card-icon-mail">
              <MailIcon />
            </div>
            <div className="ci-card-body">
              <h3 className="ci-card-title">Email Forward</h3>
              <p className="ci-card-desc">
                Auto-forward classroom notification emails
              </p>
              <p className="ci-card-hint">
                Set once, imports happen automatically
              </p>
            </div>
            <span className="ci-card-action">Set Up</span>
          </button>

          {/* Card 4: Calendar Import */}
          <button
            className="ci-card"
            onClick={() => setActivePathway('ics')}
            type="button"
          >
            <div className="ci-card-icon ci-card-icon-calendar">
              <CalendarIcon />
            </div>
            <div className="ci-card-body">
              <h3 className="ci-card-title">Calendar Import</h3>
              <p className="ci-card-desc">
                Import assignment dates from Google Calendar
              </p>
              <p className="ci-card-hint">
                Quick way to get all due dates
              </p>
            </div>
            <span className="ci-card-action">Get Started</span>
          </button>

          {/* Card 5: CSV Import */}
          <button
            className="ci-card"
            onClick={() => setActivePathway('csv')}
            type="button"
          >
            <div className="ci-card-icon ci-card-icon-table">
              <TableIcon />
            </div>
            <div className="ci-card-body">
              <h3 className="ci-card-title">CSV Import</h3>
              <p className="ci-card-desc">
                Fill in a spreadsheet template manually
              </p>
              <p className="ci-card-hint">
                Maximum control over your data
              </p>
            </div>
            <span className="ci-card-action">Get Started</span>
          </button>

          {/* Card 6: Google Account (navigates away) */}
          <button
            className="ci-card ci-card-google"
            onClick={() => navigate('/settings/lms-connections')}
            type="button"
          >
            <div className="ci-card-icon ci-card-icon-google">
              <GoogleIcon />
            </div>
            <div className="ci-card-body">
              <h3 className="ci-card-title">Google Account</h3>
              <p className="ci-card-desc">
                Connect your school Google account directly
              </p>
              <p className="ci-card-hint">
                Works if your school allows third-party apps
              </p>
            </div>
            <span className="ci-card-action">Try Connect</span>
          </button>
        </div>

        {/* Recent Imports section */}
        <div className="ci-recent">
          <h3 className="ci-recent-title">Recent Imports</h3>

          {sessionsError && (
            <div className="ci-error">{sessionsError}</div>
          )}

          {sessionsLoading ? (
            <div className="ci-recent-loading">Loading recent imports...</div>
          ) : recentSessions.length === 0 ? (
            <div className="ci-recent-empty">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              <p>No imports yet. Choose a method above to get started.</p>
            </div>
          ) : (
            <div className="ci-table-wrapper">
              <table className="ci-table">
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Status</th>
                    <th>Items Created</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {recentSessions.map((session) => (
                    <tr
                      key={session.id}
                      className="ci-table-row-clickable"
                      onClick={() => setReviewSessionId(session.id)}
                      tabIndex={0}
                      role="button"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          setReviewSessionId(session.id);
                        }
                      }}
                    >
                      <td className="ci-cell-source">
                        <span className="ci-source-icon">
                          {sourceIcon(session.source_type)}
                        </span>
                        <span>{sourceLabel(session.source_type)}</span>
                      </td>
                      <td>
                        <span className={`ci-status-badge ${statusClass(session.status)}`}>
                          {statusLabel(session.status)}
                        </span>
                      </td>
                      <td className="ci-cell-count">
                        {session.items_created ?? '—'}
                      </td>
                      <td className="ci-cell-date">
                        {formatDate(session.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
