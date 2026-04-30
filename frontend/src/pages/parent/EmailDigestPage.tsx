import { useState, useEffect, useRef } from 'react';
import { Link, useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../../components/DashboardLayout';
import {
  listIntegrations,
  getSettings,
  updateSettings,
  triggerSync,
  sendDigestNow,
  sendDigestNowForParent,
  listMonitoredEmails,
  addMonitoredEmail,
  removeMonitoredEmail,
  getGmailAuthUrl,
  connectGmail,
  sendWhatsAppOTP,
  verifyWhatsAppOTP,
  disconnectWhatsApp,
  listChildProfiles,
  createChildProfile,
  addChildSchoolEmail,
  removeChildSchoolEmail,
  listMonitoredSenders,
  addMonitoredSender,
  removeMonitoredSender,
  listDiscoveredSchoolEmails,
  assignDiscoveredSchoolEmail,
  dismissDiscoveredSchoolEmail,
  type EmailDigestIntegration,
  type EmailDigestSettings,
  type MonitoredEmail,
  type ChildProfile,
  type MonitoredSender,
  type MonitoredSenderAssignment,
  type SenderKidSelection,
  type DiscoveredSchoolEmail,
} from '../../api/parentEmailDigest';
import { parentApi, type ChildSummary } from '../../api/parent';
import { useConfirm } from '../../components/ConfirmModal';
import { useFeatureFlagEnabled } from '../../hooks/useFeatureToggle';
import { DigestHistoryPanel } from '../../components/parent/DigestHistoryPanel';
import { DashboardView } from './dashboard/DashboardView';
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

function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

/**
 * Resolve sender→assigned-kid chips robustly across API shapes (#4082).
 * Pre-#4082 backends returned only `child_profile_ids`; post-#4082 also
 * returns `assignments` with first_name. Prefer `assignments` when present,
 * otherwise derive from `child_profile_ids` via the already-loaded
 * childProfiles list.
 */
function senderChipAssignments(
  sender: MonitoredSender,
  childProfiles: ChildProfile[],
): MonitoredSenderAssignment[] {
  // #4093: check `!== undefined` specifically — an empty `assignments: []`
  // is a valid "no kids assigned" response, not a stale cache case.
  if (sender.assignments !== undefined) {
    return sender.assignments;
  }
  const ids = sender.child_profile_ids ?? [];
  const byId = new Map(childProfiles.map((p) => [p.id, p.first_name]));
  return ids.map((id) => ({
    child_profile_id: id,
    first_name: byId.get(id) ?? 'Unknown',
  }));
}

function senderKidNames(
  sender: MonitoredSender,
  childProfiles: ChildProfile[],
): string[] {
  return senderChipAssignments(sender, childProfiles).map((a) => a.first_name);
}

/**
 * Top-level Email Digest page. Feature-flag gated:
 *  - `parent.unified_digest_v2` OFF → legacy UI (preserved during ramp).
 *  - `parent.unified_digest_v2` ON  → unified multi-kid UI.
 *  - `?legacy=1` query param forces legacy regardless of flag (fallback ramp).
 *  - `email_digest_dashboard_v1` ON (CB-EDIGEST-002 #4594) → new aggregated
 *    dashboard surface. Wins over the unified UI; `?legacy=1` still escapes
 *    back to the legacy view. Flipping this flag remounts the page so each
 *    branch is a separate component (avoids rules-of-hooks issues when the
 *    cached flag value changes).
 *  - `/email-digest/settings` sub-path (#4682) escapes the dashboard branch
 *    so parents can still reach the legacy/unified settings UI when the
 *    dashboard flag is ON. The dashboard intentionally has no settings UI;
 *    this sub-route is the canonical settings entry point.
 *  - DashboardView is wrapped in `<DashboardLayout>` (#4681) so the
 *    sidebar/nav/logo chrome stay consistent with the rest of the app —
 *    legacy and unified branches already wrap.
 */
export function EmailDigestPage() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const unifiedEnabled = useFeatureFlagEnabled('parent.unified_digest_v2');
  const dashboardEnabled = useFeatureFlagEnabled('email_digest_dashboard_v1');
  const legacyForced = searchParams.get('legacy') === '1';
  // startsWith (not strict ===) so trailing slashes + future nested settings
  // sub-routes (e.g. /email-digest/settings/whatsapp) keep escaping the
  // dashboard branch.
  const isSettingsPath = location.pathname.startsWith('/email-digest/settings');
  if (legacyForced) {
    return <EmailDigestPageLegacy />;
  }
  if (dashboardEnabled && !isSettingsPath) {
    return (
      <DashboardLayout>
        <DashboardView />
      </DashboardLayout>
    );
  }
  return unifiedEnabled ? <EmailDigestPageUnified /> : <EmailDigestPageLegacy />;
}

