import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { linkRequestsApi, type LinkRequestItem } from '../api/linkRequests';
import { DashboardLayout } from '../components/DashboardLayout';
import './LinkRequestsPage.css';

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: '#f59e0b',
    approved: '#10b981',
    rejected: '#ef4444',
    expired: '#6b7280',
  };
  return (
    <span
      className="lr-status-badge"
      style={{ backgroundColor: colors[status] || '#6b7280' }}
    >
      {status}
    </span>
  );
}

function RequestCard({
  item,
  showActions,
  onRespond,
  isResponding,
}: {
  item: LinkRequestItem;
  showActions: boolean;
  onRespond: (id: number, action: 'approve' | 'reject') => void;
  isResponding: boolean;
}) {
  const isIncoming = showActions;
  const otherUser = isIncoming ? item.requester : item.target;
  const typeLabel =
    item.request_type === 'student_to_parent'
      ? 'Student wants to link'
      : 'Parent wants to link';

  return (
    <div className="lr-card">
      <div className="lr-card-header">
        <div>
          <span className="lr-card-type">{typeLabel}</span>
          <StatusBadge status={item.status} />
        </div>
        <span className="lr-card-date">
          {new Date(item.created_at).toLocaleDateString()}
        </span>
      </div>
      <div className="lr-card-body">
        <p className="lr-card-name">{otherUser.full_name}</p>
        {otherUser.email && (
          <p className="lr-card-email">{otherUser.email}</p>
        )}
        {item.relationship_type && (
          <p className="lr-card-detail">
            Relationship: {item.relationship_type}
          </p>
        )}
        {item.message && <p className="lr-card-message">{item.message}</p>}
      </div>
      {showActions && item.status === 'pending' && (
        <div className="lr-card-actions">
          <button
            className="lr-btn lr-btn-approve"
            onClick={() => onRespond(item.id, 'approve')}
            disabled={isResponding}
          >
            Approve
          </button>
          <button
            className="lr-btn lr-btn-reject"
            onClick={() => onRespond(item.id, 'reject')}
            disabled={isResponding}
          >
            Decline
          </button>
        </div>
      )}
      {item.responded_at && (
        <p className="lr-card-responded">
          Responded: {new Date(item.responded_at).toLocaleDateString()}
        </p>
      )}
    </div>
  );
}

export function LinkRequestsPage() {
  const [activeTab, setActiveTab] = useState<'received' | 'sent'>('received');
  const queryClient = useQueryClient();

  const pendingQuery = useQuery({
    queryKey: ['linkRequests', 'pending'],
    queryFn: linkRequestsApi.getPending,
  });

  const sentQuery = useQuery({
    queryKey: ['linkRequests', 'sent'],
    queryFn: linkRequestsApi.getSent,
  });

  const respondMutation = useMutation({
    mutationFn: ({ id, action }: { id: number; action: 'approve' | 'reject' }) =>
      linkRequestsApi.respond(id, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['linkRequests'] });
    },
  });

  const handleRespond = (id: number, action: 'approve' | 'reject') => {
    respondMutation.mutate({ id, action });
  };

  const pendingItems = pendingQuery.data || [];
  const sentItems = sentQuery.data || [];

  return (
    <DashboardLayout>
      <div className="lr-page">
        <h1 className="lr-title">Link Requests</h1>
        <p className="lr-subtitle">
          Manage requests to link parent and student accounts
        </p>

        <div className="lr-tabs">
          <button
            className={`lr-tab ${activeTab === 'received' ? 'lr-tab-active' : ''}`}
            onClick={() => setActiveTab('received')}
          >
            Received
            {pendingItems.length > 0 && (
              <span className="lr-tab-count">{pendingItems.length}</span>
            )}
          </button>
          <button
            className={`lr-tab ${activeTab === 'sent' ? 'lr-tab-active' : ''}`}
            onClick={() => setActiveTab('sent')}
          >
            Sent
          </button>
        </div>

        {respondMutation.isError && (
          <div className="lr-error">
            Failed to respond. Please try again.
          </div>
        )}
        {respondMutation.isSuccess && (
          <div className="lr-success">
            Request {respondMutation.data?.status} successfully.
          </div>
        )}

        {activeTab === 'received' && (
          <div className="lr-list">
            {pendingQuery.isLoading && <p className="lr-loading">Loading...</p>}
            {pendingItems.length === 0 && !pendingQuery.isLoading && (
              <p className="lr-empty">No pending link requests.</p>
            )}
            {pendingItems.map((item) => (
              <RequestCard
                key={item.id}
                item={item}
                showActions={true}
                onRespond={handleRespond}
                isResponding={respondMutation.isPending}
              />
            ))}
          </div>
        )}

        {activeTab === 'sent' && (
          <div className="lr-list">
            {sentQuery.isLoading && <p className="lr-loading">Loading...</p>}
            {sentItems.length === 0 && !sentQuery.isLoading && (
              <p className="lr-empty">No sent link requests.</p>
            )}
            {sentItems.map((item) => (
              <RequestCard
                key={item.id}
                item={item}
                showActions={false}
                onRespond={handleRespond}
                isResponding={false}
              />
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
