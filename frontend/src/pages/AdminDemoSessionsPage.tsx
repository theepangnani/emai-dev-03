import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import { ListSkeleton } from '../components/Skeleton';
import { useDebounce } from '../utils/useDebounce';
import { useToast } from '../components/Toast';
import { adminApi, type DemoSessionItem, type DemoSessionStatusCounts } from '../api/admin';
import './AdminWaitlistPage.css';
import './AdminDemoSessionsPage.css';

const PAGE_SIZE = 50;
type StatusFilter = '' | 'pending' | 'approved' | 'rejected' | 'blocklisted';
type VerifiedFilter = '' | 'true' | 'false';

export function AdminDemoSessionsPage() {
  const { toast } = useToast();
  const [items, setItems] = useState<DemoSessionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [counts, setCounts] = useState<DemoSessionStatusCounts>({
    pending: 0, approved: 0, rejected: 0, blocklisted: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('');
  const [verifiedFilter, setVerifiedFilter] = useState<VerifiedFilter>('');
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search, 400);
  const [page, setPage] = useState(1);
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});
  const [csvLoading, setCsvLoading] = useState(false);

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminApi.listDemoSessions({
        page,
        per_page: PAGE_SIZE,
        status: statusFilter || undefined,
        verified: verifiedFilter === '' ? undefined : verifiedFilter === 'true',
        search: debouncedSearch || undefined,
      });
      setItems(data.items);
      setTotal(data.total);
      if (data.counts) {
        setCounts(data.counts);
      }
    } catch {
      setError('Failed to load demo sessions.');
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, verifiedFilter, debouncedSearch]);

  useEffect(() => { loadItems(); }, [loadItems]);

  const runAction = async (
    id: string, fn: (id: string) => Promise<DemoSessionItem>, label: string,
  ) => {
    setActionLoading((p) => ({ ...p, [id]: true }));
    try {
      const updated = await fn(id);
      setItems((prev) => prev.map((it) => (it.id === id ? updated : it)));
      toast(`Session ${label}`, 'success');
    } catch {
      toast(`Failed to ${label} session`, 'error');
    } finally {
      setActionLoading((p) => ({ ...p, [id]: false }));
    }
  };

  const handleCsvDownload = async () => {
    setCsvLoading(true);
    try {
      const blob = await adminApi.downloadDemoSessionsCsv();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `demo-sessions-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch {
      toast('CSV export failed', 'error');
    } finally {
      setCsvLoading(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const moatLabel = (it: DemoSessionItem) =>
    `TM:${it.moat_summary.tm_beats_seen} RS:${it.moat_summary.rs_roles_switched} PW:${it.moat_summary.pw_viewport_reached ? '✓' : '✗'}`;

  return (
    <DashboardLayout welcomeSubtitle="Review demo sessions">
      <div className="admin-waitlist-page admin-demo-sessions-page">
        <PageNav
          items={[
            { label: 'Home', to: '/dashboard' },
            { label: 'Admin', to: '/admin/waitlist' },
            { label: 'Demo Sessions' },
          ]}
        />
        <div className="admin-demo-sessions-header">
          <h1>Demo Session Management</h1>
          <button className="btn btn-sm btn-secondary" onClick={handleCsvDownload} disabled={csvLoading}>
            {csvLoading ? 'Downloading...' : 'Download CSV'}
          </button>
        </div>

        <div className="admin-waitlist-stats admin-demo-sessions-stats">
          <div className="admin-waitlist-stat-card"><h4>Total</h4><div className="stat-value">{total}</div></div>
          <div className="admin-waitlist-stat-card pending"><h4>Pending</h4><div className="stat-value">{counts.pending}</div></div>
          <div className="admin-waitlist-stat-card approved"><h4>Approved</h4><div className="stat-value">{counts.approved}</div></div>
          <div className="admin-waitlist-stat-card declined"><h4>Rejected</h4><div className="stat-value">{counts.rejected}</div></div>
          <div className="admin-waitlist-stat-card"><h4>Blocklisted</h4><div className="stat-value">{counts.blocklisted}</div></div>
        </div>

        <div className="admin-waitlist-filters admin-demo-sessions-filters">
          <label htmlFor="demo-status-filter" className="sr-only">Filter by status</label>
          <select id="demo-status-filter" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value as StatusFilter); setPage(1); }}>
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="blocklisted">Blocklisted</option>
          </select>
          <label htmlFor="demo-verified-filter" className="sr-only">Filter by verified</label>
          <select id="demo-verified-filter" value={verifiedFilter} onChange={(e) => { setVerifiedFilter(e.target.value as VerifiedFilter); setPage(1); }}>
            <option value="">All Verified</option>
            <option value="true">Verified</option>
            <option value="false">Unverified</option>
          </select>
          <label htmlFor="demo-search" className="sr-only">Search by name or email</label>
          <input id="demo-search" type="text" placeholder="Search by name or email..." value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        </div>

        {loading ? (
          <ListSkeleton rows={8} />
        ) : error ? (
          <div className="admin-waitlist-empty">{error}</div>
        ) : items.length === 0 ? (
          <div className="admin-waitlist-empty">No demo sessions found.</div>
        ) : (
          <>
            <table className="admin-waitlist-table admin-demo-sessions-table">
              <thead>
                <tr>
                  <th>Email</th><th>Name</th><th>Role</th><th>Verified</th>
                  <th>Created</th><th>Verified At</th><th>Gens</th><th>Moat</th>
                  <th>Status</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => {
                  const status = (it.admin_status || 'pending') as StatusFilter;
                  const busy = !!actionLoading[it.id];
                  return (
                    <tr key={it.id}>
                      <td>{it.email || '--'}</td>
                      <td>{it.full_name || '--'}</td>
                      <td>{it.role || '--'}</td>
                      <td className={it.verified ? 'admin-demo-sessions-verified-yes' : 'admin-demo-sessions-verified-no'}>
                        {it.verified ? '✓' : '✗'}
                      </td>
                      <td>{it.created_at ? new Date(it.created_at).toLocaleDateString() : '--'}</td>
                      <td>{it.verified_ts ? new Date(it.verified_ts).toLocaleDateString() : '--'}</td>
                      <td>{it.generations_count}</td>
                      <td className="admin-demo-sessions-moat">{moatLabel(it)}</td>
                      <td><span className={`demo-status-badge ${status}`}>{status}</span></td>
                      <td>
                        <div className="admin-waitlist-row-actions">
                          <button className="btn btn-sm btn-success" onClick={() => runAction(it.id, adminApi.approveDemoSession, 'approved')} disabled={busy || status === 'approved'}>Approve</button>
                          <button className="btn btn-sm btn-danger" onClick={() => runAction(it.id, adminApi.rejectDemoSession, 'rejected')} disabled={busy || status === 'rejected'}>Reject</button>
                          <button className="btn btn-sm btn-secondary" onClick={() => runAction(it.id, adminApi.blocklistDemoSession, 'blocklisted')} disabled={busy || status === 'blocklisted'}>Blocklist</button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {totalPages > 1 && (
              <div className="admin-waitlist-pagination">
                <span>Showing {(page - 1) * PAGE_SIZE + 1}&ndash;{Math.min(page * PAGE_SIZE, total)} of {total}</span>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button>
                  <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

export default AdminDemoSessionsPage;