// ============================================================================
// LEGACY PAGE — preserved as-is during the ramp. Reachable:
//   - when flag is off for a parent
//   - always via `/email-digest?legacy=1`
// Keep behavior unchanged from pre-#4016.
// ============================================================================
function EmailDigestPageLegacy() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { confirm, confirmModal } = useConfirm();
  const [whatsappPhone, setWhatsappPhone] = useState('');
  const [whatsappOtp, setWhatsappOtp] = useState('');
  const [whatsappError, setWhatsappError] = useState<string | null>(null);
  const [whatsappSuccess, setWhatsappSuccess] = useState<string | null>(null);

  const { data: integrations = [], isLoading: intLoading, isError: intError } = useQuery<EmailDigestIntegration[]>({
    queryKey: ['email-digest', 'integrations'],
    queryFn: () => listIntegrations().then((r) => r.data),
  });

  const kidParam = searchParams.get('kid');
  const activeIntegration =
    (kidParam
      ? integrations.find(
          (i) => (i.child_first_name ?? '').toLowerCase() === kidParam.toLowerCase(),
        )
      : undefined) ??
    integrations[0] ??
    null;

  const handleSelectKid = (firstName: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (firstName) {
      next.set('kid', firstName);
    } else {
      next.delete('kid');
    }
    setSearchParams(next, { replace: true });
  };

  const { data: settings } = useQuery<EmailDigestSettings>({
    queryKey: ['email-digest', 'settings', activeIntegration?.id],
    queryFn: () => getSettings(activeIntegration!.id).then((r) => r.data),
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

        {integrations.length > 1 && (
          <div className="ed-kid-switcher" role="tablist" aria-label="Switch child">
            {integrations.map((i) => {
              const name = i.child_first_name ?? i.child_school_email ?? `Child ${i.id}`;
              const isActive = activeIntegration?.id === i.id;
              return (
                <button
                  key={i.id}
                  role="tab"
                  aria-selected={isActive}
                  className={`ed-kid-chip${isActive ? ' ed-kid-chip--active' : ''}`}
                  onClick={() => handleSelectKid(i.child_first_name ?? null)}
                >
                  {name}
                </button>
              );
            })}
          </div>
        )}

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
                    {(sendDigestMutation.error as ApiErrorResponse)?.response?.data?.detail || 'Failed to send digest. Please try again.'}
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
                      ? '✓'
                      : status === 'partial'
                      ? '⚠'
                      : status === 'failed'
                      ? '✕'
                      : status === 'skipped'
                      ? 'ℹ'
                      : '✓';
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
                      {status === 'skipped' && payload?.reason === 'no_eligible_channels' && (
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
                      (!!newMonEmail.trim() && !isValidEmail(newMonEmail))
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

            {/* Digest History — shared panel (#4349 Stream E). */}
            <DigestHistoryPanel
              limit={50}
              emptyState="No digests delivered yet. Your first digest will appear here after the next scheduled run."
            />
          </>
        )}
      </div>
      {confirmModal}
    </DashboardLayout>
  );
}

// ============================================================================
// UNIFIED PAGE — new multi-kid layout (#4012). One daily digest per parent,
// school-email attribution, senders assignable across kids.
// ============================================================================

/**
 * Forwarding-detected badge state derived from `forwarding_seen_at`.
 * Within 14 days → active. Older → stopped. Null → never seen.
 */
function forwardingState(seenAt: string | null): {
  label: string;
  className: string;
} {
  if (!seenAt) {
    return {
      label: '⚠ No forwarded messages yet',
      className: 'ed-fwd-badge ed-fwd-badge--none',
    };
  }
  const seen = new Date(seenAt).getTime();
  const ageDays = (Date.now() - seen) / (1000 * 60 * 60 * 24);
  if (ageDays <= 14) {
    return {
      label: '✓ Forwarding active',
      className: 'ed-fwd-badge ed-fwd-badge--active',
    };
  }
  return {
    label: '⚠ Forwarding may have stopped',
    className: 'ed-fwd-badge ed-fwd-badge--stopped',
  };
}

interface AddSenderModalProps {
  profiles: ChildProfile[];
  onClose: () => void;
  onSubmit: (payload: {
    email_address: string;
    sender_name?: string;
    label?: string;
    child_profile_ids: SenderKidSelection;
  }) => void;
  pending: boolean;
  apiError: string | null;
  // #4053: parent clears its addSenderApiError when the user edits any input
  // so stale errors don't persist across re-submissions.
  onResetError?: () => void;
  // #4327: dual-mode Add/Edit. When `initialSender` is present, the modal
  // pre-fills its fields and treats email as read-only (it's the dedupe key).
  mode?: 'add' | 'edit';
  initialSender?: MonitoredSender | null;
}

