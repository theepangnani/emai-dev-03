import { useState, useEffect, useCallback } from 'react';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import { ListSkeleton } from '../components/Skeleton';
import { useToast } from '../components/Toast';
import { adminSurveyApi } from '../api/adminSurvey';
import type {
  SurveyAnalytics,
  SurveyResponseItem,
  SurveyResponseDetail,
  SurveyQuestionAnalytics,
} from '../api/adminSurvey';
import './AdminSurveyPage.css';

const PAGE_SIZE = 20;

const CHART_COLORS = [
  '#4f46e5', '#0891b2', '#059669', '#d97706', '#dc2626',
  '#7c3aed', '#db2777', '#0ea5e9', '#f59e0b', '#84cc16',
];

const PIE_COLORS: Record<string, string> = {
  parent: '#8b5cf6',
  student: '#10b981',
  teacher: '#3b82f6',
};

const TruncatedTick = ({ x, y, payload }: any) => {
  const MAX_LEN = 45;
  const label = payload?.value ?? '';
  const display = label.length > MAX_LEN ? label.slice(0, MAX_LEN) + '...' : label;
  return (
    <g transform={`translate(${x},${y})`}>
      <title>{label}</title>
      <text x={0} y={0} dy={4} textAnchor="end" fontSize={12} fill="var(--color-ink, #333)">
        {display}
      </text>
    </g>
  );
};

