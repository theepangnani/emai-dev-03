import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { adminApi } from '../api/client';
import type { AdminStats, AdminUserItem, BroadcastItem } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { useDebounce } from '../utils/useDebounce';
import { ListSkeleton } from '../components/Skeleton';
import './AdminDashboard.css';

const PAGE_SIZE = 10;
const ALL_ROLES = ['parent', 'student', 'teacher', 'admin'] as const;

export function AdminDashboard() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [totalUsers, setTotalUsers] = useState(0);
  const [roleFilter, setRoleFilter] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const debouncedSearch = useDebounce(search, 400);

  // Role management modal
  const [selectedUser, setSelectedUser] = useState<AdminUserItem | null>(null);
  const [roleLoading, setRoleLoading] = useState<Record<string, boolean>>({});
  const [roleError, setRoleError] = useState('');

  // Broadcast state
  const [showBroadcastModal, setShowBroadcastModal] = useState(false);
  const [broadcastSubject, setBroadcastSubject] = useState('');
  const [broadcastBody, setBroadcastBody] = useState('');
  const [broadcastSending, setBroadcastSending] = useState(false);
  const [broadcastResult, setBroadcastResult] = useState('');
  const [broadcasts, setBroadcasts] = useState<BroadcastItem[]>([]);
  const [showBroadcastHistory, setShowBroadcastHistory] = useState(false);

  // Individual message state
  const [messageUser, setMessageUser] = useState<AdminUserItem | null>(null);
  const [msgSubject, setMsgSubject] = useState('');
  const [msgBody, setMsgBody] = useState('');
  const [msgSending, setMsgSending] = useState(false);
  const [msgResult, setMsgResult] = useState('');

  useEffect(() => {
    loadStats();
  }, []);

  useEffect(() => {
    loadUsers();
  }, [roleFilter, debouncedSearch, page]);

  const loadStats = async () => {
    try {
      const data = await adminApi.getStats();
      setStats(data);
    } catch {
      // Failed to load stats
    }
  };

  const loadUsers = async () => {
    setLoading(true);
    try {
      const data = await adminApi.getUsers({
        role: roleFilter || undefined,
        search: debouncedSearch || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setUsers(data.users);
      setTotalUsers(data.total);
    } catch {
      // Failed to load users
    } finally {
      setLoading(false);
    }
  };

  const handleToggleRole = async (role: string) => {
    if (!selectedUser) return;
    const hasRole = selectedUser.roles.includes(role);

    if (hasRole && selectedUser.roles.length <= 1) {
      setRoleError('Cannot remove the last role');
      return;
    }

    setRoleLoading(prev => ({ ...prev, [role]: true }));
    setRoleError('');

    try {
      const updated = hasRole
        ? await adminApi.removeRole(selectedUser.id, role)
        : await adminApi.addRole(selectedUser.id, role);

      setSelectedUser(updated);
      setUsers(prev => prev.map(u => u.id === updated.id ? updated : u));
    } catch (err: any) {
      setRoleError(err.response?.data?.detail || 'Failed to update role');
    } finally {
      setRoleLoading(prev => ({ ...prev, [role]: false }));
    }
  };

  const handleSendBroadcast = async () => {
    if (!broadcastSubject.trim() || !broadcastBody.trim()) return;
    setBroadcastSending(true);
    setBroadcastResult('');
    try {
      const result = await adminApi.sendBroadcast(broadcastSubject, broadcastBody);
      setBroadcastResult(`Broadcast sent to ${result.recipient_count} users. ${result.email_count} emails delivered.`);
      setBroadcastSubject('');
      setBroadcastBody('');
      // Refresh broadcast history if visible
      if (showBroadcastHistory) {
        loadBroadcasts();
      }
    } catch (err: any) {
      setBroadcastResult(err.response?.data?.detail || 'Failed to send broadcast');
    } finally {
      setBroadcastSending(false);
    }
  };

  const loadBroadcasts = async () => {
    try {
      const data = await adminApi.getBroadcasts();
      setBroadcasts(data);
    } catch {
      // Failed to load broadcasts
    }
  };

  const handleToggleBroadcastHistory = () => {
    if (!showBroadcastHistory) {
      loadBroadcasts();
    }
    setShowBroadcastHistory(!showBroadcastHistory);
  };

  const handleSendMessage = async () => {
    if (!messageUser || !msgSubject.trim() || !msgBody.trim()) return;
    setMsgSending(true);
    setMsgResult('');
    try {
      const result = await adminApi.sendMessage(messageUser.id, msgSubject, msgBody);
      setMsgResult(
        result.email_sent
          ? 'Message sent and email delivered.'
          : 'Message sent (no email — user has no email address).'
      );
      setMsgSubject('');
      setMsgBody('');
    } catch (err: any) {
      setMsgResult(err.response?.data?.detail || 'Failed to send message');
    } finally {
      setMsgSending(false);
    }
  };

  const totalPages = Math.ceil(totalUsers / PAGE_SIZE);

  return (
    <DashboardLayout welcomeSubtitle="Platform administration">
      <div className="dashboard-grid">
        <div className="dashboard-card">
          <div className="card-icon">&#128101;</div>
          <h3>Total Users</h3>
          <p className="card-value">{stats?.total_users ?? '—'}</p>
          <p className="card-label">Registered users</p>
        </div>

        <div className="dashboard-card">
          <div className="card-icon">&#127891;</div>
          <h3>Students</h3>
          <p className="card-value">{stats?.users_by_role?.student ?? 0}</p>
          <p className="card-label">Active students</p>
        </div>

        <div className="dashboard-card">
          <div className="card-icon">&#128104;&#8205;&#127979;</div>
          <h3>Teachers</h3>
          <p className="card-value">{stats?.users_by_role?.teacher ?? 0}</p>
          <p className="card-label">Active teachers</p>
        </div>

        <div className="dashboard-card">
          <div className="card-icon">&#128218;</div>
          <h3>Courses</h3>
          <p className="card-value">{stats?.total_courses ?? 0}</p>
          <p className="card-label">Total courses</p>
        </div>
      </div>

      <div className="dashboard-sections">
        <section className="section" style={{ marginBottom: '16px', display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
          <Link to="/admin/audit-log" className="admin-audit-link">
            View Audit Log &rarr;
          </Link>
          <Link to="/admin/inspiration" className="admin-audit-link">
            Manage Inspirational Messages &rarr;
          </Link>
          <button
            className="admin-audit-link"
            onClick={() => { setShowBroadcastModal(true); setBroadcastResult(''); }}
            style={{ cursor: 'pointer', background: 'none' }}
          >
            Send Broadcast &rarr;
          </button>
        </section>

        {/* Broadcast History */}
        <section className="section" style={{ marginBottom: '16px' }}>
          <button
            className="admin-toggle-history"
            onClick={handleToggleBroadcastHistory}
          >
            {showBroadcastHistory ? 'Hide' : 'Show'} Broadcast History
          </button>
          {showBroadcastHistory && (
            <div className="admin-broadcast-history">
              {broadcasts.length === 0 ? (
                <p style={{ color: '#999', padding: '12px 0' }}>No broadcasts sent yet.</p>
              ) : (
                <table className="admin-users-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Subject</th>
                      <th>Recipients</th>
                      <th>Emails Sent</th>
                    </tr>
                  </thead>
                  <tbody>
                    {broadcasts.map(b => (
                      <tr key={b.id}>
                        <td>{new Date(b.created_at).toLocaleString()}</td>
                        <td>{b.subject}</td>
                        <td>{b.recipient_count}</td>
                        <td>{b.email_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </section>

        <section className="section admin-users-section">
          <h3>User Management</h3>

          <div className="admin-filters">
            <select
              value={roleFilter}
              onChange={(e) => { setRoleFilter(e.target.value); setPage(0); }}
            >
              <option value="">All Roles</option>
              <option value="student">Student</option>
              <option value="parent">Parent</option>
              <option value="teacher">Teacher</option>
              <option value="admin">Admin</option>
            </select>
            <input
              type="text"
              placeholder="Search by name or email..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            />
          </div>

          {loading ? (
            <ListSkeleton rows={5} />
          ) : (
            <>
              <table className="admin-users-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Roles</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td>{user.full_name}</td>
                      <td>{user.email ?? '—'}</td>
                      <td>
                        <div className="admin-roles-cell">
                          {(user.roles?.length ? user.roles : [user.role]).map(r => (
                            <span key={r} className={`role-badge-small ${r}`}>{r}</span>
                          ))}
                        </div>
                      </td>
                      <td>
                        <span className={`status-dot ${user.is_active ? 'active' : 'inactive'}`} />
                        {user.is_active ? 'Active' : 'Inactive'}
                      </td>
                      <td>{new Date(user.created_at).toLocaleDateString()}</td>
                      <td>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            className="admin-manage-btn"
                            onClick={() => { setSelectedUser(user); setRoleError(''); }}
                          >
                            Roles
                          </button>
                          <button
                            className="admin-manage-btn admin-msg-btn"
                            onClick={() => { setMessageUser(user); setMsgResult(''); setMsgSubject(''); setMsgBody(''); }}
                          >
                            Message
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {users.length === 0 && (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '24px', color: '#999' }}>
                        No users found
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>

              {totalPages > 1 && (
                <div className="admin-pagination">
                  <span>
                    Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, totalUsers)} of {totalUsers}
                  </span>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button disabled={page === 0} onClick={() => setPage(page - 1)}>
                      Previous
                    </button>
                    <button disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </section>
      </div>

      {/* Role Management Modal */}
      {selectedUser && (
        <div className="modal-overlay" onClick={() => setSelectedUser(null)}>
          <div className="modal admin-role-modal" onClick={(e) => e.stopPropagation()}>
            <h2>Manage Roles</h2>
            <div className="admin-role-user-info">
              <span className="admin-role-user-name">{selectedUser.full_name}</span>
              <span className="admin-role-user-email">{selectedUser.email ?? 'No email'}</span>
            </div>

            <div className="admin-role-list">
              {ALL_ROLES.map(role => {
                const hasRole = selectedUser.roles.includes(role);
                const isLoading = roleLoading[role];
                const isLastRole = hasRole && selectedUser.roles.length <= 1;

                return (
                  <label
                    key={role}
                    className={`admin-role-checkbox-row${isLoading ? ' loading' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={hasRole}
                      disabled={isLoading || isLastRole}
                      onChange={() => handleToggleRole(role)}
                    />
                    <span className={`role-badge-small ${role}`}>{role}</span>
                    {isLoading && <span className="admin-role-spinner" />}
                    {isLastRole && <span className="admin-role-hint">Last role</span>}
                  </label>
                );
              })}
            </div>

            {roleError && <p className="admin-role-error">{roleError}</p>}

            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setSelectedUser(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Broadcast Modal */}
      {showBroadcastModal && (
        <div className="modal-overlay" onClick={() => { if (!broadcastSending) { setShowBroadcastModal(false); setBroadcastResult(''); } }}>
          <div className="modal admin-message-modal" onClick={(e) => e.stopPropagation()}>
            {broadcastResult && !broadcastResult.startsWith('Failed') ? (
              <>
                <div className="admin-msg-sent-confirmation">
                  <span className="admin-msg-sent-icon">&#10003;</span>
                  <h3>Broadcast Sent</h3>
                  <p>{broadcastResult}</p>
                </div>
                <div className="modal-actions" style={{ justifyContent: 'center' }}>
                  <button className="submit-btn" onClick={() => { setShowBroadcastModal(false); setBroadcastResult(''); }}>
                    OK
                  </button>
                </div>
              </>
            ) : (
              <>
                <h2>Send Broadcast</h2>
                <p className="admin-msg-subtitle">
                  This message will be sent to all {stats?.total_users ?? 0} active users as an in-app notification and email.
                </p>
                <div className="admin-msg-form">
                  <input
                    type="text"
                    placeholder="Subject"
                    value={broadcastSubject}
                    onChange={(e) => setBroadcastSubject(e.target.value)}
                    className="admin-msg-input"
                  />
                  <textarea
                    placeholder="Message body..."
                    value={broadcastBody}
                    onChange={(e) => setBroadcastBody(e.target.value)}
                    className="admin-msg-textarea"
                    rows={6}
                  />
                </div>
                {broadcastResult && (
                  <p className="admin-msg-result error">{broadcastResult}</p>
                )}
                <div className="modal-actions">
                  <button className="cancel-btn" onClick={() => { setShowBroadcastModal(false); setBroadcastResult(''); }}>Cancel</button>
                  <button
                    className="submit-btn"
                    disabled={broadcastSending || !broadcastSubject.trim() || !broadcastBody.trim()}
                    onClick={handleSendBroadcast}
                  >
                    {broadcastSending ? 'Sending...' : 'Send to All Users'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Individual Message Modal */}
      {messageUser && (
        <div className="modal-overlay" onClick={() => { if (!msgSending) { setMessageUser(null); setMsgResult(''); } }}>
          <div className="modal admin-message-modal" onClick={(e) => e.stopPropagation()}>
            {msgResult && !msgResult.startsWith('Failed') ? (
              <>
                <div className="admin-msg-sent-confirmation">
                  <span className="admin-msg-sent-icon">&#10003;</span>
                  <h3>Message Sent</h3>
                  <p>{msgResult}</p>
                </div>
                <div className="modal-actions" style={{ justifyContent: 'center' }}>
                  <button className="submit-btn" onClick={() => { setMessageUser(null); setMsgResult(''); }}>
                    OK
                  </button>
                </div>
              </>
            ) : (
              <>
                <h2>Send Message</h2>
                <div className="admin-role-user-info">
                  <span className="admin-role-user-name">{messageUser.full_name}</span>
                  <span className="admin-role-user-email">{messageUser.email ?? 'No email'}</span>
                </div>
                <div className="admin-msg-form">
                  <input
                    type="text"
                    placeholder="Subject"
                    value={msgSubject}
                    onChange={(e) => setMsgSubject(e.target.value)}
                    className="admin-msg-input"
                  />
                  <textarea
                    placeholder="Message body..."
                    value={msgBody}
                    onChange={(e) => setMsgBody(e.target.value)}
                    className="admin-msg-textarea"
                    rows={6}
                  />
                </div>
                {msgResult && (
                  <p className="admin-msg-result error">{msgResult}</p>
                )}
                <div className="modal-actions">
                  <button className="cancel-btn" onClick={() => { setMessageUser(null); setMsgResult(''); }}>Cancel</button>
                  <button
                    className="submit-btn"
                    disabled={msgSending || !msgSubject.trim() || !msgBody.trim()}
                    onClick={handleSendMessage}
                  >
                    {msgSending ? 'Sending...' : 'Send Message'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
