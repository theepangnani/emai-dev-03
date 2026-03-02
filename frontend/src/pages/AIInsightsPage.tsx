import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { aiInsightsApi, type AIInsight } from '../api/aiInsights';
import { parentApi, type ChildSummary } from '../api/parent';
import './AIInsightsPage.css';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function timeAgo(isoString: string): string {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin} minute${diffMin !== 1 ? 's' : ''} ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} hour${diffHr !== 1 ? 's' : ''} ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay} day${diffDay !== 1 ? 's' : ''} ago`;
  return new Date(isoString).toLocaleDateString();
}

function formatInsightType(type: string): string {
  switch (type) {
    case 'weekly': return 'Weekly';
    case 'monthly': return 'Monthly';
    case 'on_demand': return 'On Demand';
    default: return type;
  }
}

function getTrendArrow(trend: string): string {
  switch (trend) {
    case 'improving': return '↑';
    case 'declining': return '↓';
    default: return '→';
  }
}

function getTrendClass(trend: string): string {
  switch (trend) {
    case 'improving': return 'trend-up';
    case 'declining': return 'trend-down';
    default: return 'trend-stable';
  }
}

// ─── Subcomponents ────────────────────────────────────────────────────────────

function InsightSkeleton() {
  return (
    <div className="ai-insight-skeleton" aria-busy="true" aria-label="Loading insight">
      <div className="skeleton ai-sk-summary" />
      <div className="ai-sk-sections">
        <div className="skeleton ai-sk-section" />
        <div className="skeleton ai-sk-section" />
      </div>
    </div>
  );
}

interface GeneratingCardProps {
  childName: string;
}

function GeneratingCard({ childName }: GeneratingCardProps) {
  return (
    <div className="ai-generating-card" role="status" aria-live="polite">
      <div className="ai-generating-pulse" aria-hidden="true" />
      <p className="ai-generating-text">
        AI is analyzing <strong>{childName}</strong>'s academic data...
      </p>
      <p className="ai-generating-sub">This usually takes 10-20 seconds.</p>
    </div>
  );
}

interface InsightDetailProps {
  insight: AIInsight;
  onRegenerate: () => void;
  onDelete: () => void;
  regenerating: boolean;
  deleting: boolean;
}

function InsightDetail({ insight, onRegenerate, onDelete, regenerating, deleting }: InsightDetailProps) {
  // Local checkbox state for action items (UI only — no persistence)
  const [checkedActions, setCheckedActions] = useState<Set<number>>(new Set());

  const toggleAction = useCallback((idx: number) => {
    setCheckedActions(prev => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  }, []);

  return (
    <div className="ai-insight-detail">
      {/* Summary card */}
      <div className="ai-insight-summary-card">
        <div className="ai-insight-summary-header">
          <span className="ai-insight-type-badge">{formatInsightType(insight.insight_type)}</span>
          <span className="ai-insight-timestamp">Generated {timeAgo(insight.generated_at)}</span>
        </div>
        <p className="ai-insight-summary-text">{insight.summary}</p>
      </div>

      {/* Strengths */}
      {insight.strengths && insight.strengths.length > 0 && (
        <div className="ai-insight-section ai-section-strengths">
          <h3 className="ai-section-title">
            <span className="ai-section-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </span>
            Strengths
          </h3>
          <ul className="ai-insight-list ai-strengths-list">
            {insight.strengths.map((item, i) => (
              <li key={i} className="ai-insight-list-item">
                <span className="ai-item-check ai-item-check-green" aria-hidden="true">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Areas for Growth */}
      {insight.concerns && insight.concerns.length > 0 && (
        <div className="ai-insight-section ai-section-concerns">
          <h3 className="ai-section-title">
            <span className="ai-section-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </span>
            Areas for Growth
          </h3>
          <ul className="ai-insight-list ai-concerns-list">
            {insight.concerns.map((item, i) => (
              <li key={i} className="ai-insight-list-item">
                <span className="ai-item-check ai-item-check-amber" aria-hidden="true">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                </span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Action Items This Week */}
      {insight.parent_actions && insight.parent_actions.length > 0 && (
        <div className="ai-insight-section ai-section-actions">
          <h3 className="ai-section-title">
            <span className="ai-section-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="9 11 12 14 22 4" />
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
              </svg>
            </span>
            Your Action Items This Week
          </h3>
          <ol className="ai-action-items-list">
            {insight.parent_actions.map((action, i) => (
              <li key={i} className={`ai-action-item${checkedActions.has(i) ? ' checked' : ''}`}>
                <label className="ai-action-label">
                  <input
                    type="checkbox"
                    className="ai-action-checkbox"
                    checked={checkedActions.has(i)}
                    onChange={() => toggleAction(i)}
                    aria-label={action}
                  />
                  <span className="ai-action-text">{action}</span>
                </label>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Subject Analysis */}
      {insight.subject_analysis && Object.keys(insight.subject_analysis).length > 0 && (
        <div className="ai-insight-section ai-section-subjects">
          <h3 className="ai-section-title">
            <span className="ai-section-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="20" x2="18" y2="10" />
                <line x1="12" y1="20" x2="12" y2="4" />
                <line x1="6" y1="20" x2="6" y2="14" />
              </svg>
            </span>
            Subject Analysis
          </h3>
          <div className="ai-subject-table-wrapper">
            <table className="ai-subject-table">
              <thead>
                <tr>
                  <th>Subject</th>
                  <th>Trend</th>
                  <th>Avg Score</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(insight.subject_analysis).map(([subject, data]) => (
                  <tr key={subject}>
                    <td className="ai-subject-name">{subject}</td>
                    <td>
                      <span className={`ai-trend-badge ${getTrendClass(data.trend)}`}>
                        {getTrendArrow(data.trend)} {data.trend}
                      </span>
                    </td>
                    <td className="ai-subject-score">
                      {data.avg_score != null ? `${data.avg_score}%` : '—'}
                    </td>
                    <td className="ai-subject-note">{data.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Learning Style Note */}
      {insight.learning_style_note && (
        <div className="ai-insight-section ai-section-learning">
          <h3 className="ai-section-title">
            <span className="ai-section-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
            </span>
            Learning Style Observation
          </h3>
          <div className="ai-learning-note-card">
            <p className="ai-learning-note-text">{insight.learning_style_note}</p>
          </div>
        </div>
      )}

      {/* Footer actions */}
      <div className="ai-insight-footer">
        <span className="ai-insight-footer-time">Generated {timeAgo(insight.generated_at)}</span>
        <div className="ai-insight-footer-actions">
          <button
            className="ai-regenerate-btn"
            onClick={onRegenerate}
            disabled={regenerating}
            aria-label="Regenerate insight"
          >
            {regenerating ? (
              <>
                <span className="ai-btn-spinner" aria-hidden="true" />
                Regenerating...
              </>
            ) : (
              <>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polyline points="23 4 23 10 17 10" />
                  <polyline points="1 20 1 14 7 14" />
                  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                </svg>
                Regenerate
              </>
            )}
          </button>
          <button
            className="ai-delete-btn"
            onClick={onDelete}
            disabled={deleting}
            aria-label="Delete this insight"
          >
            {deleting ? 'Deleting...' : (
              <>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                  <path d="M10 11v6M14 11v6" />
                  <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                </svg>
                Delete
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export function AIInsightsPage() {
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChildId, setSelectedChildId] = useState<number | null>(null);
  const [insights, setInsights] = useState<AIInsight[]>([]);
  const [selectedInsightId, setSelectedInsightId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load children on mount
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    parentApi.getChildren()
      .then(data => {
        if (cancelled) return;
        setChildren(data);
        if (data.length > 0) {
          setSelectedChildId(data[0].student_id);
        }
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) {
          setError('Failed to load your children. Please refresh the page.');
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, []);

  // Load insights whenever selected child changes
  useEffect(() => {
    if (!selectedChildId) {
      setInsights([]);
      setSelectedInsightId(null);
      return;
    }
    let cancelled = false;
    aiInsightsApi.list()
      .then(all => {
        if (cancelled) return;
        const childInsights = all.filter(i => i.student_id === selectedChildId);
        setInsights(childInsights);
        // Auto-select the latest insight
        if (childInsights.length > 0) {
          setSelectedInsightId(childInsights[0].id);
        } else {
          setSelectedInsightId(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Failed to load insights.');
        }
      });
    return () => { cancelled = true; };
  }, [selectedChildId]);

  const selectedChild = children.find(c => c.student_id === selectedChildId);
  const selectedInsight = insights.find(i => i.id === selectedInsightId) ?? null;

  const handleGenerate = useCallback(async () => {
    if (!selectedChildId) return;
    setGenerating(true);
    setError(null);
    try {
      const newInsight = await aiInsightsApi.generate({
        student_id: selectedChildId,
        insight_type: 'on_demand',
      });
      setInsights(prev => [newInsight, ...prev]);
      setSelectedInsightId(newInsight.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to generate insight. Please try again.';
      setError(msg);
    } finally {
      setGenerating(false);
    }
  }, [selectedChildId]);

  const handleRegenerate = useCallback(async () => {
    if (!selectedChildId) return;
    setRegenerating(true);
    setError(null);
    try {
      const newInsight = await aiInsightsApi.generate({
        student_id: selectedChildId,
        insight_type: 'on_demand',
      });
      setInsights(prev => [newInsight, ...prev]);
      setSelectedInsightId(newInsight.id);
    } catch {
      setError('Failed to regenerate insight. Please try again.');
    } finally {
      setRegenerating(false);
    }
  }, [selectedChildId]);

  const handleDelete = useCallback(async () => {
    if (!selectedInsightId) return;
    if (!window.confirm('Delete this insight? This cannot be undone.')) return;
    setDeleting(true);
    setError(null);
    try {
      await aiInsightsApi.delete(selectedInsightId);
      setInsights(prev => {
        const remaining = prev.filter(i => i.id !== selectedInsightId);
        setSelectedInsightId(remaining.length > 0 ? remaining[0].id : null);
        return remaining;
      });
    } catch {
      setError('Failed to delete insight. Please try again.');
    } finally {
      setDeleting(false);
    }
  }, [selectedInsightId]);

  const handleChildChange = useCallback((childId: number) => {
    setSelectedChildId(childId);
    setError(null);
  }, []);

  return (
    <DashboardLayout welcomeSubtitle="AI-powered academic analysis for your child">
      <div className="ai-insights-page">
        {/* Page header */}
        <div className="ai-insights-header">
          <div className="ai-insights-title-row">
            <div className="ai-insights-title-group">
              <span className="ai-insights-icon" aria-hidden="true">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2a4 4 0 0 1 4 4c0 1.5-.7 2.8-1.8 3.7L16 22H8l1.8-12.3A4 4 0 0 1 8 6a4 4 0 0 1 4-4z" />
                  <line x1="8" y1="22" x2="16" y2="22" />
                  <line x1="9" y1="18" x2="15" y2="18" />
                </svg>
              </span>
              <h1 className="ai-insights-title">AI Insights</h1>
            </div>

            {/* Child selector */}
            {children.length > 1 && (
              <div className="ai-child-selector">
                <label htmlFor="ai-child-select" className="ai-child-selector-label">Viewing:</label>
                <select
                  id="ai-child-select"
                  className="ai-child-select"
                  value={selectedChildId ?? ''}
                  onChange={e => handleChildChange(Number(e.target.value))}
                >
                  {children.map(c => (
                    <option key={c.student_id} value={c.student_id}>
                      {c.full_name}{c.grade_level != null ? ` (Grade ${c.grade_level})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Generate button */}
          {selectedChildId && !generating && (
            <button
              className="ai-generate-btn"
              onClick={handleGenerate}
              disabled={generating}
              aria-label={`Generate new AI insight for ${selectedChild?.full_name ?? 'child'}`}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
              Generate New Insight
            </button>
          )}
        </div>

        {/* Error banner */}
        {error && (
          <div className="ai-error-banner" role="alert">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            {error}
            <button className="ai-error-dismiss" onClick={() => setError(null)} aria-label="Dismiss error">&times;</button>
          </div>
        )}

        {loading ? (
          <InsightSkeleton />
        ) : children.length === 0 ? (
          <div className="ai-empty-state">
            <p>No children linked to your account yet. Add a child from the Dashboard to get started.</p>
          </div>
        ) : (
          <div className="ai-insights-body">
            {/* Insight history sidebar */}
            <aside className="ai-history-sidebar">
              <h2 className="ai-history-title">History</h2>
              {insights.length === 0 ? (
                <div className="ai-history-empty">
                  <p>No insights yet for {selectedChild?.full_name ?? 'this child'}.</p>
                  <p className="ai-history-empty-sub">Generate your first insight above.</p>
                </div>
              ) : (
                <ul className="ai-history-list" role="list">
                  {insights.map(insight => (
                    <li key={insight.id}>
                      <button
                        className={`ai-history-item${selectedInsightId === insight.id ? ' active' : ''}`}
                        onClick={() => setSelectedInsightId(insight.id)}
                        aria-current={selectedInsightId === insight.id ? 'true' : undefined}
                      >
                        <div className="ai-history-item-header">
                          <span className="ai-history-type-badge">{formatInsightType(insight.insight_type)}</span>
                          <span className="ai-history-time">{timeAgo(insight.generated_at)}</span>
                        </div>
                        <p className="ai-history-summary">
                          {insight.summary.length > 90
                            ? `${insight.summary.slice(0, 90)}...`
                            : insight.summary}
                        </p>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </aside>

            {/* Main content area */}
            <main className="ai-insights-main">
              {generating ? (
                <GeneratingCard childName={selectedChild?.full_name ?? 'your child'} />
              ) : selectedInsight ? (
                <InsightDetail
                  insight={selectedInsight}
                  onRegenerate={handleRegenerate}
                  onDelete={handleDelete}
                  regenerating={regenerating}
                  deleting={deleting}
                />
              ) : (
                <div className="ai-no-insight-state">
                  <div className="ai-no-insight-icon" aria-hidden="true">
                    <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 2a4 4 0 0 1 4 4c0 1.5-.7 2.8-1.8 3.7L16 22H8l1.8-12.3A4 4 0 0 1 8 6a4 4 0 0 1 4-4z" />
                      <line x1="8" y1="22" x2="16" y2="22" />
                    </svg>
                  </div>
                  <h2 className="ai-no-insight-title">No insight yet</h2>
                  <p className="ai-no-insight-text">
                    Generate an AI insight to get a holistic view of{' '}
                    <strong>{selectedChild?.full_name ?? 'your child'}</strong>'s academic performance,
                    strengths, areas for growth, and personalized action items.
                  </p>
                  <button
                    className="ai-generate-btn ai-generate-btn-centered"
                    onClick={handleGenerate}
                    disabled={generating}
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                    </svg>
                    Generate First Insight
                  </button>
                </div>
              )}
            </main>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
