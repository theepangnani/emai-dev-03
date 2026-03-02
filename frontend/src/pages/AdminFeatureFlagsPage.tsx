import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  featureFlagsApi,
  FeatureFlagResponse,
  FeatureFlagCreate,
  OverrideResponse,
  FlagScope,
} from '../api/featureFlags';
import './AdminFeatureFlagsPage.css';

// ─── Types ────────────────────────────────────────────────────────────────────

const SCOPES: FlagScope[] = ['global', 'tier', 'role', 'user', 'beta'];
const ALL_TIERS = ['free', 'premium'];
const ALL_ROLES = ['student', 'parent', 'teacher', 'admin'];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function scopeLabel(scope: string): string {
  const map: Record<string, string> = {
    global: 'Global',
    tier: 'Tier',
    role: 'Role',
    user: 'User',
    beta: 'Beta',
  };
  return map[scope] ?? scope;
}

// ─── New Flag Modal ───────────────────────────────────────────────────────────

interface NewFlagModalProps {
  onClose: () => void;
  onCreated: (flag: FeatureFlagResponse) => void;
}

function NewFlagModal({ onClose, onCreated }: NewFlagModalProps) {
  const [key, setKey] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [scope, setScope] = useState<FlagScope>('global');
  const [isEnabled, setIsEnabled] = useState(false);
  const [rollout, setRollout] = useState(100);
  const [tiers, setTiers] = useState<string[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!key.trim() || !name.trim()) {
      setError('Key and Name are required.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const payload: FeatureFlagCreate = {
        key: key.trim().toLowerCase().replace(/\s+/g, '_'),
        name: name.trim(),
        description: description.trim() || undefined,
        scope,
        is_enabled: isEnabled,
        rollout_percentage: rollout,
        enabled_tiers: tiers,
        enabled_roles: roles,
        enabled_user_ids: [],
      };
      const created = await featureFlagsApi.create(payload);
      onCreated(created);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e.response?.data?.detail ?? 'Failed to create flag.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal aff-modal"
        role="dialog"
        aria-modal="true"
        aria-label="New Feature Flag"
        onClick={(e) => e.stopPropagation()}
      >
        <h2>New Feature Flag</h2>

        <div className="aff-form-group">
          <label>Key</label>
          <input
            type="text"
            placeholder="e.g. my_feature"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            className="aff-input"
          />
          <span className="aff-hint">Snake_case, unique identifier. Cannot be changed later.</span>
        </div>

        <div className="aff-form-group">
          <label>Name</label>
          <input
            type="text"
            placeholder="Human-readable name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="aff-input"
          />
        </div>

        <div className="aff-form-group">
          <label>Description</label>
          <textarea
            placeholder="What does this flag control?"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="aff-textarea"
            rows={2}
          />
        </div>

        <div className="aff-form-row">
          <div className="aff-form-group aff-form-group--half">
            <label>Scope</label>
            <select value={scope} onChange={(e) => setScope(e.target.value as FlagScope)} className="aff-select">
              {SCOPES.map((s) => (
                <option key={s} value={s}>{scopeLabel(s)}</option>
              ))}
            </select>
          </div>

          {scope === 'global' && (
            <div className="aff-form-group aff-form-group--half">
              <label>Rollout %</label>
              <div className="aff-rollout-row">
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={rollout}
                  onChange={(e) => setRollout(Number(e.target.value))}
                  className="aff-slider"
                />
                <span className="aff-rollout-val">{rollout}%</span>
              </div>
            </div>
          )}
        </div>

        {scope === 'global' && (
          <div className="aff-form-group">
            <label className="aff-toggle-label">
              <input
                type="checkbox"
                checked={isEnabled}
                onChange={(e) => setIsEnabled(e.target.checked)}
              />
              Enabled
            </label>
          </div>
        )}

        {scope === 'tier' && (
          <div className="aff-form-group">
            <label>Enabled for tiers</label>
            <div className="aff-checkbox-group">
              {ALL_TIERS.map((t) => (
                <label key={t} className="aff-checkbox-label">
                  <input
                    type="checkbox"
                    checked={tiers.includes(t)}
                    onChange={(e) =>
                      setTiers((prev) =>
                        e.target.checked ? [...prev, t] : prev.filter((x) => x !== t)
                      )
                    }
                  />
                  {t}
                </label>
              ))}
            </div>
          </div>
        )}

        {(scope === 'role') && (
          <div className="aff-form-group">
            <label>Enabled for roles</label>
            <div className="aff-checkbox-group">
              {ALL_ROLES.map((r) => (
                <label key={r} className="aff-checkbox-label">
                  <input
                    type="checkbox"
                    checked={roles.includes(r)}
                    onChange={(e) =>
                      setRoles((prev) =>
                        e.target.checked ? [...prev, r] : prev.filter((x) => x !== r)
                      )
                    }
                  />
                  {r}
                </label>
              ))}
            </div>
          </div>
        )}

        {(scope === 'user' || scope === 'beta') && (
          <p className="aff-hint">
            User IDs can be added via the User Overrides section after creating the flag.
          </p>
        )}

        {error && <p className="aff-error">{error}</p>}

        <div className="modal-actions">
          <button className="cancel-btn" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="submit-btn" onClick={handleSubmit} disabled={saving}>
            {saving ? 'Creating...' : 'Create Flag'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Edit Flag Modal ──────────────────────────────────────────────────────────

interface EditFlagModalProps {
  flag: FeatureFlagResponse;
  onClose: () => void;
  onUpdated: (flag: FeatureFlagResponse) => void;
}

function EditFlagModal({ flag, onClose, onUpdated }: EditFlagModalProps) {
  const [name, setName] = useState(flag.name);
  const [description, setDescription] = useState(flag.description ?? '');
  const [scope, setScope] = useState<FlagScope>(flag.scope);
  const [isEnabled, setIsEnabled] = useState(flag.is_enabled);
  const [rollout, setRollout] = useState(flag.rollout_percentage);
  const [tiers, setTiers] = useState<string[]>(flag.enabled_tiers);
  const [roles, setRoles] = useState<string[]>(flag.enabled_roles);
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
      const updated = await featureFlagsApi.update(flag.key, {
        name: name.trim(),
        description: description.trim() || undefined,
        scope,
        is_enabled: isEnabled,
        rollout_percentage: rollout,
        enabled_tiers: tiers,
        enabled_roles: roles,
      });
      onUpdated(updated);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e.response?.data?.detail ?? 'Failed to save flag.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal aff-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Edit Feature Flag"
        onClick={(e) => e.stopPropagation()}
      >
        <h2>Edit: <code>{flag.key}</code></h2>

        <div className="aff-form-group">
          <label>Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="aff-input"
          />
        </div>

        <div className="aff-form-group">
          <label>Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="aff-textarea"
            rows={2}
          />
        </div>

        <div className="aff-form-row">
          <div className="aff-form-group aff-form-group--half">
            <label>Scope</label>
            <select value={scope} onChange={(e) => setScope(e.target.value as FlagScope)} className="aff-select">
              {SCOPES.map((s) => (
                <option key={s} value={s}>{scopeLabel(s)}</option>
              ))}
            </select>
          </div>

          {scope === 'global' && (
            <div className="aff-form-group aff-form-group--half">
              <label>Rollout %</label>
              <div className="aff-rollout-row">
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={rollout}
                  onChange={(e) => setRollout(Number(e.target.value))}
                  className="aff-slider"
                />
                <span className="aff-rollout-val">{rollout}%</span>
              </div>
            </div>
          )}
        </div>

        {scope === 'global' && (
          <div className="aff-form-group">
            <label className="aff-toggle-label">
              <input
                type="checkbox"
                checked={isEnabled}
                onChange={(e) => setIsEnabled(e.target.checked)}
              />
              Enabled globally
            </label>
          </div>
        )}

        {scope === 'tier' && (
          <div className="aff-form-group">
            <label>Enabled for tiers</label>
            <div className="aff-checkbox-group">
              {ALL_TIERS.map((t) => (
                <label key={t} className="aff-checkbox-label">
                  <input
                    type="checkbox"
                    checked={tiers.includes(t)}
                    onChange={(e) =>
                      setTiers((prev) =>
                        e.target.checked ? [...prev, t] : prev.filter((x) => x !== t)
                      )
                    }
                  />
                  {t}
                </label>
              ))}
            </div>
          </div>
        )}

        {scope === 'role' && (
          <div className="aff-form-group">
            <label>Enabled for roles</label>
            <div className="aff-checkbox-group">
              {ALL_ROLES.map((r) => (
                <label key={r} className="aff-checkbox-label">
                  <input
                    type="checkbox"
                    checked={roles.includes(r)}
                    onChange={(e) =>
                      setRoles((prev) =>
                        e.target.checked ? [...prev, r] : prev.filter((x) => x !== r)
                      )
                    }
                  />
                  {r}
                </label>
              ))}
            </div>
          </div>
        )}

        {(scope === 'user' || scope === 'beta') && (
          <p className="aff-hint">
            Manage user IDs in the User Overrides section below.
          </p>
        )}

        {error && <p className="aff-error">{error}</p>}

        <div className="modal-actions">
          <button className="cancel-btn" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="submit-btn" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Add Override Modal ───────────────────────────────────────────────────────

interface AddOverrideModalProps {
  flags: FeatureFlagResponse[];
  onClose: () => void;
  onCreated: (override: OverrideResponse) => void;
}

function AddOverrideModal({ flags, onClose, onCreated }: AddOverrideModalProps) {
  const [userId, setUserId] = useState('');
  const [flagKey, setFlagKey] = useState(flags[0]?.key ?? '');
  const [isEnabled, setIsEnabled] = useState(true);
  const [reason, setReason] = useState('');
  const [expiresAt, setExpiresAt] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    const uid = parseInt(userId, 10);
    if (!userId || isNaN(uid)) {
      setError('Enter a valid user ID.');
      return;
    }
    if (!flagKey) {
      setError('Select a flag.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const created = await featureFlagsApi.createOverride({
        user_id: uid,
        flag_key: flagKey,
        is_enabled: isEnabled,
        reason: reason.trim() || undefined,
        expires_at: expiresAt || null,
      });
      onCreated(created);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e.response?.data?.detail ?? 'Failed to create override.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal aff-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Add User Override"
        onClick={(e) => e.stopPropagation()}
      >
        <h2>Add User Override</h2>

        <div className="aff-form-group">
          <label>User ID</label>
          <input
            type="number"
            placeholder="User ID"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className="aff-input"
          />
        </div>

        <div className="aff-form-group">
          <label>Feature Flag</label>
          <select value={flagKey} onChange={(e) => setFlagKey(e.target.value)} className="aff-select">
            {flags.map((f) => (
              <option key={f.key} value={f.key}>{f.name} ({f.key})</option>
            ))}
          </select>
        </div>

        <div className="aff-form-group">
          <label className="aff-toggle-label">
            <input
              type="checkbox"
              checked={isEnabled}
              onChange={(e) => setIsEnabled(e.target.checked)}
            />
            Enable for this user
          </label>
        </div>

        <div className="aff-form-group">
          <label>Reason (optional)</label>
          <input
            type="text"
            placeholder="Admin note"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="aff-input"
          />
        </div>

        <div className="aff-form-group">
          <label>Expires at (optional)</label>
          <input
            type="datetime-local"
            value={expiresAt}
            onChange={(e) => setExpiresAt(e.target.value)}
            className="aff-input"
          />
        </div>

        {error && <p className="aff-error">{error}</p>}

        <div className="modal-actions">
          <button className="cancel-btn" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="submit-btn" onClick={handleSubmit} disabled={saving}>
            {saving ? 'Saving...' : 'Add Override'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function AdminFeatureFlagsPage() {
  const [flags, setFlags] = useState<FeatureFlagResponse[]>([]);
  const [overrides, setOverrides] = useState<OverrideResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Modal state
  const [showNewFlag, setShowNewFlag] = useState(false);
  const [editFlag, setEditFlag] = useState<FeatureFlagResponse | null>(null);
  const [showAddOverride, setShowAddOverride] = useState(false);

  // Delete state
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [deletingOverrideId, setDeletingOverrideId] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [flagsData, overridesData] = await Promise.all([
        featureFlagsApi.adminList(),
        featureFlagsApi.listOverrides({ limit: 200 }),
      ]);
      setFlags(flagsData);
      setOverrides(overridesData.items);
    } catch {
      setError('Failed to load feature flags.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleQuickToggle = async (flag: FeatureFlagResponse) => {
    try {
      const updated = await featureFlagsApi.update(flag.key, { is_enabled: !flag.is_enabled });
      setFlags((prev) => prev.map((f) => (f.key === flag.key ? updated : f)));
    } catch {
      setError('Failed to toggle flag.');
    }
  };

  const handleDeleteFlag = async (key: string) => {
    if (!window.confirm(`Delete flag "${key}" and all its overrides? This cannot be undone.`)) return;
    setDeletingKey(key);
    try {
      await featureFlagsApi.delete(key);
      setFlags((prev) => prev.filter((f) => f.key !== key));
      setOverrides((prev) => prev.filter((o) => o.flag_key !== key));
    } catch {
      setError('Failed to delete flag.');
    } finally {
      setDeletingKey(null);
    }
  };

  const handleDeleteOverride = async (id: number) => {
    setDeletingOverrideId(id);
    try {
      await featureFlagsApi.deleteOverride(id);
      setOverrides((prev) => prev.filter((o) => o.id !== id));
    } catch {
      setError('Failed to remove override.');
    } finally {
      setDeletingOverrideId(null);
    }
  };

  const handleSeed = async () => {
    try {
      await featureFlagsApi.seed();
      await loadData();
    } catch {
      setError('Failed to seed flags.');
    }
  };

  const scopeDetails = (flag: FeatureFlagResponse): string => {
    if (flag.scope === 'tier') return flag.enabled_tiers.join(', ') || '—';
    if (flag.scope === 'role') return flag.enabled_roles.join(', ') || '—';
    if (flag.scope === 'user' || flag.scope === 'beta')
      return `${flag.enabled_user_ids.length} user(s)`;
    return '—';
  };

  return (
    <DashboardLayout welcomeSubtitle="Platform administration">
      <div className="aff-page">
        {/* Header */}
        <div className="aff-header">
          <h2 className="aff-title">Feature Flags</h2>
          <div className="aff-header-actions">
            <button className="aff-btn-secondary" onClick={handleSeed}>
              Seed Defaults
            </button>
            <button className="aff-btn-primary" onClick={() => setShowNewFlag(true)}>
              + New Flag
            </button>
          </div>
        </div>

        {error && <p className="aff-error aff-error--page">{error}</p>}

        {/* Flags Table */}
        <section className="aff-section">
          {loading ? (
            <p className="aff-loading">Loading flags...</p>
          ) : flags.length === 0 ? (
            <div className="aff-empty">
              <p>No feature flags yet.</p>
              <button className="aff-btn-primary" onClick={handleSeed}>
                Seed Default Flags
              </button>
            </div>
          ) : (
            <table className="aff-table">
              <thead>
                <tr>
                  <th>Flag</th>
                  <th>Scope</th>
                  <th>Details</th>
                  <th>Status</th>
                  <th>Rollout</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {flags.map((flag) => (
                  <tr key={flag.key}>
                    <td>
                      <div className="aff-flag-name">{flag.name}</div>
                      <div className="aff-flag-key">{flag.key}</div>
                      {flag.description && (
                        <div className="aff-flag-desc">{flag.description}</div>
                      )}
                    </td>
                    <td>
                      <span className={`aff-scope-badge aff-scope--${flag.scope}`}>
                        {scopeLabel(flag.scope)}
                      </span>
                    </td>
                    <td className="aff-details-cell">{scopeDetails(flag)}</td>
                    <td>
                      <button
                        className={`aff-status-toggle ${flag.is_enabled ? 'aff-status--on' : 'aff-status--off'}`}
                        onClick={() => handleQuickToggle(flag)}
                        title={flag.scope !== 'global' ? 'Toggle global default' : undefined}
                      >
                        <span className="aff-status-dot" />
                        {flag.is_enabled ? 'ON' : 'OFF'}
                      </button>
                    </td>
                    <td>
                      {flag.scope === 'global' ? `${flag.rollout_percentage}%` : '—'}
                    </td>
                    <td>
                      <div className="aff-actions">
                        <button
                          className="aff-btn-edit"
                          onClick={() => setEditFlag(flag)}
                        >
                          Edit
                        </button>
                        <button
                          className="aff-btn-delete"
                          onClick={() => handleDeleteFlag(flag.key)}
                          disabled={deletingKey === flag.key}
                        >
                          {deletingKey === flag.key ? '...' : 'Delete'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        {/* User Overrides */}
        <div className="aff-header aff-header--sub">
          <h3 className="aff-subtitle">User Overrides</h3>
          <button
            className="aff-btn-primary"
            onClick={() => setShowAddOverride(true)}
            disabled={flags.length === 0}
          >
            + Add Override
          </button>
        </div>

        <section className="aff-section">
          {overrides.length === 0 ? (
            <p className="aff-empty-text">No user overrides yet.</p>
          ) : (
            <table className="aff-table">
              <thead>
                <tr>
                  <th>User ID</th>
                  <th>Flag</th>
                  <th>Status</th>
                  <th>Reason</th>
                  <th>Expires</th>
                  <th>Remove</th>
                </tr>
              </thead>
              <tbody>
                {overrides.map((o) => (
                  <tr key={o.id}>
                    <td>#{o.user_id}</td>
                    <td>
                      <code className="aff-flag-key">{o.flag_key}</code>
                    </td>
                    <td>
                      <span className={`aff-status-badge ${o.is_enabled ? 'aff-status--on' : 'aff-status--off'}`}>
                        <span className="aff-status-dot" />
                        {o.is_enabled ? 'ON' : 'OFF'}
                      </span>
                    </td>
                    <td>{o.reason ?? '—'}</td>
                    <td>
                      {o.expires_at
                        ? new Date(o.expires_at).toLocaleDateString()
                        : 'Never'}
                    </td>
                    <td>
                      <button
                        className="aff-btn-remove"
                        onClick={() => handleDeleteOverride(o.id)}
                        disabled={deletingOverrideId === o.id}
                        title="Remove override"
                      >
                        {deletingOverrideId === o.id ? '...' : '×'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      {/* Modals */}
      {showNewFlag && (
        <NewFlagModal
          onClose={() => setShowNewFlag(false)}
          onCreated={(flag) => {
            setFlags((prev) => [...prev, flag]);
            setShowNewFlag(false);
          }}
        />
      )}

      {editFlag && (
        <EditFlagModal
          flag={editFlag}
          onClose={() => setEditFlag(null)}
          onUpdated={(updated) => {
            setFlags((prev) => prev.map((f) => (f.key === updated.key ? updated : f)));
            setEditFlag(null);
          }}
        />
      )}

      {showAddOverride && (
        <AddOverrideModal
          flags={flags}
          onClose={() => setShowAddOverride(false)}
          onCreated={(override) => {
            setOverrides((prev) => {
              // Replace existing override for same user+flag, or prepend
              const idx = prev.findIndex(
                (o) => o.user_id === override.user_id && o.flag_key === override.flag_key
              );
              if (idx !== -1) {
                const updated = [...prev];
                updated[idx] = override;
                return updated;
              }
              return [override, ...prev];
            });
            setShowAddOverride(false);
          }}
        />
      )}
    </DashboardLayout>
  );
}
