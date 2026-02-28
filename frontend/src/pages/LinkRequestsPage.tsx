import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
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
  const { user } = useAuth();
  const isStudent = user?.role === 'student';
  const [activeTab, setActiveTab] = useState<'received' | 'sent'>('received');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [parentEmail, setParentEmail] = useState('');
  const [relationship, setRelationship] = useState('guardian');
  const [message, setMessage] = useState('');
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

  const createMutation = useMutation({
    mutationFn: linkRequestsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['linkRequests'] });
      setShowCreateForm(false);
      setParentEmail('');
      setRelationship('guardian');
      setMessage('');
    },
  });

  const handleRespond = (id: number, action: 'approve' | 'reject') => {
    respondMutation.mutate({ id, action });
  };

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate({
      parent_email: parentEmail,
      relationship_type: relationship,
      message: message || undefined,
    });
  };

  const pendingItems = pendingQuery.data || [];
  const sentItems = sentQuery.data || [];

  return (
    <DashboardLayout>
      <div className="lr-page">
        <div className="lr-page-header">
          <div>
            <h1 className="lr-title">Link Requests</h1>
            <p className="lr-subtitle">
              Manage requests to link parent and student accounts
            </p>
          </div>
          {isStudent && !showCreateForm && (
            <button
              className="lr-btn lr-btn-create"
              onClick={() => setShowCreateForm(true)}
            >
              + Link a Parent
            </button>
          )}
        </div>

        {showCreateForm && (
          <form className="lr-create-form" onSubmit={handleCreate}>
            <h3 className="lr-create-title">Link a Parent</h3>
            <p className="lr-create-desc">
              Enter your parent's email address to send them a link request.
            </p>
            <div className="lr-form-field">
              <label htmlFor="parentEmail">Parent's Email</label>
              <input
                id="parentEmail"
                type="email"
                required
                placeholder="parent@example.com"
                value={parentEmail}
                onChange={(e) => setParentEmail(e.target.value)}
              />
            </div>
            <div className="lr-form-field">
              <label htmlFor="relationship">Relationship</label>
              <select
                id="relationship"
                value={relationship}
                onChange={(e) => setRelationship(e.target.value)}
              >
                <option value="guardian">Guardian</option>
                <option value="mother">Mother</option>
                <option value="father">Father</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div className="lr-form-field">
              <label htmlFor="linkMessage">Message (optional)</label>
              <textarea
                id="linkMessage"
                placeholder="Add a note for your parent..."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                maxLength={500}
                rows={2}
              />
            </div>
            {createMutation.isError && (
              <div className="lr-error">
                {(createMutation.error as Error & { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
                  'Failed to send request. Please try again.'}
              </div>
            )}
            <div className="lr-form-actions">
              <button
                type="button"
                className="lr-btn lr-btn-reject"
                onClick={() => setShowCreateForm(false)}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="lr-btn lr-btn-approve"
                disabled={createMutation.isPending}
              >
                {createMutation.isPending ? 'Sending...' : 'Send Request'}
              </button>
            </div>
          </form>
        )}

        {createMutation.isSuccess && (
          <div className="lr-success">
            Link request sent successfully!
          </div>
        )}

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
