import { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
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
  getGmailAuthUrl,
  connectGmail,
  sendWhatsAppOTP,
  verifyWhatsAppOTP,
  disconnectWhatsApp,
  type EmailDigestIntegration,
  type EmailDigestSettings,
  type DigestDeliveryLog,
  type MonitoredEmail,
} from '../../api/parentEmailDigest';
import { useConfirm } from '../../components/ConfirmModal';
import './EmailDigestPage.css';

interface ApiErrorResponse {
  response?: { data?: { detail?: string } };
}

function getApiErrorMessage(err: unknown, fallback: string): string {
  const e = err as ApiErrorResponse;
  return e?.response?.data?.detail || fallback;
}

/**
 * Validates E.164 phone format: '+' country-code (1-9) + 9-14 digits.
 * Conservative minimum (10 total digits) covers North American numbers
 * which are our primary user base. Some short international numbers
 * (e.g., Belize +501XXXXXXX = 10 chars total) may be incorrectly rejected.
 */
function isValidPhone(phone: string): boolean {
  const trimmed = phone.trim();
  return /^\+[1-9]\d{9,14}$/.test(trimmed);
}

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
  const { confirm, confirmModal } = useConfirm();
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);
  const [whatsappPhone, setWhatsappPhone] = useState('');
  const [whatsappOtp, setWhatsappOtp] = useState('');
  const [whatsappError, setWhatsappError] = useState<string | null>(null);
  const [whatsappSuccess, setWhatsappSuccess] = useState<string | null>(null);

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
  const [newMonName, setNewMonName] = useState('');
  const [newMonLabel, setNewMonLabel] = useState('');

  const { data: monitoredEmails = [] } = useQuery<MonitoredEmail[]>({
    queryKey: ['email-digest', 'monitored-emails', activeIntegration?.id],
    queryFn: () => listMonitoredEmails(activeIntegration!.id).then((r) => r.data),
    enabled: !!activeIntegration,
  });

  const addMonitoredMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { email_address?: string; sender_name?: string; label?: string } }) =>
      addMonitoredEmail(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-digest', 'monitored-emails'] });
      queryClient.invalidateQueries({ queryKey: ['email-digest', 'integrations'] });
      setNewMonEmail('');
      setNewMonName('');
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

  const sendOtpMutation = useMutation({
    mutationFn: ({ id, phone }: { id: number; phone: string }) => sendWhatsAppOTP(id, phone),
    onSuccess: () => {
      setWhatsappError(null);
      setWhatsappSuccess('OTP sent! Check your WhatsApp.');
      setWhatsappOtp('');
      queryClient.invalidateQueries({ queryKey: ['email-digest', 'integrations'] });
    },
    onError: (err: unknown) => {
      setWhatsappSuccess(null);
      setWhatsappError(getApiErrorMessage(err, 'Failed to send OTP. Please try again.'));
    },
  });

  const verifyOtpMutation = useMutation({
    mutationFn: ({ id, otpCode }: { id: number; otpCode: string }) => verifyWhatsAppOTP(id, otpCode),
    onSuccess: () => {
      setWhatsappError(null);
      setWhatsappSuccess('WhatsApp verified! Your digest will be delivered here.');
      setWhatsappOtp('');
      setWhatsappPhone('');
      queryClient.invalidateQueries({ queryKey: ['email-digest', 'integrations'] });
      queryClient.invalidateQueries({ queryKey: ['email-digest', 'settings'] });
    },
    onError: (err: unknown) => {
      setWhatsappSuccess(null);
      setWhatsappError(getApiErrorMessage(err, 'Failed to verify OTP. Please try again.'));
    },
  });

  const disconnectWhatsappMutation = useMutation({
    mutationFn: (id: number) => disconnectWhatsApp(id),
    onSuccess: () => {
      setWhatsappError(null);
      setWhatsappSuccess(null);
      setWhatsappOtp('');
      setWhatsappPhone('');
      queryClient.invalidateQueries({ queryKey: ['email-digest', 'integrations'] });
      queryClient.invalidateQueries({ queryKey: ['email-digest', 'settings'] });
    },
    onError: (err: unknown) => {
      setWhatsappError(getApiErrorMessage(err, 'Failed to disconnect WhatsApp.'));
    },
  });

  const handleSendOtp = () => {
    if (!activeIntegration) return;
    const phone = whatsappPhone.trim();
    if (!isValidPhone(phone)) {
      setWhatsappError('Phone must be in E.164 format (e.g. +14165551234).');
      return;
    }
    setWhatsappError(null);
    sendOtpMutation.mutate({ id: activeIntegration.id, phone });
  };

  const handleResendOtp = () => {
    if (!activeIntegration?.whatsapp_phone) return;
    setWhatsappError(null);
    setWhatsappSuccess(null);
    setWhatsappOtp('');
    sendOtpMutation.mutate({
      id: activeIntegration.id,
      phone: activeIntegration.whatsapp_phone,
    });
  };

  const handleVerifyOtp = () => {
    if (!activeIntegration) return;
    const otp = whatsappOtp.trim();
    if (!/^\d{6}$/.test(otp)) {
      setWhatsappError('Enter the 6-digit code from WhatsApp.');
      return;
    }
    setWhatsappError(null);
    verifyOtpMutation.mutate({ id: activeIntegration.id, otpCode: otp });
  };

  const handleCancelOtp = async () => {
    if (!activeIntegration) return;
    const confirmed = await confirm({
      title: 'Cancel verification',
      message: 'This will clear your phone number. You can start over with the same or a different number.',
      confirmLabel: 'Yes, cancel',
    });
    if (!confirmed) return;
    disconnectWhatsappMutation.mutate(activeIntegration.id);
  };

  const handleDisconnectWhatsapp = async () => {
    if (!activeIntegration) return;
    const confirmed = await confirm({
      title: 'Disconnect WhatsApp',
      message: 'Stop receiving your daily digest on WhatsApp? You can reconnect anytime.',
      confirmLabel: 'Disconnect',
      variant: 'danger',
    });
    if (!confirmed) return;
    disconnectWhatsappMutation.mutate(activeIntegration.id);
  };

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

  // Gmail reconnect via popup (same pattern as setup wizard)
  const oauthStateRef = useRef('');

  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      if (event.data?.type === 'gmail-oauth-callback' && event.data?.code) {
        try {
          const redirectUri = window.location.origin + '/oauth/gmail/callback';
          await connectGmail(event.data.code, oauthStateRef.current, redirectUri);
          // Refresh integration data — this will clear the reconnect banner
          queryClient.invalidateQueries({ queryKey: ['email-digest'] });
        } catch {
          // If reconnect fails, user can try again
        }
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [queryClient]);

  const handleReconnect = async () => {
    try {
      const redirectUri = window.location.origin + '/oauth/gmail/callback';
      const res = await getGmailAuthUrl(redirectUri);
      oauthStateRef.current = res.data.state;
      const w = 500;
      const h = 600;
      const left = window.screenX + (window.outerWidth - w) / 2;
      const top = window.screenY + (window.outerHeight - h) / 2;
      window.open(res.data.authorization_url, 'gmail-oauth', `width=${w},height=${h},left=${left},top=${top}`);
    } catch {
      navigate('/my-kids');
    }
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

        {!isLoading && activeIntegration && !activeIntegration.is_active && (
          <div className="ed-reconnect-banner">
            <div className="ed-reconnect-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <div className="ed-reconnect-text">
              <h3>Gmail Connection Expired</h3>
              <p>Your Gmail access has expired. Reconnect to continue receiving email digests.</p>
            </div>
            <button className="ed-primary-btn" onClick={handleReconnect}>
              Reconnect Gmail
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
                  disabled={syncMutation.isPending || !activeIntegration.is_active}
                >
                  {syncMutation.isPending ? 'Syncing...' : 'Sync Now'}
                </button>
                <button
                  className="ed-primary-btn"
                  onClick={() => {
                    sendDigestMutation.reset();
                    sendDigestMutation.mutate(activeIntegration.id);
                  }}
                  disabled={sendDigestMutation.isPending || !activeIntegration.is_active}
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
                  <span className="ed-error-text">
                    {(sendDigestMutation.error as any)?.response?.data?.detail || 'Failed to send digest. Please try again.'}
                  </span>
                )}
                {sendDigestMutation.isSuccess && (() => {
                  // #3880 + #3887: render per-channel digest status with four
                  // variants: delivered / partial / failed / skipped.
                  const payload = sendDigestMutation.data?.data;
                  const status = payload?.status ?? 'delivered';
                  const message = payload?.message ?? 'Digest sent!';
                  const variant =
                    status === 'delivered'
                      ? 'ed-digest-status--delivered'
                      : status === 'partial'
                      ? 'ed-digest-status--partial'
                      : status === 'failed'
                      ? 'ed-digest-status--failed'
                      : status === 'skipped'
                      ? 'ed-digest-status--skipped'
                      : 'ed-digest-status--delivered';
                  const icon =
                    status === 'delivered'
                      ? '\u2713'
                      : status === 'partial'
                      ? '\u26A0'
                      : status === 'failed'
                      ? '\u2715'
                      : status === 'skipped'
                      ? '\u2139'
                      : '\u2713';
                  return (
                    <div
                      className={`ed-digest-status ${variant}`}
                      role={status === 'failed' ? 'alert' : 'status'}
                      data-status={status}
                    >
                      <div className="ed-digest-status__row">
                        <span className="ed-digest-status__icon" aria-hidden="true">
                          {icon}
                        </span>
                        <span>{message}</span>
                      </div>
                      {status === 'failed' && (
                        <button
                          type="button"
                          className="ed-digest-status__retry"
                          onClick={() => {
                            sendDigestMutation.reset();
                            sendDigestMutation.mutate(activeIntegration.id);
                          }}
                          disabled={sendDigestMutation.isPending}
                        >
                          Try again
                        </button>
                      )}
                      {status === 'skipped' && (
                        <Link
                          to="/settings/notifications"
                          className="ed-digest-status__prefs-link"
                        >
                          Open preferences
                        </Link>
                      )}
                    </div>
                  );
                })()}
              </div>
            </div>

            {/* Monitored Emails */}
            <div className="ed-settings-card">
              <h2 className="ed-section-title">Monitored Emails</h2>
              {monitoredEmails.length > 0 ? (
                <div className="ed-monitored-list">
                  {monitoredEmails.map((me) => {
                    const primary = me.email_address || me.sender_name || '';
                    return (
                      <div key={me.id} className="ed-monitored-item">
                        {me.email_address && <span className="ed-monitored-email">{me.email_address}</span>}
                        {me.sender_name && <span className="ed-monitored-name">{me.sender_name}</span>}
                        {me.label && <span className="ed-monitored-label">{me.label}</span>}
                        <button
                          className="ed-monitored-remove"
                          onClick={() => removeMonitoredMutation.mutate({ integrationId: activeIntegration.id, emailId: me.id })}
                          disabled={removeMonitoredMutation.isPending}
                          aria-label={`Remove ${primary}`}
                        >
                          &times;
                        </button>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="ed-empty-history">No monitored senders configured.</p>
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
                    placeholder="Sender Name (optional), e.g. Mrs. Smith"
                    value={newMonName}
                    onChange={(e) => setNewMonName(e.target.value)}
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
                    disabled={
                      addMonitoredMutation.isPending ||
                      (!newMonEmail.trim() && !newMonName.trim()) ||
                      (!!newMonEmail.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(newMonEmail.trim()))
                    }
                    onClick={() =>
                      addMonitoredMutation.mutate({
                        id: activeIntegration.id,
                        data: {
                          email_address: newMonEmail.trim() ? newMonEmail.trim().toLowerCase() : undefined,
                          sender_name: newMonName.trim() || undefined,
                          label: newMonLabel.trim() || undefined,
                        },
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

            {/* WhatsApp (#3592) */}
            <div className="ed-settings-card ed-whatsapp-card">
              <h2 className="ed-section-title">Receive Digest on WhatsApp</h2>

              {/* State A: Not connected */}
              {!activeIntegration.whatsapp_phone && (
                <div className="ed-whatsapp-section">
                  <p className="ed-whatsapp-description">
                    Get your daily email digest delivered to WhatsApp instantly.
                  </p>
                  <div className="ed-whatsapp-row">
                    <input
                      type="tel"
                      className="ed-input"
                      placeholder="+14165551234"
                      maxLength={16}
                      value={whatsappPhone}
                      onChange={(e) => setWhatsappPhone(e.target.value)}
                      aria-label="WhatsApp phone number"
                      disabled={sendOtpMutation.isPending}
                    />
                    <button
                      className="ed-primary-btn"
                      onClick={handleSendOtp}
                      disabled={sendOtpMutation.isPending || !whatsappPhone.trim()}
                    >
                      {sendOtpMutation.isPending ? 'Sending...' : 'Send OTP'}
                    </button>
                  </div>
                  <p className="ed-whatsapp-note">
                    We'll send a 6-digit code to verify your number.
                  </p>
                </div>
              )}

              {/* State B: OTP sent, awaiting verification */}
              {activeIntegration.whatsapp_phone && !activeIntegration.whatsapp_verified && (
                <div className="ed-whatsapp-section">
                  <p className="ed-whatsapp-description">
                    Code sent to <strong>{activeIntegration.whatsapp_phone}</strong>
                  </p>
                  <div className="ed-whatsapp-row">
                    <input
                      type="text"
                      inputMode="numeric"
                      className="ed-input"
                      placeholder="6-digit code"
                      maxLength={6}
                      value={whatsappOtp}
                      onChange={(e) => setWhatsappOtp(e.target.value.replace(/\D/g, ''))}
                      aria-label="Verification code"
                      disabled={verifyOtpMutation.isPending}
                    />
                    <button
                      className="ed-primary-btn"
                      onClick={handleVerifyOtp}
                      disabled={verifyOtpMutation.isPending || whatsappOtp.length !== 6}
                    >
                      {verifyOtpMutation.isPending ? 'Verifying...' : 'Verify'}
                    </button>
                  </div>
                  <div className="ed-whatsapp-actions">
                    <button
                      className="ed-whatsapp-link"
                      onClick={handleResendOtp}
                      disabled={sendOtpMutation.isPending}
                      type="button"
                    >
                      {sendOtpMutation.isPending ? 'Resending...' : 'Resend code'}
                    </button>
                    <button
                      className="ed-whatsapp-link ed-whatsapp-link--cancel"
                      onClick={handleCancelOtp}
                      disabled={disconnectWhatsappMutation.isPending}
                      type="button"
                    >
                      {disconnectWhatsappMutation.isPending ? 'Cancelling...' : 'Cancel'}
                    </button>
                  </div>
                </div>
              )}

              {/* State C: Connected */}
              {activeIntegration.whatsapp_phone && activeIntegration.whatsapp_verified && (
                <div className="ed-whatsapp-section">
                  <p className="ed-whatsapp-connected">
                    <span className="ed-whatsapp-check" aria-hidden="true">&#10003;</span>
                    WhatsApp connected: <strong>{activeIntegration.whatsapp_phone}</strong>
                  </p>
                  <p className="ed-whatsapp-note">
                    Your daily digest will be delivered to this number.
                  </p>
                  <button
                    className="ed-sync-btn"
                    onClick={handleDisconnectWhatsapp}
                    disabled={disconnectWhatsappMutation.isPending}
                  >
                    {disconnectWhatsappMutation.isPending ? 'Disconnecting...' : 'Disconnect'}
                  </button>
                </div>
              )}

              {whatsappError && <p className="ed-error-text ed-whatsapp-message">{whatsappError}</p>}
              {whatsappSuccess && (
                <p className="ed-success-text ed-whatsapp-message">{whatsappSuccess}</p>
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
      {confirmModal}
    </DashboardLayout>
  );
}
