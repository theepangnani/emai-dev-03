import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { ListSkeleton } from '../components/Skeleton';
import { PageNav } from '../components/PageNav';
import { useDebounce } from '../utils/useDebounce';
import {
  adminAIUsageApi,
  type AIUsageUser,
  type AIUsageSummary,
  type AICostSummary,
  type AILimitRequest,
  type AIUsageHistoryEntry,
} from '../api/adminAIUsage';
import './AdminAIUsagePage.css';

const PAGE_SIZE = 25;

type Tab = 'users' | 'history' | 'requests' | 'audit';

export function AdminAIUsagePage() {
  const [tab, setTab] = useState<Tab>('users');

  // Summary
  const [summary, setSummary] = useState<AIUsageSummary | null>(null);
  const [costSummary, setCostSummary] = useState<AICostSummary | null>(null);

  // Users
  const [users, setUsers] = useState<AIUsageUser[]>([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersPage, setUsersPage] = useState(0);
  const [search, setSearch] = useState('');
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc');
  const [usersLoading, setUsersLoading] = useState(true);
  const debouncedSearch = useDebounce(search, 400);

  // Usage History
  const [history, setHistory] = useState<AIUsageHistoryEntry[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPage, setHistoryPage] = useState(0);
  const [historySearch, setHistorySearch] = useState('');
  const [historyType, setHistoryType] = useState<string>('');
  const [historyEntryType, setHistoryEntryType] = useState<string>('');
  const [historyDateFrom, setHistoryDateFrom] = useState('');
  const [historyDateTo, setHistoryDateTo] = useState('');
  const [historyLoading, setHistoryLoading] = useState(false);
  const debouncedHistorySearch = useDebounce(historySearch, 400);

  // Requests
  const [requests, setRequests] = useState<AILimitRequest[]>([]);
  const [requestsTotal, setRequestsTotal] = useState(0);
  const [requestsPage, setRequestsPage] = useState(0);
  const [requestsStatus, setRequestsStatus] = useState<string>('all');
  const [requestsLoading, setRequestsLoading] = useState(false);

  // Audit Log
  const [auditItems, setAuditItems] = useState<Array<{
    id: number;
    admin_name: string;
    action_type: string;
    target_user_name: string | null;
    details: string | null;
    created_at: string | null;
  }>>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditPage, setAuditPage] = useState(0);
  const [auditLoading, setAuditLoading] = useState(false);

  // Modals / inline state
  const [limitModal, setLimitModal] = useState<{ user: AIUsageUser; value: number } | null>(null);
  const [confirmReset, setConfirmReset] = useState<number | null>(null);
  const [bulkLimitModal, setBulkLimitModal] = useState<{ value: number; resetCounts: boolean } | null>(null);
  const [approveAmounts, setApproveAmounts] = useState<Record<number, number>>({});
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

  // Load summary + request count on mount
  useEffect(() => {
    adminAIUsageApi.getSummary().then(setSummary).catch((err) => console.error('Failed to load AI usage summary:', err));
    adminAIUsageApi.getCostSummary().then(setCostSummary).catch((err) => console.error('Failed to load cost summary:', err));
    // Pre-fetch pending request count for badge
    adminAIUsageApi.listRequests({ status: 'pending', skip: 0, limit: 1 })
      .then((data) => setRequestsTotal(data.total))
      .catch((err) => console.error('Failed to load pending requests:', err));
  }, []);

  // Load users
  const loadUsers = useCallback(async () => {
    setUsersLoading(true);
    try {
      const data = await adminAIUsageApi.listUsers({
        search: debouncedSearch || undefined,
        sort_by: 'ai_usage_count',
        sort_dir: sortDir,
        skip: usersPage * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setUsers(data.items);
      setUsersTotal(data.total);
    } catch {
      // Failed to load
    } finally {
      setUsersLoading(false);
    }
  }, [debouncedSearch, sortDir, usersPage]);

  useEffect(() => {
    if (tab === 'users') loadUsers();
  }, [tab, loadUsers]);

  // Load history
  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const data = await adminAIUsageApi.listHistory({
        search: debouncedHistorySearch || undefined,
        generation_type: historyType || undefined,
        type: historyEntryType || undefined,
        date_from: historyDateFrom || undefined,
        date_to: historyDateTo || undefined,
        skip: historyPage * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setHistory(data.items);
      setHistoryTotal(data.total);
    } catch {
      // Failed to load
    } finally {
      setHistoryLoading(false);
    }
  }, [debouncedHistorySearch, historyType, historyEntryType, historyDateFrom, historyDateTo, historyPage]);

  useEffect(() => {
    if (tab === 'history') loadHistory();
  }, [tab, loadHistory]);

  // Load requests
  const loadRequests = useCallback(async () => {
    setRequestsLoading(true);
    try {
      const data = await adminAIUsageApi.listRequests({
        status: requestsStatus,
        skip: requestsPage * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setRequests(data.items);
      setRequestsTotal(data.total);
    } catch {
      // Failed to load
    } finally {
      setRequestsLoading(false);
    }
  }, [requestsStatus, requestsPage]);

  useEffect(() => {
    if (tab === 'requests') loadRequests();
  }, [tab, loadRequests]);

  // Load audit log
  const loadAuditLog = useCallback(async () => {
    setAuditLoading(true);
    try {
      const data = await adminAIUsageApi.listAuditLog({
        skip: auditPage * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setAuditItems(data.items);
      setAuditTotal(data.total);
    } catch {
      // Failed to load
    } finally {
      setAuditLoading(false);
    }
  }, [auditPage]);

  useEffect(() => {
    if (tab === 'audit') loadAuditLog();
  }, [tab, loadAuditLog]);

  // Actions
  const setActionBusy = (key: string, busy: boolean) => {
    setActionLoading((prev) => ({ ...prev, [key]: busy }));
  };

  const handleSetLimit = async () => {
    if (!limitModal) return;
    const key = `limit-${limitModal.user.id}`;
    setActionBusy(key, true);
    try {
      await adminAIUsageApi.setUserLimit(limitModal.user.id, limitModal.value);
      setLimitModal(null);
      loadUsers();
      adminAIUsageApi.getSummary().then(setSummary).catch(() => {});
    } finally {
      setActionBusy(key, false);
    }
  };

  const handleBulkSetLimit = async () => {
    if (!bulkLimitModal) return;
    const key = 'bulk-limit';
    setActionBusy(key, true);
    try {
      await adminAIUsageApi.bulkSetLimit(bulkLimitModal.value, bulkLimitModal.resetCounts);
      setBulkLimitModal(null);
      loadUsers();
      adminAIUsageApi.getSummary().then(setSummary).catch(() => {});
    } finally {
      setActionBusy(key, false);
    }
  };

  const handleResetCount = async (userId: number) => {
    const key = `reset-${userId}`;
    setActionBusy(key, true);
    try {
      await adminAIUsageApi.resetUserCount(userId);
      setConfirmReset(null);
      loadUsers();
      adminAIUsageApi.getSummary().then(setSummary).catch(() => {});
    } finally {
      setActionBusy(key, false);
    }
  };

  const handleApprove = async (req: AILimitRequest) => {
    const amount = approveAmounts[req.id] ?? req.requested_amount;
    const key = `approve-${req.id}`;
    setActionBusy(key, true);
    try {
      await adminAIUsageApi.approveRequest(req.id, amount);
      loadRequests();
    } finally {
      setActionBusy(key, false);
    }
  };

  const handleDecline = async (req: AILimitRequest) => {
    const key = `decline-${req.id}`;
    setActionBusy(key, true);
    try {
      await adminAIUsageApi.declineRequest(req.id);
      loadRequests();
    } finally {
      setActionBusy(key, false);
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const getProgressClass = (count: number, limit: number) => {
    if (limit === 0) return '';
    const pct = count / limit;
    if (pct >= 1) return 'danger';
    if (pct >= 0.8) return 'warning';
    return '';
  };

  const getStatusBadgeClass = (status: string) => {
    if (status === 'approved') return 'ai-usage-status-badge approved';
    if (status === 'declined') return 'ai-usage-status-badge declined';
    return 'ai-usage-status-badge pending';
  };

  const formatGenerationType = (type: string) => {
    const map: Record<string, string> = {
      study_guide: 'Study Guide',
      quiz: 'Quiz',
      flashcards: 'Flashcards',
    };
    return map[type] || type;
  };

  const usersTotalPages = Math.ceil(usersTotal / PAGE_SIZE);
  const historyTotalPages = Math.ceil(historyTotal / PAGE_SIZE);
  const requestsTotalPages = Math.ceil(requestsTotal / PAGE_SIZE);
  const auditTotalPages = Math.ceil(auditTotal / PAGE_SIZE);

  // Count pending requests for badge
  const pendingCount = tab !== 'requests' ? requestsTotal : requests.filter((r) => r.status === 'pending').length;

  return (
    <DashboardLayout welcomeSubtitle="Platform administration">
      <div className="ai-usage-page">
        <PageNav
          items={[
            { label: 'Home', to: '/dashboard' },
            { label: 'Admin', to: '/dashboard' },
            { label: 'AI Usage' },
          ]}
        />

        <div className="ai-usage-header">
          <h2>AI Usage Management</h2>
          <p className="ai-usage-subtitle">Monitor and manage AI usage across the platform</p>
        </div>

        {/* Summary */}
        <div className="ai-usage-summary">
          <div className="ai-usage-summary-card">
            <h3>Total AI Calls</h3>
            <div className="ai-usage-summary-value">
              {summary ? summary.total_ai_calls.toLocaleString() : '--'}
            </div>
          </div>
          <div className="ai-usage-summary-card">
            <h3>Total Estimated Cost</h3>
            <div className="ai-usage-summary-value">
              {costSummary ? `$${costSummary.total_cost_usd.toFixed(4)}` : '--'}
            </div>
            {costSummary && (
              <p style={{ fontSize: 12, color: 'var(--color-ink-muted)', margin: '4px 0 0' }}>
                {costSummary.total_tokens.toLocaleString()} tokens
              </p>
            )}
          </div>
          <div className="ai-usage-summary-card">
            <h3>Top Users by Usage</h3>
            {summary ? (
              <ul className="ai-usage-top-list">
                {summary.top_users.map((u) => (
                  <li key={u.id}>
                    <span>{u.full_name}</span>
                    <span>{u.ai_usage_count}</span>
                  </li>
                ))}
                {summary.top_users.length === 0 && (
                  <li><span>No usage yet</span><span></span></li>
                )}
              </ul>
            ) : (
              <p style={{ fontSize: 13, color: 'var(--color-ink-muted)', margin: 0 }}>Loading...</p>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="ai-usage-tabs">
          <button
            className={`ai-usage-tab${tab === 'users' ? ' active' : ''}`}
            onClick={() => setTab('users')}
          >
            Overview
          </button>
          <button
            className={`ai-usage-tab${tab === 'history' ? ' active' : ''}`}
            onClick={() => setTab('history')}
          >
            Usage History
          </button>
          <button
            className={`ai-usage-tab${tab === 'requests' ? ' active' : ''}`}
            onClick={() => setTab('requests')}
          >
            Credit Requests
            {pendingCount > 0 && tab !== 'requests' && (
              <span style={{ marginLeft: 6, fontWeight: 700 }}>({pendingCount})</span>
            )}
          </button>
          <button
            className={`ai-usage-tab${tab === 'audit' ? ' active' : ''}`}
            onClick={() => setTab('audit')}
          >
            Activity Log
          </button>
        </div>

        {/* Users Tab (Overview) */}
        {tab === 'users' && (
          <>
            <div className="ai-usage-search">
              <input
                type="text"
                placeholder="Search by name or email..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setUsersPage(0);
                }}
              />
              <button
                className="ai-usage-btn primary"
                onClick={() => setBulkLimitModal({ value: 10, resetCounts: false })}
              >
                Set Limit for All
              </button>
            </div>

            {usersLoading ? (
              <ListSkeleton rows={8} />
            ) : (
              <>
                <table className="ai-usage-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th
                        className="sortable"
                        onClick={() => setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))}
                      >
                        Usage {sortDir === 'desc' ? '\u2193' : '\u2191'}
                      </th>
                      <th>Role</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id}>
                        <td>{u.full_name}</td>
                        <td>{u.email}</td>
                        <td>
                          <div className="ai-usage-progress">
                            <div className="ai-usage-progress-bar">
                              <div
                                className={`ai-usage-progress-fill ${getProgressClass(u.ai_usage_count, u.ai_usage_limit)}`}
                                style={{
                                  width: u.ai_usage_limit > 0
                                    ? `${Math.min(100, (u.ai_usage_count / u.ai_usage_limit) * 100)}%`
                                    : '0%',
                                }}
                              />
                            </div>
                            <span className="ai-usage-progress-label">
                              {u.ai_usage_count} / {u.ai_usage_limit}
                            </span>
                          </div>
                        </td>
                        <td>
                          <span className="ai-usage-role">{u.role}</span>
                        </td>
                        <td>
                          <div className="ai-usage-actions">
                            {confirmReset === u.id ? (
                              <div className="ai-usage-confirm">
                                <span>Reset?</span>
                                <button
                                  className="ai-usage-btn reset"
                                  disabled={!!actionLoading[`reset-${u.id}`]}
                                  onClick={() => handleResetCount(u.id)}
                                >
                                  Yes
                                </button>
                                <button
                                  className="ai-usage-btn"
                                  onClick={() => setConfirmReset(null)}
                                >
                                  No
                                </button>
                              </div>
                            ) : (
                              <>
                                <button
                                  className="ai-usage-btn"
                                  onClick={() =>
                                    setLimitModal({ user: u, value: u.ai_usage_limit })
                                  }
                                >
                                  Adjust Limit
                                </button>
                                <button
                                  className="ai-usage-btn reset"
                                  onClick={() => setConfirmReset(u.id)}
                                >
                                  Reset Count
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                    {users.length === 0 && (
                      <tr>
                        <td colSpan={5} className="ai-usage-empty">
                          No users found
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>

                {usersTotalPages > 1 && (
                  <div className="ai-usage-pagination">
                    <span>
                      Showing {usersPage * PAGE_SIZE + 1}--
                      {Math.min((usersPage + 1) * PAGE_SIZE, usersTotal)} of {usersTotal}
                    </span>
                    <div className="ai-usage-pagination-btns">
                      <button
                        disabled={usersPage === 0}
                        onClick={() => setUsersPage(usersPage - 1)}
                      >
                        Previous
                      </button>
                      <button
                        disabled={usersPage >= usersTotalPages - 1}
                        onClick={() => setUsersPage(usersPage + 1)}
                      >
                        Next
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* Usage History Tab */}
        {tab === 'history' && (
          <>
            <div className="ai-usage-filters">
              <input
                type="text"
                placeholder="Search by user name or email..."
                value={historySearch}
                onChange={(e) => {
                  setHistorySearch(e.target.value);
                  setHistoryPage(0);
                }}
                className="ai-usage-filter-input"
              />
              <select
                value={historyType}
                onChange={(e) => {
                  setHistoryType(e.target.value);
                  setHistoryPage(0);
                }}
                className="ai-usage-filter-select"
              >
                <option value="">All Types</option>
                <option value="study_guide">Study Guide</option>
                <option value="quiz">Quiz</option>
                <option value="flashcards">Flashcards</option>
              </select>
              <select
                value={historyEntryType}
                onChange={(e) => {
                  setHistoryEntryType(e.target.value);
                  setHistoryPage(0);
                }}
                className="ai-usage-filter-select"
              >
                <option value="">All</option>
                <option value="original">Original</option>
                <option value="regeneration">Regenerations</option>
              </select>
              <input
                type="date"
                value={historyDateFrom}
                onChange={(e) => {
                  setHistoryDateFrom(e.target.value);
                  setHistoryPage(0);
                }}
                className="ai-usage-filter-date"
                placeholder="From"
                title="From date"
              />
              <input
                type="date"
                value={historyDateTo}
                onChange={(e) => {
                  setHistoryDateTo(e.target.value);
                  setHistoryPage(0);
                }}
                className="ai-usage-filter-date"
                placeholder="To"
                title="To date"
              />
            </div>

            {historyLoading ? (
              <ListSkeleton rows={8} />
            ) : (
              <>
                <table className="ai-usage-table">
                  <thead>
                    <tr>
                      <th>User</th>
                      <th>Type</th>
                      <th>Material</th>
                      <th>Tokens</th>
                      <th>Cost (USD)</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((entry) => (
                      <tr key={entry.id}>
                        <td>
                          <div>{entry.user_name}</div>
                          <div style={{ fontSize: 11, color: 'var(--color-ink-muted)' }}>
                            {entry.user_email}
                          </div>
                        </td>
                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                            <span className={`ai-usage-type-badge ${entry.generation_type}`}>
                              {formatGenerationType(entry.generation_type)}
                            </span>
                            {entry.is_regeneration && (
                              <span className="ai-usage-regen-badge">Regen</span>
                            )}
                          </div>
                        </td>
                        <td className="ai-usage-reason" title={entry.course_material_title || ''}>
                          {entry.course_material_title || '--'}
                        </td>
                        <td style={{ fontSize: 12 }}>
                          {entry.total_tokens != null ? entry.total_tokens.toLocaleString() : '--'}
                        </td>
                        <td style={{ fontSize: 12 }}>
                          {entry.estimated_cost_usd != null ? `$${entry.estimated_cost_usd.toFixed(5)}` : '--'}
                        </td>
                        <td className="ai-usage-date">{formatDate(entry.created_at)}</td>
                      </tr>
                    ))}
                    {history.length === 0 && (
                      <tr>
                        <td colSpan={6} className="ai-usage-empty">
                          No usage history found
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>

                {historyTotalPages > 1 && (
                  <div className="ai-usage-pagination">
                    <span>
                      Showing {historyPage * PAGE_SIZE + 1}--
                      {Math.min((historyPage + 1) * PAGE_SIZE, historyTotal)} of {historyTotal}
                    </span>
                    <div className="ai-usage-pagination-btns">
                      <button
                        disabled={historyPage === 0}
                        onClick={() => setHistoryPage(historyPage - 1)}
                      >
                        Previous
                      </button>
                      <button
                        disabled={historyPage >= historyTotalPages - 1}
                        onClick={() => setHistoryPage(historyPage + 1)}
                      >
                        Next
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* Requests Tab */}
        {tab === 'requests' && (
          <>
            <div className="ai-usage-filters">
              <select
                value={requestsStatus}
                onChange={(e) => {
                  setRequestsStatus(e.target.value);
                  setRequestsPage(0);
                }}
                className="ai-usage-filter-select"
              >
                <option value="all">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="declined">Declined</option>
              </select>
            </div>

            {requestsLoading ? (
              <ListSkeleton rows={5} />
            ) : (
              <>
                <table className="ai-usage-table">
                  <thead>
                    <tr>
                      <th>User</th>
                      <th>Requested</th>
                      <th>Reason</th>
                      <th>Status</th>
                      <th>Date</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requests.map((req) => (
                      <tr key={req.id}>
                        <td>
                          <div>{req.user_name}</div>
                          <div style={{ fontSize: 11, color: 'var(--color-ink-muted)' }}>
                            {req.user_email}
                          </div>
                        </td>
                        <td>{req.requested_amount}</td>
                        <td className="ai-usage-reason" title={req.reason}>
                          {req.reason}
                        </td>
                        <td>
                          <span className={getStatusBadgeClass(req.status)}>
                            {req.status}
                          </span>
                        </td>
                        <td className="ai-usage-date">{formatDate(req.created_at)}</td>
                        <td>
                          {req.status === 'pending' ? (
                            <div className="ai-usage-actions">
                              <input
                                type="number"
                                className="ai-usage-approve-input"
                                value={approveAmounts[req.id] ?? req.requested_amount}
                                min={1}
                                onChange={(e) =>
                                  setApproveAmounts((prev) => ({
                                    ...prev,
                                    [req.id]: parseInt(e.target.value, 10) || 0,
                                  }))
                                }
                              />
                              <button
                                className="ai-usage-btn approve"
                                disabled={!!actionLoading[`approve-${req.id}`]}
                                onClick={() => handleApprove(req)}
                              >
                                Approve
                              </button>
                              <button
                                className="ai-usage-btn decline"
                                disabled={!!actionLoading[`decline-${req.id}`]}
                                onClick={() => handleDecline(req)}
                              >
                                Decline
                              </button>
                            </div>
                          ) : (
                            <span className="ai-usage-resolved-info">
                              {req.status === 'approved' && req.approved_amount != null
                                ? `+${req.approved_amount} credits`
                                : '--'}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                    {requests.length === 0 && (
                      <tr>
                        <td colSpan={6} className="ai-usage-empty">
                          No requests found
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>

                {requestsTotalPages > 1 && (
                  <div className="ai-usage-pagination">
                    <span>
                      Showing {requestsPage * PAGE_SIZE + 1}--
                      {Math.min((requestsPage + 1) * PAGE_SIZE, requestsTotal)} of{' '}
                      {requestsTotal}
                    </span>
                    <div className="ai-usage-pagination-btns">
                      <button
                        disabled={requestsPage === 0}
                        onClick={() => setRequestsPage(requestsPage - 1)}
                      >
                        Previous
                      </button>
                      <button
                        disabled={requestsPage >= requestsTotalPages - 1}
                        onClick={() => setRequestsPage(requestsPage + 1)}
                      >
                        Next
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* Activity Log Tab */}
        {tab === 'audit' && (
          <>
            {auditLoading ? (
              <ListSkeleton rows={8} />
            ) : (
              <>
                <table className="ai-usage-table">
                  <thead>
                    <tr>
                      <th>Admin</th>
                      <th>Action</th>
                      <th>Target User</th>
                      <th>Details</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditItems.map((entry) => (
                      <tr key={entry.id}>
                        <td>{entry.admin_name}</td>
                        <td>
                          <span className={`ai-usage-type-badge ${entry.action_type}`}>
                            {entry.action_type.replace(/_/g, ' ')}
                          </span>
                        </td>
                        <td>{entry.target_user_name || '--'}</td>
                        <td className="ai-usage-reason" title={entry.details || ''}>
                          {entry.details || '--'}
                        </td>
                        <td className="ai-usage-date">
                          {entry.created_at ? formatDate(entry.created_at) : '--'}
                        </td>
                      </tr>
                    ))}
                    {auditItems.length === 0 && (
                      <tr>
                        <td colSpan={5} className="ai-usage-empty">
                          No activity log entries found
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>

                {auditTotalPages > 1 && (
                  <div className="ai-usage-pagination">
                    <span>
                      Showing {auditPage * PAGE_SIZE + 1}--
                      {Math.min((auditPage + 1) * PAGE_SIZE, auditTotal)} of {auditTotal}
                    </span>
                    <div className="ai-usage-pagination-btns">
                      <button
                        disabled={auditPage === 0}
                        onClick={() => setAuditPage(auditPage - 1)}
                      >
                        Previous
                      </button>
                      <button
                        disabled={auditPage >= auditTotalPages - 1}
                        onClick={() => setAuditPage(auditPage + 1)}
                      >
                        Next
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* Adjust Limit Modal */}
        {limitModal && (
          <div className="ai-usage-modal-overlay" onClick={() => setLimitModal(null)}>
            <div className="ai-usage-modal" onClick={(e) => e.stopPropagation()}>
              <h3>Adjust AI Limit</h3>
              <p style={{ fontSize: 13, color: 'var(--color-ink-muted)', margin: '0 0 16px' }}>
                Set a new AI usage limit for <strong>{limitModal.user.full_name}</strong>
              </p>
              <label htmlFor="limit-input">New Limit</label>
              <input
                id="limit-input"
                type="number"
                min={0}
                value={limitModal.value}
                onChange={(e) =>
                  setLimitModal({ ...limitModal, value: parseInt(e.target.value, 10) || 0 })
                }
              />
              <div className="ai-usage-modal-actions">
                <button className="ai-usage-modal-btn" onClick={() => setLimitModal(null)}>
                  Cancel
                </button>
                <button
                  className="ai-usage-modal-btn primary"
                  disabled={!!actionLoading[`limit-${limitModal.user.id}`]}
                  onClick={handleSetLimit}
                >
                  Save
                </button>
              </div>
            </div>
          </div>
        )}

        {bulkLimitModal && (
          <div className="ai-usage-modal-overlay" onClick={() => setBulkLimitModal(null)}>
            <div className="ai-usage-modal" onClick={(e) => e.stopPropagation()}>
              <h3>Set Limit for All Users</h3>
              <p style={{ fontSize: 13, color: 'var(--color-ink-muted)', margin: '0 0 16px' }}>
                This will update the AI credit limit for <strong>every user</strong> on the platform.
              </p>
              <label htmlFor="bulk-limit-input">New Limit</label>
              <input
                id="bulk-limit-input"
                type="number"
                min={0}
                value={bulkLimitModal.value}
                onChange={(e) =>
                  setBulkLimitModal({ ...bulkLimitModal, value: parseInt(e.target.value, 10) || 0 })
                }
              />
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={bulkLimitModal.resetCounts}
                  onChange={(e) =>
                    setBulkLimitModal({ ...bulkLimitModal, resetCounts: e.target.checked })
                  }
                />
                Also reset all usage counts to 0
              </label>
              <div className="ai-usage-modal-actions">
                <button className="ai-usage-modal-btn" onClick={() => setBulkLimitModal(null)}>
                  Cancel
                </button>
                <button
                  className="ai-usage-modal-btn primary"
                  disabled={!!actionLoading['bulk-limit']}
                  onClick={handleBulkSetLimit}
                >
                  {actionLoading['bulk-limit'] ? 'Applying...' : 'Apply to All'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
