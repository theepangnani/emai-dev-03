import { useState, useEffect } from 'react';
import { adminApi } from '../api/client';
import type { AuditLogItem } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { ListSkeleton } from '../components/Skeleton';
import { useDebounce } from '../utils/useDebounce';
import { PageNav } from '../components/PageNav';
import './AdminAuditLog.css';

const PAGE_SIZE = 25;

const ACTION_OPTIONS = ['login', 'login_failed', 'create', 'read', 'update', 'delete', 'sync'];
const RESOURCE_OPTIONS = ['user', 'task', 'course', 'study_guide', 'message', 'student', 'children', 'google_classroom', 'invite'];

const ACTION_LABELS: Record<string, string> = {
  login: 'Login',
  login_failed: 'Failed Login',
  create: 'Create',
  read: 'Read',
  update: 'Update',
  delete: 'Delete',
  sync: 'Sync',
  export: 'Export',
};

const ACTION_COLORS: Record<string, string> = {
  login: '#2e7d32',
  login_failed: '#c62828',
  create: '#1565c0',
  read: '#6a6a6a',
  update: '#e65100',
  delete: '#c62828',
  sync: '#6a1b9a',
};

export function AdminAuditLog() {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [actionFilter, setActionFilter] = useState('');
  const [resourceFilter, setResourceFilter] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const debouncedSearch = useDebounce(search, 400);

  useEffect(() => {
    loadLogs();
  }, [actionFilter, resourceFilter, debouncedSearch, page]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const data = await adminApi.getAuditLogs({
        action: actionFilter || undefined,
        resource_type: resourceFilter || undefined,
        search: debouncedSearch || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setLogs(data.items);
      setTotal(data.total);
    } catch {
      // Failed to load
    } finally {
      setLoading(false);
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    });
  };

  const parseDetails = (details: string | null): Record<string, unknown> | null => {
    if (!details) return null;
    try { return JSON.parse(details); } catch { return null; }
  };

  return (
    <DashboardLayout welcomeSubtitle="Platform administration">
      <div className="audit-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Admin', to: '/dashboard' },
          { label: 'Audit Log' },
        ]} />
        <div className="audit-header">
          <h2>Audit Log</h2>
          <p className="audit-subtitle">{total} entries</p>
        </div>

        <div className="audit-filters">
          <select value={actionFilter} onChange={(e) => { setActionFilter(e.target.value); setPage(0); }}>
            <option value="">All Actions</option>
            {ACTION_OPTIONS.map(a => <option key={a} value={a}>{ACTION_LABELS[a] || a}</option>)}
          </select>
          <select value={resourceFilter} onChange={(e) => { setResourceFilter(e.target.value); setPage(0); }}>
            <option value="">All Resources</option>
            {RESOURCE_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
          <input
            type="text"
            placeholder="Search details..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          />
        </div>

        {loading ? (
          <ListSkeleton rows={8} />
        ) : (
          <>
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>Details</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => {
                  const details = parseDetails(log.details);
                  return (
                    <tr key={log.id}>
                      <td className="audit-time">{formatTime(log.created_at)}</td>
                      <td>{log.user_name || (log.user_id ? `User #${log.user_id}` : '—')}</td>
                      <td>
                        <span className="audit-action-badge" style={{ color: ACTION_COLORS[log.action] || '#333' }}>
                          {ACTION_LABELS[log.action] || log.action}
                        </span>
                      </td>
                      <td>
                        <span className="audit-resource">
                          {log.resource_type}
                          {log.resource_id != null && <span className="audit-resource-id">#{log.resource_id}</span>}
                        </span>
                      </td>
                      <td className="audit-details">
                        {details ? Object.entries(details).map(([k, v]) => (
                          <span key={k} className="audit-detail-tag">{k}: {String(v)}</span>
                        )) : '—'}
                      </td>
                      <td className="audit-ip">{log.ip_address || '—'}</td>
                    </tr>
                  );
                })}
                {logs.length === 0 && (
                  <tr>
                    <td colSpan={6} className="audit-empty">No audit logs found</td>
                  </tr>
                )}
              </tbody>
            </table>

            {totalPages > 1 && (
              <div className="audit-pagination">
                <span>
                  Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
                </span>
                <div className="audit-pagination-btns">
                  <button disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
                  <button disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>Next</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
