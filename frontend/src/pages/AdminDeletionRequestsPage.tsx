import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { accountDeletionApi } from '../api/accountDeletion';
import type { DeletionRequestItem } from '../api/accountDeletion';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import './AdminDeletionRequestsPage.css';

export function AdminDeletionRequestsPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const [processingId, setProcessingId] = useState<number | null>(null);

  const requestsQuery = useQuery({
    queryKey: ['adminDeletionRequests', statusFilter],
    queryFn: () => accountDeletionApi.listDeletionRequests({ status: statusFilter || undefined }),
  });

  const processMutation = useMutation({
    mutationFn: (userId: number) => accountDeletionApi.processDeletion(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminDeletionRequests'] });
      setProcessingId(null);
    },
    onError: () => {
      setProcessingId(null);
    },
  });

  const items = requestsQuery.data?.items || [];
  const total = requestsQuery.data?.total || 0;

  const handleProcess = (userId: number) => {
    if (!window.confirm('This will immediately and permanently anonymize this user. Are you sure?')) {
      return;
    }
    setProcessingId(userId);
    processMutation.mutate(userId);
  };

  return (
    <DashboardLayout>
      <div className="admin-deletion-requests">
        <PageNav items={[
          { label: 'Dashboard', to: '/dashboard' },
          { label: 'Deletion Requests' },
        ]} />

        <div className="admin-deletion-header">
          <div>
            <h1 className="admin-deletion-title">Account Deletion Requests</h1>
            <p className="admin-deletion-desc">
              Manage user account deletion requests. Users have a 30-day grace period before
              automatic anonymization.
            </p>
          </div>
        </div>

        <div className="admin-deletion-filters">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="admin-deletion-filter-select"
          >
            <option value="pending">Pending</option>
            <option value="processed">Processed</option>
            <option value="">All</option>
          </select>
          <span className="admin-deletion-count">{total} request(s)</span>
        </div>

        {requestsQuery.isLoading && <p className="admin-deletion-loading">Loading...</p>}

        {!requestsQuery.isLoading && items.length === 0 && (
          <div className="admin-deletion-empty">
            <p>No deletion requests found.</p>
          </div>
        )}

        <div className="admin-deletion-list">
          {items.map((item: DeletionRequestItem) => (
            <div
              key={item.user_id}
              className={`admin-deletion-card${item.is_deleted ? ' admin-deletion-card-processed' : ''}`}
            >
              <div className="admin-deletion-card-info">
                <div className="admin-deletion-card-name">
                  {item.full_name}
                  {item.is_deleted && (
                    <span className="admin-deletion-badge admin-deletion-badge-processed">Anonymized</span>
                  )}
                  {!item.is_deleted && item.deletion_confirmed_at && (
                    <span className="admin-deletion-badge admin-deletion-badge-confirmed">Confirmed</span>
                  )}
                  {!item.is_deleted && !item.deletion_confirmed_at && (
                    <span className="admin-deletion-badge admin-deletion-badge-pending">Pending Confirmation</span>
                  )}
                </div>
                <div className="admin-deletion-card-meta">
                  <span>Email: {item.email || 'N/A'}</span>
                  <span>Role: {item.role || 'N/A'}</span>
                  <span>Requested: {item.deletion_requested_at ? new Date(item.deletion_requested_at).toLocaleDateString() : 'N/A'}</span>
                  {item.deletion_confirmed_at && (
                    <span>Confirmed: {new Date(item.deletion_confirmed_at).toLocaleDateString()}</span>
                  )}
                </div>
              </div>
              {!item.is_deleted && (
                <div className="admin-deletion-card-actions">
                  <button
                    className="admin-deletion-btn-process"
                    onClick={() => handleProcess(item.user_id)}
                    disabled={processingId === item.user_id}
                  >
                    {processingId === item.user_id ? 'Processing...' : 'Anonymize Now'}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        {processMutation.isError && (
          <p className="admin-deletion-error">
            {(processMutation.error as Error & { response?: { data?: { detail?: string } } })
              ?.response?.data?.detail || 'Failed to process deletion.'}
          </p>
        )}
      </div>
    </DashboardLayout>
  );
}
