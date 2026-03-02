/**
 * AdminLMSPage — /admin/lms
 *
 * Admin page for LMS Institution Management (#28) and Sync Orchestration (#27).
 *
 * Sections:
 *  - Stats cards (total, active, errors, last sync)
 *  - Institutions table with Add / Edit / Deactivate actions
 *  - Recent Connections table (all user connections)
 *  - Sync section: trigger full sync + last result
 */

import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  adminLMSApi,
  type LMSInstitution,
  type AdminConnection,
  type LMSStats,
  type InstitutionCreatePayload,
  type InstitutionUpdatePayload,
} from '../api/adminLMS';
import './AdminLMSPage.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const VALID_PROVIDERS = [
  { value: 'google_classroom', label: 'Google Classroom' },
  { value: 'brightspace', label: 'D2L Brightspace' },
  { value: 'canvas', label: 'Canvas LMS' },
  { value: 'moodle', label: 'Moodle' },
];

const PROVIDER_LABELS: Record<string, string> = {
  google_classroom: 'Google Classroom',
  brightspace: 'D2L Brightspace',
  canvas: 'Canvas LMS',
  moodle: 'Moodle',
};

// ---------------------------------------------------------------------------
// StatusBadge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === 'connected'
      ? 'alms-badge alms-badge--connected'
      : status === 'expired'
      ? 'alms-badge alms-badge--expired'
      : status === 'error'
      ? 'alms-badge alms-badge--error'
      : status === 'stale'
      ? 'alms-badge alms-badge--stale'
      : 'alms-badge alms-badge--disconnected';

  const label =
    status === 'connected'
      ? 'Connected'
      : status === 'expired'
      ? 'Expired'
      : status === 'error'
      ? 'Error'
      : status === 'stale'
      ? 'Stale'
      : 'Disconnected';

  return <span className={cls}>{label}</span>;
}

// ---------------------------------------------------------------------------
// Institution form modal (Add + Edit)
// ---------------------------------------------------------------------------

interface InstitutionFormProps {
  mode: 'add' | 'edit';
  initial?: LMSInstitution | null;
  onClose: () => void;
  onSave: (data: InstitutionCreatePayload | InstitutionUpdatePayload) => Promise<void>;
}

