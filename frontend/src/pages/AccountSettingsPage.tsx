import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { accountDeletionApi } from '../api/accountDeletion';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import { StorageUsageBar } from '../components/StorageUsageBar';
import './AccountSettingsPage.css';

export function AccountSettingsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [showConfirm, setShowConfirm] = useState(false);
  const [confirmText, setConfirmText] = useState('');

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
          <h2>Storage Usage</h2>
          <StorageUsageBar
            usedBytes={user?.storage_used_bytes ?? 0}
            limitBytes={user?.storage_limit_bytes ?? 104857600}
            uploadLimitBytes={user?.upload_limit_bytes ?? 10485760}
          />
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
