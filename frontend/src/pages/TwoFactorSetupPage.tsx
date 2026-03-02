/**
 * TwoFactorSetupPage — step wizard for enrolling TOTP 2FA.
 *
 * Steps
 * -----
 * 1. Intro       — security explanation, "Enable 2FA" CTA
 * 2. QR code     — scan QR or enter secret manually
 * 3. Verify      — enter the 6-digit code to confirm enrollment
 * 4. Backup codes — display 8 one-time codes, copy-all button
 * 5. Done        — confirmation screen with link back to Account Settings
 */
import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { setup2FA, enable2FA, disable2FA } from '../api/twoFactor';
import type { TwoFASetupResponse } from '../api/twoFactor';
import './TwoFactorSetupPage.css';

type Step = 'intro' | 'qrcode' | 'verify' | 'backup' | 'done' | 'disable';

export function TwoFactorSetupPage() {
  const navigate = useNavigate();

  const [step, setStep] = useState<Step>('intro');
  const [setupData, setSetupData] = useState<TwoFASetupResponse | null>(null);
  const [code, setCode] = useState('');
  const [disableCode, setDisableCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [copied, setCopied] = useState(false);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleSetup = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await setup2FA();
      setSetupData(data);
      setStep('qrcode');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Failed to start 2FA setup. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleEnable = useCallback(async () => {
    if (!code || code.length < 6) {
      setError('Please enter the 6-digit code from your authenticator app.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await enable2FA(code);
      setStep('backup');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Invalid code. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [code]);

  const handleDisable = useCallback(async () => {
    if (!disableCode || disableCode.length < 6) {
      setError('Please enter your 6-digit code to confirm.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await disable2FA(disableCode);
      navigate('/settings/account');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Invalid code. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [disableCode, navigate]);

  const handleCopyAll = useCallback(async () => {
    if (!setupData) return;
    const text = setupData.backup_codes.join('\n');
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setError('Could not copy to clipboard. Please copy the codes manually.');
    }
  }, [setupData]);

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  const renderIntro = () => (
    <div className="tfa-card">
      <div className="tfa-shield-icon" aria-hidden="true">
        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <polyline points="9 12 11 14 15 10" />
        </svg>
      </div>
      <h2 className="tfa-title">Secure Your Account</h2>
      <p className="tfa-subtitle">
        Two-factor authentication (2FA) adds a second layer of security.
        After entering your password you will also need to enter a 6-digit
        code from your authenticator app.
      </p>
      <ul className="tfa-benefits">
        <li>Protects your account even if your password is stolen</li>
        <li>Works with Google Authenticator, Authy, 1Password, and more</li>
        <li>Backup codes let you access your account if you lose your phone</li>
      </ul>
      {error && <p className="tfa-error">{error}</p>}
      <button className="tfa-btn-primary" onClick={handleSetup} disabled={loading}>
        {loading ? 'Setting up...' : 'Enable Two-Factor Authentication'}
      </button>
      <button className="tfa-btn-ghost" onClick={() => navigate('/settings/account')}>
        Maybe later
      </button>
    </div>
  );

  const renderQRCode = () => (
    <div className="tfa-card">
      <div className="tfa-step-indicator">Step 1 of 3</div>
      <h2 className="tfa-title">Scan the QR Code</h2>
      <p className="tfa-subtitle">
        Open your authenticator app (Google Authenticator, Authy, etc.) and
        scan the QR code below, or enter the secret key manually.
      </p>

      {setupData?.qr_code_url && (
        <div className="tfa-qr-container">
          {setupData.qr_code_url.startsWith('data:image') ? (
            <img
              src={setupData.qr_code_url}
              alt="TOTP QR code — scan with your authenticator app"
              className="tfa-qr-image"
            />
          ) : (
            // Fallback: show the URI as text so user can copy it
            <p className="tfa-uri-fallback">
              <strong>Provisioning URI:</strong>
              <code className="tfa-secret-code">{setupData.qr_code_url}</code>
            </p>
          )}
        </div>
      )}

      <button
        className="tfa-btn-ghost tfa-secret-toggle"
        onClick={() => setShowSecret(s => !s)}
      >
        {showSecret ? 'Hide manual entry key' : 'Can\'t scan? Enter key manually'}
      </button>

      {showSecret && setupData?.secret && (
        <div className="tfa-secret-box">
          <p className="tfa-secret-label">Secret key (enter in your app):</p>
          <code className="tfa-secret-code">{setupData.secret}</code>
        </div>
      )}

      <div className="tfa-nav-row">
        <button className="tfa-btn-ghost" onClick={() => setStep('intro')}>
          Back
        </button>
        <button className="tfa-btn-primary" onClick={() => setStep('verify')}>
          Next — Enter Code
        </button>
      </div>
    </div>
  );

  const renderVerify = () => (
    <div className="tfa-card">
      <div className="tfa-step-indicator">Step 2 of 3</div>
      <h2 className="tfa-title">Verify Your Authenticator</h2>
      <p className="tfa-subtitle">
        Enter the 6-digit code shown in your authenticator app to confirm
        that setup was successful.
      </p>
      <input
        type="text"
        inputMode="numeric"
        pattern="[0-9]*"
        maxLength={6}
        className="tfa-code-input"
        placeholder="000000"
        value={code}
        onChange={e => {
          setError('');
          setCode(e.target.value.replace(/\D/g, '').slice(0, 6));
        }}
        onKeyDown={e => { if (e.key === 'Enter') handleEnable(); }}
        autoFocus
        autoComplete="one-time-code"
      />
      {error && <p className="tfa-error">{error}</p>}
      <div className="tfa-nav-row">
        <button className="tfa-btn-ghost" onClick={() => { setCode(''); setStep('qrcode'); }}>
          Back
        </button>
        <button
          className="tfa-btn-primary"
          onClick={handleEnable}
          disabled={loading || code.length < 6}
        >
          {loading ? 'Verifying...' : 'Enable 2FA'}
        </button>
      </div>
    </div>
  );

  const renderBackupCodes = () => (
    <div className="tfa-card">
      <div className="tfa-step-indicator">Step 3 of 3</div>
      <div className="tfa-check-icon" aria-hidden="true">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <polyline points="9 12 11 14 15 10" />
        </svg>
      </div>
      <h2 className="tfa-title">Save Your Backup Codes</h2>
      <p className="tfa-subtitle">
        If you ever lose access to your authenticator app, you can use one of
        these backup codes to log in. Each code can only be used once.
      </p>
      <div className="tfa-backup-grid">
        {(setupData?.backup_codes ?? []).map((c, i) => (
          <code key={i} className="tfa-backup-code">{c}</code>
        ))}
      </div>
      <button className="tfa-btn-secondary" onClick={handleCopyAll}>
        {copied ? 'Copied!' : 'Copy All Codes'}
      </button>
      {error && <p className="tfa-error">{error}</p>}
      <p className="tfa-warning">
        Store these codes somewhere safe. They will not be shown again in full.
      </p>
      <button className="tfa-btn-primary" onClick={() => setStep('done')}>
        I have saved my codes
      </button>
    </div>
  );

  const renderDone = () => (
    <div className="tfa-card">
      <div className="tfa-check-icon tfa-check-icon--green" aria-hidden="true">
        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <polyline points="9 12 11 14 15 10" />
        </svg>
      </div>
      <h2 className="tfa-title">Two-Factor Authentication Enabled</h2>
      <p className="tfa-subtitle">
        Your account is now protected with 2FA. You will be asked for a code
        from your authenticator app each time you sign in.
      </p>
      <button className="tfa-btn-primary" onClick={() => navigate('/settings/account')}>
        Back to Account Settings
      </button>
    </div>
  );

  const renderDisable = () => (
    <div className="tfa-card">
      <h2 className="tfa-title tfa-title--danger">Disable Two-Factor Authentication</h2>
      <p className="tfa-subtitle">
        Enter the 6-digit code from your authenticator app (or a backup code)
        to confirm that you want to disable 2FA.
      </p>
      <input
        type="text"
        inputMode="numeric"
        pattern="[0-9]*"
        maxLength={8}
        className="tfa-code-input"
        placeholder="000000"
        value={disableCode}
        onChange={e => {
          setError('');
          setDisableCode(e.target.value.replace(/\D/g, '').slice(0, 8));
        }}
        onKeyDown={e => { if (e.key === 'Enter') handleDisable(); }}
        autoFocus
        autoComplete="one-time-code"
      />
      {error && <p className="tfa-error">{error}</p>}
      <div className="tfa-nav-row">
        <button className="tfa-btn-ghost" onClick={() => navigate('/settings/account')}>
          Cancel
        </button>
        <button
          className="tfa-btn-danger"
          onClick={handleDisable}
          disabled={loading || disableCode.length < 6}
        >
          {loading ? 'Disabling...' : 'Disable 2FA'}
        </button>
      </div>
    </div>
  );

  // ---------------------------------------------------------------------------
  // Main render
  // ---------------------------------------------------------------------------

  return (
    <DashboardLayout welcomeSubtitle="Manage your account security">
      <div className="tfa-page">
        <div className="tfa-breadcrumb">
          <button className="tfa-breadcrumb-link" onClick={() => navigate('/settings/account')}>
            Account Settings
          </button>
          <span className="tfa-breadcrumb-sep">/</span>
          <span>Two-Factor Authentication</span>
        </div>

        {step === 'intro' && renderIntro()}
        {step === 'qrcode' && renderQRCode()}
        {step === 'verify' && renderVerify()}
        {step === 'backup' && renderBackupCodes()}
        {step === 'done' && renderDone()}
        {step === 'disable' && renderDisable()}
      </div>
    </DashboardLayout>
  );
}

export default TwoFactorSetupPage;
