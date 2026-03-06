import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { api } from '../api/client';
import './AccountSettingsPage.css';

interface DeletionStatus {
  message: string;
  deletion_requested_at: string | null;
  grace_period_ends_at: string | null;
  grace_period_days: number;
}

export function AccountSettingsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [confirmText, setConfirmText] = useState('');

  const { data: deletionStatus, isLoading } = useQuery<DeletionStatus>({
    queryKey: ['deletion-status'],
    queryFn: async () => {
      const res = await api.get('/api/users/me/deletion-status');
      return res.data;
    },
  });

  const requestDeletion = useMutation({
    mutationFn: async () => {
      const res = await api.delete('/api/users/me');
      return res.data as DeletionStatus;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deletion-status'] });
      setShowConfirmModal(false);
      setConfirmText('');
    },
  });

  const cancelDeletion = useMutation({
    mutationFn: async () => {
      const res = await api.post('/api/users/me/cancel-deletion');
      return res.data as DeletionStatus;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deletion-status'] });
    },
  });

  const isPending = deletionStatus?.deletion_requested_at != null;

  const handleDeleteRequest = () => {
    if (confirmText !== 'DELETE') return;
    requestDeletion.mutate();
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  return (
    <DashboardLayout>
      <div className="account-settings-page">
        <h1>Account Settings</h1>

        <section className="settings-section">
          <h2>Account Information</h2>
          <div className="info-grid">
            <div className="info-item">
              <label>Name</label>
              <span>{user?.full_name}</span>
            </div>
            <div className="info-item">
              <label>Email</label>
              <span>{user?.email}</span>
            </div>
            <div className="info-item">
              <label>Role</label>
              <span className="role-badge">{user?.role}</span>
            </div>
          </div>
        </section>

        <section className="settings-section danger-zone">
          <h2>Danger Zone</h2>

          {isLoading ? (
            <p className="loading-text">Loading deletion status...</p>
          ) : isPending ? (
            <div className="deletion-pending-banner">
              <div className="banner-icon">&#9888;</div>
              <div className="banner-content">
                <h3>Account Deletion Pending</h3>
                <p>
                  Your account is scheduled for deletion on{' '}
                  <strong>{formatDate(deletionStatus?.grace_period_ends_at ?? null)}</strong>.
                  After this date, all your personal data will be permanently anonymized.
                </p>
                <p className="requested-date">
                  Requested on {formatDate(deletionStatus?.deletion_requested_at ?? null)}
                </p>
                <button
                  className="btn btn-cancel-deletion"
                  onClick={() => cancelDeletion.mutate()}
                  disabled={cancelDeletion.isPending}
                >
                  {cancelDeletion.isPending ? 'Cancelling...' : 'Cancel Deletion'}
                </button>
              </div>
            </div>
          ) : (
            <div className="delete-account-section">
              <p>
                Once you delete your account, all your personal data will be anonymized after a
                30-day grace period. This action affects your profile, messages, and study
                materials. Educational content you created will be preserved but disassociated
                from your identity.
              </p>
              <button
                className="btn btn-danger"
                onClick={() => setShowConfirmModal(true)}
              >
                Delete My Account
              </button>
            </div>
          )}
        </section>

        {showConfirmModal && (
          <div className="modal-overlay" onClick={() => setShowConfirmModal(false)}>
            <div className="modal delete-confirm-modal" onClick={(e) => e.stopPropagation()}>
              <h2>Are you sure?</h2>
              <p>
                This will schedule your account for permanent deletion. You will have 30 days
                to change your mind before all personal data is anonymized.
              </p>
              <p className="confirm-instruction">
                Type <strong>DELETE</strong> to confirm:
              </p>
              <input
                type="text"
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder="Type DELETE"
                className="confirm-input"
                autoFocus
              />
              {requestDeletion.isError && (
                <p className="error-text">
                  {(requestDeletion.error as any)?.response?.data?.detail || 'Failed to request deletion'}
                </p>
              )}
              <div className="modal-actions">
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    setShowConfirmModal(false);
                    setConfirmText('');
                  }}
                >
                  Cancel
                </button>
                <button
                  className="btn btn-danger"
                  onClick={handleDeleteRequest}
                  disabled={confirmText !== 'DELETE' || requestDeletion.isPending}
                >
                  {requestDeletion.isPending ? 'Processing...' : 'Delete My Account'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