function InstitutionFormModal({ mode, initial, onClose, onSave }: InstitutionFormProps) {
  const [name, setName] = useState(initial?.name ?? '');
  const [provider, setProvider] = useState(initial?.provider ?? 'brightspace');
  const [baseUrl, setBaseUrl] = useState(initial?.base_url ?? '');
  const [region, setRegion] = useState(initial?.region ?? '');
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSave = async () => {
    if (!name.trim()) {
      setError('Name is required.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const payload: InstitutionCreatePayload = {
        name: name.trim(),
        provider,
        base_url: baseUrl.trim() || undefined,
        region: region.trim() || undefined,
        is_active: isActive,
      };
      await onSave(payload);
      onClose();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? 'Failed to save institution.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="alms-modal-backdrop" onClick={onClose}>
      <div className="alms-modal" onClick={(e) => e.stopPropagation()}>
        <div className="alms-modal__header">
          <h2>{mode === 'add' ? 'Add Institution' : 'Edit Institution'}</h2>
          <button className="alms-modal__close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        <div className="alms-modal__body">
          <div className="alms-field">
            <label htmlFor="alms-inst-name">Name *</label>
            <input
              id="alms-inst-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. TDSB Brightspace"
              className="alms-input"
            />
          </div>

          <div className="alms-field">
            <label htmlFor="alms-inst-provider">Provider *</label>
            <select
              id="alms-inst-provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="alms-select"
            >
              {VALID_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          <div className="alms-field">
            <label htmlFor="alms-inst-url">Base URL</label>
            <input
              id="alms-inst-url"
              type="url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://school.brightspace.com"
              className="alms-input"
            />
          </div>

          <div className="alms-field">
            <label htmlFor="alms-inst-region">Region</label>
            <input
              id="alms-inst-region"
              type="text"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              placeholder="ON"
              maxLength={10}
              className="alms-input"
            />
          </div>

          {mode === 'edit' && (
            <div className="alms-field alms-field--checkbox">
              <label>
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                />
                Active
              </label>
            </div>
          )}

          {error && <p className="alms-modal__error">{error}</p>}
        </div>

        <div className="alms-modal__footer">
          <button className="alms-btn" onClick={onClose}>
            Cancel
          </button>
          <button
            className="alms-btn alms-btn--primary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving...' : mode === 'add' ? 'Add Institution' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function AdminLMSPage() {
  const [stats, setStats] = useState<LMSStats | null>(null);
  const [institutions, setInstitutions] = useState<LMSInstitution[]>([]);
  const [connections, setConnections] = useState<AdminConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [editTarget, setEditTarget] = useState<LMSInstitution | null>(null);

  // Sync state
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string>('');
  const [lastSyncTime, setLastSyncTime] = useState<string>('');

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [statsData, instsData] = await Promise.all([
        adminLMSApi.getStats(),
        adminLMSApi.listInstitutions({ include_inactive: true }),
      ]);
      setStats(statsData);
      setInstitutions(instsData);

      // Load connections for all institutions
      const allConns: AdminConnection[] = [];
      for (const inst of instsData) {
        try {
          const conns = await adminLMSApi.listInstitutionConnections(inst.id);
          allConns.push(...conns);
        } catch {
          // Institution might have no connections — that is fine
        }
      }
      setConnections(allConns);
    } catch {
      setError('Failed to load LMS management data. Please refresh.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleAddInstitution = async (data: InstitutionCreatePayload) => {
    const created = await adminLMSApi.createInstitution(data);
    setInstitutions((prev) => [...prev, created]);
    await loadAll(); // Reload stats
  };

  const handleEditInstitution = async (data: InstitutionUpdatePayload) => {
    if (!editTarget) return;
    const updated = await adminLMSApi.updateInstitution(editTarget.id, data);
    setInstitutions((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
    setEditTarget(null);
    await loadAll();
  };

  const handleDeactivate = async (inst: LMSInstitution) => {
    if (!window.confirm(`Deactivate "${inst.name}"? Users will no longer be able to connect to it.`)) return;
    await adminLMSApi.deactivateInstitution(inst.id);
    setInstitutions((prev) =>
      prev.map((i) => (i.id === inst.id ? { ...i, is_active: false } : i)),
    );
    await loadAll();
  };

  const handleTriggerSync = async () => {
    setSyncing(true);
    setSyncResult('');
    try {
      const result = await adminLMSApi.triggerFullSync();
      setSyncResult(result.message);
      setLastSyncTime(new Date().toLocaleString());
      await loadAll();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setSyncResult(e?.response?.data?.detail ?? 'Sync failed. Check server logs.');
    } finally {
      setSyncing(false);
    }
  };

  // Derived stats for the 4 stat cards
  const totalConns = stats?.total_connections ?? 0;
  const activeConns = Object.values(stats?.by_provider ?? {}).reduce(
    (sum, prov) => sum + (prov['connected'] ?? 0),
    0,
  );
  const errorConns = Object.values(stats?.by_provider ?? {}).reduce(
    (sum, prov) => sum + (prov['error'] ?? 0) + (prov['stale'] ?? 0),
    0,
  );
  const lastSyncCount = stats?.last_sync_summary.synced_last_hour ?? 0;

  return (
    <DashboardLayout welcomeSubtitle="LMS platform administration">
      <div className="alms-page">
        <div className="alms-page__header">
          <h1 className="alms-page__title">LMS Management</h1>
          <button
            className="alms-btn alms-btn--primary"
            onClick={() => setShowAddModal(true)}
          >
            + Add Institution
          </button>
        </div>

        {error && <div className="alms-error">{error}</div>}
        {loading && <div className="alms-loading">Loading LMS data...</div>}

        {!loading && (
          <>
            {/* ── Stats cards ── */}
            <div className="alms-stats-row">
              <div className="alms-stat-card">
                <div className="alms-stat-card__value">{totalConns}</div>
                <div className="alms-stat-card__label">Total Connections</div>
              </div>
              <div className="alms-stat-card alms-stat-card--green">
                <div className="alms-stat-card__value">{activeConns}</div>
                <div className="alms-stat-card__label">Active</div>
              </div>
              <div className="alms-stat-card alms-stat-card--red">
                <div className="alms-stat-card__value">{errorConns}</div>
                <div className="alms-stat-card__label">Errors / Stale</div>
              </div>
              <div className="alms-stat-card alms-stat-card--blue">
                <div className="alms-stat-card__value">{lastSyncCount}</div>
                <div className="alms-stat-card__label">Synced Last Hour</div>
              </div>
            </div>

            {/* ── Institutions ── */}
            <section className="alms-section">
              <h2 className="alms-section__title">Institutions</h2>
              {institutions.length === 0 ? (
                <p className="alms-empty">No institutions configured yet.</p>
              ) : (
                <div className="alms-table-wrapper">
                  <table className="alms-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Provider</th>
                        <th>Base URL</th>
                        <th>Region</th>
                        <th>Active</th>
                        <th>Connections</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {institutions.map((inst) => {
                        const connCount =
                          stats?.by_institution.find((b) => b.institution_id === inst.id)
                            ?.active_connections ?? 0;
                        return (
                          <tr
                            key={inst.id}
                            className={inst.is_active ? '' : 'alms-table__row--inactive'}
                          >
                            <td>{inst.name}</td>
                            <td>{PROVIDER_LABELS[inst.provider] ?? inst.provider}</td>
                            <td className="alms-table__url">
                              {inst.base_url ? (
                                <a
                                  href={inst.base_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="alms-link"
                                >
                                  {inst.base_url}
                                </a>
                              ) : (
                                <span className="alms-none">—</span>
                              )}
                            </td>
                            <td>{inst.region ?? '—'}</td>
                            <td>
                              <span
                                className={
                                  inst.is_active ? 'alms-badge alms-badge--connected' : 'alms-badge alms-badge--disconnected'
                                }
                              >
                                {inst.is_active ? 'Yes' : 'No'}
                              </span>
                            </td>
                            <td>{connCount}</td>
                            <td>
                              <div className="alms-table__actions">
                                <button
                                  className="alms-btn alms-btn--sm"
                                  onClick={() => setEditTarget(inst)}
                                >
                                  Edit
                                </button>
                                {inst.is_active && (
                                  <button
                                    className="alms-btn alms-btn--sm alms-btn--danger"
                                    onClick={() => handleDeactivate(inst)}
                                  >
                                    Deactivate
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* ── Provider stats breakdown ── */}
            {stats && Object.keys(stats.by_provider).length > 0 && (
              <section className="alms-section">
                <h2 className="alms-section__title">Connections by Provider</h2>
                <div className="alms-provider-stats">
                  {Object.entries(stats.by_provider).map(([prov, counts]) => (
                    <div key={prov} className="alms-provider-stat-card">
                      <div className="alms-provider-stat-card__name">
                        {PROVIDER_LABELS[prov] ?? prov}
                      </div>
                      <div className="alms-provider-stat-card__counts">
                        {Object.entries(counts).map(([status, count]) => (
                          <div key={status} className="alms-provider-stat-card__row">
                            <StatusBadge status={status} />
                            <span className="alms-provider-stat-card__count">{count}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* ── Recent Connections ── */}
            <section className="alms-section">
              <h2 className="alms-section__title">Recent Connections</h2>
              {connections.length === 0 ? (
                <p className="alms-empty">No connections found for any institution.</p>
              ) : (
                <div className="alms-table-wrapper">
                  <table className="alms-table">
                    <thead>
                      <tr>
                        <th>User</th>
                        <th>Provider</th>
                        <th>Institution</th>
                        <th>Status</th>
                        <th>Last Synced</th>
                        <th>Courses</th>
                      </tr>
                    </thead>
                    <tbody>
                      {connections.map((conn) => {
                        const instName = institutions.find(
                          (i) => i.id === conn.institution_id,
                        )?.name;
                        return (
                          <tr key={conn.id}>
                            <td>
                              <div>{conn.user_name ?? '—'}</div>
                              {conn.user_email && (
                                <div className="alms-table__sub">{conn.user_email}</div>
                              )}
                            </td>
                            <td>{PROVIDER_LABELS[conn.provider] ?? conn.provider}</td>
                            <td>{instName ?? '—'}</td>
                            <td>
                              <StatusBadge status={conn.status} />
                              {conn.sync_error && (
                                <div
                                  className="alms-table__error"
                                  title={conn.sync_error}
                                >
                                  {conn.sync_error.slice(0, 40)}
                                  {conn.sync_error.length > 40 ? '…' : ''}
                                </div>
                              )}
                            </td>
                            <td>
                              {conn.last_sync_at
                                ? new Date(conn.last_sync_at).toLocaleString()
                                : 'Never'}
                            </td>
                            <td>{conn.courses_synced}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* ── Sync section ── */}
            <section className="alms-section alms-sync-section">
              <h2 className="alms-section__title">Sync</h2>
              <p className="alms-sync-desc">
                The LMS sync job runs automatically every 15 minutes.  You can also trigger
                an immediate full sync here.
              </p>
              <div className="alms-sync-actions">
                <button
                  className="alms-btn alms-btn--primary"
                  onClick={handleTriggerSync}
                  disabled={syncing}
                >
                  {syncing ? 'Syncing...' : 'Trigger Full Sync'}
                </button>
                {lastSyncTime && (
                  <span className="alms-sync-time">
                    Last triggered: {lastSyncTime}
                  </span>
                )}
              </div>
              {syncResult && (
                <div
                  className={`alms-sync-result ${
                    syncResult.toLowerCase().includes('fail') ||
                    syncResult.toLowerCase().includes('error')
                      ? 'alms-sync-result--error'
                      : 'alms-sync-result--ok'
                  }`}
                >
                  {syncResult}
                </div>
              )}
              {stats && (
                <div className="alms-sync-summary">
                  <span>
                    Last hour: {stats.last_sync_summary.synced_last_hour} synced,{' '}
                    {stats.last_sync_summary.errors_last_hour} errors
                  </span>
                </div>
              )}
            </section>
          </>
        )}
      </div>

      {/* Add Institution modal */}
      {showAddModal && (
        <InstitutionFormModal
          mode="add"
          onClose={() => setShowAddModal(false)}
          onSave={handleAddInstitution}
        />
      )}

      {/* Edit Institution modal */}
      {editTarget && (
        <InstitutionFormModal
          mode="edit"
          initial={editTarget}
          onClose={() => setEditTarget(null)}
          onSave={handleEditInstitution}
        />
      )}
    </DashboardLayout>
  );
}
