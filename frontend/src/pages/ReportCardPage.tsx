import { useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import { PageSkeleton } from '../components/Skeleton';
import { reportCardApi } from '../api/reportCard';
import type { ReportCardData } from '../api/reportCard';
import { downloadAsPdf } from '../utils/exportUtils';
import { ReportBugLink } from '../components/ReportBugLink';
import './ReportCardPage.css';

export function ReportCardPage() {
  const cardRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, error } = useQuery<ReportCardData>({
    queryKey: ['report-card'],
    queryFn: () => reportCardApi.get(),
  });

  const handleDownloadPdf = async () => {
    if (!cardRef.current) return;
    await downloadAsPdf(cardRef.current, `Report-Card-${data?.term || 'term'}.pdf`);
  };

  const handleShare = async () => {
    const url = window.location.href;
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(url);
    }
  };

  return (
    <DashboardLayout>
      <PageNav
        items={[
          { label: 'Dashboard', to: '/dashboard' },
          { label: 'Report Card' },
        ]}
      />
      <div className="rc-page">
        {isLoading && <PageSkeleton />}
        {error && <><div className="rc-error">Failed to load report card.</div><ReportBugLink errorMessage="Failed to load report card" /></>}
        {data && (
          <>
            <div className="rc-actions">
              <button className="rc-btn rc-btn--primary" onClick={handleDownloadPdf}>
                Download PDF
              </button>
              <button className="rc-btn rc-btn--secondary" onClick={handleShare}>
                Share
              </button>
            </div>
            <div className="rc-card" ref={cardRef}>
              <div className="rc-header">
                <div className="rc-logo">ClassBridge</div>
                <h1 className="rc-title">Report Card</h1>
                <p className="rc-term">{data.term}</p>
                <p className="rc-student">{data.student_name}</p>
              </div>

              <div className="rc-section">
                <h2 className="rc-section-title">Overview</h2>
                <div className="rc-stats-grid">
                  <div className="rc-stat">
                    <span className="rc-stat-value">{data.total_uploads}</span>
                    <span className="rc-stat-label">Uploads</span>
                  </div>
                  <div className="rc-stat">
                    <span className="rc-stat-value">{data.total_guides}</span>
                    <span className="rc-stat-label">Study Guides</span>
                  </div>
                  <div className="rc-stat">
                    <span className="rc-stat-value">{data.total_quizzes}</span>
                    <span className="rc-stat-label">Quizzes</span>
                  </div>
                  <div className="rc-stat">
                    <span className="rc-stat-value">{data.total_xp}</span>
                    <span className="rc-stat-label">XP Earned</span>
                  </div>
                </div>
              </div>

              {data.subjects_studied.length > 0 && (
                <div className="rc-section">
                  <h2 className="rc-section-title">Subjects</h2>
                  <table className="rc-subjects-table">
                    <thead>
                      <tr>
                        <th>Subject</th>
                        <th>Guides</th>
                        <th>Quizzes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.subjects_studied.map((s) => (
                        <tr key={s.name}>
                          <td>{s.name}</td>
                          <td>{s.guides}</td>
                          <td>{s.quizzes}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="rc-section">
                <h2 className="rc-section-title">Achievements</h2>
                <div className="rc-achievements">
                  <div className="rc-level-badge">
                    <span className="rc-level-number">Lv. {data.level_reached.level}</span>
                    <span className="rc-level-title">{data.level_reached.title}</span>
                  </div>
                  {data.badges_earned.length > 0 && (
                    <div className="rc-badges">
                      {data.badges_earned.map((b) => (
                        <span key={b.name} className="rc-badge-chip">{b.name}</span>
                      ))}
                    </div>
                  )}
                  {data.badges_earned.length === 0 && (
                    <p className="rc-muted">No new badges this term.</p>
                  )}
                </div>
              </div>

              <div className="rc-section">
                <h2 className="rc-section-title">Streaks</h2>
                <div className="rc-stats-grid">
                  <div className="rc-stat">
                    <span className="rc-stat-value">{data.longest_streak}</span>
                    <span className="rc-stat-label">Longest Streak (days)</span>
                  </div>
                </div>
              </div>

              {data.most_reviewed_topics.length > 0 && (
                <div className="rc-section">
                  <h2 className="rc-section-title">Most Reviewed Topics</h2>
                  <ul className="rc-topics-list">
                    {data.most_reviewed_topics.map((t) => (
                      <li key={t}>{t}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="rc-section">
                <h2 className="rc-section-title">Study Sessions</h2>
                <div className="rc-stats-grid">
                  <div className="rc-stat">
                    <span className="rc-stat-value">{data.study_sessions}</span>
                    <span className="rc-stat-label">Sessions</span>
                  </div>
                  <div className="rc-stat">
                    <span className="rc-stat-value">{data.total_study_minutes}</span>
                    <span className="rc-stat-label">Minutes Studied</span>
                  </div>
                </div>
              </div>

              <div className="rc-footer">
                <p className="rc-cta">Ready to start strong in Semester 2?</p>
                <p className="rc-generated">Generated by ClassBridge</p>
              </div>
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
