import { useState, useRef, useCallback, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import { PageSkeleton } from '../components/Skeleton';
import { xpApi } from '../api/xp';
import type { XpLedgerEntry } from '../api/xp';
import { downloadAsPdf } from '../utils/exportUtils';
import { ReportBugLink } from '../components/ReportBugLink';
import './XpHistoryPage.css';

const ACTION_LABELS: Record<string, string> = {
  upload: 'Uploaded Document',
  upload_lms: 'Uploaded from LMS',
  study_guide: 'Generated Study Guide',
  flashcard_deck: 'Generated Flashcards',
  flashcard_review: 'Flashcard Review',
  ai_chat: 'AI Chat Question',
  pomodoro: 'Study Session',
  flashcard_got_it: 'Flashcard Mastered',
  daily_login: 'Daily Login Bonus',
  weekly_review: 'Weekly Review',
  quiz_complete: 'Completed Quiz',
  quiz_improvement: 'Quiz Improvement',
  brownie_points: 'Brownie Points',
};

const ACTION_COLORS: Record<string, string> = {
  upload: '#2563eb',
  upload_lms: '#2563eb',
  study_guide: '#7c3aed',
  flashcard_deck: '#7c3aed',
  flashcard_review: '#7c3aed',
  ai_chat: '#0891b2',
  pomodoro: '#059669',
  flashcard_got_it: '#059669',
  daily_login: '#d97706',
  weekly_review: '#d97706',
  quiz_complete: '#dc2626',
  quiz_improvement: '#dc2626',
  brownie_points: '#db2777',
};

const PAGE_SIZE = 50;

function getActionLabel(actionType: string): string {
  return ACTION_LABELS[actionType] || actionType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function getActionColor(actionType: string): string {
  return ACTION_COLORS[actionType] || '#6b7280';
}

export function XpHistoryPage() {
  const [entries, setEntries] = useState<XpLedgerEntry[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [filter, setFilter] = useState('all');
  const tableRef = useRef<HTMLDivElement>(null);

  const { isLoading, error } = useQuery({
    queryKey: ['xp-ledger'],
    queryFn: async () => {
      const data = await xpApi.getLedger(PAGE_SIZE, 0);
      setEntries(data.entries);
      setTotalCount(data.total_count);
      setOffset(data.entries.length);
      return data;
    },
  });

  const { data: summary } = useQuery({
    queryKey: ['xp-summary'],
    queryFn: xpApi.getSummary,
  });

  const { data: streak } = useQuery({
    queryKey: ['xp-streak'],
    queryFn: xpApi.getStreak,
  });

  const handleLoadMore = useCallback(async () => {
    setLoadingMore(true);
    try {
      const data = await xpApi.getLedger(PAGE_SIZE, offset);
      setEntries(prev => [...prev, ...data.entries]);
      setOffset(prev => prev + data.entries.length);
      setTotalCount(data.total_count);
    } finally {
      setLoadingMore(false);
    }
  }, [offset]);

  const filteredEntries = useMemo(() => {
    if (filter === 'all') return entries;
    return entries.filter(e => e.action_type === filter);
  }, [entries, filter]);

  // Compute running totals
  const entriesWithRunning = useMemo(() => {
    // We don't have a true running total from the API, so compute from total_xp backwards
    const totalXp = summary?.total_xp ?? 0;
    // entries are newest-first; running total for row 0 = total_xp,
    // row 1 = total_xp - entries[0].xp_awarded, etc.
    // But we only have a page of entries, so approximate using the loaded set.
    // We'll compute backwards from total XP for all loaded entries.
    let running = totalXp;
    const result: Array<XpLedgerEntry & { runningTotal: number }> = [];
    for (const entry of entries) {
      result.push({ ...entry, runningTotal: running });
      running -= entry.xp_awarded;
    }
    // Now filter if needed
    if (filter === 'all') return result;
    return result.filter(e => e.action_type === filter);
  }, [entries, filter, summary?.total_xp]);

  const uniqueActionTypes = useMemo(() => {
    const types = new Set(entries.map(e => e.action_type));
    return Array.from(types).sort();
  }, [entries]);

  const handleExportPdf = useCallback(async () => {
    if (!tableRef.current) return;
    await downloadAsPdf(tableRef.current, 'xp-history.pdf');
  }, []);

  const hasMore = entries.length < totalCount;

  return (
    <DashboardLayout showBackButton>
      <div className="xph-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'XP History' },
        ]} />

        <div className="xph-header">
          <div className="xph-header-left">
            <h2>XP History</h2>
            {summary && (
              <span className="xph-level-badge">
                Lv. {summary.level} &middot; {summary.level_title}
              </span>
            )}
          </div>
          {summary && (
            <span className="xph-total-xp">{summary.total_xp.toLocaleString()} XP</span>
          )}
        </div>

        {/* Summary cards */}
        {(summary || streak) && (
          <div className="xph-stats-grid">
            {streak && (
              <div className="xph-stat-card">
                <span className="xph-stat-value">{streak.current_streak}</span>
                <span className="xph-stat-label">Day Streak</span>
              </div>
            )}
            {summary && (
              <>
                <div className="xph-stat-card">
                  <span className="xph-stat-value">{summary.level}</span>
                  <span className="xph-stat-label">Level</span>
                </div>
                <div className="xph-stat-card">
                  <span className="xph-stat-value">{summary.total_xp.toLocaleString()}</span>
                  <span className="xph-stat-label">Total XP</span>
                </div>
                <div className="xph-stat-card">
                  <span className="xph-stat-value">{summary.xp_for_next_level - summary.xp_in_level}</span>
                  <span className="xph-stat-label">XP to Next Level</span>
                </div>
              </>
            )}
          </div>
        )}

        {isLoading && <PageSkeleton />}

        {error && (
          <div className="xph-error">Failed to load XP history. Please try again.<ReportBugLink errorMessage="Failed to load XP history" /></div>
        )}

        {!isLoading && !error && (
          <>
            {/* Toolbar */}
            <div className="xph-toolbar">
              <select
                className="xph-filter"
                value={filter}
                onChange={e => setFilter(e.target.value)}
                aria-label="Filter by action type"
              >
                <option value="all">All Actions</option>
                {uniqueActionTypes.map(type => (
                  <option key={type} value={type}>{getActionLabel(type)}</option>
                ))}
              </select>
              <button className="xph-export-btn" onClick={handleExportPdf} type="button">
                Export PDF
              </button>
            </div>

            {/* Ledger table */}
            <div className="xph-table-wrapper" ref={tableRef}>
              {entriesWithRunning.length > 0 ? (
                <table className="xph-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Action</th>
                      <th className="xph-col-num">XP Earned</th>
                      <th className="xph-col-num">Multiplier</th>
                      <th className="xph-col-num">Running Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entriesWithRunning.map((entry, idx) => (
                      <tr key={idx} className="xph-row">
                        <td className="xph-cell-date">
                          {new Date(entry.created_at).toLocaleDateString(undefined, {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          })}
                        </td>
                        <td>
                          <span
                            className="xph-action-pill"
                            style={{ '--pill-color': getActionColor(entry.action_type) } as React.CSSProperties}
                          >
                            {getActionLabel(entry.action_type)}
                          </span>
                          {entry.action_type === 'brownie_points' && entry.reason && (
                            <span className="xph-reason">{entry.reason}</span>
                          )}
                        </td>
                        <td className="xph-col-num xph-cell-xp">+{entry.xp_awarded}</td>
                        <td className="xph-col-num">
                          {entry.multiplier !== 1 ? `${entry.multiplier}x` : '1x'}
                        </td>
                        <td className="xph-col-num">{entry.runningTotal.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="xph-empty">
                  <h3>No XP entries yet</h3>
                  <p>Start earning XP by uploading documents, completing quizzes, and more!</p>
                </div>
              )}
            </div>

            {/* Load More */}
            {hasMore && filter === 'all' && (
              <div className="xph-load-more">
                <button
                  className="xph-load-more-btn"
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  type="button"
                >
                  {loadingMore ? 'Loading...' : `Load More (${entries.length} of ${totalCount})`}
                </button>
              </div>
            )}

            {/* Show count */}
            <div className="xph-count">
              Showing {filteredEntries.length} of {totalCount} entries
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
