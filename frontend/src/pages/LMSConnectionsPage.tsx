/**
 * LMSConnectionsPage — /settings/lms
 *
 * Allows users to manage their connections to Learning Management Systems.
 * Shows active connections as cards and lets users add new connections.
 */

import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  lmsConnectionsApi,
  type LMSProvider,
  type LMSConnection,
  type LMSInstitution,
} from '../api/lmsConnections';
import './LMSConnectionsPage.css';

// ---------------------------------------------------------------------------
// Provider logo / initials placeholder
// ---------------------------------------------------------------------------

const PROVIDER_INITIALS: Record<string, string> = {
  google_classroom: 'GC',
  brightspace: 'BS',
  canvas: 'CA',
  moodle: 'MO',
};

const PROVIDER_COLORS: Record<string, string> = {
  google_classroom: '#4285f4',
  brightspace: '#e87722',
  canvas: '#e66000',
  moodle: '#f98012',
};

const PROVIDER_DESCRIPTIONS: Record<string, string> = {
  google_classroom:
    'Connect your Google Classroom account to sync courses, assignments, and materials automatically.',
  brightspace:
    'Connect your school board\'s D2L Brightspace instance to import courses and assignments.',
  canvas: 'Connect your institution\'s Canvas LMS to sync courses, grades, and materials.',
  moodle: 'Connect your Moodle learning environment to sync course content and assignments.',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ProviderLogo({ provider }: { provider: string }) {
  const initials = PROVIDER_INITIALS[provider] ?? provider.slice(0, 2).toUpperCase();
  const color = PROVIDER_COLORS[provider] ?? '#6c757d';
  return (
    <div
      className="lms-provider-logo"
      style={{ backgroundColor: color }}
      aria-label={provider}
    >
      {initials}
    </div>
  );
}

function StatusBadge({ status }: { status: LMSConnection['status'] }) {
  const config: Record<LMSConnection['status'], { label: string; cls: string }> = {
    connected: { label: 'Connected', cls: 'lms-badge--connected' },
    expired: { label: 'Token Expired', cls: 'lms-badge--expired' },
    error: { label: 'Error', cls: 'lms-badge--error' },
    disconnected: { label: 'Not Connected', cls: 'lms-badge--disconnected' },
  };
  const { label, cls } = config[status] ?? { label: status, cls: '' };
  return <span className={`lms-badge ${cls}`}>{label}</span>;
}

// ---------------------------------------------------------------------------
// ConnectedCard
// ---------------------------------------------------------------------------

interface ConnectedCardProps {
  connection: LMSConnection;
  onDelete: (id: number) => Promise<void>;
  onLabelChange: (id: number, label: string) => Promise<void>;
}

function ConnectedCard({ connection, onDelete, onLabelChange }: ConnectedCardProps) {
  const [editingLabel, setEditingLabel] = useState(false);
  const [labelDraft, setLabelDraft] = useState(connection.label ?? '');
  const [deleting, setDeleting] = useState(false);
  const [saving, setSaving] = useState(false);

  const displayName = connection.institution_name
    ? `${connection.institution_name}`
    : connection.provider
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase());

  const handleLabelSave = async () => {
    setSaving(true);
    try {
      await onLabelChange(connection.id, labelDraft.trim());
      setEditingLabel(false);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Remove this connection? Your courses will remain but won\'t sync.')) return;
    setDeleting(true);
    try {
      await onDelete(connection.id);
    } finally {
      setDeleting(false);
    }
  };

  const lastSync = connection.last_sync_at
    ? new Date(connection.last_sync_at).toLocaleString()
    : 'Never';

  return (
    <div className="lms-connection-card">
      <div className="lms-connection-card__header">
        <ProviderLogo provider={connection.provider} />
        <div className="lms-connection-card__info">
          <div className="lms-connection-card__name">{displayName}</div>
          {connection.institution_base_url && (
            <div className="lms-connection-card__url">{connection.institution_base_url}</div>
          )}
        </div>
        <StatusBadge status={connection.status} />
      </div>

      <div className="lms-connection-card__label-row">
        {editingLabel ? (
          <div className="lms-connection-card__label-edit">
            <input
              type="text"
              value={labelDraft}
              onChange={(e) => setLabelDraft(e.target.value)}
              placeholder="Label (e.g. TDSB School)"
              className="lms-label-input"
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleLabelSave();
                if (e.key === 'Escape') setEditingLabel(false);
              }}
              autoFocus
            />
            <button
              className="lms-btn lms-btn--sm lms-btn--primary"
              onClick={handleLabelSave}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
            <button
              className="lms-btn lms-btn--sm"
              onClick={() => setEditingLabel(false)}
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            className="lms-connection-card__label-display"
            onClick={() => { setLabelDraft(connection.label ?? ''); setEditingLabel(true); }}
            title="Click to edit label"
          >
            {connection.label || <span className="lms-placeholder">Add label</span>}
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
          </button>
        )}
      </div>

      <div className="lms-connection-card__meta">
        <span>Last synced: {lastSync}</span>
        {connection.courses_synced > 0 && (
          <span>{connection.courses_synced} course{connection.courses_synced !== 1 ? 's' : ''}</span>
        )}
        {connection.sync_error && (
          <span className="lms-connection-card__error" title={connection.sync_error}>
            Sync error
          </span>
        )}
      </div>

      <div className="lms-connection-card__actions">
        <button
          className="lms-btn lms-btn--danger"
          onClick={handleDelete}
          disabled={deleting}
        >
          {deleting ? 'Removing...' : 'Disconnect'}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AddConnectionModal
