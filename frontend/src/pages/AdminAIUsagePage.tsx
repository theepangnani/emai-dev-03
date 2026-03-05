import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { ListSkeleton } from '../components/Skeleton';
import { PageNav } from '../components/PageNav';
import { useDebounce } from '../utils/useDebounce';
import {
  adminAIUsageApi,
  type AIUsageUser,
  type AIUsageSummary,
  type AILimitRequest,
} from '../api/adminAIUsage';
import './AdminAIUsagePage.css';

const PAGE_SIZE = 25;

type Tab = 'users' | 'requests';

export function AdminAIUsagePage() {
  const [tab, setTab] = useState<Tab>('users');

  // Summary
  const [summary, setSummary] = useState<AIUsageSummary | null>(null);

  // Users
  const [users, setUsers] = useState<AIUsageUser[]>([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersPage, setUsersPage] = useState(0);
  const [search, setSearch] = useState('');
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc');
  const [usersLoading, setUsersLoading] = useState(true);
  const debouncedSearch = useDebounce(search, 400);

  // Requests
  const [requests, setRequests] = useState<AILimitRequest[]>([]);
  const [requestsTotal, setRequestsTotal] = useState(0);
  const [requestsPage, setRequestsPage] = useState(0);
  const [requestsLoading, setRequestsLoading] = useState(false);

  // Modals / inline state
  const [limitModal, setLimitModal] = useState<{ user: AIUsageUser; value: number } | null>(null);
  const [confirmReset, setConfirmReset] = useState<number | null>(null);
  const [approveAmounts, setApproveAmounts] = useState<Record<number, number>>({});
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

  // Load summary + request count on mount
  useEffect(() => {
    adminAIUsageApi.getSummary().then(setSummary).catch(() => {});
    // Pre-fetch pending request count for badge
    adminAIUsageApi.listRequests({ status: 'pending', skip: 0, limit: 1 })
      .then((data) => setRequestsTotal(data.total))
      .catch(() => {});
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

  // Load requests
  const loadRequests = useCallback(async () => {
    setRequestsLoading(true);
    try {
      const data = await adminAIUsageApi.listRequests({
        status: 'pending',
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
  }, [requestsPage]);

  useEffect(() => {
    if (tab === 'requests') loadRequests();
  }, [tab, loadRequests]);

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

  const usersTotalPages = Math.ceil(usersTotal / PAGE_SIZE);
  const requestsTotalPages = Math.ceil(requestsTotal / PAGE_SIZE);

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
            Users
          </button>
          <button
            className={`ai-usage-tab${tab === 'requests' ? ' active' : ''}`}
            onClick={() => setTab('requests')}
          >
            Pending Requests
            {requestsTotal > 0 && tab !== 'requests' && (
              <span style={{ marginLeft: 6, fontWeight: 700 }}>({requestsTotal})</span>
            )}
          </button>
        </div>

        {/* Users Tab */}
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

        {/* Requests Tab */}
        {tab === 'requests' && (
          <>
            {requestsLoading ? (
              <ListSkeleton rows={5} />
            ) : (
              <>
                <table className="ai-usage-table">
                  <thead>
                    <tr>
                      <th>User</th>
                      <th>Requested Amount</th>
                      <th>Reason</th>
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
                        <td className="ai-usage-date">{formatDate(req.created_at)}</td>
                        <td>
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
                        </td>
                      </tr>
                    ))}
                    {requests.length === 0 && (
                      <tr>
                        <td colSpan={5} className="ai-usage-empty">
                          No pending requests
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
      </div>
    </DashboardLayout>
  );
}
