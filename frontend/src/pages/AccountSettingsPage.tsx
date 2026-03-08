import { useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { accountDeletionApi } from '../api/accountDeletion';
import { authApi } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import './AccountSettingsPage.css';

export function AccountSettingsPage() {
  const { user, refreshUser } = useAuth();
  const queryClient = useQueryClient();
  const [showConfirm, setShowConfirm] = useState(false);
  const [confirmText, setConfirmText] = useState('');

  // Interests state
  const [interests, setInterests] = useState<string[]>(user?.interests ?? []);
  const [interestInput, setInterestInput] = useState('');
  const [interestsSaved, setInterestsSaved] = useState(false);
  const interestInputRef = useRef<HTMLInputElement>(null);

  const interestsMutation = useMutation({
    mutationFn: (newInterests: string[]) => authApi.updateInterests(newInterests),
    onSuccess: () => {
      refreshUser();
      setInterestsSaved(true);
      setTimeout(() => setInterestsSaved(false), 3000);
    },
  });

  const addInterest = (value: string) => {
    const trimmed = value.trim().toLowerCase();
    if (!trimmed || trimmed.length > 50 || interests.length >= 10 || interests.includes(trimmed)) return;
    setInterests(prev => [...prev, trimmed]);
    setInterestInput('');
  };

  const removeInterest = (index: number) => {
    setInterests(prev => prev.filter((_, i) => i !== index));
  };

  const handleInterestKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addInterest(interestInput);
    } else if (e.key === 'Backspace' && !interestInput && interests.length > 0) {
      removeInterest(interests.length - 1);
    }
  };

  const statusQuery = useQuery({
    queryKey: ['deletionStatus'],
    queryFn: accountDeletionApi.getStatus,
  });

  const requestMutation = useMutation({
    mutationFn: accountDeletionApi.requestDeletion,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deletionStatus'] });
      setShowConfirm(false);
      setConfirmText('');
    },
  });

  const cancelMutation = useMutation({
    mutationFn: accountDeletionApi.cancelDeletion,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deletionStatus'] });
    },
  });

  const status = statusQuery.data;
  const isPending = status?.deletion_requested && !status?.deletion_confirmed;
  const isConfirmed = status?.deletion_confirmed;

  const handleRequestDeletion = (e: React.FormEvent) => {
    e.preventDefault();
    if (confirmText !== 'DELETE') return;
    requestMutation.mutate();
  };

  return (
    <DashboardLayout>
      <div className="account-settings">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Account Settings' },
        ]} />

        <h1 className="account-settings-title">Account Settings</h1>

        <section className="account-section">
          <h2>Account Information</h2>
          <div className="account-info-grid">
            <div className="account-info-item">
              <span className="account-info-label">Name</span>
              <span className="account-info-value">{user?.full_name}</span>
            </div>
            <div className="account-info-item">
              <span className="account-info-label">Email</span>
              <span className="account-info-value">{user?.email || 'Not set'}</span>
            </div>
            <div className="account-info-item">
              <span className="account-info-label">Role</span>
              <span className="account-info-value">{user?.roles?.join(', ') || user?.role || 'N/A'}</span>
            </div>
          </div>
        </section>

        <section className="account-section">
          <h2>Learn Your Way</h2>
          <p className="account-interests-desc">
            Add your interests and hobbies so AI-generated study materials use relatable examples. Up to 10 interests.
          </p>
          <div className="interests-tag-input" onClick={() => interestInputRef.current?.focus()}>
            <div className="interests-tags">
              {interests.map((interest, i) => (
                <span key={i} className="interest-tag">
                  {interest}
                  <button type="button" className="interest-tag-remove" onClick={() => removeInterest(i)}>&times;</button>
                </span>
              ))}
              {interests.length < 10 && (
                <input
                  ref={interestInputRef}
                  type="text"
                  className="interest-input"
                  value={interestInput}
                  onChange={e => setInterestInput(e.target.value)}
                  onKeyDown={handleInterestKeyDown}
                  placeholder={interests.length === 0 ? 'Type an interest and press Enter...' : ''}
                  maxLength={50}
                />
              )}
            </div>
          </div>
          <div className="interests-actions">
            <span className="interests-count">{interests.length}/10</span>
            <button
              className="account-btn account-btn-save-interests"
              onClick={() => interestsMutation.mutate(interests)}
              disabled={interestsMutation.isPending || JSON.stringify(interests) === JSON.stringify(user?.interests ?? [])}
            >
              {interestsMutation.isPending ? 'Saving...' : interestsSaved ? 'Saved!' : 'Save Interests'}
            </button>
          </div>
          {interestsMutation.isError && (
            <p className="account-error" style={{ marginTop: 8 }}>Failed to save interests.</p>
          )}
        </section>

        <section className="account-section account-danger-zone">
          <h2>Danger Zone</h2>
          <div className="danger-zone-content">
            <div className="danger-zone-info">
              <h3>Delete Account</h3>
              <p>
                Permanently delete your account and all associated data. This action
                cannot be undone after the 30-day grace period.
              </p>
            </div>

            {statusQuery.isLoading && <p className="account-loading">Loading status...</p>}

            {isConfirmed && (
              <div className="deletion-status deletion-status-confirmed">
                <p>
                  Your account deletion has been confirmed. Your account is deactivated
                  and will be permanently anonymized after 30 days
                  {status?.deletion_confirmed_at && (
                    <> (confirmed on {new Date(status.deletion_confirmed_at).toLocaleDateString()})</>
                  )}.
                </p>
                <button
                  className="account-btn account-btn-cancel-deletion"
                  onClick={() => cancelMutation.mutate()}
                  disabled={cancelMutation.isPending}
                >
                  {cancelMutation.isPending ? 'Cancelling...' : 'Cancel Deletion & Reactivate'}
                </button>
              </div>
            )}

            {isPending && !isConfirmed && (
              <div className="deletion-status deletion-status-pending">
                <p>
                  A deletion request is pending. Check your email for a confirmation link.
                </p>
                <button
                  className="account-btn account-btn-cancel-deletion"
                  onClick={() => cancelMutation.mutate()}
                  disabled={cancelMutation.isPending}
                >
                  {cancelMutation.isPending ? 'Cancelling...' : 'Cancel Deletion Request'}
                </button>
              </div>
            )}

            {!isPending && !isConfirmed && !statusQuery.isLoading && (
              <>
                {!showConfirm ? (
                  <button
                    className="account-btn account-btn-delete"
                    onClick={() => setShowConfirm(true)}
                  >
                    Request Account Deletion
                  </button>
                ) : (
                  <form className="deletion-confirm-form" onSubmit={handleRequestDeletion}>
                    <p className="deletion-confirm-warning">
                      This will send a confirmation email to <strong>{user?.email}</strong>.
                      After you confirm via email, your account will be deactivated immediately
                      and permanently anonymized after 30 days.
                    </p>
                    <label htmlFor="confirmDelete" className="deletion-confirm-label">
                      Type <strong>DELETE</strong> to proceed:
                    </label>
                    <input
                      id="confirmDelete"
                      type="text"
                      value={confirmText}
                      onChange={(e) => setConfirmText(e.target.value)}
                      placeholder="DELETE"
                      className="deletion-confirm-input"
                      autoComplete="off"
                    />
                    {requestMutation.isError && (
                      <p className="account-error">
                        {(requestMutation.error as Error & { response?: { data?: { detail?: string } } })
                          ?.response?.data?.detail || 'Failed to request deletion.'}
                      </p>
                    )}
                    <div className="deletion-confirm-actions">
                      <button
                        type="button"
                        className="account-btn account-btn-secondary"
                        onClick={() => { setShowConfirm(false); setConfirmText(''); }}
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="account-btn account-btn-delete"
                        disabled={confirmText !== 'DELETE' || requestMutation.isPending}
                      >
                        {requestMutation.isPending ? 'Requesting...' : 'Confirm Deletion Request'}
                      </button>
                    </div>
                  </form>
                )}
              </>
            )}

            {cancelMutation.isError && (
              <p className="account-error">
                {(cancelMutation.error as Error & { response?: { data?: { detail?: string } } })
                  ?.response?.data?.detail || 'Failed to cancel deletion.'}
              </p>
            )}
          </div>
        </section>
      </div>
    </DashboardLayout>
  );
}
