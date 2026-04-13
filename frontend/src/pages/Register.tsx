import { useState, useEffect, useRef, useCallback } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api/auth';
import { isValidEmail } from '../utils/validation';
import { useFeatureToggles } from '../hooks/useFeatureToggle';
import { useBotProtection } from '../hooks/useBotProtection';
import { PasswordInput } from '../components/PasswordInput';
import './Auth.css';

type RegisterMode = 'email' | 'username';

export function Register() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [mode, setMode] = useState<RegisterMode>('email');
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    parent_email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    email_consent: false,
  });
  const [googleData, setGoogleData] = useState<{
    google_id: string;
  } | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [usernameStatus, setUsernameStatus] = useState<{
    checking: boolean;
    available: boolean | null;
    message: string;
  }>({ checking: false, available: null, message: '' });
  const { register } = useAuth();
  const navigate = useNavigate();
  const usernameTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const waitlistProcessedRef = useRef(false);
  const googleOAuthProcessedRef = useRef(false);
  const features = useFeatureToggles();
  const botProtection = useBotProtection();

  // Waitlist token state
  const [waitlistToken, setWaitlistToken] = useState<string | null>(null);
  const [waitlistVerifying, setWaitlistVerifying] = useState(false);
  const [waitlistEmail, setWaitlistEmail] = useState<string | null>(null);
  const [waitlistError, setWaitlistError] = useState('');

  // Handle waitlist token from URL
  useEffect(() => {
    if (waitlistProcessedRef.current) return;
    const token = searchParams.get('token');
    if (token) {
      waitlistProcessedRef.current = true;
      setWaitlistToken(token);
      setWaitlistVerifying(true);
      authApi.verifyWaitlistToken(token)
        .then((data) => {
          setFormData((prev) => ({
            ...prev,
            full_name: data.name || prev.full_name,
            email: data.email,
          }));
          setWaitlistEmail(data.email);
          setWaitlistVerifying(false);
        })
        .catch((err) => {
          const detail = err?.response?.data?.detail || 'Invalid or expired invitation token.';
          setWaitlistError(detail);
          setWaitlistVerifying(false);
        });
    } else if (features.waitlist_enabled) {
      // No token and waitlist is enabled -- redirect to waitlist page
      navigate('/waitlist', { replace: true });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle Google OAuth redirect with pre-fill data
  useEffect(() => {
    if (googleOAuthProcessedRef.current) return;
    const googleEmail = searchParams.get('google_email');
    const googleName = searchParams.get('google_name');
    const googleId = searchParams.get('google_id');

    if (googleEmail && googleId) {
      googleOAuthProcessedRef.current = true;
      setFormData((prev) => ({
        ...prev,
        email: googleEmail,
        full_name: googleName || '',
      }));
      setGoogleData({ google_id: googleId });
      setMode('email'); // Google OAuth forces email mode
      // Clear URL params
      setSearchParams({});
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const isGoogleSignup = googleData !== null;
  const isWaitlistSignup = waitlistEmail !== null;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  // Debounced username availability check
  const checkUsernameAvailability = useCallback((username: string) => {
    if (usernameTimerRef.current) {
      clearTimeout(usernameTimerRef.current);
    }

    const trimmed = username.trim().toLowerCase();

    if (!trimmed || trimmed.length < 3) {
      setUsernameStatus({ checking: false, available: null, message: '' });
      return;
    }

    setUsernameStatus({ checking: true, available: null, message: 'Checking...' });

    usernameTimerRef.current = setTimeout(async () => {
      try {
        const result = await authApi.checkUsername(trimmed);
        setUsernameStatus({
          checking: false,
          available: result.available,
          message: result.message,
        });
      } catch {
        setUsernameStatus({ checking: false, available: null, message: 'Could not check availability' });
      }
    }, 500);
  }, []);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (usernameTimerRef.current) {
        clearTimeout(usernameTimerRef.current);
      }
    };
  }, []);

  const handleUsernameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setFormData((prev) => ({ ...prev, username: value }));
    checkUsernameAvailability(value);
  };

  const handleModeSwitch = (newMode: RegisterMode) => {
    if (isGoogleSignup) return; // Google OAuth forces email mode
    if (isWaitlistSignup) return; // Waitlist forces email mode
    setMode(newMode);
    setError('');
    setUsernameStatus({ checking: false, available: null, message: '' });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (mode === 'email') {
      if (!isValidEmail(formData.email)) {
        setError('Please enter a valid email address');
        return;
      }
    } else {
      // Username mode validations
      const trimmedUsername = formData.username.trim().toLowerCase();
      if (!trimmedUsername || trimmedUsername.length < 3 || trimmedUsername.length > 20) {
        setError('Username must be 3-20 characters');
        return;
      }
      if (!/^[a-zA-Z0-9_]+$/.test(trimmedUsername)) {
        setError('Username can only contain letters, numbers, and underscores');
        return;
      }
      if (usernameStatus.available === false) {
        setError('Please choose an available username');
        return;
      }
      if (!isValidEmail(formData.parent_email)) {
        setError('Please enter a valid parent email address');
        return;
      }
    }

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsLoading(true);

    try {
      const { website, started_at } = botProtection.getFields();

      if (mode === 'email') {
        const registrationData: {
          email: string;
          password: string;
          full_name: string;
          roles: string[];
          google_id?: string;
          token?: string;
          website?: string;
          started_at?: number;
          email_consent?: boolean;
        } = {
          email: formData.email,
          password: formData.password,
          full_name: formData.full_name,
          roles: [],
          website,
          started_at,
          email_consent: formData.email_consent,
        };

        if (googleData) registrationData.google_id = googleData.google_id;
        if (waitlistToken) registrationData.token = waitlistToken;

        await register(registrationData);
        navigate('/onboarding');
      } else {
        // Username mode: auto-set student role
        const registrationData = {
          username: formData.username.trim().toLowerCase(),
          parent_email: formData.parent_email,
          password: formData.password,
          full_name: formData.full_name,
          roles: ['student'] as string[],
          website,
          started_at,
        };

        await register(registrationData);
        navigate('/dashboard');
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail) {
        setError(detail);
      } else {
        setError('Registration failed. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Show loading state while verifying waitlist token
  if (waitlistVerifying) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />
          <h1 className="auth-title">Verifying Invitation</h1>
          <p className="auth-subtitle">Please wait while we verify your invitation...</p>
        </div>
      </div>
    );
  }

  // Show error if waitlist token is invalid
  if (waitlistError) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />
          <h1 className="auth-title">Invalid Invitation</h1>
          <div className="auth-error">{waitlistError}</div>
          <p className="auth-subtitle" style={{ marginTop: '16px' }}>
            Your invitation link is invalid or has expired.
          </p>
          <p className="auth-footer">
            <Link to="/waitlist">Join the waitlist</Link> to request access.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />
        <h1 className="auth-title">Join ClassBridge</h1>
        <p className="auth-subtitle">
          {isGoogleSignup
            ? 'Complete your Google account setup'
            : isWaitlistSignup
              ? 'Complete your invited account setup'
              : 'Create your account to get started'}
        </p>

        {/* Mode toggle (hidden during Google or waitlist signup) */}
        {!isGoogleSignup && !isWaitlistSignup && (
          <div className="auth-mode-toggle">
            <button
              type="button"
              className={`auth-mode-btn ${mode === 'email' ? 'active' : ''}`}
              onClick={() => handleModeSwitch('email')}
            >
              Register with Email
            </button>
            <button
              type="button"
              className={`auth-mode-btn ${mode === 'username' ? 'active' : ''}`}
              onClick={() => handleModeSwitch('username')}
            >
              Register with Username
            </button>
          </div>
        )}

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <input {...botProtection.honeypotProps} />
          <div className="form-group">
            <label htmlFor="full_name">Full Name</label>
            <input
              type="text"
              id="full_name"
              name="full_name"
              value={formData.full_name}
              onChange={handleChange}
              placeholder="John Doe"
              required
            />
          </div>

          {mode === 'email' ? (
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="you@example.com"
                required
                disabled={isGoogleSignup || isWaitlistSignup}
              />
              {isWaitlistSignup && (
                <span className="form-hint">Email is set from your invitation and cannot be changed.</span>
              )}
            </div>
          ) : (
            <>
              <div className="form-group">
                <label htmlFor="username">Username</label>
                <input
                  type="text"
                  id="username"
                  name="username"
                  value={formData.username}
                  onChange={handleUsernameChange}
                  placeholder="cool_student_42"
                  required
                  minLength={3}
                  maxLength={20}
                  autoComplete="username"
                />
                {formData.username.trim().length >= 3 && (
                  <div
                    className={`username-status ${
                      usernameStatus.checking ? 'checking' :
                      usernameStatus.available === true ? 'available' :
                      usernameStatus.available === false ? 'taken' : ''
                    }`}
                    role="status"
                    aria-live="polite"
                  >
                    {usernameStatus.message}
                  </div>
                )}
              </div>

              <div className="form-group">
                <label htmlFor="parent_email">Parent Email</label>
                <input
                  type="email"
                  id="parent_email"
                  name="parent_email"
                  value={formData.parent_email}
                  onChange={handleChange}
                  placeholder="parent@example.com"
                  required
                />
                <span className="form-hint">Your parent will receive a notification to connect with your account.</span>
              </div>
            </>
          )}

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <PasswordInput
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="--------"
              required
              minLength={8}
            />
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <PasswordInput
              id="confirmPassword"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              placeholder="--------"
              required
            />
          </div>

          {mode === 'email' && (
            <div className="form-group" style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              <input
                type="checkbox"
                id="email_consent"
                checked={formData.email_consent}
                onChange={(e) => setFormData({ ...formData, email_consent: e.target.checked })}
                style={{ marginTop: 3, width: 16, height: 16, flexShrink: 0 }}
              />
              <label htmlFor="email_consent" style={{ fontSize: 13, color: '#6b7280', cursor: 'pointer' }}>
                I'd like to receive weekly study updates and tips via email
              </label>
            </div>
          )}

          <button type="submit" className="auth-button" disabled={isLoading}>
            {isLoading ? 'Creating account...' : 'Create Account'}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
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
