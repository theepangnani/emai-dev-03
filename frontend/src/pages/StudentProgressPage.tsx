import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { progressApi } from '../api/progress';
import type { StudentProgress } from '../api/progress';
import { parentApi } from '../api/parent';
import type { ChildSummary } from '../api/parent';
import { DashboardLayout } from '../components/DashboardLayout';
import './StudentProgressPage.css';

// ---------------------------------------------------------------------------
// Small helper sub-components
// ---------------------------------------------------------------------------

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="sp-stat-card">
      <div className="sp-stat-value">{value}</div>
      <div className="sp-stat-label">{label}</div>
      {sub && <div className="sp-stat-sub">{sub}</div>}
    </div>
  );
}

function QuizBars({ guides }: { guides: { guide_title: string; avg_score: number; attempts: number }[] }) {
  if (guides.length === 0) return null;
  return (
    <div className="sp-quiz-bars">
      {guides.map((g) => (
        <div key={g.guide_title} className="sp-quiz-bar-row">
          <div className="sp-quiz-bar-label" title={g.guide_title}>
            {g.guide_title}
          </div>
          <div className="sp-quiz-bar-track">
            <div
              className="sp-quiz-bar-fill"
              style={{ width: `${Math.min(g.avg_score, 100)}%` }}
              aria-valuenow={g.avg_score}
              aria-valuemin={0}
              aria-valuemax={100}
              role="progressbar"
            />
          </div>
          <div className="sp-quiz-bar-pct">{g.avg_score.toFixed(0)}%</div>
          <div className="sp-quiz-bar-attempts">({g.attempts} attempt{g.attempts !== 1 ? 's' : ''})</div>
        </div>
      ))}
    </div>
  );
}

function LetterBadge({ letter }: { letter: string }) {
  const colorClass =
    letter.startsWith('A') ? 'badge-a' :
    letter.startsWith('B') ? 'badge-b' :
    letter.startsWith('C') ? 'badge-c' :
    letter.startsWith('D') ? 'badge-d' : 'badge-f';
  return <span className={`sp-letter-badge ${colorClass}`}>{letter}</span>;
}

