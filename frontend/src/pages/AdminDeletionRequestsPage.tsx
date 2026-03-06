import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { api } from '../api/client';
import './AdminDeletionRequestsPage.css';

interface DeletionRequestItem {
  user_id: number;
  email: string | null;
  full_name: string;
  role: string | null;
  deletion_requested_at: string | null;
  grace_period_ends_at: string | null;
}

interface DeletionRequestList {
  items: DeletionRequestItem[];
  total: number;
}

export function AdminDeletionRequestsPage() {
  const queryClient = useQueryClient();
  const [processingId, setProcessingId] = useState<number | null>(null);

  const { data, isLoading, error } = useQuery<DeletionRequestList>({
    queryKey: ['admin-deletion-requests'],
    queryFn: async () => {
      const res = await api.get('/api/admin/deletion-requests');
      return res.data;
    },
  });

  const processDeletion = useMutation({
    mutationFn: async (userId: number) => {
      const res = await api.post(`/api/admin/deletion-requests/${userId}/process`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-deletion-requests'] });
      setProcessingId(null);
    },
    onError: () => {
      setProcessingId(null);
    },
  });

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const isExpired = (graceEnd: string | null) => {
    if (!graceEnd) return false;
    return new Date(graceEnd) <= new Date();
  };

  return (
    <DashboardLayout>
      <div className="admin-deletion-page">
        <h1>Account Deletion Requests</h1>
        <p className="page-subtitle">
          Manage pending account deletion requests. Accounts are automatically anonymized
          after the 30-day grace period.
        </p>

        {isLoading && <p className="loading-text">Loading requests...</p>}
        {error && <p className="error-text">Failed to load deletion requests.</p>}

        {data && data.items.length === 0 && (
          <div className="empty-state">
            <p>No pending deletion requests.</p>
          </div>
        )}

        {data && data.items.length > 0 && (
          <div className="deletion-table-wrapper">
            <table className="deletion-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th>Requested</th>
                  <th>Grace Period Ends</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.user_id}>
                    <td>
                      <div className="user-cell">
                        <span className="user-name">{item.full_name}</span>
                        <span className="user-email">{item.email || 'No email'}</span>
                      </div>
                    </td>
                    <td>
                      <span className="role-tag">{item.role || 'Unknown'}</span>
                    </td>
                    <td>{formatDate(item.deletion_requested_at)}</td>
                    <td>
                      <span className={isExpired(item.grace_period_ends_at) ? 'expired' : ''}>
                        {formatDate(item.grace_period_ends_at)}
                        {isExpired(item.grace_period_ends_at) && (
                          <span className="expired-badge">Expired</span>
                        )}
                      </span>
                    </td>
                    <td>
                      <span className="status-pending">Pending</span>
                    </td>
                    <td>
                      {processingId === item.user_id ? (
                        <div className="confirm-actions">
                          <span className="confirm-text">Confirm?</span>
                          <button
                            className="btn btn-sm btn-danger"
                            onClick={() => processDeletion.mutate(item.user_id)}
                            disabled={processDeletion.isPending}
                          >
                            {processDeletion.isPending ? '...' : 'Yes'}
                          </button>
                          <button
                            className="btn btn-sm btn-secondary"
                            onClick={() => setProcessingId(null)}
                          >
                            No
                          </button>
                        </div>
                      ) : (
                        <button
                          className="btn btn-sm btn-danger-outline"
                          onClick={() => setProcessingId(item.user_id)}
                        >
                          Process Now
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="table-footer">
              <span className="total-count">{data.total} pending request(s)</span>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
