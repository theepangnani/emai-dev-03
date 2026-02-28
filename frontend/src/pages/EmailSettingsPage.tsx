import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { studentEmailsApi, type StudentEmailItem, type EmailType } from '../api/studentEmails';
import { DashboardLayout } from '../components/DashboardLayout';
import './EmailSettingsPage.css';

export function EmailSettingsPage() {
  const queryClient = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [emailType, setEmailType] = useState<EmailType>('personal');

  const emailsQuery = useQuery({
    queryKey: ['studentEmails'],
    queryFn: studentEmailsApi.list,
  });

  const addMutation = useMutation({
    mutationFn: studentEmailsApi.add,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studentEmails'] });
      setShowAdd(false);
      setNewEmail('');
      setEmailType('personal');
    },
  });

  const setPrimaryMutation = useMutation({
    mutationFn: studentEmailsApi.setPrimary,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studentEmails'] });
    },
  });

  const removeMutation = useMutation({
    mutationFn: studentEmailsApi.remove,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studentEmails'] });
    },
  });

  const verifyMutation = useMutation({
    mutationFn: studentEmailsApi.verify,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studentEmails'] });
    },
  });

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    addMutation.mutate({ email: newEmail, email_type: emailType });
  };

  const emails = emailsQuery.data || [];

  return (
    <DashboardLayout>
      <div className="email-settings">
        <div className="email-settings-header">
          <div>
            <h1 className="email-settings-title">Email Addresses</h1>
            <p className="email-settings-desc">
              Manage your email identities. Add a school email so both resolve to your account.
            </p>
          </div>
          {!showAdd && (
            <button
              className="email-add-btn"
              onClick={() => setShowAdd(true)}
            >
              + Add Email
            </button>
          )}
        </div>

        {showAdd && (
          <form className="email-add-form" onSubmit={handleAdd}>
            <div className="email-form-row">
              <div className="email-form-field email-form-field-email">
                <label htmlFor="addEmail">Email address</label>
                <input
                  id="addEmail"
                  type="email"
                  required
                  placeholder="school@example.com"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                />
              </div>
              <div className="email-form-field">
                <label htmlFor="emailType">Type</label>
                <select
                  id="emailType"
                  value={emailType}
                  onChange={(e) => setEmailType(e.target.value as EmailType)}
                >
                  <option value="personal">Personal</option>
                  <option value="school">School</option>
                </select>
              </div>
            </div>
            {addMutation.isError && (
              <p className="email-error">
                {(addMutation.error as Error & { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
                  'Failed to add email.'}
              </p>
            )}
            <div className="email-form-actions">
              <button
                type="button"
                className="email-btn email-btn-cancel"
                onClick={() => { setShowAdd(false); setNewEmail(''); }}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="email-btn email-btn-save"
                disabled={addMutation.isPending}
              >
                {addMutation.isPending ? 'Adding...' : 'Add Email'}
              </button>
            </div>
          </form>
        )}

        {emailsQuery.isLoading && <p className="email-loading">Loading emails...</p>}

        {emails.length === 0 && !emailsQuery.isLoading && (
          <div className="email-empty">
            <p>No email identities configured yet.</p>
            <p className="email-empty-hint">
              Add your personal and school emails so they both link to your account.
            </p>
          </div>
        )}

        <div className="email-list">
          {emails.map((item) => (
            <EmailCard
              key={item.id}
              item={item}
              onSetPrimary={(id) => setPrimaryMutation.mutate(id)}
              onRemove={(id) => removeMutation.mutate(id)}
              onVerify={(id) => verifyMutation.mutate(id)}
              isMutating={
                setPrimaryMutation.isPending ||
                removeMutation.isPending ||
                verifyMutation.isPending
              }
            />
          ))}
        </div>
      </div>
    </DashboardLayout>
  );
}

function EmailCard({
  item,
  onSetPrimary,
  onRemove,
  onVerify,
  isMutating,
}: {
  item: StudentEmailItem;
  onSetPrimary: (id: number) => void;
  onRemove: (id: number) => void;
  onVerify: (id: number) => void;
  isMutating: boolean;
}) {
  return (
    <div className={`email-card${item.is_primary ? ' email-card-primary' : ''}`}>
      <div className="email-card-left">
        <span className="email-card-icon">
          {item.email_type === 'school' ? '\uD83C\uDFEB' : '\u2709\uFE0F'}
        </span>
        <div className="email-card-info">
          <span className="email-card-address">{item.email}</span>
          <div className="email-card-badges">
            <span className={`email-type-badge email-type-${item.email_type}`}>
              {item.email_type}
            </span>
            {item.is_primary && (
              <span className="email-primary-badge">Primary</span>
            )}
            {item.verified_at ? (
              <span className="email-verified-badge">Verified</span>
            ) : (
              <span className="email-unverified-badge">Unverified</span>
            )}
          </div>
        </div>
      </div>
      <div className="email-card-actions">
        {!item.verified_at && (
          <button
            className="email-btn email-btn-verify"
            onClick={() => onVerify(item.id)}
            disabled={isMutating}
            title="Verify this email"
          >
            Verify
          </button>
        )}
        {!item.is_primary && item.verified_at && (
          <button
            className="email-btn email-btn-primary"
            onClick={() => onSetPrimary(item.id)}
            disabled={isMutating}
            title="Set as primary"
          >
            Make Primary
          </button>
        )}
        {!item.is_primary && (
          <button
            className="email-btn email-btn-remove"
            onClick={() => onRemove(item.id)}
            disabled={isMutating}
            title="Remove this email"
          >
            Remove
          </button>
        )}
      </div>
    </div>
  );
}
