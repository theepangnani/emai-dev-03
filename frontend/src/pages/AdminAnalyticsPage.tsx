import { useQuery } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  fetchOverview,
  fetchUserGrowth,
  fetchContentStats,
  fetchEngagementStats,
  fetchPrivacyStats,
} from '../api/adminAnalytics';
import type {
  OverviewStats,
  UserGrowthStats,
  ContentStats,
  EngagementStats,
  PrivacyStats,
} from '../api/adminAnalytics';
import './AdminAnalyticsPage.css';

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------
function LoadingSkeleton() {
  return (
    <div className="aap-skeleton-wrapper" aria-label="Loading analytics data">
      <div className="aap-skeleton-bar" />
      <div className="aap-skeleton-bar aap-skeleton-bar--medium" />
      <div className="aap-skeleton-bar aap-skeleton-bar--short" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------
interface StatCardProps {
  label: string;
  value: number | string;
  sub?: string;
}

function StatCard({ label, value, sub }: StatCardProps) {
  return (
    <div className="aap-stat-card">
      <div className="aap-stat-value">{value}</div>
      <div className="aap-stat-label">{label}</div>
      {sub && <div className="aap-stat-sub">{sub}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bar chart (CSS only, no chart library)
// ---------------------------------------------------------------------------
interface BarChartProps {
  data: UserGrowthStats['daily_registrations'];
}

function BarChart({ data }: BarChartProps) {
  const max = Math.max(...data.map((d) => d.total), 1);
  // Show only last 14 days for readability
  const visible = data.slice(-14);

  return (
    <div className="aap-bar-chart" aria-label="User growth bar chart">
      <div className="aap-bar-chart__bars">
        {visible.map((d) => {
          const heightPct = Math.round((d.total / max) * 100);
          return (
            <div key={d.date} className="aap-bar-chart__col" title={`${d.date}: ${d.total} new users`}>
              <div
                className="aap-bar-chart__bar"
                style={{ height: `${Math.max(heightPct, d.total > 0 ? 4 : 0)}%` }}
                aria-label={`${d.date}: ${d.total}`}
              />
              <div className="aap-bar-chart__label">
                {d.date.slice(8)} {/* day of month */}
              </div>
            </div>
          );
        })}
      </div>
      <div className="aap-bar-chart__legend">
        <span>Last 14 days</span>
        <span>Max: {max}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export function AdminAnalyticsPage() {
  const {
    data: overview,
    isLoading: loadingOverview,
    isError: errorOverview,
    refetch: refetchOverview,
  } = useQuery<OverviewStats>({ queryKey: ['admin-analytics-overview'], queryFn: fetchOverview });

  const {
    data: userGrowth,
    isLoading: loadingUsers,
    isError: errorUsers,
    refetch: refetchUsers,
  } = useQuery<UserGrowthStats>({ queryKey: ['admin-analytics-users'], queryFn: fetchUserGrowth });

  const {
    data: content,
    isLoading: loadingContent,
    isError: errorContent,
    refetch: refetchContent,
  } = useQuery<ContentStats>({ queryKey: ['admin-analytics-content'], queryFn: fetchContentStats });

  const {
    data: engagement,
    isLoading: loadingEngagement,
    isError: errorEngagement,
    refetch: refetchEngagement,
  } = useQuery<EngagementStats>({ queryKey: ['admin-analytics-engagement'], queryFn: fetchEngagementStats });

  const {
    data: privacy,
    isLoading: loadingPrivacy,
    isError: errorPrivacy,
    refetch: refetchPrivacy,
  } = useQuery<PrivacyStats>({ queryKey: ['admin-analytics-privacy'], queryFn: fetchPrivacyStats });

  const handleRefreshAll = () => {
    refetchOverview();
    refetchUsers();
    refetchContent();
    refetchEngagement();
    refetchPrivacy();
  };

  const anyError = errorOverview || errorUsers || errorContent || errorEngagement || errorPrivacy;
  const generatedAt = overview?.generated_at
    ? new Date(overview.generated_at).toLocaleString()
    : null;

  return (
    <DashboardLayout welcomeSubtitle="Platform Analytics">
      <div className="aap-page">
        <div className="aap-header">
          <h2 className="aap-title">Platform Analytics</h2>
          <div className="aap-header-right">
            {generatedAt && (
              <span className="aap-timestamp">Last updated: {generatedAt}</span>
            )}
            <button className="aap-refresh-btn" onClick={handleRefreshAll}>
              Refresh
            </button>
          </div>
        </div>

        {anyError && (
          <div className="aap-error-banner" role="alert">
            Some analytics data failed to load.{' '}
            <button className="aap-retry-btn" onClick={handleRefreshAll}>
              Retry
            </button>
          </div>
        )}

        {/* Row 1: 6 stat cards */}
        <section className="aap-section">
          <div className="aap-stat-grid">
            {loadingOverview ? (
              <LoadingSkeleton />
            ) : (
              <>
                <StatCard
                  label="Total Users"
                  value={overview?.total_users ?? 0}
                  sub={`${overview?.users_by_role.student ?? 0} students · ${overview?.users_by_role.teacher ?? 0} teachers`}
                />
                <StatCard
                  label="Active (7d)"
                  value={overview?.active_last_7d ?? 0}
                  sub="New registrations"
                />
                <StatCard
                  label="New This Week"
                  value={overview?.new_users_this_week ?? 0}
                  sub="Last 7 days"
                />
                <StatCard
                  label="Study Guides"
                  value={overview?.total_study_guides ?? 0}
                  sub="Non-archived"
                />
                <StatCard
                  label="Quiz Attempts"
                  value={overview?.total_quiz_attempts ?? 0}
                  sub="All time"
                />
                <StatCard
                  label="Premium Users"
                  value={overview?.premium_users ?? 0}
                  sub={`${overview?.google_connected_users ?? 0} Google connected`}
                />
              </>
            )}
          </div>
        </section>

        {/* Row 2: User growth chart + Content breakdown */}
        <section className="aap-section aap-section--two-col">
          <div className="aap-card">
            <h3 className="aap-card-title">User Growth (Last 30 Days)</h3>
            {loadingUsers ? (
              <LoadingSkeleton />
            ) : errorUsers ? (
              <p className="aap-error-text">Failed to load user growth data.</p>
            ) : userGrowth ? (
              <>
                <div className="aap-growth-summary">
                  <span className="aap-growth-total">{userGrowth.total_period}</span>
                  <span className="aap-growth-label"> new users in 30 days</span>
                </div>
                <BarChart data={userGrowth.daily_registrations} />
              </>
            ) : null}
          </div>

          <div className="aap-card">
            <h3 className="aap-card-title">Content Breakdown</h3>
            {loadingContent ? (
              <LoadingSkeleton />
            ) : errorContent ? (
              <p className="aap-error-text">Failed to load content data.</p>
            ) : content ? (
              <ul className="aap-content-list">
                <li className="aap-content-item">
                  <span className="aap-content-label">Study Guides (7d)</span>
                  <span className="aap-content-value">{content.study_guides_last_7d}</span>
                </li>
                <li className="aap-content-item">
                  <span className="aap-content-label">Study Guides (30d)</span>
                  <span className="aap-content-value">{content.study_guides_last_30d}</span>
                </li>
                <li className="aap-content-item">
                  <span className="aap-content-label">Quizzes Generated</span>
                  <span className="aap-content-value">{content.quizzes_generated}</span>
                </li>
                <li className="aap-content-item">
                  <span className="aap-content-label">Flashcard Sets</span>
                  <span className="aap-content-value">{content.flashcard_sets}</span>
                </li>
                <li className="aap-content-item">
                  <span className="aap-content-label">Exam Prep Plans</span>
                  <span className="aap-content-value">{content.exam_prep_plans}</span>
                </li>
                <li className="aap-content-item">
                  <span className="aap-content-label">Mock Exams</span>
                  <span className="aap-content-value">{content.mock_exams_created}</span>
                </li>
                <li className="aap-content-item">
                  <span className="aap-content-label">Documents Uploaded</span>
                  <span className="aap-content-value">{content.documents_uploaded}</span>
                </li>
                {content.top_courses_by_materials.length > 0 && (
                  <li className="aap-content-item aap-content-item--header">
                    <span className="aap-content-label">Top Courses by Materials</span>
                  </li>
                )}
                {content.top_courses_by_materials.map((c) => (
                  <li key={c.course_id} className="aap-content-item aap-content-item--indent">
                    <span className="aap-content-label">{c.course_name || `Course #${c.course_id}`}</span>
                    <span className="aap-content-value">{c.material_count}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </section>

        {/* Row 3: Engagement stats + Privacy summary */}
        <section className="aap-section aap-section--two-col">
          <div className="aap-card">
            <h3 className="aap-card-title">Engagement (Last 7 Days)</h3>
            {loadingEngagement ? (
              <LoadingSkeleton />
            ) : errorEngagement ? (
              <p className="aap-error-text">Failed to load engagement data.</p>
            ) : engagement ? (
              <table className="aap-table">
                <tbody>
                  <tr>
                    <td>Quiz Attempts</td>
                    <td className="aap-table-val">{engagement.quiz_attempts_last_7d}</td>
                  </tr>
                  <tr>
                    <td>Avg Quiz Score</td>
                    <td className="aap-table-val">{engagement.avg_quiz_score.toFixed(1)}%</td>
                  </tr>
                  <tr>
                    <td>Messages Sent</td>
                    <td className="aap-table-val">{engagement.messages_last_7d}</td>
                  </tr>
                  <tr>
                    <td>Tasks Created</td>
                    <td className="aap-table-val">{engagement.tasks_created_last_7d}</td>
                  </tr>
                  <tr>
                    <td>Tasks Completed</td>
                    <td className="aap-table-val">{engagement.tasks_completed_last_7d}</td>
                  </tr>
                  <tr className="aap-table-divider">
                    <td colSpan={2} className="aap-table-section-header">Study Streaks</td>
                  </tr>
                  <tr>
                    <td>Avg Active Days</td>
                    <td className="aap-table-val">{engagement.study_streaks.avg_streak_days.toFixed(1)}</td>
                  </tr>
                  <tr>
                    <td>Users 7+ Active Days</td>
                    <td className="aap-table-val">{engagement.study_streaks.users_with_streak_7plus}</td>
                  </tr>
                  <tr>
                    <td>Users 30+ Active Days</td>
                    <td className="aap-table-val">{engagement.study_streaks.users_with_streak_30plus}</td>
                  </tr>
                </tbody>
              </table>
            ) : null}
          </div>

          <div className="aap-card">
            <h3 className="aap-card-title">Privacy &amp; Compliance</h3>
            {loadingPrivacy ? (
              <LoadingSkeleton />
            ) : errorPrivacy ? (
              <p className="aap-error-text">Failed to load privacy data.</p>
            ) : privacy ? (
              <>
                <table className="aap-table">
                  <tbody>
                    <tr>
                      <td>Pending Deletion Requests</td>
                      <td className="aap-table-val aap-table-val--warn">{privacy.pending_deletion_requests}</td>
                    </tr>
                    <tr>
                      <td>Completed Deletions (30d)</td>
                      <td className="aap-table-val">{privacy.completed_deletions_30d}</td>
                    </tr>
                    <tr>
                      <td>Data Exports (30d)</td>
                      <td className="aap-table-val">{privacy.data_exports_30d}</td>
                    </tr>
                    <tr>
                      <td>Cookie Consent Given</td>
                      <td className="aap-table-val">{privacy.cookie_consent_given}</td>
                    </tr>
                    <tr>
                      <td>Cookie Consent Pending</td>
                      <td className="aap-table-val aap-table-val--warn">{privacy.cookie_consent_pending}</td>
                    </tr>
                    <tr className="aap-table-divider">
                      <td colSpan={2} className="aap-table-section-header">MFIPPA Age Consent (est.)</td>
                    </tr>
                    <tr>
                      <td>Under 16</td>
                      <td className="aap-table-val">{privacy.mfippa_consents.under_16}</td>
                    </tr>
                    <tr>
                      <td>Ages 16–17</td>
                      <td className="aap-table-val">{privacy.mfippa_consents['16_17']}</td>
                    </tr>
                    <tr>
                      <td>18 and Over</td>
                      <td className="aap-table-val">{privacy.mfippa_consents['18_plus']}</td>
                    </tr>
                  </tbody>
                </table>
              </>
            ) : null}
          </div>
        </section>
      </div>
    </DashboardLayout>
  );
}
