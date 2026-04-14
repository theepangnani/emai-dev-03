import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import DOMPurify from 'dompurify';
import { DashboardLayout } from '../../components/DashboardLayout';
import {
  listIntegrations,
  getSettings,
  updateSettings,
  getLogs,
  triggerSync,
  sendDigestNow,
  listMonitoredEmails,
  addMonitoredEmail,
  removeMonitoredEmail,
  type EmailDigestIntegration,
  type EmailDigestSettings,
  type DigestDeliveryLog,
  type MonitoredEmail,
} from '../../api/parentEmailDigest';
import './EmailDigestPage.css';

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function StatusBadge({ status }: { status: string }) {
  const cls = status === 'delivered' ? 'ed-status--delivered' : 'ed-status--failed';
  return <span className={`ed-status ${cls}`}>{status}</span>;
}

export function EmailDigestPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);

  const { data: integrations = [], isLoading: intLoading, isError: intError } = useQuery<EmailDigestIntegration[]>({
    queryKey: ['email-digest', 'integrations'],
    queryFn: () => listIntegrations().then((r) => r.data),
  });

  const activeIntegration = integrations[0] ?? null;

  const { data: settings } = useQuery<EmailDigestSettings>({
    queryKey: ['email-digest', 'settings', activeIntegration?.id],
    queryFn: () => getSettings(activeIntegration!.id).then((r) => r.data),
    enabled: !!activeIntegration,
  });

  const { data: logs = [], isLoading: logsLoading } = useQuery<DigestDeliveryLog[]>({
    queryKey: ['email-digest', 'logs', activeIntegration?.id],
    queryFn: () =>
      getLogs(activeIntegration ? { integration_id: activeIntegration.id, limit: 50 } : { limit: 50 }).then(
        (r) => r.data,
      ),
    enabled: !!activeIntegration,
  });

  const [newMonEmail, setNewMonEmail] = useState('');
  const [newMonLabel, setNewMonLabel] = useState('');

  const { data: monitoredEmails = [] } = useQuery<MonitoredEmail[]>({
    queryKey: ['email-digest', 'monitored-emails', activeIntegration?.id],
    queryFn: () => listMonitoredEmails(activeIntegration!.id).then((r) => r.data),
    enabled: !!activeIntegration,
  });

  const addMonitoredMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { email_address: string; label?: string } }) =>
      addMonitoredEmail(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-digest', 'monitored-emails'] });
      queryClient.invalidateQueries({ queryKey: ['email-digest', 'integrations'] });
      setNewMonEmail('');
      setNewMonLabel('');
    },
  });

  const removeMonitoredMutation = useMutation({
    mutationFn: ({ integrationId, emailId }: { integrationId: number; emailId: number }) =>
      removeMonitoredEmail(integrationId, emailId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-digest', 'monitored-emails'] });
      queryClient.invalidateQueries({ queryKey: ['email-digest', 'integrations'] });
    },
  });

  const syncMutation = useMutation({
    mutationFn: (id: number) => triggerSync(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-digest'] });
    },
  });

  const sendDigestMutation = useMutation({
    mutationFn: (id: number) => sendDigestNow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-digest'] });
    },
  });

  const settingsMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<EmailDigestSettings> }) =>
      updateSettings(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-digest', 'settings'] });
    },
  });

  const toggleDigest = () => {
    if (!activeIntegration || !settings) return;
    settingsMutation.mutate({
      id: activeIntegration.id,
      data: { digest_enabled: !settings.digest_enabled },
    });
  };

  const handleDeliveryTimeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    if (!activeIntegration) return;
    settingsMutation.mutate({
      id: activeIntegration.id,
      data: { delivery_time: e.target.value },
    });
  };

  const isLoading = intLoading;

  return (
    <DashboardLayout>
      <div className="ed-page">
        <div className="ed-header">
          <button className="ed-back-btn" onClick={() => navigate('/dashboard')} aria-label="Back to dashboard">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Dashboard
          </button>
          <h1 className="ed-title">Email Digest</h1>
          {activeIntegration?.child_first_name && (
            <span className="ed-child-context">for {activeIntegration.child_first_name}</span>
          )}
        </div>

        {isLoading && <div className="ed-loading">Loading...</div>}

        {!isLoading && intError && (
          <div className="ed-empty-state">
            <h2>Something went wrong</h2>
            <p>Failed to load email digest data. Please try again later.</p>
            <button className="ed-primary-btn" onClick={() => window.location.reload()}>
              Try Again
            </button>
          </div>
        )}

        {!isLoading && !activeIntegration && (
          <div className="ed-empty-state">
            <div className="ed-empty-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                <rect x="2" y="4" width="20" height="16" rx="2" />
                <polyline points="2 4 12 13 22 4" />
              </svg>
            </div>
            <h2>No Email Digest Set Up</h2>
            <p>Connect your Gmail account from the My Kids page to start receiving email digests about your child's school communications.</p>
            <button className="ed-primary-btn" onClick={() => navigate('/my-kids')}>
              Go to My Kids
            </button>
          </div>
        )}

        {!isLoading && activeIntegration && (
          <>
            {/* Quick Settings */}
            <div className="ed-settings-card">
              <h2 className="ed-section-title">Quick Settings</h2>
              <div className="ed-settings-row">
                <div className="ed-setting-item">
                  <span className="ed-setting-label">Digest Enabled</span>
                  <button
                    className={`ed-toggle ${settings?.digest_enabled ? 'ed-toggle--on' : ''}`}
                    onClick={toggleDigest}
                    disabled={settingsMutation.isPending}
                    aria-label={settings?.digest_enabled ? 'Disable digest' : 'Enable digest'}
                  >
                    <span className="ed-toggle-knob" />
                  </button>
                </div>
                <div className="ed-setting-item">
                  <label className="ed-setting-label" htmlFor="delivery-time">Delivery Time</label>
                  <select
                    id="delivery-time"
                    className="ed-select"
                    value={settings?.delivery_time ?? '07:00'}
                    onChange={handleDeliveryTimeChange}
                    disabled={settingsMutation.isPending}
                  >
                    <option value="06:00">6:00 AM</option>
                    <option value="07:00">7:00 AM</option>
                    <option value="08:00">8:00 AM</option>
                    <option value="09:00">9:00 AM</option>
                    <option value="12:00">12:00 PM</option>
                    <option value="17:00">5:00 PM</option>
                    <option value="20:00">8:00 PM</option>
                  </select>
                </div>
              </div>
              <div className="ed-settings-actions">
                <button
                  className="ed-sync-btn"
                  onClick={() => syncMutation.mutate(activeIntegration.id)}
                  disabled={syncMutation.isPending}
                >
                  {syncMutation.isPending ? 'Syncing...' : 'Sync Now'}
                </button>
                <button
                  className="ed-primary-btn"
                  onClick={() => sendDigestMutation.mutate(activeIntegration.id)}
                  disabled={sendDigestMutation.isPending}
                >
                  {sendDigestMutation.isPending ? 'Sending...' : 'Send Digest Now'}
                </button>
                {syncMutation.isError && (
                  <span className="ed-error-text">Sync failed. Please try again.</span>
                )}
                {syncMutation.isSuccess && (
                  <span className="ed-success-text">Sync complete!</span>
                )}
                {sendDigestMutation.isError && (
                  <span className="ed-error-text">Failed to send digest. Please try again.</span>
                )}
                {sendDigestMutation.isSuccess && (
                  <span className="ed-success-text">{sendDigestMutation.data?.data?.message ?? 'Digest sent!'}</span>
                )}
              </div>
            </div>

            {/* Monitored Emails */}
            <div className="ed-settings-card">
              <h2 className="ed-section-title">Monitored Emails</h2>
              {monitoredEmails.length > 0 ? (
                <div className="ed-monitored-list">
                  {monitoredEmails.map((me) => (
                    <div key={me.id} className="ed-monitored-item">
                      <span className="ed-monitored-email">{me.email_address}</span>
                      {me.label && <span className="ed-monitored-label">{me.label}</span>}
                      <button
                        className="ed-monitored-remove"
                        onClick={() => removeMonitoredMutation.mutate({ integrationId: activeIntegration.id, emailId: me.id })}
                        disabled={removeMonitoredMutation.isPending}
                        aria-label={`Remove ${me.email_address}`}
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="ed-empty-history">No monitored email addresses configured.</p>
              )}
              {monitoredEmails.length < 10 && (
                <div className="ed-add-email-row">
                  <input
                    type="email"
                    className="ed-input"
                    placeholder="sender@school.ca"
                    value={newMonEmail}
                    onChange={(e) => setNewMonEmail(e.target.value)}
                  />
                  <input
                    type="text"
                    className="ed-input"
                    placeholder="Label (optional)"
                    value={newMonLabel}
                    onChange={(e) => setNewMonLabel(e.target.value)}
                  />
                  <button
                    className="ed-primary-btn"
                    disabled={!newMonEmail.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(newMonEmail.trim()) || addMonitoredMutation.isPending}
                    onClick={() =>
                      addMonitoredMutation.mutate({
                        id: activeIntegration.id,
                        data: { email_address: newMonEmail.trim().toLowerCase(), label: newMonLabel.trim() || undefined },
                      })
                    }
                  >
                    {addMonitoredMutation.isPending ? 'Adding...' : 'Add'}
                  </button>
                </div>
              )}
              {addMonitoredMutation.isError && (
                <span className="ed-error-text">Failed to add email. It may already be monitored.</span>
              )}
            </div>

            {/* Digest History */}
            <div className="ed-history-section">
              <h2 className="ed-section-title">Digest History</h2>
              {logsLoading && <div className="ed-loading">Loading history...</div>}
              {!logsLoading && logs.length === 0 && (
                <div className="ed-empty-history">
                  <p>No digests delivered yet. Your first digest will appear here after the next scheduled run.</p>
                </div>
              )}
              {!logsLoading && logs.length > 0 && (
                <div className="ed-log-list">
                  {logs.map((log) => (
                    <div key={log.id} className="ed-log-card">
                      <button
                        className="ed-log-header"
                        onClick={() => setExpandedLogId(expandedLogId === log.id ? null : log.id)}
                        aria-expanded={expandedLogId === log.id}
                      >
                        <div className="ed-log-meta">
                          <span className="ed-log-date">{formatDate(log.delivered_at)}</span>
                          <span className="ed-log-count">
                            {log.email_count} {log.email_count === 1 ? 'email' : 'emails'}
                          </span>
                          <StatusBadge status={log.status} />
                        </div>
                        <svg
                          className={`ed-chevron ${expandedLogId === log.id ? 'ed-chevron--open' : ''}`}
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          aria-hidden="true"
                        >
                          <polyline points="6 9 12 15 18 9" />
                        </svg>
                      </button>
                      {expandedLogId === log.id && (
                        <div className="ed-log-content">
                          {log.digest_content ? (
                            <div className="ed-digest-text" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(log.digest_content) }} />
                          ) : (
                            <p className="ed-no-content">No digest content available.</p>
                          )}
                          {log.channels_used && (
                            <div className="ed-log-channels">
                              Delivered via: {log.channels_used}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