export function AdminSurveyPage() {
  const { toast } = useToast();

  const [roleFilter, setRoleFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [analytics, setAnalytics] = useState<SurveyAnalytics | null>(null);
  const [responses, setResponses] = useState<SurveyResponseItem[]>([]);
  const [responsesTotal, setResponsesTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedDetail, setExpandedDetail] = useState<SurveyResponseDetail | null>(null);
  const [showAllText, setShowAllText] = useState<Record<string, boolean>>({});

  const buildParams = useCallback(() => {
    const params: Record<string, string> = {};
    if (roleFilter) params.role = roleFilter;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    return params;
  }, [roleFilter, dateFrom, dateTo]);

  const loadAnalytics = useCallback(async () => {
    try {
      const data = await adminSurveyApi.analytics(buildParams());
      setAnalytics(data);
    } catch {
      toast('Failed to load analytics', 'error');
    }
  }, [buildParams, toast]);

  const loadResponses = useCallback(async () => {
    try {
      const data = await adminSurveyApi.responses({
        ...buildParams(),
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setResponses(data.items);
      setResponsesTotal(data.total);
    } catch {
      toast('Failed to load responses', 'error');
    }
  }, [buildParams, page, toast]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([loadAnalytics(), loadResponses()]);
    setLoading(false);
  }, [loadAnalytics, loadResponses]);

  useEffect(() => {
    loadAll(); // eslint-disable-line react-hooks/set-state-in-effect -- async data fetch on filter change
  }, [loadAll]);

  const handleExport = async () => {
    try {
      await adminSurveyApi.exportCsv(buildParams());
      toast('CSV exported', 'success');
    } catch {
      toast('Export failed', 'error');
    }
  };

  const handleViewDetail = async (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      setExpandedDetail(null);
      return;
    }
    try {
      const detail = await adminSurveyApi.responseDetail(id);
      setExpandedId(id);
      setExpandedDetail(detail);
    } catch {
      toast('Failed to load response detail', 'error');
    }
  };

  const stats = analytics?.stats;
  const totalPages = Math.ceil(responsesTotal / PAGE_SIZE);

  const pieData = stats
    ? Object.entries(stats.by_role).map(([role, count]) => ({ name: role, value: count }))
    : [];

  const renderQuestionChart = (q: SurveyQuestionAnalytics) => {
    if (q.question_type === 'free_text') {
      const texts = q.free_text_responses || [];
      const visible = showAllText[q.question_key] ? texts : texts.slice(0, 5);
      return (
        <>
          <ul className="admin-survey-free-text-list">
            {visible.map((t, i) => (
              <li key={i} className="admin-survey-free-text-item">{t}</li>
            ))}
            {texts.length === 0 && (
              <li className="admin-survey-free-text-item" style={{ color: 'var(--color-ink-muted)' }}>
                No responses yet
              </li>
            )}
          </ul>
          {texts.length > 5 && (
            <button
              className="admin-survey-view-btn"
              style={{ marginTop: 8 }}
              onClick={() => setShowAllText(prev => ({ ...prev, [q.question_key]: !prev[q.question_key] }))}
            >
              {showAllText[q.question_key] ? 'Show less' : `Show all (${texts.length})`}
            </button>
          )}
        </>
      );
    }

    if (q.question_type === 'likert_matrix' && q.sub_item_averages) {
      const data = Object.entries(q.sub_item_averages).map(([item, avg]) => ({
        name: item,
        average: Number(avg.toFixed(2)),
      }));
      return (
        <ResponsiveContainer width="100%" height={data.length * 50 + 40}>
          <BarChart data={data} layout="vertical" margin={{ left: 210, right: 20, top: 5, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" domain={[0, 5]} />
            <YAxis type="category" dataKey="name" width={200} tick={<TruncatedTick />} />
            <Tooltip />
            <Bar dataKey="average" fill={CHART_COLORS[0]} />
          </BarChart>
        </ResponsiveContainer>
      );
    }

    if (q.distribution) {
      const data = Object.entries(q.distribution).map(([label, count]) => ({
        name: label,
        count,
      }));

      if (q.question_type === 'likert') {
        return (
          <>
            {q.average != null && (
              <div className="admin-survey-question-meta">
                Average: <strong>{q.average.toFixed(2)}</strong> / 5
              </div>
            )}
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={data} margin={{ left: 10, right: 10, top: 5, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill={CHART_COLORS[0]}>
                  {data.map((_, i) => (
                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </>
        );
      }

      // single_select / multi_select — horizontal bar
      return (
        <ResponsiveContainer width="100%" height={data.length * 45 + 40}>
          <BarChart data={data} layout="vertical" margin={{ left: 210, right: 20, top: 5, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" allowDecimals={false} />
            <YAxis type="category" dataKey="name" width={200} tick={<TruncatedTick />} />
            <Tooltip />
            <Bar dataKey="count" fill={CHART_COLORS[0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      );
    }

    return <p className="admin-survey-question-meta">No data available</p>;
  };

  const formatAnswerValue = (value: any): string => {
    if (value == null) return '-';
    if (Array.isArray(value)) return value.join(', ');
    if (typeof value === 'object') {
      return Object.entries(value).map(([k, v]) => `${k}: ${v}`).join(', ');
    }
    return String(value);
  };

  return (
    <DashboardLayout>
      <div className="admin-survey-page">
        <PageNav items={[
          { label: 'Admin', to: '/admin' },
          { label: 'Survey Results' },
        ]} />
        <h1>Survey Results</h1>

        {/* Filters */}
        <div className="admin-survey-filters">
          <select value={roleFilter} onChange={e => { setRoleFilter(e.target.value); setPage(0); }}>
            <option value="">All Roles</option>
            <option value="parent">Parent</option>
            <option value="student">Student</option>
            <option value="teacher">Teacher</option>
          </select>
          <input
            type="date"
            value={dateFrom}
            onChange={e => { setDateFrom(e.target.value); setPage(0); }}
            placeholder="From"
          />
          <input
            type="date"
            value={dateTo}
            onChange={e => { setDateTo(e.target.value); setPage(0); }}
            placeholder="To"
          />
          <button className="admin-survey-export-btn" onClick={handleExport}>
            Export CSV
          </button>
        </div>

        {loading ? (
          <ListSkeleton rows={6} />
        ) : !analytics ? (
          <div className="admin-survey-empty">No survey data available.</div>
        ) : (
          <>
            {/* Stats cards */}
            <div className="admin-survey-stats">
              <div className="admin-survey-stat-card">
                <div className="admin-survey-stat-value">{stats?.total_responses ?? 0}</div>
                <div className="admin-survey-stat-label">Total Responses</div>
              </div>
              <div className="admin-survey-stat-card">
                <div className="admin-survey-stat-value">{stats?.by_role?.parent ?? 0}</div>
                <div className="admin-survey-stat-label">Parents</div>
              </div>
              <div className="admin-survey-stat-card">
                <div className="admin-survey-stat-value">{stats?.by_role?.student ?? 0}</div>
                <div className="admin-survey-stat-label">Students</div>
              </div>
              <div className="admin-survey-stat-card">
                <div className="admin-survey-stat-value">{stats?.by_role?.teacher ?? 0}</div>
                <div className="admin-survey-stat-label">Teachers</div>
              </div>
              <div className="admin-survey-stat-card">
                <div className="admin-survey-stat-value">
                  {stats?.completion_rate != null ? `${(stats.completion_rate * 100).toFixed(0)}%` : '-'}
                </div>
                <div className="admin-survey-stat-label">Completion Rate</div>
              </div>
            </div>

            {/* Charts row: Pie + Line */}
            <div className="admin-survey-charts">
              <div className="admin-survey-chart-card">
                <div className="admin-survey-chart-title">Role Distribution</div>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      label={(props: any) => `${props.name} ${((props.percent ?? 0) * 100).toFixed(0)}%`}
                    >
                      {pieData.map((entry) => (
                        <Cell key={entry.name} fill={PIE_COLORS[entry.name] || CHART_COLORS[0]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="admin-survey-chart-card">
                <div className="admin-survey-chart-title">Daily Submissions</div>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={analytics.daily_submissions} margin={{ left: 10, right: 10, top: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Line type="monotone" dataKey="count" stroke="#4f46e5" strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Per-question breakdown */}
            {analytics.questions.map((q) => (
              <div key={q.question_key} className="admin-survey-question-card">
                <div className="admin-survey-question-header">
                  <span className="admin-survey-question-key">{q.question_key}</span>
                  <span className="admin-survey-question-text">{q.question_text}</span>
                </div>
                <div className="admin-survey-question-meta">
                  Type: {q.question_type} &middot; {q.total_answers} answer{q.total_answers !== 1 ? 's' : ''}
                </div>
                {renderQuestionChart(q)}
              </div>
            ))}

            {/* Individual Responses table */}
            <h2>Individual Responses</h2>
            {responses.length === 0 ? (
              <div className="admin-survey-empty">No responses found.</div>
            ) : (
              <>
                <table className="admin-survey-responses-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Role</th>
                      <th>Date</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {responses.map((r, idx) => (
                      <>
                        <tr key={r.id}>
                          <td>{page * PAGE_SIZE + idx + 1}</td>
                          <td>
                            <span className={`admin-survey-role-badge ${r.role}`}>
                              {r.role}
                            </span>
                          </td>
                          <td>{new Date(r.created_at).toLocaleDateString()}</td>
                          <td>
                            <button
                              className="admin-survey-view-btn"
                              onClick={() => handleViewDetail(r.id)}
                            >
                              {expandedId === r.id ? 'Hide' : 'View'}
                            </button>
                          </td>
                        </tr>
                        {expandedId === r.id && expandedDetail && (
                          <tr key={`detail-${r.id}`}>
                            <td colSpan={4}>
                              <div className="admin-survey-detail">
                                {expandedDetail.answers.map((a) => (
                                  <div key={a.id} className="admin-survey-detail-answer">
                                    <div className="admin-survey-detail-key">{a.question_key}</div>
                                    <div className="admin-survey-detail-value">
                                      {formatAnswerValue(a.answer_value)}
                                    </div>
                                  </div>
                                ))}
                                {expandedDetail.answers.length === 0 && (
                                  <div className="admin-survey-question-meta">No answers recorded</div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    ))}
                  </tbody>
                </table>

                <div className="admin-survey-pagination">
                  <button disabled={page === 0} onClick={() => setPage(p => p - 1)}>
                    Previous
                  </button>
                  <span style={{ padding: '6px 8px', fontSize: 14, color: 'var(--color-ink-muted)' }}>
                    Page {page + 1} of {totalPages || 1}
                  </span>
                  <button disabled={page + 1 >= totalPages} onClick={() => setPage(p => p + 1)}>
                    Next
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
