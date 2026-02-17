import { useEffect, useState, useMemo, lazy, Suspense } from 'react';
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from 'recharts';
import { useAuth } from '../context/AuthContext';
import { analyticsApi } from '../api/analytics';
import type { GradeSummary, TrendPoint, GradeItem, CourseAverage } from '../api/analytics';
import { parentApi } from '../api/parent';
import type { ChildSummary } from '../api/parent';
import './AnalyticsPage.css';

const ReactMarkdown = lazy(() => import('react-markdown'));

const COURSE_COLORS = ['#4f46e5', '#0891b2', '#059669', '#d97706', '#dc2626', '#7c3aed', '#db2777'];

const TIME_RANGES = [
  { label: '30d', days: 30 },
  { label: '60d', days: 60 },
  { label: '90d', days: 90 },
  { label: 'All', days: 365 },
];

export function AnalyticsPage() {
  const { user } = useAuth();
  const isParent = user?.role === 'parent';

  // Children (for parents)
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null);

  // Data
  const [summary, setSummary] = useState<GradeSummary | null>(null);
  const [trendPoints, setTrendPoints] = useState<TrendPoint[]>([]);
  const [grades, setGrades] = useState<GradeItem[]>([]);
  const [, setTrendLabel] = useState('stable');

  // UI state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [trendDays, setTrendDays] = useState(90);
  const [trendCourseFilter, setTrendCourseFilter] = useState<number | undefined>();

  // AI insights
  const [aiInsight, setAiInsight] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  // Load children for parents
  useEffect(() => {
    if (!isParent) return;
    parentApi.getChildren().then((kids) => {
      setChildren(kids);
      if (kids.length > 0 && !selectedStudentId) {
        setSelectedStudentId(kids[0].student_id);
      }
    }).catch(() => { /* handled by main load */ });
  }, [isParent]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load analytics data when student is selected
  useEffect(() => {
    if (!selectedStudentId) {
      if (!isParent) {
        // Student viewing own data — student_id not needed, API resolves it
        loadData(undefined);
      }
      return;
    }
    loadData(selectedStudentId);
  }, [selectedStudentId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reload trends when filters change
  useEffect(() => {
    if (!selectedStudentId && isParent) return;
    loadTrends(selectedStudentId ?? undefined);
  }, [trendDays, trendCourseFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadData(studentId: number | undefined) {
    setLoading(true);
    setError('');
    try {
      const sid = studentId ?? 0; // 0 won't be sent if undefined in API
      const [summaryData, trendsData, gradesData] = await Promise.all([
        studentId !== undefined
          ? analyticsApi.getSummary(sid)
          : analyticsApi.getSummary(sid),
        studentId !== undefined
          ? analyticsApi.getTrends(sid, trendCourseFilter, trendDays)
          : analyticsApi.getTrends(sid, trendCourseFilter, trendDays),
        studentId !== undefined
          ? analyticsApi.getGrades(sid)
          : analyticsApi.getGrades(sid),
      ]);

      setSummary(summaryData);
      setTrendPoints(trendsData.points);
      setTrendLabel(trendsData.trend);
      setGrades(gradesData.grades);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load analytics';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  async function loadTrends(studentId: number | undefined) {
    if (studentId === undefined && isParent) return;
    try {
      const sid = studentId ?? 0;
      const trendsData = await analyticsApi.getTrends(sid, trendCourseFilter, trendDays);
      setTrendPoints(trendsData.points);
      setTrendLabel(trendsData.trend);
    } catch {
      // Keep existing data on filter error
    }
  }

  // Chart data: group trend points by course for multi-line chart
  const trendChartData = useMemo(() => {
    const byDate: Record<string, Record<string, string | number>> = {};
    for (const pt of trendPoints) {
      const dateKey = pt.date.slice(0, 10);
      if (!byDate[dateKey]) byDate[dateKey] = { date: dateKey };
      byDate[dateKey][pt.course_name] = pt.percentage;
    }
    return Object.values(byDate).sort((a, b) =>
      String(a.date).localeCompare(String(b.date))
    );
  }, [trendPoints]);

  // Unique course names from trend data
  const trendCourseNames = useMemo(() => {
    const names = new Set<string>();
    for (const pt of trendPoints) names.add(pt.course_name);
    return Array.from(names);
  }, [trendPoints]);

  // Bar chart data for course averages
  const courseBarData = useMemo(() => {
    if (!summary) return [];
    return summary.course_averages.map((ca: CourseAverage) => ({
      name: ca.course_name,
      average: ca.average_percentage,
      completion: ca.completion_rate,
    }));
  }, [summary]);

  // All unique courses (for trend filter dropdown)
  const courseOptions = useMemo(() => {
    if (!summary) return [];
    return summary.course_averages.map((ca: CourseAverage) => ({
      id: ca.course_id,
      name: ca.course_name,
    }));
  }, [summary]);

  async function handleGenerateInsight() {
    if (!selectedStudentId && isParent) return;
    setAiLoading(true);
    try {
      const result = await analyticsApi.getAIInsight(selectedStudentId ?? 0);
      setAiInsight(result.insight);
    } catch {
      setAiInsight('Failed to generate insights. Please try again.');
    } finally {
      setAiLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="analytics-page">
        <div className="analytics-loading">Loading analytics...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="analytics-page">
        <div className="analytics-error">{error}</div>
      </div>
    );
  }

  return (
    <div className="analytics-page">
      <h1>Analytics</h1>

      {/* Child selector for parents */}
      {isParent && children.length > 1 && (
        <div className="analytics-child-selector">
          <label>Student:</label>
          <select
            value={selectedStudentId ?? ''}
            onChange={(e) => setSelectedStudentId(Number(e.target.value))}
          >
            {children.map((child) => (
              <option key={child.student_id} value={child.student_id}>
                {child.full_name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Summary cards */}
      {summary && (
        <div className="analytics-summary">
          <div className="analytics-summary-card">
            <div className="value">{summary.overall_average.toFixed(1)}%</div>
            <div className="label">Overall Average</div>
          </div>
          <div className="analytics-summary-card">
            <div className="value">{summary.completion_rate.toFixed(0)}%</div>
            <div className="label">Completion Rate</div>
          </div>
          <div className="analytics-summary-card">
            <div className="value">{summary.total_graded}</div>
            <div className="label">Assignments Graded</div>
          </div>
          <div className="analytics-summary-card">
            <span className={`trend-badge ${summary.trend}`}>
              {summary.trend === 'improving' ? 'Improving' :
               summary.trend === 'declining' ? 'Declining' : 'Stable'}
            </span>
            <div className="label">Overall Trend</div>
          </div>
        </div>
      )}

      {/* Grade Trend Chart */}
      {trendPoints.length > 0 && (
        <div className="analytics-chart-section">
          <h2>Grade Trends</h2>
          <div className="analytics-chart-filters">
            {TIME_RANGES.map((r) => (
              <button
                key={r.days}
                className={trendDays === r.days ? 'active' : ''}
                onClick={() => setTrendDays(r.days)}
              >
                {r.label}
              </button>
            ))}
            <select
              value={trendCourseFilter ?? ''}
              onChange={(e) => setTrendCourseFilter(e.target.value ? Number(e.target.value) : undefined)}
            >
              <option value="">All Courses</option>
              {courseOptions.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trendChartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 12 }}
                tickFormatter={(v: string) => v.slice(5)}
              />
              <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              {trendCourseNames.map((name, i) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  stroke={COURSE_COLORS[i % COURSE_COLORS.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Course Averages Bar Chart */}
      {courseBarData.length > 0 && (
        <div className="analytics-chart-section">
          <h2>Course Averages</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={courseBarData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="average" fill="#4f46e5" name="Average %" radius={[4, 4, 0, 0]} />
              <Bar dataKey="completion" fill="#0891b2" name="Completion %" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* AI Insights */}
      <div className="analytics-ai-section">
        <h2>AI Insights</h2>
        <button
          className="analytics-ai-btn"
          onClick={handleGenerateInsight}
          disabled={aiLoading}
        >
          {aiLoading ? 'Generating...' : 'Generate AI Insights'}
        </button>
        {aiInsight && (
          <div className="analytics-ai-content">
            <Suspense fallback={<div>Loading...</div>}>
              <ReactMarkdown>{aiInsight}</ReactMarkdown>
            </Suspense>
          </div>
        )}
      </div>

      {/* Recent Grades Table */}
      {grades.length > 0 && (
        <div className="analytics-chart-section">
          <h2>Recent Grades</h2>
          <table className="analytics-grades-table">
            <thead>
              <tr>
                <th>Assignment</th>
                <th>Course</th>
                <th>Grade</th>
                <th>Due Date</th>
              </tr>
            </thead>
            <tbody>
              {grades.map((g) => (
                <tr key={g.student_assignment_id}>
                  <td>{g.assignment_title}</td>
                  <td>{g.course_name}</td>
                  <td>{g.grade}/{g.max_points} ({g.percentage.toFixed(1)}%)</td>
                  <td>{g.due_date ? new Date(g.due_date).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty state */}
      {!summary?.total_graded && !loading && (
        <div className="analytics-empty">
          No graded assignments yet. Grades will appear here once assignments are graded.
        </div>
      )}
    </div>
  );
}