function AddSenderModal({
  profiles,
  onClose,
  onSubmit,
  pending,
  apiError,
  onResetError,
  mode = 'add',
  initialSender = null,
}: AddSenderModalProps) {
  const isEdit = mode === 'edit' && initialSender != null;
  const [email, setEmail] = useState(isEdit ? initialSender!.email_address : '');
  const [name, setName] = useState(
    isEdit ? initialSender!.sender_name ?? '' : '',
  );
  const [label, setLabel] = useState(
    isEdit ? initialSender!.label ?? '' : '',
  );
  const [allKids, setAllKids] = useState(
    isEdit ? initialSender!.applies_to_all : true,
  );
  const [selectedIds, setSelectedIds] = useState<Set<number>>(
    isEdit ? new Set(initialSender!.child_profile_ids ?? []) : new Set(),
  );
  const [validationError, setValidationError] = useState<string | null>(null);

  // #4055: ESC-to-close for accessibility.
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const toggleKid = (id: number) => {
    onResetError?.();
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleSubmit = () => {
    setValidationError(null);
    const trimmedEmail = email.trim().toLowerCase();
    if (!isValidEmail(trimmedEmail)) {
      setValidationError('Enter a valid email address.');
      return;
    }
    if (!allKids && selectedIds.size === 0) {
      setValidationError('Select at least one kid, or check "All kids".');
      return;
    }
    onSubmit({
      email_address: trimmedEmail,
      sender_name: name.trim() || undefined,
      label: label.trim() || undefined,
      child_profile_ids: allKids ? 'all' : Array.from(selectedIds),
    });
  };

  return (
    <div
      className="ed-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={isEdit ? 'Edit monitored sender' : 'Add monitored sender'}
    >
      <div className="ed-modal">
        <div className="ed-modal__header">
          <h3>{isEdit ? 'Edit monitored sender' : 'Add monitored sender'}</h3>
          <button
            type="button"
            className="ed-modal__close"
            onClick={onClose}
            aria-label="Close"
          >
            &times;
          </button>
        </div>
        <div className="ed-modal__body">
          <label className="ed-modal__label" htmlFor="sender-email">
            Email<span aria-hidden="true"> *</span>
          </label>
          <input
            id="sender-email"
            type="email"
            className={`ed-input${isEdit ? ' ed-input--readonly' : ''}`}
            placeholder="teacher@school.ca"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              onResetError?.();
            }}
            readOnly={isEdit}
            autoFocus={!isEdit}
          />
          {isEdit && (
            <p className="ed-modal__hint">
              To change the email, remove this entry and add a new one.
            </p>
          )}

          <label className="ed-modal__label" htmlFor="sender-name">
            Name (optional)
          </label>
          <input
            id="sender-name"
            type="text"
            className="ed-input"
            placeholder="Mrs. Smith"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              onResetError?.();
            }}
          />

          <label className="ed-modal__label" htmlFor="sender-label">
            Label (optional)
          </label>
          <input
            id="sender-label"
            type="text"
            className="ed-input"
            placeholder="Homeroom, Principal, etc."
            value={label}
            onChange={(e) => {
              setLabel(e.target.value);
              onResetError?.();
            }}
          />

          <div className="ed-modal__kid-section">
            <p className="ed-modal__label">Applies to</p>
            <label className="ed-modal__checkbox">
              <input
                type="checkbox"
                checked={allKids}
                onChange={(e) => {
                  setAllKids(e.target.checked);
                  onResetError?.();
                }}
              />
              All kids (incl. future)
            </label>
            {!allKids && (
              <div className="ed-kid-chip-row" role="group" aria-label="Select kids">
                {profiles.map((p) => {
                  const active = selectedIds.has(p.id);
                  return (
                    <button
                      type="button"
                      key={p.id}
                      className={`ed-kid-chip ${active ? 'ed-kid-chip--active' : ''}`}
                      onClick={() => toggleKid(p.id)}
                      aria-pressed={active}
                    >
                      {p.first_name}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {validationError && (
            <p className="ed-error-text" role="alert">
              {validationError}
            </p>
          )}
          {apiError && !validationError && (
            <p className="ed-error-text" role="alert">
              {apiError}
            </p>
          )}
        </div>
        <div className="ed-modal__footer">
          <button
            type="button"
            className="ed-sync-btn"
            onClick={onClose}
            disabled={pending}
          >
            Cancel
          </button>
          <button
            type="button"
            className="ed-primary-btn"
            onClick={handleSubmit}
            disabled={pending}
          >
            {pending
              ? isEdit
                ? 'Saving...'
                : 'Adding...'
              : isEdit
                ? 'Save changes'
                : 'Add sender'}
          </button>
        </div>
      </div>
    </div>
  );
}

function EmailDigestPageUnified() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { confirm, confirmModal } = useConfirm();
  const [whatsappPhone, setWhatsappPhone] = useState('');
  const [whatsappOtp, setWhatsappOtp] = useState('');
  const [whatsappError, setWhatsappError] = useState<string | null>(null);
  const [whatsappSuccess, setWhatsappSuccess] = useState<string | null>(null);
  const [addSenderOpen, setAddSenderOpen] = useState(false);
  const [addSenderApiError, setAddSenderApiError] = useState<string | null>(null);
  // #4327: when set, the AddSenderModal opens in edit mode pre-filled with this sender.
  const [editSenderTarget, setEditSenderTarget] = useState<MonitoredSender | null>(null);
  const [addSchoolEmailFor, setAddSchoolEmailFor] = useState<number | null>(null);
  const [newSchoolEmail, setNewSchoolEmail] = useState('');
  // #4053: per-profile inline error for addSchoolEmailMutation.
  const [addEmailErrorByProfile, setAddEmailErrorByProfile] = useState<
    Record<number, string>
  >({});
  // #4053: dismissable banner for removeSenderMutation failures.
  const [removeSenderError, setRemoveSenderError] = useState<string | null>(null);
  // #4098: dismissable banner for removeSchoolEmailMutation failures.
  const [removeSchoolEmailError, setRemoveSchoolEmailError] = useState<string | null>(null);
  // #4055: restore focus to the "+ Add sender" trigger when modal closes.
  const addSenderTriggerRef = useRef<HTMLButtonElement | null>(null);
  // #4329: open-state for the discovered-school-emails assign modal.
  const [discoveredOpen, setDiscoveredOpen] = useState(false);

  const { data: integrations = [], isLoading: intLoading, isError: intError } =
    useQuery<EmailDigestIntegration[]>({
      queryKey: ['email-digest', 'integrations'],
      queryFn: () => listIntegrations().then((r) => r.data),
    });

  const activeIntegration = integrations[0] ?? null;

  const { data: settings } = useQuery<EmailDigestSettings>({
    queryKey: ['email-digest', 'settings', activeIntegration?.id],
    queryFn: () => getSettings(activeIntegration!.id).then((r) => r.data),
    enabled: !!activeIntegration,
  });

  const { data: childProfiles = [] } = useQuery<ChildProfile[]>({
    queryKey: ['parent', 'child-profiles'],
    queryFn: () => listChildProfiles().then((r) => r.data),
    // Always fetch — these are parent-scoped, not integration-scoped (#4048).
  });

  // #4044: also fetch the parent's actual kids so that kids without a
  // ParentChildProfile row still show up in "Your kids".
  const { data: parentKids = [] } = useQuery<ChildSummary[]>({
    queryKey: ['parent', 'children'],
    queryFn: () => parentApi.getChildren(),
  });

  const { data: senders = [] } = useQuery<MonitoredSender[]>({
    queryKey: ['parent', 'monitored-senders'],
    queryFn: () => listMonitoredSenders().then((r) => r.data),
    // Always fetch — parent-scoped (#4048).
  });

  // #4329: auto-discovered school addresses (unregistered To: hits).
  const { data: discovered = [] } = useQuery<DiscoveredSchoolEmail[]>({
    queryKey: ['parent', 'discovered-school-emails'],
    queryFn: () => listDiscoveredSchoolEmails().then((r) => r.data),
  });

  // #4329: assign / dismiss mutations for discovered addresses.
  const assignDiscoveredMutation = useMutation({
    mutationFn: ({ id, childProfileId }: { id: number; childProfileId: number }) =>
      assignDiscoveredSchoolEmail(id, childProfileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parent', 'discovered-school-emails'] });
      queryClient.invalidateQueries({ queryKey: ['parent', 'child-profiles'] });
    },
  });

  const dismissDiscoveredMutation = useMutation({
    mutationFn: (id: number) => dismissDiscoveredSchoolEmail(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parent', 'discovered-school-emails'] });
    },
  });

  // #4044: derive a unified list of "rows" to render. Every linked kid gets
  // a row; if a ParentChildProfile already exists for that kid (matched by
  // student_id == ChildSummary.user_id) we use it; otherwise we render a
  // placeholder row with empty school_emails and a "+ Add school email" CTA.
  // We also append any orphan profiles (no matching kid in parentKids) so
  // pre-existing data is never hidden.
  type KidRow =
    | { kind: 'profile'; profile: ChildProfile; firstName: string; userId: number | null }
    | { kind: 'placeholder'; userId: number; firstName: string };

  const profilesByUserId = new Map<number, ChildProfile>();
  // #4101 / I1: also build a case-insensitive first_name lookup so that
  // legacy wizard-created profiles whose student_id was never populated
  // by the Stream 1 backfill still merge into the linked-kid row instead
  // of rendering as a duplicate orphan row.
  const profilesByLowerName = new Map<string, ChildProfile>();
  for (const p of childProfiles) {
    if (p.student_id != null) {
      profilesByUserId.set(p.student_id, p);
    }
    if (p.first_name) {
      profilesByLowerName.set(p.first_name.toLowerCase(), p);
    }
  }

  const deriveFirstName = (fullName: string): string => {
    const trimmed = (fullName || '').trim();
    if (!trimmed) return 'Kid';
    return trimmed.split(/\s+/)[0];
  };

  const linkedProfileIds = new Set<number>();
  const kidRows: KidRow[] = [];
  for (const kid of parentKids) {
    const firstName = deriveFirstName(kid.full_name);
    // Prefer student_id match; fall back to case-insensitive first_name
    // match for legacy profiles whose student_id was never populated by
    // the Stream 1 backfill (#4101 / I1).
    //
    // #4100 pass-4 review (N1): a profile must not bind to TWO kids in
    // the same render. If the fallback returns a profile we've already
    // linked (because its student_id matched an earlier kid AND its
    // first_name now matches this kid), skip the fallback so the second
    // kid renders as a placeholder rather than aliasing onto a profile
    // that's already in use.
    const idMatch = profilesByUserId.get(kid.user_id);
    const nameMatch = profilesByLowerName.get(firstName.toLowerCase());
    const linked =
      idMatch ??
      (nameMatch && !linkedProfileIds.has(nameMatch.id) ? nameMatch : undefined);
    if (linked) {
      linkedProfileIds.add(linked.id);
      kidRows.push({
        kind: 'profile',
        profile: linked,
        firstName: linked.first_name,
        userId: kid.user_id,
      });
    } else {
      kidRows.push({
        kind: 'placeholder',
        userId: kid.user_id,
        firstName,
      });
    }
  }
  // Append true orphan profiles (no matching kid in parentKids by either
  // student_id or first_name — e.g., wizard pre-creation or an unlinked kid).
  for (const p of childProfiles) {
    if (!linkedProfileIds.has(p.id)) {
      kidRows.push({
        kind: 'profile',
        profile: p,
        firstName: p.first_name,
        userId: p.student_id,
      });
    }
  }

  const settingsMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<EmailDigestSettings> }) =>
      updateSettings(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-digest', 'settings'] });
    },
  });

  // #4056: Sync Now + Send Digest Now — mirrors legacy declarations.
  const syncMutation = useMutation({
    mutationFn: (id: number) => triggerSync(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-digest'] });
    },
  });

  // #4483 (D2/D3): unified UI is the multi-kid surface — call the parent-
  // scoped /send-now endpoint so the V2 flag dispatches once across all
  // integrations and produces multi-kid subject + body. Legacy view (single-
  // integration) keeps using the per-integration `sendDigestNow`.
  const sendDigestMutation = useMutation({
    mutationFn: () => sendDigestNowForParent(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-digest'] });
    },
  });

  // #4044: When adding a school email to a kid that doesn't have a
  // ParentChildProfile yet, auto-create the profile first, then add the
  // school email to it. The mutation now accepts EITHER an existing profileId
  // OR a (userId, firstName) pair; the dedupe key is the per-row reactive key
  // — for placeholders we use the user_id, for existing profiles the
  // profile.id. ApplicableErrorKey is what we surface inline-error against.
  type AddSchoolEmailVars =
    | { kind: 'existing'; profileId: number; errorKey: number; email: string }
    | { kind: 'create'; userId: number; firstName: string; errorKey: number; email: string };

  const addSchoolEmailMutation = useMutation({
    mutationFn: async (vars: AddSchoolEmailVars) => {
      let profileId: number;
      if (vars.kind === 'existing') {
        profileId = vars.profileId;
      } else {
        const created = await createChildProfile({
          first_name: vars.firstName,
          student_id: vars.userId,
        });
        profileId = created.data.id;
      }
      return addChildSchoolEmail(profileId, vars.email);
    },
    onSuccess: (_d, vars) => {
      queryClient.invalidateQueries({ queryKey: ['parent', 'child-profiles'] });
      setAddSchoolEmailFor(null);
      setNewSchoolEmail('');
      setAddEmailErrorByProfile((prev) => {
        const next = { ...prev };
        delete next[vars.errorKey];
        return next;
      });
    },
    // #4053: surface user-friendly error inline per-row.
    onError: (err: unknown, vars) => {
      const msg = getApiErrorMessage(
        err,
        "Couldn't add school email. Please try again.",
      );
      setAddEmailErrorByProfile((prev) => ({ ...prev, [vars.errorKey]: msg }));
    },
  });

  // #4098: remove a misclassified/legacy school email from a kid profile.
  const removeSchoolEmailMutation = useMutation({
    mutationFn: ({ profileId, emailId }: { profileId: number; emailId: number }) =>
      removeChildSchoolEmail(profileId, emailId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parent', 'child-profiles'] });
      setRemoveSchoolEmailError(null);
    },
    onError: (err: unknown) => {
      setRemoveSchoolEmailError(
        getApiErrorMessage(err, 'Could not remove school email. Please try again.'),
      );
    },
  });

  const addSenderMutation = useMutation({
    mutationFn: addMonitoredSender,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parent', 'monitored-senders'] });
      setAddSenderOpen(false);
      setEditSenderTarget(null);
      setAddSenderApiError(null);
    },
    onError: (err: unknown) => {
      setAddSenderApiError(getApiErrorMessage(err, 'Failed to add sender.'));
    },
  });

  const removeSenderMutation = useMutation({
    mutationFn: (id: number) => removeMonitoredSender(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parent', 'monitored-senders'] });
      setRemoveSenderError(null);
    },
    // #4053: surface remove failures as a dismissable banner above the list.
    onError: (err: unknown) => {
      setRemoveSenderError(
        getApiErrorMessage(err, 'Could not remove sender. Please try again.'),
      );
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
    },
  });

  // Gmail reconnect popup — same pattern as legacy.
  const oauthStateRef = useRef('');
  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      if (event.data?.type === 'gmail-oauth-callback' && event.data?.code) {
        try {
          const redirectUri = window.location.origin + '/oauth/gmail/callback';
          await connectGmail(event.data.code, oauthStateRef.current, redirectUri);
          queryClient.invalidateQueries({ queryKey: ['email-digest'] });
        } catch {
          // retry available
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

  const handleDeliveryTimeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    if (!activeIntegration) return;
    settingsMutation.mutate({
      id: activeIntegration.id,
      data: { delivery_time: e.target.value },
    });
  };

  const handleRemoveSender = async (sender: MonitoredSender) => {
    // #4055: surface which kids the sender applies to so parents know the impact.
    // #4082: fall back through assignments → child_profile_ids lookup when the
    // response lacks the richer shape (pre-#4082 backend or stale cache).
    const kidNames = senderKidNames(sender, childProfiles);
    const kidContext = sender.applies_to_all
      ? 'All kids (current and future)'
      : kidNames.join(', ') || 'no kids';
    const confirmed = await confirm({
      title: 'Remove monitored sender',
      message: `Remove "${sender.email_address}"? Applies to: ${kidContext}. This stops it from appearing in future digests.`,
      confirmLabel: 'Remove',
      variant: 'danger',
    });
    if (!confirmed) return;
    removeSenderMutation.mutate(sender.id);
  };

  const handleAddSchoolEmail = (row: KidRow) => {
    const trimmed = newSchoolEmail.trim().toLowerCase();
    if (!isValidEmail(trimmed)) return;
    // #4100 pass-1 review: negate userId for placeholder rows so
    // ChildSummary.user_id can never collide with a different kid's
    // ParentChildProfile.id (different tables, IDs CAN coincide).
    const errorKey =
      row.kind === 'profile' ? row.profile.id : -row.userId;
    setAddEmailErrorByProfile((prev) => {
      const next = { ...prev };
      delete next[errorKey];
      return next;
    });
    if (row.kind === 'profile') {
      addSchoolEmailMutation.mutate({
        kind: 'existing',
        profileId: row.profile.id,
        errorKey,
        email: trimmed,
      });
    } else {
      // #4044: kid has no profile yet — auto-create then add the email.
      addSchoolEmailMutation.mutate({
        kind: 'create',
        userId: row.userId,
        firstName: row.firstName,
        errorKey,
        email: trimmed,
      });
    }
  };

  // #4098: confirm + remove a school email row (parents must be able to clear
  // misclassified entries left behind by the legacy setup wizard).
  const handleRemoveSchoolEmail = async (
    profileId: number,
    emailId: number,
    addr: string,
  ) => {
    const confirmed = await confirm({
      title: 'Remove school email',
      message: `Remove "${addr}" from this kid? Future digests will no longer attribute messages from this address to this kid.`,
      confirmLabel: 'Remove',
      variant: 'danger',
    });
    if (!confirmed) return;
    removeSchoolEmailMutation.mutate({ profileId, emailId });
  };

  if (intLoading) {
    return (
      <DashboardLayout>
        <div className="ed-page">
          <div className="ed-loading">Loading...</div>
        </div>
      </DashboardLayout>
    );
  }

  if (intError) {
    return (
      <DashboardLayout>
        <div className="ed-page">
          <div className="ed-empty-state">
            <h2>Something went wrong</h2>
            <p>Failed to load email digest data. Please try again later.</p>
            <button className="ed-primary-btn" onClick={() => window.location.reload()}>
              Try Again
            </button>
          </div>
        </div>
      </DashboardLayout>
    );
  }

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
        </div>

        {/* #4048: when Gmail isn't connected yet, show a banner (not a full
            empty state) so parents can still pre-configure kids + senders. */}
        {!activeIntegration && (
          <div className="ed-connect-banner">
            <div className="ed-connect-banner__text">
              <h2>Connect Gmail to receive your digest</h2>
              <p>
                You can pre-configure your kids' school emails and monitored
                senders below. Connect Gmail from My Kids when you're ready.
              </p>
            </div>
            <button className="ed-primary-btn" onClick={() => navigate('/my-kids')}>
              Go to My Kids
            </button>
          </div>
        )}

        {activeIntegration && !activeIntegration.is_active && (
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

        {/* 1. Header band: Gmail + Delivery + WhatsApp — integration-scoped (#4048). */}
        {activeIntegration && (
        <div className="ed-settings-card">
          <h2 className="ed-section-title">Delivery</h2>
          <div className="ed-header-band">
            <div className="ed-header-band__item">
              <span className="ed-setting-label">Gmail</span>
              <span className="ed-header-band__value">
                {activeIntegration.gmail_address}
              </span>
            </div>
            <div className="ed-header-band__item">
              <label className="ed-setting-label" htmlFor="unified-delivery-time">
                Delivery time
              </label>
              <select
                id="unified-delivery-time"
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
            <div className="ed-header-band__item">
              <span className="ed-setting-label">WhatsApp</span>
              {activeIntegration.whatsapp_phone && activeIntegration.whatsapp_verified ? (
                <span className="ed-header-band__value">
                  <span className="ed-whatsapp-check" aria-hidden="true">&#10003;</span>{' '}
                  {activeIntegration.whatsapp_phone}
                </span>
              ) : activeIntegration.whatsapp_phone ? (
                <span className="ed-header-band__value">
                  Pending: {activeIntegration.whatsapp_phone}
                </span>
              ) : (
                <span className="ed-header-band__value ed-header-band__value--muted">
                  Not connected
                </span>
              )}
            </div>
          </div>

          {/* WhatsApp inline states */}
          {!activeIntegration.whatsapp_phone && (
            <div className="ed-whatsapp-section">
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
            </div>
          )}
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
          {activeIntegration.whatsapp_phone && activeIntegration.whatsapp_verified && (
            <button
              className="ed-sync-btn"
              onClick={handleDisconnectWhatsapp}
              disabled={disconnectWhatsappMutation.isPending}
            >
              {disconnectWhatsappMutation.isPending ? 'Disconnecting...' : 'Disconnect WhatsApp'}
            </button>
          )}

          {whatsappError && <p className="ed-error-text ed-whatsapp-message">{whatsappError}</p>}
          {whatsappSuccess && (
            <p className="ed-success-text ed-whatsapp-message">{whatsappSuccess}</p>
          )}
        </div>
        )}

        {/* Sync & Send (#4056) — port of legacy Sync Now + Send Digest Now. */}
        {activeIntegration && (
          <div className="ed-settings-card">
            <h2 className="ed-section-title">Sync & Send</h2>
            <p className="ed-help-text">
              Pull the latest emails from Gmail or send your digest now without waiting for the next scheduled run.
            </p>
            <div className="ed-settings-actions">
              <button
                type="button"
                className="ed-sync-btn"
                onClick={() => syncMutation.mutate(activeIntegration.id)}
                disabled={syncMutation.isPending || !activeIntegration.is_active}
              >
                {syncMutation.isPending ? 'Syncing...' : 'Sync Now'}
              </button>
              <button
                type="button"
                className="ed-primary-btn"
                onClick={() => {
                  sendDigestMutation.reset();
                  // #4483: parent-scoped — no integration_id needed.
                  sendDigestMutation.mutate();
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
                  {(sendDigestMutation.error as ApiErrorResponse)?.response?.data?.detail || 'Failed to send digest. Please try again.'}
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
                    ? '✓'
                    : status === 'partial'
                    ? '⚠'
                    : status === 'failed'
                    ? '✕'
                    : status === 'skipped'
                    ? 'ℹ'
                    : '✓';
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
                          // #4483: parent-scoped — no integration_id needed.
                          sendDigestMutation.mutate();
                        }}
                        disabled={sendDigestMutation.isPending}
                      >
                        Try again
                      </button>
                    )}
                    {status === 'skipped' && payload?.reason === 'no_eligible_channels' && (
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
        )}

        {/* 4329: Auto-discovered school addresses banner (above "Your kids"). */}
        {discovered.length > 0 && (
          <DiscoveredSchoolEmailsBanner
            count={discovered.length}
            onOpen={() => setDiscoveredOpen(true)}
          />
        )}

        {/* 2. Your kids */}
        <div className="ed-settings-card">
          <h2 className="ed-section-title">Your kids</h2>
          <p className="ed-help-text">
            School email is the board-issued address where teachers email your kid
            (e.g., @ocdsb.ca). Different from the ClassBridge login email.
          </p>
          {removeSchoolEmailError && (
            <div className="ed-remove-sender-error" role="alert">
              <span>{removeSchoolEmailError}</span>
              <button
                type="button"
                className="ed-remove-sender-error__dismiss"
                onClick={() => setRemoveSchoolEmailError(null)}
                aria-label="Dismiss error"
              >
                &times;
              </button>
            </div>
          )}
          {kidRows.length === 0 && (
            <p className="ed-empty-history">No kids on your account yet.</p>
          )}
          {/* #4044: render every linked kid (with or without a
              ParentChildProfile). Profiles get their school_emails;
              placeholders get a "+ Add school email" CTA that auto-creates
              the profile when the parent submits the first email.
              #4098: each existing school-email row gets a × remove button
              wired to handleRemoveSchoolEmail. */}
          {kidRows.map((row) => {
            // Stable per-row identity: profile.id when present, else negative
            // user_id sentinel so placeholder rows can't collide with profile
            // IDs in the keyed list / focus-target state.
            const rowKey =
              row.kind === 'profile' ? row.profile.id : -row.userId;
            // #4100 pass-1 review: use the negative-userId trick (same as
            // editTargetKey + rowKey) for placeholder errorKey so a profile
            // and a placeholder can never collide on errorKey when their
            // ids share a value (profile.id and ChildSummary.user_id come
            // from different tables and CAN coincide).
            const errorKey =
              row.kind === 'profile' ? row.profile.id : -row.userId;
            const editTargetKey =
              row.kind === 'profile' ? row.profile.id : -row.userId;
            const schoolEmails =
              row.kind === 'profile' ? row.profile.school_emails : [];
            const studentBadgeId =
              row.kind === 'profile'
                ? row.profile.student_id
                : row.userId;
            const addCtaLabel =
              schoolEmails.length === 0
                ? '+ Add school email'
                : '+ Add another school email';
            return (
              <div key={rowKey} className="ed-kid-row">
                <div className="ed-kid-row__header">
                  <span className="ed-kid-row__name">{row.firstName}</span>
                  {studentBadgeId != null && (
                    <span className="ed-kid-row__student-id">
                      student #{studentBadgeId}
                    </span>
                  )}
                </div>
                <div className="ed-school-email-list">
                  {schoolEmails.length === 0 && (
                    <p className="ed-empty-history ed-empty-history--inline">
                      No school email configured yet.
                    </p>
                  )}
                  {schoolEmails.map((se) => {
                    const badge = forwardingState(se.forwarding_seen_at);
                    // #4098: profile.id is guaranteed when school_emails is
                    // non-empty (placeholders have schoolEmails=[] above).
                    const ownerProfileId =
                      row.kind === 'profile' ? row.profile.id : null;
                    return (
                      <div key={se.id} className="ed-school-email-item">
                        <span className="ed-school-email-addr">{se.email_address}</span>
                        <span className={badge.className}>{badge.label}</span>
                        {ownerProfileId != null && (
                          <button
                            type="button"
                            className="ed-icon-btn"
                            aria-label={`Remove ${se.email_address}`}
                            onClick={() =>
                              handleRemoveSchoolEmail(
                                ownerProfileId,
                                se.id,
                                se.email_address,
                              )
                            }
                            disabled={removeSchoolEmailMutation.isPending}
                          >
                            &times;
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
                {addSchoolEmailFor === editTargetKey ? (
                  <>
                    <div className="ed-add-email-row">
                      <input
                        type="email"
                        className="ed-input"
                        placeholder="kid@ocdsb.ca"
                        value={newSchoolEmail}
                        onChange={(e) => setNewSchoolEmail(e.target.value)}
                        autoFocus
                      />
                      <button
                        className="ed-primary-btn"
                        onClick={() => handleAddSchoolEmail(row)}
                        disabled={
                          addSchoolEmailMutation.isPending ||
                          !isValidEmail(newSchoolEmail)
                        }
                      >
                        {addSchoolEmailMutation.isPending ? 'Adding...' : 'Add'}
                      </button>
                      <button
                        className="ed-sync-btn"
                        onClick={() => {
                          setAddSchoolEmailFor(null);
                          setNewSchoolEmail('');
                          setAddEmailErrorByProfile((prev) => {
                            const next = { ...prev };
                            delete next[errorKey];
                            return next;
                          });
                        }}
                        disabled={addSchoolEmailMutation.isPending}
                      >
                        Cancel
                      </button>
                    </div>
                    {addEmailErrorByProfile[errorKey] && (
                      <p className="ed-error-text" role="alert">
                        {addEmailErrorByProfile[errorKey]}
                      </p>
                    )}
                  </>
                ) : (
                  <button
                    type="button"
                    className="ed-link-btn"
                    onClick={() => {
                      setAddSchoolEmailFor(editTargetKey);
                      setNewSchoolEmail('');
                    }}
                  >
                    {addCtaLabel}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* 3. Monitored senders */}
        <div className="ed-settings-card">
          <div className="ed-section-title-row">
            <h2 className="ed-section-title">Monitored senders</h2>
            <button
              ref={addSenderTriggerRef}
              type="button"
              className="ed-primary-btn"
              onClick={() => {
                setAddSenderApiError(null);
                setAddSenderOpen(true);
              }}
            >
              + Add sender
            </button>
          </div>
          {removeSenderError && (
            <div className="ed-remove-sender-error" role="alert">
              <span>{removeSenderError}</span>
              <button
                type="button"
                className="ed-remove-sender-error__dismiss"
                onClick={() => setRemoveSenderError(null)}
                aria-label="Dismiss error"
              >
                &times;
              </button>
            </div>
          )}
          {senders.length === 0 ? (
            <p className="ed-empty-history">No monitored senders yet.</p>
          ) : (
            <div className="ed-monitored-list">
              {senders.map((s) => (
                <div key={s.id} className="ed-sender-row">
                  <div className="ed-sender-row__primary">
                    <span className="ed-monitored-email">{s.email_address}</span>
                    {s.sender_name && (
                      <span className="ed-monitored-name">{s.sender_name}</span>
                    )}
                    {s.label && <span className="ed-monitored-label">{s.label}</span>}
                  </div>
                  <div className="ed-sender-row__chips">
                    {s.applies_to_all ? (
                      <span className="ed-kid-chip ed-kid-chip--all" aria-label="Applies to all kids">
                        All kids
                      </span>
                    ) : (
                      // #4082: fall back to child_profile_ids + childProfiles
                      // lookup so a missing `assignments` field does not crash
                      // the page with `undefined.map`.
                      senderChipAssignments(s, childProfiles).map((a) => (
                        <span
                          key={a.child_profile_id}
                          className="ed-kid-chip ed-kid-chip--assigned"
                        >
                          {a.first_name}
                        </span>
                      ))
                    )}
                  </div>
                  <button
                    type="button"
                    className="ed-monitored-edit"
                    onClick={() => {
                      setAddSenderApiError(null);
                      setEditSenderTarget(s);
                    }}
                    aria-label={`Edit ${s.email_address}`}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="ed-monitored-remove"
                    onClick={() => handleRemoveSender(s)}
                    disabled={removeSenderMutation.isPending}
                    aria-label={`Remove ${s.email_address}`}
                  >
                    &times;
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 4. Digest History (#4056, #4349 Stream E) — shared panel. */}
        {activeIntegration && (
          <DigestHistoryPanel
            limit={50}
            emptyState="No digests delivered yet. Your first digest will appear here after the next scheduled run."
          />
        )}

        {(addSenderOpen || editSenderTarget) && (
          <AddSenderModal
            // #4327: keying by mode + sender id forces fresh state when the
            // user opens edit for a different row without unmounting between.
            key={editSenderTarget ? `edit-${editSenderTarget.id}` : 'add'}
            profiles={childProfiles}
            mode={editSenderTarget ? 'edit' : 'add'}
            initialSender={editSenderTarget}
            onClose={() => {
              setAddSenderOpen(false);
              setEditSenderTarget(null);
              setAddSenderApiError(null);
              // #4055: restore focus to the opening trigger on close.
              addSenderTriggerRef.current?.focus();
            }}
            onSubmit={(payload) => {
              setAddSenderApiError(null);
              addSenderMutation.mutate(payload);
            }}
            pending={addSenderMutation.isPending}
            apiError={addSenderApiError}
            onResetError={() => setAddSenderApiError(null)}
          />
        )}

        {/* #4329: discovered-school-emails assign modal */}
        {discoveredOpen && (
          <DiscoveredAssignModal
            discovered={discovered}
            profiles={childProfiles}
            assignPending={assignDiscoveredMutation.isPending}
            dismissPending={dismissDiscoveredMutation.isPending}
            onAssign={(id, childProfileId) =>
              assignDiscoveredMutation.mutate({ id, childProfileId })
            }
            onDismiss={(id) => dismissDiscoveredMutation.mutate(id)}
            onClose={() => setDiscoveredOpen(false)}
          />
        )}
      </div>
      {confirmModal}
    </DashboardLayout>
  );
}


// ---------------------------------------------------------------------------
// #4329 — Discovered school addresses banner + assign modal
// ---------------------------------------------------------------------------

interface DiscoveredSchoolEmailsBannerProps {
  count: number;
  onOpen: () => void;
}

function DiscoveredSchoolEmailsBanner({
  count,
  onOpen,
}: DiscoveredSchoolEmailsBannerProps) {
  const noun = count === 1 ? 'school address' : 'school addresses';
  return (
    <div
      className="ed-discovered-banner"
      role="region"
      aria-label="Unclassified school addresses"
    >
      <div className="ed-discovered-banner__copy">
        <strong>
          We&rsquo;ve seen {count} {noun} we couldn&rsquo;t classify.
        </strong>
        <p className="ed-help-text">
          Assigning each address to a kid keeps future emails attributed correctly.
        </p>
      </div>
      <button
        type="button"
        className="ed-primary-btn"
        onClick={onOpen}
      >
        Assign to a kid &rarr;
      </button>
    </div>
  );
}

interface DiscoveredAssignModalProps {
  discovered: DiscoveredSchoolEmail[];
  profiles: ChildProfile[];
  assignPending: boolean;
  dismissPending: boolean;
  onAssign: (id: number, childProfileId: number) => void;
  onDismiss: (id: number) => void;
  onClose: () => void;
}

function DiscoveredAssignModal({
  discovered,
  profiles,
  assignPending,
  dismissPending,
  onAssign,
  onDismiss,
  onClose,
}: DiscoveredAssignModalProps) {
  const [selections, setSelections] = useState<Record<number, number | ''>>({});

  // ESC-to-close — matches the AddSenderModal pattern.
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleAssign = (id: number) => {
    const choice = selections[id];
    if (typeof choice !== 'number') return;
    onAssign(id, choice);
  };

  const noProfiles = profiles.length === 0;

  return (
    <div
      className="ed-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Assign discovered school addresses"
    >
      <div className="ed-modal">
        <div className="ed-modal__header">
          <h3>Assign school addresses</h3>
          <button
            type="button"
            className="ed-modal__close"
            onClick={onClose}
            aria-label="Close"
          >
            &times;
          </button>
        </div>
        <div className="ed-modal__body">
          <p className="ed-help-text">
            We saw these school-looking addresses in your forwarded emails but they
            aren&rsquo;t registered for any kid yet. Assign each to a kid so future
            emails get attributed correctly.
          </p>
          {noProfiles && (
            <p className="ed-error-text">
              You need at least one kid profile before you can assign an address.
            </p>
          )}
          {discovered.length === 0 && (
            <p className="ed-empty-history">No discovered addresses.</p>
          )}
          <div className="ed-discovered-list">
            {discovered.map((d) => {
              const selected = selections[d.id];
              return (
                <div key={d.id} className="ed-discovered-row">
                  <div className="ed-discovered-row__primary">
                    <span className="ed-discovered-addr">{d.email_address}</span>
                    {d.sample_sender && (
                      <span className="ed-discovered-meta">
                        last sender: {d.sample_sender}
                      </span>
                    )}
                    <span className="ed-discovered-meta">
                      {d.occurrences} email{d.occurrences === 1 ? '' : 's'}
                    </span>
                  </div>
                  <div className="ed-discovered-row__actions">
                    <select
                      className="ed-input"
                      aria-label={`Assign ${d.email_address} to a kid`}
                      value={selected ?? ''}
                      onChange={(e) =>
                        setSelections((prev) => ({
                          ...prev,
                          [d.id]: e.target.value === '' ? '' : Number(e.target.value),
                        }))
                      }
                      disabled={noProfiles || assignPending}
                    >
                      <option value="">Select a kid…</option>
                      {profiles.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.first_name}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="ed-primary-btn"
                      onClick={() => handleAssign(d.id)}
                      disabled={
                        typeof selected !== 'number' || assignPending || noProfiles
                      }
                    >
                      {assignPending ? 'Assigning…' : 'Assign'}
                    </button>
                    <button
                      type="button"
                      className="ed-sync-btn"
                      onClick={() => onDismiss(d.id)}
                      disabled={dismissPending}
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
