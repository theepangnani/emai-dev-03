import { useState, useCallback, useEffect, useRef } from 'react';
import { getGmailAuthUrl, connectGmail, updateIntegration, updateSettings, addMonitoredEmail, listIntegrations } from '../api/parentEmailDigest';
import './EmailDigestSetupWizard.css';

const TIMEZONES = [
  'America/Toronto',
  'America/Vancouver',
  'America/Edmonton',
  'America/Winnipeg',
  'America/Halifax',
  'America/St_Johns',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'UTC',
];

const DIGEST_FORMATS = [
  { value: 'full', label: 'Full' },
  { value: 'brief', label: 'Brief' },
  { value: 'actions_only', label: 'Actions Only' },
];

const CHANNEL_OPTIONS = [
  { value: 'email', label: 'Email' },
  { value: 'in_app', label: 'In-app notification' },
];

interface EmailDigestSetupWizardProps {
  open: boolean;
  onClose: () => void;
  childName?: string;
  onComplete?: (integrationId: number) => void;
}

type WizardStep = 1 | 2 | 3 | 4;

export function EmailDigestSetupWizard({
  open,
  onClose,
  childName,
  onComplete,
}: EmailDigestSetupWizardProps) {
  const [step, setStep] = useState<WizardStep>(1);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Step 1: Gmail connection
  const [gmailConnected, setGmailConnected] = useState(false);
  const [connectedEmail, setConnectedEmail] = useState('');
  const [integrationId, setIntegrationId] = useState<number | null>(null);

  // OAuth state
  const [oauthState, setOauthState] = useState('');
  const oauthStateRef = useRef(oauthState);

  // Step 2: Child info
  const [monitoredEmails, setMonitoredEmails] = useState<{ email: string; label: string }[]>([]);
  const [newEmail, setNewEmail] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [childFirstName, setChildFirstName] = useState(childName ?? '');

  // Step 3: Settings
  const [deliveryTime, setDeliveryTime] = useState('07:00');
  const [timezone, setTimezone] = useState('America/Toronto');
  const [digestFormat, setDigestFormat] = useState('full');
  const [channels, setChannels] = useState<string[]>(['in_app', 'email']);

  // Focus trap ref
  const modalRef = useRef<HTMLDivElement>(null);

  // Reset on open/close — check for existing integration
  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    setError('');
    setGmailConnected(false);
    setConnectedEmail('');
    setIntegrationId(null);
    setOauthState('');
    setMonitoredEmails([]);
    setNewEmail('');
    setNewLabel('');
    setChildFirstName(childName ?? '');
    setDeliveryTime('07:00');
    setTimezone('America/Toronto');
    setDigestFormat('full');
    setChannels(['in_app', 'email']);

    // Check if the parent already has an integration
    setLoading(true);
    setStep(1);
    listIntegrations()
      .then(({ data }) => {
        if (cancelled) return;
        if (data.length > 0) {
          const integration = data[0];
          setGmailConnected(true);
          setConnectedEmail(integration.gmail_address);
          setIntegrationId(integration.id);
          if (integration.monitored_emails && integration.monitored_emails.length > 0) {
            setMonitoredEmails(integration.monitored_emails.map(me => ({
              email: me.email_address,
              label: me.label || '',
            })));
          } else if (integration.child_school_email) {
            setMonitoredEmails([{ email: integration.child_school_email, label: '' }]);
          }
          if (integration.child_first_name) {
            setChildFirstName(integration.child_first_name);
          }
          setStep(2);
        }
      })
      .catch(() => {
        // Silently fall back to Step 1 on error
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [open, childName]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  // Keep ref in sync with state so the message handler always uses the latest value
  useEffect(() => {
    oauthStateRef.current = oauthState;
  }, [oauthState]);

  // Listen for OAuth callback message from popup
  useEffect(() => {
    if (!open) return;
    const handleMessage = async (event: MessageEvent) => {
      if (event.data?.type === 'gmail-oauth-callback' && event.data?.code) {
        setLoading(true);
        setError('');
        try {
          const redirectUri = window.location.origin + '/oauth/gmail/callback';
          const response = await connectGmail(event.data.code, oauthStateRef.current, redirectUri);
          setGmailConnected(true);
          setConnectedEmail(response.data.gmail_address ?? '');
          setIntegrationId(response.data.integration_id ?? null);
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : 'Failed to connect Gmail';
          setError(msg);
        } finally {
          setLoading(false);
        }
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [open]);

  const handleConnectGmail = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const redirectUri = window.location.origin + '/oauth/gmail/callback';
      const { data } = await getGmailAuthUrl(redirectUri);
      setOauthState(data.state);
      // Open OAuth in a popup
      const w = 500;
      const h = 600;
      const left = window.screenX + (window.outerWidth - w) / 2;
      const top = window.screenY + (window.outerHeight - h) / 2;
      window.open(data.authorization_url, 'gmail-oauth', `width=${w},height=${h},left=${left},top=${top}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to get auth URL';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleNextStep = useCallback(async () => {
    setError('');

    if (step === 1) {
      if (!gmailConnected) {
        setError('Please connect your Gmail account first.');
        return;
      }
      setStep(2);
    } else if (step === 2) {
      if (monitoredEmails.length === 0) {
        setError('Please add at least one email address to monitor.');
        return;
      }
      if (!childFirstName.trim()) {
        setError('Please enter your child\'s first name.');
        return;
      }
      // Save child info and monitored emails to the integration
      if (integrationId) {
        setLoading(true);
        try {
          await updateIntegration(integrationId, {
            child_school_email: monitoredEmails[0].email,
            child_first_name: childFirstName.trim(),
          });
          for (const entry of monitoredEmails) {
            try {
              await addMonitoredEmail(integrationId, {
                email_address: entry.email,
                label: entry.label || undefined,
              });
            } catch (err: unknown) {
              // Skip 409 (already exists) — not an error on re-entry
              const axiosErr = err as { response?: { status?: number } };
              if (axiosErr.response?.status !== 409) throw err;
            }
          }
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : 'Failed to save child info';
          setError(msg);
          setLoading(false);
          return;
        }
        setLoading(false);
      }
      setStep(3);
    } else if (step === 3) {
      if (channels.length === 0) {
        setError('Please select at least one notification channel.');
        return;
      }
      setStep(4);
    } else if (step === 4) {
      // Complete setup — save settings
      if (!integrationId) return;
      setLoading(true);
      try {
        await updateSettings(integrationId, {
          delivery_time: deliveryTime,
          timezone,
          digest_format: digestFormat,
          delivery_channels: channels.join(','),
        });
        onComplete?.(integrationId);
        onClose();
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to save settings';
        setError(msg);
      } finally {
        setLoading(false);
      }
    }
  }, [step, gmailConnected, monitoredEmails, childFirstName, channels, integrationId, deliveryTime, timezone, digestFormat, onComplete, onClose]);

  const handleBack = useCallback(() => {
    setError('');
    if (step > 1) setStep((step - 1) as WizardStep);
  }, [step]);

  const toggleChannel = useCallback((ch: string) => {
    setChannels(prev =>
      prev.includes(ch) ? prev.filter(c => c !== ch) : [...prev, ch]
    );
  }, []);

  if (!open) return null;

  const stepTitles = ['Connect Gmail', 'Child Info', 'Settings', 'Confirm'];

  return (
    <div className="edw-overlay" onClick={onClose}>
      <div
        className="edw-modal"
        ref={modalRef}
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Email Digest Setup"
      >
        {/* Header */}
        <div className="edw-header">
          <h2>Set Up Email Digest</h2>
          <button className="edw-close-btn" onClick={onClose} aria-label="Close">&times;</button>
        </div>

        {/* Step Indicator */}
        <div className="edw-steps" aria-label={`Step ${step} of 4: ${stepTitles[step - 1]}`}>
          {[1, 2, 3, 4].map((s, i) => (
            <span key={s}>
              {i > 0 && (
                <span className={`edw-step-line${s <= step ? ' edw-step-line--done' : ''}`} />
              )}
              <span
                className={`edw-step-dot${
                  s === step ? ' edw-step-dot--active' : s < step ? ' edw-step-dot--done' : ''
                }`}
              />
            </span>
          ))}
        </div>

        {/* Body */}
        <div className="edw-body">
          {error && <div className="edw-error">{error}</div>}

          {/* Step 1: Connect Gmail */}
          {step === 1 && (
            <>
              <h3 className="edw-step-title">Connect Your Gmail</h3>
              <p className="edw-step-desc">
                We need access to your Gmail to monitor emails from your child&rsquo;s school and
                create daily digests of important updates.
              </p>
              {gmailConnected ? (
                <div className="edw-connected-badge">
                  &#10003; Connected as {connectedEmail}
                </div>
              ) : (
                <button
                  className="edw-connect-btn"
                  onClick={handleConnectGmail}
                  disabled={loading}
                >
                  {loading ? 'Connecting...' : 'Connect Your Gmail'}
                </button>
              )}
            </>
          )}

          {/* Step 2: Monitored Emails */}
          {step === 2 && (
            <>
              <h3 className="edw-step-title">Emails to Monitor</h3>
              <p className="edw-step-desc">
                Add email addresses you want to monitor for school communications. You can add up to 10.
              </p>
              {monitoredEmails.length > 0 && (
                <div className="edw-monitored-list">
                  {monitoredEmails.map((entry, idx) => (
                    <div key={idx} className="edw-monitored-item">
                      <span className="edw-monitored-email">{entry.email}</span>
                      {entry.label && <span className="edw-monitored-label">{entry.label}</span>}
                      <button
                        type="button"
                        className="edw-monitored-remove"
                        onClick={() => setMonitoredEmails(prev => prev.filter((_, i) => i !== idx))}
                        aria-label={`Remove ${entry.email}`}
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {monitoredEmails.length < 10 && (
                <div className="edw-add-email-row">
                  <div className="edw-field" style={{ flex: 2 }}>
                    <label htmlFor="edw-new-email">Email Address</label>
                    <input
                      id="edw-new-email"
                      type="email"
                      placeholder="sender@school.ca"
                      value={newEmail}
                      onChange={e => setNewEmail(e.target.value)}
                      autoFocus
                    />
                  </div>
                  <div className="edw-field" style={{ flex: 1 }}>
                    <label htmlFor="edw-new-label">Label (optional)</label>
                    <input
                      id="edw-new-label"
                      type="text"
                      placeholder="e.g. Teacher"
                      value={newLabel}
                      onChange={e => setNewLabel(e.target.value)}
                    />
                  </div>
                  <button
                    type="button"
                    className="edw-btn-add"
                    disabled={!newEmail.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(newEmail.trim())}
                    onClick={() => {
                      const email = newEmail.trim().toLowerCase();
                      if (monitoredEmails.some(e => e.email === email)) {
                        setError('This email address is already in the list.');
                        return;
                      }
                      setMonitoredEmails(prev => [...prev, { email, label: newLabel.trim() }]);
                      setNewEmail('');
                      setNewLabel('');
                      setError('');
                    }}
                  >
                    Add
                  </button>
                </div>
              )}
              <div className="edw-field">
                <label htmlFor="edw-child-name">Child&rsquo;s First Name</label>
                <input
                  id="edw-child-name"
                  type="text"
                  placeholder="First name"
                  value={childFirstName}
                  onChange={e => setChildFirstName(e.target.value)}
                  className={error && !childFirstName.trim() ? 'edw-input-error' : ''}
                />
              </div>
            </>
          )}

          {/* Step 3: Configure Settings */}
          {step === 3 && (
            <>
              <h3 className="edw-step-title">Configure Your Digest</h3>
              <p className="edw-step-desc">
                Choose when and how you want to receive your email digest.
              </p>
              <div className="edw-field">
                <label htmlFor="edw-delivery-time">Delivery Time</label>
                <input
                  id="edw-delivery-time"
                  type="time"
                  value={deliveryTime}
                  onChange={e => setDeliveryTime(e.target.value)}
                />
              </div>
              <div className="edw-field">
                <label htmlFor="edw-timezone">Timezone</label>
                <select
                  id="edw-timezone"
                  value={timezone}
                  onChange={e => setTimezone(e.target.value)}
                >
                  {TIMEZONES.map(tz => (
                    <option key={tz} value={tz}>{tz.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              </div>
              <div className="edw-field">
                <label htmlFor="edw-format">Digest Format</label>
                <select
                  id="edw-format"
                  value={digestFormat}
                  onChange={e => setDigestFormat(e.target.value)}
                >
                  {DIGEST_FORMATS.map(f => (
                    <option key={f.value} value={f.value}>{f.label}</option>
                  ))}
                </select>
              </div>
              <div className="edw-field">
                <label>Notification Channels</label>
                <div className="edw-checkbox-group">
                  {CHANNEL_OPTIONS.map(ch => (
                    <label key={ch.value} className="edw-checkbox-label">
                      <input
                        type="checkbox"
                        checked={channels.includes(ch.value)}
                        onChange={() => toggleChannel(ch.value)}
                      />
                      {ch.label}
                    </label>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Step 4: Confirmation */}
          {step === 4 && (
            <>
              <h3 className="edw-step-title">Review &amp; Complete</h3>
              <p className="edw-step-desc">
                Please review your settings before completing the setup.
              </p>
              <div className="edw-summary">
                <div className="edw-summary-row">
                  <span className="edw-summary-label">Gmail Account</span>
                  <span className="edw-summary-value">{connectedEmail}</span>
                </div>
                <div className="edw-summary-row">
                  <span className="edw-summary-label">Child&rsquo;s Name</span>
                  <span className="edw-summary-value">{childFirstName}</span>
                </div>
                <div className="edw-summary-row">
                  <span className="edw-summary-label">Monitored Emails</span>
                  <span className="edw-summary-value">
                    {monitoredEmails.length} address{monitoredEmails.length !== 1 ? 'es' : ''}: {monitoredEmails.map(e => e.email).join(', ')}
                  </span>
                </div>
                <div className="edw-summary-row">
                  <span className="edw-summary-label">Delivery Time</span>
                  <span className="edw-summary-value">{deliveryTime}</span>
                </div>
                <div className="edw-summary-row">
                  <span className="edw-summary-label">Timezone</span>
                  <span className="edw-summary-value">{timezone.replace(/_/g, ' ')}</span>
                </div>
                <div className="edw-summary-row">
                  <span className="edw-summary-label">Format</span>
                  <span className="edw-summary-value">
                    {DIGEST_FORMATS.find(f => f.value === digestFormat)?.label ?? digestFormat}
                  </span>
                </div>
                <div className="edw-summary-row">
                  <span className="edw-summary-label">Channels</span>
                  <span className="edw-summary-value">
                    {channels.map(ch => CHANNEL_OPTIONS.find(o => o.value === ch)?.label ?? ch).join(', ')}
                  </span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="edw-footer">
          {step > 1 ? (
            <button className="edw-btn-back" onClick={handleBack} disabled={loading}>
              Back
            </button>
          ) : (
            <span />
          )}
          <button
            className="edw-btn-next"
            onClick={handleNextStep}
            disabled={loading || (step === 1 && !gmailConnected)}
          >
            {loading
              ? 'Saving...'
              : step === 4
                ? 'Complete Setup'
                : 'Next'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default EmailDigestSetupWizard;
