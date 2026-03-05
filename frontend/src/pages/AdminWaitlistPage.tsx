import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import { ListSkeleton } from '../components/Skeleton';
import { adminWaitlistApi } from '../api/adminWaitlist';
import type { WaitlistEntry, WaitlistStats } from '../api/adminWaitlist';
import { useDebounce } from '../utils/useDebounce';
import './AdminWaitlistPage.css';

const PAGE_SIZE = 20;

export function AdminWaitlistPage() {
  const navigate = useNavigate();

  // Stats
  const [stats, setStats] = useState<WaitlistStats | null>(null);

  // List
  const [entries, setEntries] = useState<WaitlistEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search, 400);
  const [page, setPage] = useState(0);

  // Bulk selection
  const [selected, setSelected] = useState<Set<number>>(new Set());

  // Action loading
  const [actionLoading, setActionLoading] = useState<Record<number, boolean>>({});

  // Notes editing
  const [editingNotes, setEditingNotes] = useState<number | null>(null);
  const [notesValue, setNotesValue] = useState('');
  const notesInputRef = useRef<HTMLInputElement>(null);

  // Bulk action loading
  const [bulkLoading, setBulkLoading] = useState(false);

  const loadStats = useCallback(async () => {
    try {
      const data = await adminWaitlistApi.stats();
      setStats(data);
    } catch {
      // Failed to load stats
    }
  }, []);

  const loadEntries = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminWaitlistApi.list({
        status: statusFilter || undefined,
        search: debouncedSearch || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setEntries(data.items);
      setTotal(data.total);
    } catch {
      // Failed to load entries
    } finally {
      setLoading(false);
    }
  }, [statusFilter, debouncedSearch, page]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    loadEntries();
  }, [loadEntries]);

  // Clear selection when filters/page change
  useEffect(() => {
    setSelected(new Set());
  }, [statusFilter, debouncedSearch, page]);

  // Focus notes input when editing starts
  useEffect(() => {
    if (editingNotes !== null && notesInputRef.current) {
      notesInputRef.current.focus();
    }
  }, [editingNotes]);

  const handleApprove = async (id: number) => {
    setActionLoading(prev => ({ ...prev, [id]: true }));
    try {
      await adminWaitlistApi.approve(id);
      loadEntries();
      loadStats();
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: false }));
    }
  };

  const handleDecline = async (id: number) => {
    setActionLoading(prev => ({ ...prev, [id]: true }));
    try {
      await adminWaitlistApi.decline(id);
      loadEntries();
      loadStats();
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: false }));
    }
  };

  const handleRemind = async (id: number) => {
    setActionLoading(prev => ({ ...prev, [id]: true }));
    try {
      await adminWaitlistApi.remind(id);
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: false }));
    }
  };

  const handleSaveNotes = async (id: number) => {
    setActionLoading(prev => ({ ...prev, [id]: true }));
    try {
      await adminWaitlistApi.updateNotes(id, notesValue);
      setEntries(prev =>
        prev.map(e => (e.id === id ? { ...e, admin_notes: notesValue || null } : e))
      );
    } finally {
      setEditingNotes(null);
      setActionLoading(prev => ({ ...prev, [id]: false }));
    }
  };

  const handleBulkApprove = async () => {
    const pendingIds = Array.from(selected).filter(id =>
      entries.find(e => e.id === id && e.status === 'pending')
    );
    if (pendingIds.length === 0) return;

    setBulkLoading(true);
    try {
      await adminWaitlistApi.bulkApprove(pendingIds);
      setSelected(new Set());
      loadEntries();
      loadStats();
    } finally {
      setBulkLoading(false);
    }
  };

  const toggleSelect = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selected.size === entries.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(entries.map(e => e.id)));
    }
  };

  const selectedPendingCount = Array.from(selected).filter(id =>
    entries.find(e => e.id === id && e.status === 'pending')
  ).length;

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <DashboardLayout welcomeSubtitle="Manage waitlist signups">
      <div className="admin-waitlist-page">
        <PageNav
          items={[
            { label: 'Home', to: '/dashboard' },
            { label: 'Admin', to: '/dashboard' },
            { label: 'Waitlist' },
          ]}
        />

        <div className="admin-waitlist-header">
          <h1>Waitlist Management</h1>
        </div>

        {/* Stats Bar */}
        <div className="admin-waitlist-stats">
          <div className="admin-waitlist-stat-card">
            <h4>Total</h4>
            <div className="stat-value">{stats?.total ?? '--'}</div>
          </div>
          <div className="admin-waitlist-stat-card pending">
            <h4>Pending</h4>
            <div className="stat-value">{stats?.pending ?? '--'}</div>
          </div>
          <div className="admin-waitlist-stat-card approved">
            <h4>Approved</h4>
            <div className="stat-value">{stats?.approved ?? '--'}</div>
          </div>
          <div className="admin-waitlist-stat-card registered">
            <h4>Registered</h4>
            <div className="stat-value">{stats?.registered ?? '--'}</div>
          </div>
          <div className="admin-waitlist-stat-card declined">
            <h4>Declined</h4>
            <div className="stat-value">{stats?.declined ?? '--'}</div>
          </div>
        </div>

        {/* Filters */}
        <div className="admin-waitlist-filters">
          <label htmlFor="waitlist-status-filter" className="sr-only">
            Filter by status
          </label>
          <select
            id="waitlist-status-filter"
            value={statusFilter}
            onChange={e => {
              setStatusFilter(e.target.value);
              setPage(0);
            }}
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="registered">Registered</option>
            <option value="declined">Declined</option>
          </select>
          <label htmlFor="waitlist-search" className="sr-only">
            Search by name or email
          </label>
          <input
            id="waitlist-search"
            type="text"
            placeholder="Search by name or email..."
            value={search}
            onChange={e => {
              setSearch(e.target.value);
              setPage(0);
            }}
          />
        </div>

        {/* Bulk Action Bar */}
        {selected.size > 0 && (
          <div className="admin-waitlist-bulk-bar">
            <span>
              {selected.size} selected
              {selectedPendingCount > 0 && ` (${selectedPendingCount} pending)`}
            </span>
            {selectedPendingCount > 0 && (
              <button
                className="btn btn-sm btn-success"
                onClick={handleBulkApprove}
                disabled={bulkLoading}
              >
                {bulkLoading ? 'Approving...' : `Approve Selected (${selectedPendingCount})`}
              </button>
            )}
          </div>
        )}

        {/* Table */}
        {loading ? (
          <ListSkeleton rows={8} />
        ) : entries.length === 0 ? (
          <div className="admin-waitlist-empty">
            No waitlist entries found.
          </div>
        ) : (
          <>
            <table className="admin-waitlist-table">
              <thead>
                <tr>
                  <th className="col-checkbox">
                    <input
                      type="checkbox"
                      checked={selected.size === entries.length && entries.length > 0}
                      onChange={toggleSelectAll}
                      aria-label="Select all"
                    />
                  </th>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Roles</th>
                  <th>Status</th>
                  <th>Date Joined</th>
                  <th>Date Approved</th>
                  <th>Notes</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {entries.map(entry => (
                  <tr key={entry.id}>
                    <td className="col-checkbox">
                      <input
                        type="checkbox"
                        checked={selected.has(entry.id)}
                        onChange={() => toggleSelect(entry.id)}
                        aria-label={`Select ${entry.full_name}`}
                      />
                    </td>
                    <td>{entry.full_name}</td>
                    <td>{entry.email}</td>
                    <td>
                      <div className="admin-waitlist-roles">
                        {entry.roles.map(role => (
                          <span
                            key={role}
                            className={`waitlist-role-badge ${role}`}
                          >
                            {role}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <span className={`waitlist-status-badge ${entry.status}`}>
                        {entry.status}
                      </span>
                    </td>
                    <td>
                      {new Date(entry.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      {entry.approved_at
                        ? new Date(entry.approved_at).toLocaleDateString()
                        : '--'}
                    </td>
                    <td>
                      <div className="admin-waitlist-notes">
                        {editingNotes === entry.id ? (
                          <input
                            ref={notesInputRef}
                            className="admin-waitlist-notes-input"
                            type="text"
                            value={notesValue}
                            onChange={e => setNotesValue(e.target.value)}
                            onBlur={() => handleSaveNotes(entry.id)}
                            onKeyDown={e => {
                              if (e.key === 'Enter') handleSaveNotes(entry.id);
                              if (e.key === 'Escape') setEditingNotes(null);
                            }}
                            disabled={actionLoading[entry.id]}
                          />
                        ) : (
                          <span
                            className="admin-waitlist-notes-text"
                            onClick={() => {
                              setEditingNotes(entry.id);
                              setNotesValue(entry.admin_notes || '');
                            }}
                            title="Click to edit"
                          >
                            {entry.admin_notes || 'Add note...'}
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <div className="admin-waitlist-row-actions">
                        {entry.status === 'pending' && (
                          <>
                            <button
                              className="btn btn-sm btn-success"
                              onClick={() => handleApprove(entry.id)}
                              disabled={actionLoading[entry.id]}
                            >
                              Approve
                            </button>
                            <button
                              className="btn btn-sm btn-danger"
                              onClick={() => handleDecline(entry.id)}
                              disabled={actionLoading[entry.id]}
                            >
                              Decline
                            </button>
                          </>
                        )}
                        {entry.status === 'approved' && (
                          <button
                            className="btn btn-sm btn-secondary"
                            onClick={() => handleRemind(entry.id)}
                            disabled={actionLoading[entry.id]}
                          >
                            Send Reminder
                          </button>
                        )}
                        {entry.status === 'registered' && (
                          <button
                            className="btn btn-sm btn-secondary"
                            onClick={() => navigate(`/admin/users?search=${encodeURIComponent(entry.email)}`)}
                          >
                            View Profile
                          </button>
                        )}
                        {entry.status === 'declined' && (
                          <button
                            className="btn btn-sm btn-primary"
                            onClick={() => handleApprove(entry.id)}
                            disabled={actionLoading[entry.id]}
                          >
                            Re-approve
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="admin-waitlist-pagination">
                <span>
                  Showing {page * PAGE_SIZE + 1}&ndash;
                  {Math.min((page + 1) * PAGE_SIZE, total)} of {total}
                </span>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    disabled={page === 0}
                    onClick={() => setPage(page - 1)}
                  >
                    Previous
                  </button>
                  <button
                    disabled={page >= totalPages - 1}
                    onClick={() => setPage(page + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