// ---------------------------------------------------------------------------

interface AddConnectionModalProps {
  provider: LMSProvider;
  institutions: LMSInstitution[];
  onClose: () => void;
  onAdd: (provider: string, institutionId: number | null, label: string) => Promise<void>;
}

function AddConnectionModal({ provider, institutions, onClose, onAdd }: AddConnectionModalProps) {
  const [selectedInstitution, setSelectedInstitution] = useState<number | ''>('');
  const [label, setLabel] = useState('');
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');

  const providerInstitutions = institutions.filter((i) => i.provider === provider.provider_id);

  const handleAdd = async () => {
    if (provider.requires_institution_url && !selectedInstitution) {
      setError('Please select your school board.');
      return;
    }
    setAdding(true);
    setError('');
    try {
      await onAdd(
        provider.provider_id,
        selectedInstitution ? Number(selectedInstitution) : null,
        label,
      );
      onClose();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? 'Failed to add connection.');
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="lms-modal-backdrop" onClick={onClose}>
      <div className="lms-modal" onClick={(e) => e.stopPropagation()}>
        <div className="lms-modal__header">
          <ProviderLogo provider={provider.provider_id} />
          <h2>Connect to {provider.display_name}</h2>
          <button className="lms-modal__close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        {provider.requires_institution_url && (
          <div className="lms-modal__field">
            <label htmlFor="lms-institution">School Board</label>
            <select
              id="lms-institution"
              value={selectedInstitution}
              onChange={(e) => setSelectedInstitution(e.target.value ? Number(e.target.value) : '')}
              className="lms-select"
            >
              <option value="">-- Select your school board --</option>
              {providerInstitutions.map((inst) => (
                <option key={inst.id} value={inst.id}>
                  {inst.name}
                </option>
              ))}
            </select>
            {providerInstitutions.length === 0 && (
              <p className="lms-modal__hint">No institutions configured yet. Contact your administrator.</p>
            )}
          </div>
        )}

        <div className="lms-modal__field">
          <label htmlFor="lms-label">Label (optional)</label>
          <input
            id="lms-label"
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder={`e.g. ${provider.display_name} — My School`}
            className="lms-input"
          />
        </div>

        {error && <p className="lms-modal__error">{error}</p>}

        <div className="lms-modal__footer">
          <button className="lms-btn" onClick={onClose}>Cancel</button>
          <button
            className="lms-btn lms-btn--primary"
            onClick={handleAdd}
            disabled={adding}
          >
            {adding ? 'Connecting...' : 'Connect'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ProviderCard (Add Connection section)
// ---------------------------------------------------------------------------

interface ProviderCardProps {
  provider: LMSProvider;
  onConnect: (provider: LMSProvider) => void;
}

function ProviderCard({ provider, onConnect }: ProviderCardProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  const isAvailable = provider.provider_id === 'google_classroom';
  const description = PROVIDER_DESCRIPTIONS[provider.provider_id] ?? '';

  const handleConnect = () => {
    if (provider.provider_id === 'google_classroom') {
      // Delegate to existing Google OAuth flow
      window.location.href = '/api/google/connect';
      return;
    }
    onConnect(provider);
  };

  return (
    <div className="lms-provider-card">
      <div className="lms-provider-card__header">
        <ProviderLogo provider={provider.provider_id} />
        <div className="lms-provider-card__name">{provider.display_name}</div>
      </div>
      <p className="lms-provider-card__description">{description}</p>
      {provider.requires_institution_url && (
        <p className="lms-provider-card__note">Requires your school's URL</p>
      )}
      <div className="lms-provider-card__footer">
        {isAvailable ? (
          <button className="lms-btn lms-btn--primary" onClick={handleConnect}>
            Connect
          </button>
        ) : (
          <div
            className="lms-coming-soon-wrapper"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
          >
            <button className="lms-btn lms-btn--disabled" disabled>
              Coming Soon
            </button>
            {showTooltip && (
              <div className="lms-tooltip">
                {provider.display_name} integration is not yet available.
                We're working on it!
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function LMSConnectionsPage() {
  const [providers, setProviders] = useState<LMSProvider[]>([]);
  const [connections, setConnections] = useState<LMSConnection[]>([]);
  const [institutions, setInstitutions] = useState<LMSInstitution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [addModalProvider, setAddModalProvider] = useState<LMSProvider | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [p, c, i] = await Promise.all([
        lmsConnectionsApi.listProviders(),
        lmsConnectionsApi.listConnections(),
        lmsConnectionsApi.listInstitutions(),
      ]);
      setProviders(p);
      setConnections(c);
      setInstitutions(i);
    } catch {
      setError('Failed to load LMS connection data. Please refresh and try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleDelete = async (id: number) => {
    await lmsConnectionsApi.deleteConnection(id);
    setConnections((prev) => prev.filter((c) => c.id !== id));
  };

  const handleLabelChange = async (id: number, label: string) => {
    const updated = await lmsConnectionsApi.updateConnection(id, { label: label || null });
    setConnections((prev) => prev.map((c) => (c.id === id ? updated : c)));
  };

  const handleAdd = async (provider: string, institutionId: number | null, label: string) => {
    const conn = await lmsConnectionsApi.createConnection({
      provider,
      institution_id: institutionId,
      label: label || null,
    });
    setConnections((prev) => [...prev, conn]);
  };

  return (
    <DashboardLayout>
      <div className="lms-page">
        <div className="lms-page__header">
          <h1 className="lms-page__title">Learning Platform Connections</h1>
          <p className="lms-page__subtitle">
            Connect ClassBridge to your school's learning management systems to sync courses,
            assignments, and materials automatically.
          </p>
        </div>

        {loading && <div className="lms-loading">Loading connections...</div>}
        {error && <div className="lms-error">{error}</div>}

        {!loading && (
          <>
            {/* Connected Platforms */}
            <section className="lms-section">
              <h2 className="lms-section__title">Connected Platforms</h2>
              {connections.length === 0 ? (
                <div className="lms-empty">
                  <p>No connections yet. Add one below to get started.</p>
                </div>
              ) : (
                <div className="lms-connections-grid">
                  {connections.map((conn) => (
                    <ConnectedCard
                      key={conn.id}
                      connection={conn}
                      onDelete={handleDelete}
                      onLabelChange={handleLabelChange}
                    />
                  ))}
                </div>
              )}
            </section>

            {/* Add Connection */}
            <section className="lms-section">
              <h2 className="lms-section__title">Add Connection</h2>
              <div className="lms-providers-grid">
                {providers.map((provider) => (
                  <ProviderCard
                    key={provider.provider_id}
                    provider={provider}
                    onConnect={setAddModalProvider}
                  />
                ))}
              </div>
            </section>
          </>
        )}

        {/* Add connection modal (for non-Google providers with institution selector) */}
        {addModalProvider && (
          <AddConnectionModal
            provider={addModalProvider}
            institutions={institutions}
            onClose={() => setAddModalProvider(null)}
            onAdd={handleAdd}
          />
        )}
      </div>
    </DashboardLayout>
  );
}
