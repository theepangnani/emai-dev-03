/**
 * APIKeysPage — create, list, and revoke API keys for MCP/external integrations (#905).
 * Route: /settings/api-keys
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiKeysApi, type APIKeyListItem, type APIKeyCreatedResponse } from '../api/apiKeys';
import { DashboardLayout } from '../components/DashboardLayout';
import './APIKeysPage.css';

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function keyStatus(key: APIKeyListItem): 'active' | 'expired' | 'revoked' {
  if (!key.is_active) return 'revoked';
  if (key.expires_at && new Date(key.expires_at) < new Date()) return 'expired';
  return 'active';
}

export function APIKeysPage() {
  const queryClient = useQueryClient();

  // ── Create modal state ──────────────────────────────────────────
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyExpires, setNewKeyExpires] = useState<string>('');
  const [createError, setCreateError] = useState('');

  // ── One-time display modal (shown after key creation) ───────────
  const [createdKey, setCreatedKey] = useState<APIKeyCreatedResponse | null>(null);
  const [copied, setCopied] = useState(false);

  // ── Revoke confirmation ─────────────────────────────────────────
  const [revokeTarget, setRevokeTarget] = useState<APIKeyListItem | null>(null);

  // ── Data ────────────────────────────────────────────────────────
  const { data: keys = [], isLoading, isError } = useQuery<APIKeyListItem[]>({
    queryKey: ['apiKeys'],
    queryFn: apiKeysApi.list,
  });

  const createMutation = useMutation({
    mutationFn: apiKeysApi.create,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['apiKeys'] });
      setShowCreateModal(false);
      setNewKeyName('');
      setNewKeyExpires('');
      setCreateError('');
      setCreatedKey(data);
      setCopied(false);
    },
    onError: (err: any) => {
      setCreateError(err?.response?.data?.detail || 'Failed to create API key.');
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: number) => apiKeysApi.revoke(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['apiKeys'] });
      setRevokeTarget(null);
    },
    onError: (err: any) => {
      alert(err?.response?.data?.detail || 'Failed to revoke key.');
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError('');
    const name = newKeyName.trim();
    if (!name) {
      setCreateError('Please enter a name for this key.');
      return;
    }
    const expires_days = newKeyExpires ? parseInt(newKeyExpires, 10) : null;
    createMutation.mutate({ name, expires_days });
  };

  const handleCopy = async () => {
    if (!createdKey) return;
    try {
      await navigator.clipboard.writeText(createdKey.key);
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
    } catch {
      // Fallback: select text
      const el = document.getElementById('created-key-display') as HTMLInputElement | null;
      el?.select();
    }
  };

  return (
    <DashboardLayout>
      <div className="api-keys-page">
        {/* Header */}
        <div className="api-keys-header">
          <div className="api-keys-header-text">
            <h1 className="api-keys-title">API Keys</h1>
            <p className="api-keys-subtitle">
              Use API keys to access ClassBridge data from external tools (e.g. Claude Desktop,
              custom integrations)
            </p>
          </div>
          <button
            className="api-keys-create-btn"
            onClick={() => { setShowCreateModal(true); setCreateError(''); }}
          >
            Create New API Key
          </button>
        </div>

        {/* Keys table */}
        {isLoading && <p className="api-keys-loading">Loading...</p>}
        {isError && <p className="api-keys-error">Failed to load API keys. Please try again.</p>}

        {!isLoading && !isError && keys.length === 0 && (
          <div className="api-keys-empty">
            <p>No API keys yet. Create one to connect external tools.</p>
          </div>
        )}

        {!isLoading && !isError && keys.length > 0 && (
          <div className="api-keys-table-wrapper">
            <table className="api-keys-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Key Preview</th>
                  <th>Created</th>
                  <th>Last Used</th>
                  <th>Expires</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {keys.map((key) => {
                  const status = keyStatus(key);
                  return (
                    <tr key={key.id} className={`api-keys-row api-keys-row-${status}`}>
                      <td className="api-keys-name">{key.name}</td>
                      <td className="api-keys-preview">
                        <code>{key.prefix}...</code>
                      </td>
                      <td>{formatDate(key.created_at)}</td>
                      <td>{formatDate(key.last_used_at)}</td>
                      <td>{formatDate(key.expires_at)}</td>
                      <td>
                        <span className={`api-keys-status api-keys-status-${status}`}>
                          {status === 'active' ? 'Active' : status === 'expired' ? 'Expired' : 'Revoked'}
                        </span>
                      </td>
                      <td>
                        {status === 'active' && (
                          <button
                            className="api-keys-revoke-btn"
                            onClick={() => setRevokeTarget(key)}
                          >
                            Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Info box */}
        <div className="api-keys-info-box">
          <strong>Using API Keys with the ClassBridge MCP Server</strong>
          <p>
            API keys can be used to access the ClassBridge MCP server from Claude Desktop or other
            MCP-compatible tools. Configure your MCP client with the key above and the server URL
            provided by your administrator. See documentation for details.
          </p>
          <p>
            <Link to="/settings/account">Account Settings</Link>
            {' | '}
            <Link to="/help">Help &amp; Support</Link>
          </p>
        </div>
      </div>

      {/* ── Create modal ──────────────────────────────────────────── */}
      {showCreateModal && (
        <div
          className="modal-overlay"
          onClick={() => { setShowCreateModal(false); setCreateError(''); setNewKeyName(''); setNewKeyExpires(''); }}
        >
          <div
            className="modal api-keys-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Create API Key"
            onClick={(e) => e.stopPropagation()}
          >
            <h2>Create New API Key</h2>
            <p className="api-keys-modal-desc">
              Give this key a descriptive name (e.g. "Claude Desktop" or "Home Automation").
            </p>
            <form onSubmit={handleCreate}>
              <div className="api-keys-form-field">
                <label htmlFor="api-key-name">Key Name</label>
                <input
                  id="api-key-name"
                  type="text"
                  placeholder="e.g. Claude Desktop"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  className="api-keys-input"
                  autoFocus
                  maxLength={100}
                />
              </div>
              <div className="api-keys-form-field">
                <label htmlFor="api-key-expires">Expires in (days, optional)</label>
                <input
                  id="api-key-expires"
                  type="number"
                  placeholder="e.g. 90 (leave blank for no expiry)"
                  value={newKeyExpires}
                  onChange={(e) => setNewKeyExpires(e.target.value)}
                  className="api-keys-input"
                  min={1}
                  max={365}
                />
              </div>
              {createError && <p className="api-keys-error">{createError}</p>}
              <div className="modal-actions">
                <button
                  type="button"
                  className="cancel-btn"
                  onClick={() => { setShowCreateModal(false); setCreateError(''); setNewKeyName(''); setNewKeyExpires(''); }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="submit-btn"
                  disabled={createMutation.isPending}
                >
                  {createMutation.isPending ? 'Creating...' : 'Create Key'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── One-time key display modal ────────────────────────────── */}
      {createdKey && (
        <div
          className="modal-overlay"
          onClick={() => setCreatedKey(null)}
        >
          <div
            className="modal api-keys-modal api-keys-created-modal"
            role="dialog"
            aria-modal="true"
            aria-label="API Key Created"
            onClick={(e) => e.stopPropagation()}
          >
            <h2>API Key Created</h2>
            <div className="api-keys-onetime-warning">
              This key will not be shown again. Copy it now and store it securely.
            </div>
            <p className="api-keys-created-name">
              <strong>{createdKey.name}</strong>
            </p>
            <div className="api-keys-created-key-container">
              <input
                id="created-key-display"
                type="text"
                readOnly
                value={createdKey.key}
                className="api-keys-created-key-input"
                onClick={(e) => (e.target as HTMLInputElement).select()}
              />
              <button
                className={`api-keys-copy-btn${copied ? ' api-keys-copy-btn-success' : ''}`}
                onClick={handleCopy}
              >
                {copied ? 'Copied!' : 'Copy'}
              </button>
            </div>
            {createdKey.expires_at && (
              <p className="api-keys-created-expires">
                Expires: {formatDate(createdKey.expires_at)}
              </p>
            )}
            <div className="modal-actions">
              <button
                className="submit-btn"
                onClick={() => setCreatedKey(null)}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Revoke confirmation dialog ────────────────────────────── */}
      {revokeTarget && (
        <div
          className="modal-overlay"
          onClick={() => setRevokeTarget(null)}
        >
          <div
            className="modal api-keys-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Revoke API Key"
            onClick={(e) => e.stopPropagation()}
          >
            <h2>Revoke API Key</h2>
            <p>
              Are you sure you want to revoke <strong>{revokeTarget.name}</strong>?
              Any integrations using this key will stop working immediately.
            </p>
            <div className="modal-actions">
              <button
                className="cancel-btn"
                onClick={() => setRevokeTarget(null)}
              >
                Cancel
              </button>
              <button
                className="danger-btn"
                onClick={() => revokeMutation.mutate(revokeTarget.id)}
                disabled={revokeMutation.isPending}
              >
                {revokeMutation.isPending ? 'Revoking...' : 'Revoke Key'}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
