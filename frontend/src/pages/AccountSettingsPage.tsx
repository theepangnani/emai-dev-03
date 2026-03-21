import { useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { accountDeletionApi } from '../api/accountDeletion';
import { authApi } from '../api/auth';
import { dailyDigestApi, type DailyDigestPreview } from '../api/dailyDigest';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import { StorageUsageBar } from '../components/StorageUsageBar';
import './AccountSettingsPage.css';

export function AccountSettingsPage() {
  const { user, refreshUser } = useAuth();
  const queryClient = useQueryClient();
  const [showConfirm, setShowConfirm] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [showDigestPreview, setShowDigestPreview] = useState(false);
  const [digestPreview, setDigestPreview] = useState<DailyDigestPreview | null>(null);
  const [sendResult, setSendResult] = useState<string | null>(null);

  // Interests state
  const [interests, setInterests] = useState<string[]>(user?.interests ?? []);
  const [interestInput, setInterestInput] = useState('');
  const [interestsSaved, setInterestsSaved] = useState(false);
  const interestInputRef = useRef<HTMLInputElement>(null);

  // Language preference state
  const [selectedLanguage, setSelectedLanguage] = useState(user?.preferred_language ?? 'en');
  const [languageSaved, setLanguageSaved] = useState(false);

  const isParent = user?.roles?.includes('parent') || user?.role === 'parent';

  const interestsMutation = useMutation({
    mutationFn: (newInterests: string[]) => authApi.updateInterests(newInterests),
    onSuccess: () => {
      refreshUser();
      setInterestsSaved(true);
      setTimeout(() => setInterestsSaved(false), 3000);
    },
  });

  const languageMutation = useMutation({
    mutationFn: (lang: string) => authApi.updateLanguage(lang),
    onSuccess: () => {
      refreshUser();
      setLanguageSaved(true);
      setTimeout(() => setLanguageSaved(false), 3000);
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

  const digestSettingsQuery = useQuery({
    queryKey: ['digestSettings'],
    queryFn: dailyDigestApi.getSettings,
    enabled: isParent,
  });

  const digestToggleMutation = useMutation({
    mutationFn: (enabled: boolean) => dailyDigestApi.updateSettings({ daily_digest_enabled: enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['digestSettings'] });
    },
  });

  const digestPreviewMutation = useMutation({
    mutationFn: dailyDigestApi.preview,
    onSuccess: (data) => {
      setDigestPreview(data);
      setShowDigestPreview(true);
    },
  });

  const digestSendMutation = useMutation({
    mutationFn: dailyDigestApi.send,
    onSuccess: (data) => {
      setSendResult(data.message);
      setTimeout(() => setSendResult(null), 5000);
    },
    onError: () => {
      setSendResult('Failed to send test email.');
      setTimeout(() => setSendResult(null), 5000);
    },
  });

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

        <section className="account-section">
          <h2>Storage Usage</h2>
          <StorageUsageBar
            usedBytes={user?.storage_used_bytes ?? 0}
            limitBytes={user?.storage_limit_bytes ?? 104857600}
            uploadLimitBytes={user?.upload_limit_bytes ?? 10485760}
          />
        </section>

        {isParent && (
          <section className="account-section">
            <h2>Language Preference</h2>
            <p style={{ color: '#6b7280', marginBottom: 16 }}>
              Choose the language for parent summaries on study guides. Summaries will be automatically translated.
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <select
                className="account-language-select"
                value={selectedLanguage}
                onChange={(e) => setSelectedLanguage(e.target.value)}
              >
                <option value="en">English</option>
                <option value="fr">French</option>
                <option value="ta">Tamil</option>
                <option value="zh">Mandarin (Simplified)</option>
                <option value="pa">Punjabi</option>
                <option value="ur">Urdu</option>
              </select>
              <button
                className="account-btn account-btn-save-interests"
                onClick={() => languageMutation.mutate(selectedLanguage)}
                disabled={languageMutation.isPending || selectedLanguage === (user?.preferred_language ?? 'en')}
              >
                {languageMutation.isPending ? 'Saving...' : languageSaved ? 'Saved!' : 'Save'}
              </button>
            </div>
            {languageMutation.isError && (
              <p className="account-error" style={{ marginTop: 8 }}>Failed to save language preference.</p>
            )}
          </section>
        )}

        {isParent && (
          <section className="account-section">
            <h2>Daily Email Digest</h2>
            <p style={{ color: '#6b7280', marginBottom: 16 }}>
              Receive a daily morning email summarizing overdue tasks, items due today, and upcoming assignments for your children.
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={digestSettingsQuery.data?.daily_digest_enabled ?? false}
                  onChange={(e) => digestToggleMutation.mutate(e.target.checked)}
                  disabled={digestToggleMutation.isPending || digestSettingsQuery.isLoading}
                  style={{ width: 18, height: 18, accentColor: '#4f46e5' }}
                />
                <span style={{ fontWeight: 500 }}>Enable daily digest emails</span>
              </label>
              {digestToggleMutation.isPending && <span style={{ color: '#6b7280', fontSize: 13 }}>Saving...</span>}
            </div>
            {digestSettingsQuery.data?.email_consent_date && (
              <p style={{ color: '#9ca3af', fontSize: 12, margin: '0 0 16px' }}>
                Consent given on {new Date(digestSettingsQuery.data.email_consent_date).toLocaleDateString()}
              </p>
            )}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                className="account-btn account-btn-secondary"
                onClick={() => digestPreviewMutation.mutate()}
                disabled={digestPreviewMutation.isPending}
              >
                {digestPreviewMutation.isPending ? 'Loading...' : 'Preview Digest'}
              </button>
              <button
                className="account-btn account-btn-secondary"
                onClick={() => digestSendMutation.mutate()}
                disabled={digestSendMutation.isPending}
                style={{ background: '#4f46e5', color: '#fff', borderColor: '#4f46e5' }}
              >
                {digestSendMutation.isPending ? 'Sending...' : 'Send Test Email'}
              </button>
            </div>
            {sendResult && (
              <p style={{ marginTop: 12, color: digestSendMutation.isError ? '#dc2626' : '#059669', fontSize: 14 }}>
                {sendResult}
              </p>
            )}
            {showDigestPreview && digestPreview && (
              <div style={{ marginTop: 16, padding: 16, background: '#f9fafb', borderRadius: 12, border: '1px solid #e5e7eb' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <h3 style={{ margin: 0 }}>Digest Preview</h3>
                  <button
                    onClick={() => setShowDigestPreview(false)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: '#6b7280' }}
                  >
                    &times;
                  </button>
                </div>
                <p style={{ color: '#6b7280', fontSize: 13, margin: '0 0 8px' }}>{digestPreview.date}</p>
                <p style={{ margin: '0 0 16px' }}>{digestPreview.greeting}</p>
                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
                  <div style={{ padding: '8px 12px', background: digestPreview.total_overdue > 0 ? '#fef2f2' : '#f0fdf4', borderRadius: 8, fontSize: 14 }}>
                    <strong>{digestPreview.total_overdue}</strong> overdue
                  </div>
                  <div style={{ padding: '8px 12px', background: digestPreview.total_due_today > 0 ? '#fffbeb' : '#f0fdf4', borderRadius: 8, fontSize: 14 }}>
                    <strong>{digestPreview.total_due_today}</strong> due today
                  </div>
                  <div style={{ padding: '8px 12px', background: '#eef2ff', borderRadius: 8, fontSize: 14 }}>
                    <strong>{digestPreview.total_upcoming}</strong> upcoming
                  </div>
                </div>
                {digestPreview.children.map((child) => (
                  <div key={child.student_id} style={{ marginBottom: 12, padding: 12, background: '#fff', borderRadius: 8, borderLeft: '3px solid #4f46e5' }}>
                    <strong>{child.full_name}</strong>
                    {child.grade_level && <span style={{ color: '#6b7280', marginLeft: 8, fontSize: 13 }}>Grade {child.grade_level}</span>}
                    {child.needs_attention && <span style={{ marginLeft: 8, background: '#fef2f2', color: '#dc2626', fontSize: 11, padding: '2px 6px', borderRadius: 8 }}>Needs attention</span>}
                    {child.overdue_tasks.length > 0 && (
                      <ul style={{ margin: '8px 0 0 16px', padding: 0, fontSize: 13, color: '#dc2626' }}>
                        {child.overdue_tasks.map((t) => <li key={t.id}>{t.title}{t.course_name ? ` (${t.course_name})` : ''}</li>)}
                      </ul>
                    )}
                    {child.due_today_tasks.length > 0 && (
                      <ul style={{ margin: '8px 0 0 16px', padding: 0, fontSize: 13, color: '#d97706' }}>
                        {child.due_today_tasks.map((t) => <li key={t.id}>{t.title}{t.course_name ? ` (${t.course_name})` : ''}</li>)}
                      </ul>
                    )}
                    {child.upcoming_assignments.length > 0 && (
                      <ul style={{ margin: '8px 0 0 16px', padding: 0, fontSize: 13, color: '#4b5563' }}>
                        {child.upcoming_assignments.map((a) => <li key={a.id}>{a.title} ({a.course_name})</li>)}
                      </ul>
                    )}
                  </div>
                ))}
                {digestPreview.children.length === 0 && (
                  <p style={{ color: '#6b7280', fontStyle: 'italic' }}>No children linked to your account.</p>
                )}
              </div>
            )}
          </section>
        )}


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
