/**
 * Account Settings page — BYOK AI key management (#578) and subscription tier (#1007).
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { profileApi, type AIKeyStatus } from '../api/profile';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import './AccountSettingsPage.css';

export function AccountSettingsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  // ── BYOK key management ──────────────────────────────────────
  const [showSetKeyModal, setShowSetKeyModal] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [keyError, setKeyError] = useState('');
  const [keySuccess, setKeySuccess] = useState('');

  const aiKeyQuery = useQuery<AIKeyStatus>({
    queryKey: ['aiKeyStatus'],
    queryFn: profileApi.getAIKeyStatus,
  });

  const setKeyMutation = useMutation({
    mutationFn: (apiKey: string) => profileApi.setAIKey(apiKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['aiKeyStatus'] });
      setShowSetKeyModal(false);
      setNewKey('');
      setKeyError('');
      setKeySuccess('API key saved successfully.');
      setTimeout(() => setKeySuccess(''), 4000);
    },
    onError: (err: any) => {
      setKeyError(err?.response?.data?.detail || 'Failed to save key.');
    },
  });

  const deleteKeyMutation = useMutation({
    mutationFn: profileApi.deleteAIKey,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['aiKeyStatus'] });
      setKeySuccess('API key removed. Platform key will be used.');
      setTimeout(() => setKeySuccess(''), 4000);
    },
    onError: (err: any) => {
      setKeyError(err?.response?.data?.detail || 'Failed to remove key.');
    },
  });

  const handleSetKey = (e: React.FormEvent) => {
    e.preventDefault();
    setKeyError('');
    const trimmed = newKey.trim();
    if (!trimmed) {
      setKeyError('Please enter an API key.');
      return;
    }
    if (!trimmed.startsWith('sk-')) {
      setKeyError("Key must start with 'sk-'.");
      return;
    }
    setKeyMutation.mutate(trimmed);
  };

  const keyStatus = aiKeyQuery.data;
  const tier = user?.subscription_tier ?? 'free';
  const limits = user?.limits;

  return (
    <DashboardLayout>
      <div className="account-settings">
        <h1 className="account-settings-title">Account Settings</h1>

        {/* ── Subscription Tier ────────────────────────────────── */}
        <section className="account-settings-section">
          <h2 className="account-settings-section-title">Subscription</h2>
          <div className="account-tier-row">
            <span className="account-tier-label">Current plan</span>
            <span className={`account-tier-badge account-tier-${tier}`}>
              {tier === 'premium' ? 'Premium' : 'Free'}
            </span>
          </div>
          {limits && (
            <ul className="account-limits-list">
              <li>Upload size: up to <strong>{limits.max_upload_size_mb} MB</strong> per file</li>
              <li>Files per session: up to <strong>{limits.max_session_files}</strong></li>
              <li>Study guides: up to <strong>{limits.max_study_guides}</strong></li>
            </ul>
          )}
          {tier === 'free' && (
            <p className="account-tier-upgrade-hint">
              Contact your administrator to upgrade to Premium for higher limits.
            </p>
          )}
        </section>

        {/* ── BYOK AI API Key ──────────────────────────────────── */}
        <section className="account-settings-section">
          <h2 className="account-settings-section-title">Your OpenAI / Anthropic API Key (Optional)</h2>
          <p className="account-settings-section-desc">
            Provide your own AI key to use for study guide, quiz, and flashcard generation.
            When set, your key is used instead of the shared platform key.
          </p>

          {aiKeyQuery.isLoading && <p className="account-settings-loading">Loading...</p>}

          {keySuccess && <p className="account-settings-success">{keySuccess}</p>}
          {keyError && !showSetKeyModal && <p className="account-settings-error">{keyError}</p>}

          {!aiKeyQuery.isLoading && (
            <>
              {keyStatus?.has_key ? (
                <div className="account-key-status">
                  <span className="account-key-preview">Key: <code>{keyStatus.key_preview}</code></span>
                  <div className="account-key-actions">
                    <button
                      className="account-btn account-btn-secondary"
                      onClick={() => { setShowSetKeyModal(true); setKeyError(''); }}
                    >
                      Replace
                    </button>
                    <button
                      className="account-btn account-btn-danger"
                      onClick={() => deleteKeyMutation.mutate()}
                      disabled={deleteKeyMutation.isPending}
                    >
                      {deleteKeyMutation.isPending ? 'Removing...' : 'Remove'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="account-key-status account-key-status-empty">
                  <span className="account-key-empty-label">No key set — using platform key</span>
                  <button
                    className="account-btn account-btn-primary"
                    onClick={() => { setShowSetKeyModal(true); setKeyError(''); }}
                  >
                    Set My Key
                  </button>
                </div>
              )}
            </>
          )}
        </section>
      </div>

      {/* ── Set / Replace Key Modal ──────────────────────────── */}
      {showSetKeyModal && (
        <div
          className="modal-overlay"
          onClick={() => { setShowSetKeyModal(false); setKeyError(''); setNewKey(''); }}
        >
          <div
            className="modal account-key-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Set API Key"
            onClick={(e) => e.stopPropagation()}
          >
            <h2>Set Your AI API Key</h2>
            <p className="account-key-modal-desc">
              Enter your Anthropic or OpenAI API key. It will be encrypted before storage and
              never displayed in full.
            </p>
            <form onSubmit={handleSetKey}>
              <label htmlFor="api-key-input" className="sr-only">API Key</label>
              <input
                id="api-key-input"
                type="password"
                autoComplete="off"
                placeholder="sk-..."
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                className="account-key-input"
              />
              {keyError && <p className="account-settings-error">{keyError}</p>}
              <div className="modal-actions">
                <button
                  type="button"
                  className="cancel-btn"
                  onClick={() => { setShowSetKeyModal(false); setKeyError(''); setNewKey(''); }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="submit-btn"
                  disabled={setKeyMutation.isPending}
                >
                  {setKeyMutation.isPending ? 'Saving...' : 'Save Key'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
