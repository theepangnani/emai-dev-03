import { useState, useEffect, useRef, useCallback } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { googleApi } from '../api/client';
import { useFeature } from '../hooks/useFeatureToggle';
import './Auth.css';

export function Login() {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [lockoutSeconds, setLockoutSeconds] = useState(0);
  const [remainingAttempts, setRemainingAttempts] = useState<number | null>(null);
  const { user, login, loginWithToken } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const waitlistEnabled = useFeature('waitlist_enabled');
  const lockoutTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Redirect to dashboard once user is loaded (after OAuth or if already logged in)
  useEffect(() => {
    if (user) {
      navigate('/dashboard', { replace: true });
    }
  }, [user, navigate]);

  // Handle OAuth callback — set the token, then let the user-loaded effect navigate
  useEffect(() => {
    const token = searchParams.get('token');
    const oauthError = searchParams.get('error');

    if (token) {
      loginWithToken(token);
      setSearchParams({}, { replace: true });
    } else if (oauthError) {
      setError(`Google sign-in failed: ${oauthError}`);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams, loginWithToken]);

  // Lockout countdown timer
  const startLockoutTimer = useCallback((seconds: number) => {
    if (lockoutTimerRef.current) {
      clearInterval(lockoutTimerRef.current);
    }
    setLockoutSeconds(seconds);
    lockoutTimerRef.current = setInterval(() => {
      setLockoutSeconds((prev) => {
        if (prev <= 1) {
          if (lockoutTimerRef.current) {
            clearInterval(lockoutTimerRef.current);
            lockoutTimerRef.current = null;
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, []);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (lockoutTimerRef.current) {
        clearInterval(lockoutTimerRef.current);
      }
    };
  }, []);

  const formatLockoutTime = (seconds: number): string => {
    if (seconds >= 3600) {
      const hours = Math.floor(seconds / 3600);
      const mins = Math.floor((seconds % 3600) / 60);
      return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
    }
    if (seconds >= 60) {
      const mins = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
    }
    return `${seconds}s`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (lockoutSeconds > 0) return;
    setError('');
    setRemainingAttempts(null);
    setIsLoading(true);

    try {
      await login(identifier, password);
      setLockoutSeconds(0);
      setRemainingAttempts(null);
      navigate('/dashboard');
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail || '';
      const retryAfter = err?.response?.headers?.['retry-after'];

      if (status === 423) {
        // Account locked
        const seconds = retryAfter ? parseInt(retryAfter, 10) : 900;
        startLockoutTimer(seconds);
        setError('');
      } else if (detail) {
        setError(detail);
        // Parse remaining attempts from the detail message
        const match = detail.match(/(\d+) attempt\(s\) remaining/);
        if (match) {
          setRemainingAttempts(parseInt(match[1], 10));
        }
      } else {
        setError('Login failed. Please check your credentials.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setIsGoogleLoading(true);
    try {
      const { authorization_url } = await googleApi.getAuthUrl();
      window.location.href = authorization_url;
    } catch {
      setError('Failed to initiate Google sign-in');
      setIsGoogleLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />
        <h1 className="auth-title">Welcome to ClassBridge</h1>
        <p className="auth-subtitle">Sign in to your account</p>

        {lockoutSeconds > 0 && (
          <div className="auth-lockout-banner">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
            <div>
              <strong>Account locked</strong>
              <p>Too many failed login attempts. Try again in {formatLockoutTime(lockoutSeconds)}.</p>
              <p className="auth-lockout-hint">
                <Link to="/forgot-password">Reset your password</Link> to regain access immediately.
              </p>
            </div>
          </div>
        )}

        {error && <div className="auth-error">{error}</div>}

        {remainingAttempts !== null && remainingAttempts <= 2 && (
          <div className="auth-warning">
            {remainingAttempts} attempt{remainingAttempts !== 1 ? 's' : ''} remaining before your account is temporarily locked.
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label htmlFor="identifier">Email or Username</label>
            <input
              type="text"
              id="identifier"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="you@example.com or username"
              required
              disabled={lockoutSeconds > 0}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <div className="password-input-wrapper">
              <input
                type={showPassword ? 'text' : 'password'}
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                disabled={lockoutSeconds > 0}
              />
              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                    <line x1="1" y1="1" x2="23" y2="23"/>
                  </svg>
                ) : (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                )}
              </button>
            </div>
          </div>

          <button type="submit" className="auth-button" disabled={isLoading || lockoutSeconds > 0}>
            {isLoading ? 'Signing in...' : lockoutSeconds > 0 ? `Locked (${formatLockoutTime(lockoutSeconds)})` : 'Sign In'}
          </button>

          <p className="auth-forgot-link">
            <Link to="/forgot-password">Forgot password?</Link>
          </p>
        </form>

        <div className="auth-divider">
          <span>or</span>
        </div>

        <button
          type="button"
          className="google-button"
          onClick={handleGoogleSignIn}
          disabled={isGoogleLoading}
        >
          <svg className="google-icon" viewBox="0 0 24 24" width="20" height="20">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          {isGoogleLoading ? 'Redirecting...' : 'Continue with Google'}
        </button>

        <p className="auth-footer">
          {waitlistEnabled ? (
            <>Interested? <Link to="/waitlist">Join the Waitlist</Link></>
          ) : (
            <>Don't have an account? <Link to="/register">Sign up</Link></>
          )}
        </p>
        <p className="auth-footer" style={{ marginTop: '8px', fontSize: '13px' }}>
          <Link to="/privacy">Privacy Policy</Link>
          {' | '}
          <Link to="/terms">Terms of Service</Link>
        </p>
      </div>
    </div>
  );
}
