/**
 * LMSConnectionsPage — /settings/lms  (Multi-LMS Connection Manager UI, #26)
 *
 * Fully polished provider catalog with:
 * - Provider cards grid (Google Classroom, Brightspace/D2L, Canvas) showing
 *   connection status, course count, last sync time, and action buttons.
 * - Institution selector modal for Brightspace with pre-seeded Ontario boards
 *   (TDSB, PDSB, YRDSB, HDSB, OCDSB) plus a custom URL fallback.
 * - OAuth connect flow: Google → /api/google/connect, Brightspace → /api/lms/brightspace/connect
 * - Sync Now / Disconnect (with confirmation) on each connected provider.
 * - Detail panel slide-in showing synced courses list for a connected provider.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  lmsConnectionsApi,
  type LMSProvider,
  type LMSConnection,
  type LMSInstitution,
} from '../api/lmsConnections';
import './LMSConnectionsPage.css';

// ---------------------------------------------------------------------------
// Static provider metadata
// ---------------------------------------------------------------------------

const PROVIDER_META: Record<
  string,
  {
    color: string;
    initials: string;
    tagline: string;
    description: string;
    connectLabel: string;
    comingSoon?: boolean;
  }
> = {
  google_classroom: {
    color: '#4285f4',
    initials: 'GC',
    tagline: 'Google Classroom',
    description:
      'Sync courses, assignments, and announcements from Google Classroom automatically.',
    connectLabel: 'Connect Google',
  },
  brightspace: {
    color: '#e87722',
    initials: 'D2L',
    tagline: 'D2L Brightspace',
    description:
      'Connect your school board\'s Brightspace instance — TDSB, PDSB, YRDSB, HDSB, OCDSB, and more.',
    connectLabel: 'Connect Brightspace',
  },
  canvas: {
    color: '#e66000',
    initials: 'CA',
    tagline: 'Canvas (Instructure)',
    description:
      'Connect your institution\'s Canvas LMS to sync courses, grades, and materials.',
    connectLabel: 'Connect Canvas',
    comingSoon: true,
  },
  moodle: {
    color: '#f98012',
    initials: 'MO',
    tagline: 'Moodle',
    description: 'Connect your Moodle learning environment to sync course content.',
    connectLabel: 'Connect Moodle',
    comingSoon: true,
  },
};

const MORE_COMING_SOON = {
  color: '#9ca3af',
  initials: '+',
  tagline: 'More coming soon',
  description: 'Contact us to request support for your learning platform.',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatRelativeTime(isoString: string | null | undefined): string {
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

function providerMeta(providerId: string) {
  return PROVIDER_META[providerId] ?? {
    color: '#6b7280',
    initials: providerId.slice(0, 2).toUpperCase(),
    tagline: providerId.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
    description: '',
    connectLabel: 'Connect',
  };
}

// ---------------------------------------------------------------------------
// ProviderLogo
// ---------------------------------------------------------------------------

function ProviderLogo({
  providerId,
  size = 44,
}: {
  providerId: string;
  size?: number;
}) {
  const meta = providerMeta(providerId);
  return (
    <div
      className="lms-provider-logo"
      style={{ backgroundColor: meta.color, width: size, height: size, fontSize: size * 0.27 }}
      aria-label={meta.tagline}
    >
      {meta.initials}
    </div>
  );
}

// ---------------------------------------------------------------------------
// StatusDot
// ---------------------------------------------------------------------------

function StatusDot({ status }: { status: LMSConnection['status'] }) {
  const cls =
    status === 'connected'
      ? 'lms-dot--connected'
      : status === 'expired'
      ? 'lms-dot--expired'
      : status === 'error'
      ? 'lms-dot--error'
      : 'lms-dot--disconnected';
  const label =
    status === 'connected'
      ? 'Connected'
      : status === 'expired'
      ? 'Token Expired'
      : status === 'error'
      ? 'Sync Error'
      : 'Not connected';
  return (
    <span className={`lms-dot ${cls}`} title={label}>
      <span className="lms-dot__circle" aria-hidden="true" />
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// ConfirmDialog
// ---------------------------------------------------------------------------

interface ConfirmDialogProps {
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

function ConfirmDialog({
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <div className="lms-modal-backdrop" onClick={onCancel}>
      <div className="lms-confirm-dialog" onClick={(e) => e.stopPropagation()}>
        <p className="lms-confirm-dialog__message">{message}</p>
        <div className="lms-confirm-dialog__actions">
          <button className="lms-btn" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button className="lms-btn lms-btn--danger" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Institution Selector Modal (for Brightspace)
// ---------------------------------------------------------------------------

interface InstitutionSelectorProps {
  provider: LMSProvider;
  institutions: LMSInstitution[];
  onClose: () => void;
  onSelect: (institutionId: number) => void;
}

function InstitutionSelectorModal({
  provider,
  institutions,
  onClose,
  onSelect,
}: InstitutionSelectorProps) {
  const [query, setQuery] = useState('');
  const [customUrl, setCustomUrl] = useState('');
  const [useCustom, setUseCustom] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const filtered = institutions
    .filter((i) => i.provider === provider.provider_id)
    .filter(
      (i) =>
        !query ||
        i.name.toLowerCase().includes(query.toLowerCase()) ||
        (i.base_url ?? '').toLowerCase().includes(query.toLowerCase()),
    );

  const meta = providerMeta(provider.provider_id);

  return (
    <div className="lms-modal-backdrop" onClick={onClose}>
      <div className="lms-modal lms-modal--institution" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="lms-modal__header">
          <ProviderLogo providerId={provider.provider_id} />
          <div className="lms-modal__header-text">
            <h2>Connect to {meta.tagline}</h2>
            <p className="lms-modal__subtitle">Select your school board to begin</p>
          </div>
          <button className="lms-modal__close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        {/* Search */}
        <div className="lms-modal__search-wrapper">
          <svg
            className="lms-modal__search-icon"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            className="lms-input lms-modal__search-input"
            placeholder="Search school boards…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        {/* Institution list */}
        <div className="lms-institution-list">
          {filtered.length === 0 && !useCustom && (
            <p className="lms-institution-list__empty">
              No matching school boards found.{' '}
              <button
                className="lms-link"
                onClick={() => setUseCustom(true)}
              >
                Enter a custom URL instead.
              </button>
            </p>
          )}
          {filtered.map((inst) => (
            <button
              key={inst.id}
              className="lms-institution-item"
              onClick={() => onSelect(inst.id)}
            >
              <div className="lms-institution-item__name">{inst.name}</div>
              {inst.base_url && (
                <div className="lms-institution-item__url">{inst.base_url}</div>
              )}
              {inst.region && (
                <span className="lms-institution-item__region">{inst.region}</span>
              )}
            </button>
          ))}
        </div>

        {/* Custom URL toggle */}
        {!useCustom && filtered.length > 0 && (
          <p className="lms-modal__hint">
            Don't see your board?{' '}
            <button className="lms-link" onClick={() => setUseCustom(true)}>
              Enter a custom URL
            </button>
          </p>
        )}

        {useCustom && (
          <div className="lms-modal__custom-url">
            <label className="lms-modal__field-label" htmlFor="lms-custom-url">
              Your school's Brightspace URL
            </label>
            <div className="lms-modal__custom-url-row">
              <input
                id="lms-custom-url"
                type="url"
                className="lms-input"
                placeholder="https://yourboard.brightspace.com"
                value={customUrl}
                onChange={(e) => setCustomUrl(e.target.value)}
              />
              <button
                className="lms-btn lms-btn--primary"
                disabled={!customUrl.trim()}
                onClick={() => {
                  // Custom URL: contact support — show a helpful message
                  alert(
                    'Custom Brightspace instances require admin setup.\n\n' +
                      'Please contact support@classbridgeapp.com with your school\'s URL ' +
                      'and we\'ll add it within 24 hours.',
                  );
                }}
              >
                Request Access
              </button>
            </div>
            <p className="lms-modal__hint">
              Or go back to{' '}
              <button className="lms-link" onClick={() => setUseCustom(false)}>
                select a school board
              </button>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Connected Detail Panel
// ---------------------------------------------------------------------------

interface DetailPanelProps {
  connection: LMSConnection;
  onClose: () => void;
  onSync: (id: number) => Promise<void>;
  onDisconnect: (id: number) => Promise<void>;
}

function ConnectedDetailPanel({
  connection,
  onClose,
  onSync,
  onDisconnect,
}: DetailPanelProps) {
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);

  const meta = providerMeta(connection.provider);
  const displayName = connection.institution_name ?? meta.tagline;
  const lastSync = formatRelativeTime(connection.last_sync_at);

  const handleSync = async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      await onSync(connection.id);
      setSyncMsg('Sync completed successfully.');
    } catch {
      setSyncMsg('Sync failed. Please try again.');
    } finally {
      setSyncing(false);
    }
  };

  const handleDisconnect = async () => {
    setConfirmDisconnect(false);
    await onDisconnect(connection.id);
    onClose();
  };

  return (
    <div className="lms-detail-backdrop" onClick={onClose}>
      <div className="lms-detail-panel" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="lms-detail-panel__header">
          <ProviderLogo providerId={connection.provider} size={52} />
          <div className="lms-detail-panel__header-text">
            <h2 className="lms-detail-panel__title">{displayName}</h2>
            {connection.institution_base_url && (
              <a
                href={connection.institution_base_url}
                target="_blank"
                rel="noopener noreferrer"
                className="lms-detail-panel__url"
              >
                {connection.institution_base_url}
              </a>
            )}
          </div>
          <button className="lms-modal__close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        {/* Status row */}
        <div className="lms-detail-panel__status-row">
          <StatusDot status={connection.status} />
          <span className="lms-detail-panel__last-sync">Last synced: {lastSync}</span>
        </div>

        {/* Stats */}
        <div className="lms-detail-panel__stats">
          <div className="lms-detail-stat">
            <span className="lms-detail-stat__value">{connection.courses_synced}</span>
            <span className="lms-detail-stat__label">Courses synced</span>
          </div>
          {connection.status === 'connected' && (
            <div className="lms-detail-stat">
              <span className="lms-detail-stat__value lms-detail-stat__value--green">Active</span>
              <span className="lms-detail-stat__label">Status</span>
            </div>
          )}
        </div>

        {/* Sync error */}
        {connection.sync_error && (
          <div className="lms-detail-panel__error">
            <strong>Last error:</strong> {connection.sync_error}
          </div>
        )}

        {/* Sync feedback */}
        {syncMsg && (
          <div
            className={
              syncMsg.includes('fail')
                ? 'lms-detail-panel__feedback lms-detail-panel__feedback--error'
                : 'lms-detail-panel__feedback lms-detail-panel__feedback--success'
            }
          >
            {syncMsg}
          </div>
        )}

        {/* Courses list placeholder */}
        {connection.courses_synced > 0 && (
          <div className="lms-detail-panel__courses">
            <h3 className="lms-detail-panel__courses-title">Synced Courses</h3>
            <div className="lms-detail-panel__courses-list">
              <div className="lms-detail-panel__courses-placeholder">
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  aria-hidden="true"
                >
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
                </svg>
                {connection.courses_synced} course
                {connection.courses_synced !== 1 ? 's' : ''} synced from {displayName}.
                View them in the{' '}
                <a href="/courses" className="lms-link">
                  Courses page
                </a>
                .
              </div>
            </div>
          </div>
        )}

        {/* Provider badge note */}
        <div className="lms-detail-panel__badge-note">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
          Provider badges appear on synced courses in your dashboard
        </div>

        {/* Actions */}
        <div className="lms-detail-panel__actions">
          {connection.status === 'connected' || connection.status === 'error' ? (
            <button
              className="lms-btn lms-btn--primary"
              onClick={handleSync}
              disabled={syncing}
            >
              {syncing ? (
                <>
                  <span className="lms-spinner" aria-hidden="true" /> Syncing…
                </>
              ) : (
                'Sync Now'
              )}
            </button>
          ) : null}
          <button
            className="lms-btn lms-btn--danger"
            onClick={() => setConfirmDisconnect(true)}
          >
            Disconnect
          </button>
        </div>
      </div>

      {confirmDisconnect && (
        <ConfirmDialog
          message={`Disconnect from ${displayName}? Your synced courses will remain but won't update.`}
          confirmLabel="Disconnect"
          onConfirm={handleDisconnect}
          onCancel={() => setConfirmDisconnect(false)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Provider Card
// ---------------------------------------------------------------------------

interface ProviderCardProps {
  provider: LMSProvider;
  connections: LMSConnection[];
  onConnect: (provider: LMSProvider) => void;
  onManage: (connection: LMSConnection) => void;
}

function ProviderCard({ provider, connections, onConnect, onManage }: ProviderCardProps) {
  const meta = providerMeta(provider.provider_id);
  const userConnections = connections.filter((c) => c.provider === provider.provider_id);
  const primaryConn = userConnections[0] ?? null;
  const isConnected = primaryConn?.status === 'connected';
  const hasConnection = primaryConn !== null;
  const isComingSoon = meta.comingSoon === true;

  const statusLabel = isConnected
    ? 'Connected'
    : primaryConn?.status === 'expired'
    ? 'Token Expired — Reconnect'
    : primaryConn?.status === 'error'
    ? 'Sync Error'
    : null;

  return (
    <div
      className={`lms-provider-card ${isConnected ? 'lms-provider-card--connected' : ''} ${isComingSoon ? 'lms-provider-card--coming-soon' : ''}`}
    >
      {/* Header */}
      <div className="lms-provider-card__header">
        <ProviderLogo providerId={provider.provider_id} />
        <div className="lms-provider-card__info">
          <div className="lms-provider-card__name">{meta.tagline}</div>
          {isConnected && (
            <div className="lms-provider-card__connected-indicator">
              <span className="lms-green-dot" aria-hidden="true" />
              Connected
            </div>
          )}
          {statusLabel && !isConnected && (
            <div className="lms-provider-card__status-label">{statusLabel}</div>
          )}
        </div>
      </div>

      <div className="lms-provider-card__divider" />

      {/* Body */}
      {isConnected && primaryConn ? (
        <div className="lms-provider-card__connected-body">
          <div className="lms-provider-card__stat-row">
            <span className="lms-provider-card__stat-icon" aria-hidden="true">📚</span>
            <span>{primaryConn.courses_synced} course{primaryConn.courses_synced !== 1 ? 's' : ''} synced</span>
          </div>
          <div className="lms-provider-card__stat-row">
            <span className="lms-provider-card__stat-icon" aria-hidden="true">🔄</span>
            <span>Last sync: {formatRelativeTime(primaryConn.last_sync_at)}</span>
          </div>
          {primaryConn.institution_name && (
            <div className="lms-provider-card__stat-row">
              <span className="lms-provider-card__stat-icon" aria-hidden="true">🏫</span>
              <span className="lms-provider-card__institution-name">{primaryConn.institution_name}</span>
            </div>
          )}
        </div>
      ) : (
        <p className="lms-provider-card__description">{meta.description}</p>
      )}

      {/* Footer actions */}
      <div className="lms-provider-card__footer">
        {isComingSoon ? (
          <span className="lms-coming-soon-tag">Coming Soon</span>
        ) : isConnected && primaryConn ? (
          <>
            <button
              className="lms-btn lms-btn--sm lms-btn--outline"
              onClick={() => onManage(primaryConn)}
            >
              Manage
            </button>
          </>
        ) : hasConnection && !isConnected ? (
          <button
            className="lms-btn lms-btn--sm lms-btn--primary"
            onClick={() => onConnect(provider)}
          >
            Reconnect
          </button>
        ) : (
          <button
            className="lms-btn lms-btn--sm lms-btn--primary"
            onClick={() => onConnect(provider)}
          >
            Connect
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// "More coming soon" placeholder card
// ---------------------------------------------------------------------------

function MoreComingSoonCard() {
  return (
    <div className="lms-provider-card lms-provider-card--coming-soon lms-provider-card--more">
      <div className="lms-provider-card__header">
        <div
          className="lms-provider-logo"
          style={{
            backgroundColor: MORE_COMING_SOON.color,
            width: 44,
            height: 44,
            fontSize: 20,
          }}
          aria-hidden="true"
        >
          {MORE_COMING_SOON.initials}
        </div>
        <div className="lms-provider-card__info">
          <div className="lms-provider-card__name">{MORE_COMING_SOON.tagline}</div>
        </div>
      </div>
      <div className="lms-provider-card__divider" />
      <p className="lms-provider-card__description">{MORE_COMING_SOON.description}</p>
      <div className="lms-provider-card__footer">
        <a
          href="mailto:support@classbridgeapp.com?subject=LMS%20Integration%20Request"
          className="lms-btn lms-btn--sm lms-btn--outline"
        >
          Contact Us
        </a>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function LMSConnectionsPage() {
  const [providers, setProviders] = useState<LMSProvider[]>([]);
  const [connections, setConnections] = useState<LMSConnection[]>([]);
  const [institutions, setInstitutions] = useState<LMSInstitution[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  // Modals / panels
  const [institutionSelectorProvider, setInstitutionSelectorProvider] =
    useState<LMSProvider | null>(null);
  const [detailConnection, setDetailConnection] = useState<LMSConnection | null>(null);

  // ── Load data ──────────────────────────────────────────────────────────

  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadError('');
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
      setLoadError('Failed to load connection data. Please refresh the page.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ── Actions ────────────────────────────────────────────────────────────

  const handleConnect = (provider: LMSProvider) => {
    if (provider.provider_id === 'google_classroom') {
      window.location.href = lmsConnectionsApi.getGoogleConnectUrl();
      return;
    }
    if (provider.provider_id === 'brightspace') {
      setInstitutionSelectorProvider(provider);
      return;
    }
    // Other providers: show institution selector or coming soon
    if (provider.requires_institution_url) {
      setInstitutionSelectorProvider(provider);
    }
  };

  const handleInstitutionSelect = (institutionId: number) => {
    setInstitutionSelectorProvider(null);
    // Redirect to Brightspace OAuth for the chosen institution
    window.location.href = lmsConnectionsApi.getBrightspaceConnectUrl(institutionId);
  };

  const handleSync = async (connectionId: number) => {
    const result = await lmsConnectionsApi.syncConnection(connectionId);
    setConnections((prev) =>
      prev.map((c) =>
        c.id === connectionId
          ? {
              ...c,
              status: result.status as LMSConnection['status'],
              last_sync_at: result.last_sync_at,
              sync_error: result.sync_error,
              courses_synced: result.courses_synced,
            }
          : c,
      ),
    );
    // Refresh the detail panel connection to reflect new state
    if (detailConnection?.id === connectionId) {
      setDetailConnection((prev) =>
        prev
          ? {
              ...prev,
              status: result.status as LMSConnection['status'],
              last_sync_at: result.last_sync_at,
              sync_error: result.sync_error,
              courses_synced: result.courses_synced,
            }
          : null,
      );
    }
  };

  const handleDisconnect = async (connectionId: number) => {
    await lmsConnectionsApi.deleteConnection(connectionId);
    setConnections((prev) => prev.filter((c) => c.id !== connectionId));
    setDetailConnection(null);
  };

  // ── Render ─────────────────────────────────────────────────────────────

  // Build the display list: registered providers first, then coming-soon
  const registeredProviderIds = providers.map((p) => p.provider_id);
  const allDisplayProviders: LMSProvider[] = [
    ...providers,
    // Show canvas as coming-soon even if not in the registry
    ...(['canvas'] as const)
      .filter((id) => !registeredProviderIds.includes(id))
      .map((id) => ({
        provider_id: id,
        display_name: PROVIDER_META[id]?.tagline ?? id,
        supports_oauth: false,
        requires_institution_url: false,
      })),
  ];

  const connectedCount = connections.filter((c) => c.status === 'connected').length;

  return (
    <DashboardLayout>
      <div className="lms-page">
        {/* Page header */}
        <div className="lms-page__header">
          <div className="lms-page__header-left">
            <h1 className="lms-page__title">Connected Learning Platforms</h1>
            <p className="lms-page__subtitle">
              Connect ClassBridge to your school's learning management systems to automatically
              sync courses, assignments, and materials.
            </p>
          </div>
          {connectedCount > 0 && (
            <div className="lms-page__header-badge">
              <span className="lms-green-dot" aria-hidden="true" />
              {connectedCount} platform{connectedCount !== 1 ? 's' : ''} connected
            </div>
          )}
        </div>

        {/* Loading / error */}
        {loading && (
          <div className="lms-loading">
            <span className="lms-spinner lms-spinner--lg" aria-hidden="true" />
            Loading connections…
          </div>
        )}
        {loadError && <div className="lms-error">{loadError}</div>}

        {/* Provider catalog */}
        {!loading && (
          <div className="lms-catalog-grid">
            {allDisplayProviders.map((provider) => (
              <ProviderCard
                key={provider.provider_id}
                provider={provider}
                connections={connections}
                onConnect={handleConnect}
                onManage={(conn) => setDetailConnection(conn)}
              />
            ))}
            <MoreComingSoonCard />
          </div>
        )}

        {/* Help text */}
        {!loading && (
          <div className="lms-page__help">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            Connections sync courses and assignments from your school's LMS into ClassBridge.
            Your data is never shared between institutions.
          </div>
        )}
      </div>

      {/* Institution selector modal (Brightspace / other institution-based providers) */}
      {institutionSelectorProvider && (
        <InstitutionSelectorModal
          provider={institutionSelectorProvider}
          institutions={institutions}
          onClose={() => setInstitutionSelectorProvider(null)}
          onSelect={handleInstitutionSelect}
        />
      )}

      {/* Connected provider detail panel */}
      {detailConnection && (
        <ConnectedDetailPanel
          connection={detailConnection}
          onClose={() => setDetailConnection(null)}
          onSync={handleSync}
          onDisconnect={handleDisconnect}
        />
      )}
    </DashboardLayout>
  );
}
