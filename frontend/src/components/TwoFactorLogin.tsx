/**
 * TwoFactorLogin — modal/inline step shown after a successful password login
 * when the server returns `{ requires_2fa: true, temp_token }`.
 *
 * On a valid code the component stores the real JWT and calls the `onSuccess`
 * callback so the parent (Login page / AuthContext) can complete the auth flow.
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import { login2FA } from '../api/twoFactor';
import './TwoFactorLogin.css';

interface TwoFactorLoginProps {
  /** The short-lived token returned by POST /auth/login when 2FA is required. */
  tempToken: string;
  /** Called with the full JWT after successful 2FA verification. */
  onSuccess: (accessToken: string, refreshToken: string | undefined, onboardingCompleted: boolean | undefined) => void;
  /** Called when the user cancels and wants to go back to the password form. */
  onCancel: () => void;
}

export function TwoFactorLogin({ tempToken, onSuccess, onCancel }: TwoFactorLoginProps) {
  const [code, setCode] = useState('');
  const [useBackup, setUseBackup] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-focus the code input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Re-focus when toggling backup mode
  useEffect(() => {
    setCode('');
    setError('');
    inputRef.current?.focus();
  }, [useBackup]);

  const handleSubmit = useCallback(async () => {
    const trimmed = code.trim();
    if (!trimmed) {
      setError('Please enter a code.');
      return;
    }
    const minLen = useBackup ? 8 : 6;
    if (trimmed.length < minLen) {
      setError(useBackup ? 'Backup codes are 8 characters.' : 'TOTP codes are 6 digits.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const data = await login2FA(tempToken, trimmed);
      onSuccess(data.access_token, data.refresh_token, data.onboarding_completed);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Invalid code. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [code, tempToken, onSuccess, useBackup]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSubmit();
  };

  return (
    <div className="tfa-login-overlay" role="dialog" aria-modal="true" aria-label="Two-factor authentication">
      <div className="tfa-login-card">
        {/* Icon */}
        <div className="tfa-login-icon" aria-hidden="true">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>

        <h2 className="tfa-login-title">Two-Factor Authentication</h2>

        {!useBackup ? (
          <p className="tfa-login-subtitle">
            Enter the 6-digit code from your authenticator app.
          </p>
        ) : (
          <p className="tfa-login-subtitle">
            Enter one of your 8-character backup codes.
          </p>
        )}

        <input
          ref={inputRef}
          type="text"
          inputMode={useBackup ? 'text' : 'numeric'}
          pattern={useBackup ? undefined : '[0-9]*'}
          maxLength={useBackup ? 8 : 6}
          className="tfa-login-input"
          placeholder={useBackup ? 'XXXXXXXX' : '000000'}
          value={code}
          onChange={e => {
            setError('');
            const raw = e.target.value;
            const cleaned = useBackup
              ? raw.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8)
              : raw.replace(/\D/g, '').slice(0, 6);
            setCode(cleaned);
          }}
          onKeyDown={handleKeyDown}
          autoComplete="one-time-code"
          aria-label={useBackup ? 'Backup code' : 'Authentication code'}
        />

        {error && (
          <p className="tfa-login-error" role="alert">
            {error}
          </p>
        )}

        <button
          className="tfa-login-btn-primary"
          onClick={handleSubmit}
          disabled={loading || code.length < (useBackup ? 8 : 6)}
        >
          {loading ? 'Verifying...' : 'Verify'}
        </button>

        {/* Toggle between TOTP and backup code */}
        <button
          className="tfa-login-btn-ghost"
          onClick={() => setUseBackup(u => !u)}
        >
          {useBackup ? 'Use authenticator app instead' : 'Use a backup code instead'}
        </button>

        <button className="tfa-login-btn-cancel" onClick={onCancel}>
          Back to login
        </button>
      </div>
    </div>
  );
}

export default TwoFactorLogin;
