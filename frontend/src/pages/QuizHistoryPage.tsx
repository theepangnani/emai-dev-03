import { useState, useEffect, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { DashboardLayout } from '../components/DashboardLayout';
import { studyApi, parentApi } from '../api/client';
import type { QuizResultSummary, QuizHistoryStats, ChildSummary } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { PageNav } from '../components/PageNav';
import './QuizHistoryPage.css';

export function QuizHistoryPage() {
  const [searchParams] = useSearchParams();
  const quizFilter = searchParams.get('quiz');
  const { user } = useAuth();
  const isParent = user?.role === 'parent' || (user?.roles ?? []).includes('parent');

  const [results, setResults] = useState<QuizResultSummary[]>([]);
  const [stats, setStats] = useState<QuizHistoryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Parent child selector
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChild, setSelectedChild] = useState<number | null>(null);

  useEffect(() => {
    if (isParent) {
      parentApi.getChildren().then((c) => {
        setChildren(c);
        if (c.length > 0) {
          const storedUserId = sessionStorage.getItem('selectedChildId');
          const storedMatch = storedUserId ? c.find(k => k.user_id === Number(storedUserId)) : null;
          setSelectedChild(storedMatch ? storedMatch.user_id : c[0].user_id);
        }
      });
    }
  }, [isParent]);

  useEffect(() => {
    // For parents, wait until a child is selected before loading
    if (isParent && selectedChild === null && children.length === 0) {
      // Still loading children — skip
      return;
    }

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const params: { study_guide_id?: number; student_user_id?: number; limit?: number } = { limit: 100 };
        if (quizFilter) params.study_guide_id = parseInt(quizFilter);
        if (isParent && selectedChild) params.student_user_id = selectedChild;
        const [historyData, statsData] = await Promise.all([
          studyApi.getQuizHistory(params),
          studyApi.getQuizStats(isParent && selectedChild ? { student_user_id: selectedChild } : undefined),
        ]);
        setResults(historyData);
        setStats(statsData);
      } catch {
        setError('Failed to load quiz history');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [quizFilter, selectedChild, isParent, children.length]);

  const chartData = useMemo(() => {
    return [...results]
      .reverse()
      .map((r) => ({
        date: new Date(r.completed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
        percentage: r.percentage,
        quiz: r.quiz_title || `Quiz #${r.study_guide_id}`,
      }));
  }, [results]);

  const trendIcon = stats?.recent_trend === 'improving' ? '\u2191' : stats?.recent_trend === 'declining' ? '\u2193' : '\u2192';
  const trendColor = stats?.recent_trend === 'improving' ? '#2e7d32' : stats?.recent_trend === 'declining' ? '#c62828' : '#666';

  const handleDelete = async (id: number) => {
    try {
      await studyApi.deleteQuizResult(id);
      setResults((prev) => prev.filter((r) => r.id !== id));
    } catch {
      // silently fail
    }
  };

  return (
    <DashboardLayout showBackButton>
      <div className="quiz-history-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Quiz History' },
        ]} />
        <div className="quiz-history-header">
          <h2>Quiz History</h2>
          {isParent && children.length > 0 && (
            <select
              className="qh-child-select"
              value={selectedChild ?? ''}
              onChange={(e) => { const val = Number(e.target.value); setSelectedChild(val); sessionStorage.setItem('selectedChildId', String(val)); }}
            >
              {children.map((c) => (
                <option key={c.user_id} value={c.user_id}>
                  {c.full_name}
                </option>
              ))}
            </select>
          )}
          {quizFilter && (
            <Link to="/quiz-history" className="clear-filter">
              Show all quizzes
            </Link>
          )}
        </div>

        {loading && (
          <div className="quiz-history-loading">
            <div className="skeleton" style={{ width: '100%', height: 120 }} />
            <div className="skeleton" style={{ width: '100%', height: 200, marginTop: 16 }} />
          </div>
        )}

        {error && <div className="quiz-history-error">{error}</div>}

        {!loading && !error && stats && (
          <>
            {/* Stats cards */}
            <div className="qh-stats-grid">
              <div className="qh-stat-card">
                <span className="qh-stat-value">{stats.total_attempts}</span>
                <span className="qh-stat-label">Total Attempts</span>
              </div>
              <div className="qh-stat-card">
                <span className="qh-stat-value">{stats.unique_quizzes}</span>
                <span className="qh-stat-label">Unique Quizzes</span>
              </div>
              <div className="qh-stat-card">
                <span className="qh-stat-value">{stats.average_score}%</span>
                <span className="qh-stat-label">Average Score</span>
              </div>
              <div className="qh-stat-card">
                <span className="qh-stat-value">{stats.best_score}%</span>
                <span className="qh-stat-label">
                  Best Score{' '}
                  <span style={{ color: trendColor, fontWeight: 600 }}>{trendIcon}</span>
                </span>
              </div>
            </div>

            {/* Score trend chart */}
            {chartData.length > 1 && (
              <div className="qh-chart-card">
                <h3>Score Trend</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" fontSize={12} />
                    <YAxis domain={[0, 100]} fontSize={12} />
                    <Tooltip
                      formatter={(value) => [`${value}%`, 'Score']}
                      labelFormatter={(label) => String(label)}
                    />
                    <Line
                      type="monotone"
                      dataKey="percentage"
                      stroke="#1565c0"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Attempts list */}
            {results.length > 0 ? (
              <div className="qh-attempts-list">
                <h3>Attempts</h3>
                <div className="qh-attempts-table">
                  {results.map((r) => (
                    <div key={r.id} className="qh-attempt-row">
                      <div className="qh-attempt-info">
                        <span className="qh-attempt-title">{r.quiz_title || `Quiz #${r.study_guide_id}`}</span>
                        <span className="qh-attempt-meta">
                          Attempt #{r.attempt_number} &middot;{' '}
                          {new Date(r.completed_at).toLocaleDateString(undefined, {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                            hour: 'numeric',
                            minute: '2-digit',
                          })}
                        </span>
                      </div>
                      <div className="qh-attempt-score">
                        <span className="qh-score-text">
                          {r.score}/{r.total_questions}
                        </span>
                        <div className="qh-score-bar">
                          <div
                            className="qh-score-fill"
                            style={{
                              width: `${r.percentage}%`,
                              background: r.percentage >= 80 ? '#2e7d32' : r.percentage >= 60 ? '#f57f17' : '#c62828',
                            }}
                          />
                        </div>
                        <span className="qh-score-pct">{r.percentage}%</span>
                      </div>
                      <div className="qh-attempt-actions">
                        <Link to={`/study/quiz/${r.study_guide_id}`} className="qh-retry-btn">
                          Retry
                        </Link>
                        <button className="qh-delete-btn" onClick={() => handleDelete(r.id)} title="Delete">
                          &times;
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="qh-empty-state">
                <p className="qh-empty-icon">{'\u{1F4CA}'}</p>
                <h3>No quiz attempts yet</h3>
                <p>Complete a quiz to start tracking your progress!</p>
                <Link to="/course-materials" className="qh-cta-btn">
                  Browse Class Materials
                </Link>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