function ReportCardTrend({ terms }: { terms: { term: string; average: number }[] }) {
  if (terms.length === 0) return null;
  return (
    <ul className="sp-rc-trend">
      {terms.map((t, i) => {
        const prev = i > 0 ? terms[i - 1].average : null;
        const arrow = prev === null ? '' : t.average > prev ? ' ▲' : t.average < prev ? ' ▼' : ' ─';
        const arrowClass = prev === null ? '' : t.average > prev ? 'trend-up' : t.average < prev ? 'trend-down' : 'trend-flat';
        return (
          <li key={t.term} className="sp-rc-term-row">
            <span className="sp-rc-term">{t.term}</span>
            <span className="sp-rc-avg">{t.average.toFixed(1)}%</span>
            {arrow && <span className={`sp-rc-arrow ${arrowClass}`}>{arrow}</span>}
          </li>
        );
      })}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function StudentProgressPage() {
  const { user } = useAuth();
  const isParent = user?.role === 'parent';

  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null);

  const [progress, setProgress] = useState<StudentProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [aiLoading, setAiLoading] = useState(false);

  // Load children list for parents
  useEffect(() => {
    if (!isParent) return;
    parentApi.getChildren().then((kids) => {
      setChildren(kids);
      if (kids.length > 0) {
        const stored = sessionStorage.getItem('selectedChildId');
        const match = stored ? kids.find((k) => k.user_id === Number(stored)) : null;
        setSelectedStudentId(match ? match.student_id : kids[0].student_id);
      }
    }).catch(() => {});
  }, [isParent]);

  // For students: resolve own student ID via API
  useEffect(() => {
    if (isParent) return;
    // Student: fetch own student profile to get numeric student_id
    import('../api/student').then(({ studentApi }) => {
      studentApi.getMyProfile().then((profile) => {
        setSelectedStudentId(profile.id);
      }).catch(() => {
        setError('Could not load student profile.');
        setLoading(false);
      });
    });
  }, [isParent]);

  const loadProgress = useCallback(async (sid: number, refreshAi = false) => {
    setLoading(true);
    setError('');
    try {
      const data = isParent
        ? await progressApi.getChildProgress(sid, refreshAi)
        : await progressApi.getStudentProgress(sid, refreshAi);
      setProgress(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load progress data.');
    } finally {
      setLoading(false);
    }
  }, [isParent]);

  useEffect(() => {
    if (selectedStudentId !== null) {
      loadProgress(selectedStudentId);
    }
  }, [selectedStudentId, loadProgress]);

  async function handleRefreshAI() {
    if (!selectedStudentId) return;
    setAiLoading(true);
    try {
      const data = isParent
        ? await progressApi.getChildProgress(selectedStudentId, true)
        : await progressApi.getStudentProgress(selectedStudentId, true);
      setProgress(data);
    } catch {
      // keep existing data
    } finally {
      setAiLoading(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  const p = progress;

  function renderContent() {
    if (loading) {
      return <div className="sp-loading">Loading progress data...</div>;
    }
    if (error) {
      return <div className="sp-error">{error}</div>;
    }
    if (!p) {
      return <div className="sp-empty">No progress data available.</div>;
    }

    const quizAvg = p.quiz_performance.average_score;
    const gradeAvg = p.teacher_grades.overall_average;
    const rcAvg = p.report_cards.latest_average;
    const subRate = p.assignments.submission_rate_pct;
    const streak = p.study_streak.current;

    return (
      <div className="sp-content">
        {/* Header */}
        <div className="sp-header">
          <div className="sp-student-name">{p.student_name}</div>
          <div className="sp-streak-badge" title={`Longest streak: ${p.study_streak.longest} day(s)`}>
            <span className="sp-flame" aria-hidden="true">🔥</span>
            <span className="sp-streak-count">{streak}</span>
            <span className="sp-streak-label">day streak</span>
          </div>
        </div>

        {/* Stat cards */}
        <div className="sp-stats-row">
          <StatCard
            label="Quiz Average"
            value={p.quiz_performance.total_attempts > 0 ? `${quizAvg.toFixed(1)}%` : '—'}
            sub={p.quiz_performance.total_attempts > 0 ? `${p.quiz_performance.total_attempts} attempt(s)` : 'No quizzes yet'}
          />
          <StatCard
            label="Grade Average"
            value={p.teacher_grades.by_course.length > 0 ? `${gradeAvg.toFixed(1)}%` : '—'}
            sub={p.teacher_grades.by_course.length > 0 ? `${p.teacher_grades.by_course.length} course(s)` : 'No grades yet'}
          />
          <StatCard
            label="Report Card"
            value={rcAvg !== null ? `${rcAvg.toFixed(1)}%` : '—'}
            sub={rcAvg !== null ? 'Latest term' : 'Not uploaded yet'}
          />
          <StatCard
            label="Assignments"
            value={p.assignments.total > 0 ? `${subRate.toFixed(0)}%` : '—'}
            sub={p.assignments.total > 0 ? `${p.assignments.submitted}/${p.assignments.total} submitted` : 'No assignments'}
          />
        </div>

        {/* Quiz Performance */}
        {p.quiz_performance.by_guide.length > 0 && (
          <section className="sp-section">
            <h2 className="sp-section-title">Quiz Performance</h2>
            <p className="sp-section-hint">Sorted by lowest score — focus on these guides first.</p>
            <QuizBars guides={p.quiz_performance.by_guide} />
          </section>
        )}

        {/* Teacher Grades */}
        {p.teacher_grades.by_course.length > 0 && (
          <section className="sp-section">
            <h2 className="sp-section-title">Teacher Grades</h2>
            <div className="sp-grade-cards">
              {p.teacher_grades.by_course.map((c) => (
                <div key={c.course_name} className="sp-grade-card">
                  <LetterBadge letter={c.letter} />
                  <div className="sp-grade-card-name">{c.course_name}</div>
                  <div className="sp-grade-card-avg">{c.average.toFixed(1)}%</div>
                  <div className="sp-grade-card-entries">{c.entries} grade{c.entries !== 1 ? 's' : ''} recorded</div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Report Cards */}
        {p.report_cards.by_term.length > 0 && (
          <section className="sp-section">
            <h2 className="sp-section-title">Report Cards</h2>
            <ReportCardTrend terms={p.report_cards.by_term} />
          </section>
        )}

        {/* AI Insights */}
        <section className="sp-section sp-ai-section">
          <h2 className="sp-section-title">
            <span className="sp-lightbulb" aria-hidden="true">💡</span>
            AI Insights
          </h2>
          {p.ai_insights ? (
            <div className="sp-ai-text">{p.ai_insights}</div>
          ) : (
            <div className="sp-ai-empty">No AI insights generated yet. Click Refresh to generate.</div>
          )}
          <button
            className="sp-ai-refresh-btn"
            onClick={handleRefreshAI}
            disabled={aiLoading}
          >
            {aiLoading ? 'Generating...' : 'Refresh Insights'}
          </button>
        </section>
      </div>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle="Your consolidated progress overview">
      <div className="sp-page">
        <h1 className="sp-page-title">Progress Dashboard</h1>

        {/* Child selector for parents */}
        {isParent && children.length > 0 && (
          <div className="sp-child-selector">
            {children.map((child) => (
              <button
                key={child.student_id}
                className={`sp-child-pill${selectedStudentId === child.student_id ? ' active' : ''}`}
                onClick={() => {
                  setSelectedStudentId(child.student_id);
                  sessionStorage.setItem('selectedChildId', String(child.user_id));
                }}
              >
                {child.full_name}
              </button>
            ))}
          </div>
        )}

        {renderContent()}
      </div>
    </DashboardLayout>
  );
}
