import { useState, useEffect, useRef, useCallback } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api/auth';
import { isValidEmail } from '../utils/validation';
import './Auth.css';

type RegistrationMode = 'choose' | 'student' | 'standard';

export function Register() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [mode, setMode] = useState<RegistrationMode>('choose');
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    parent_email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
  });
  const [googleData, setGoogleData] = useState<{
    google_id: string;
  } | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
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

  // Handle Google OAuth redirect with pre-fill data
  useEffect(() => {
    const googleEmail = searchParams.get('google_email');
    const googleName = searchParams.get('google_name');
    const googleId = searchParams.get('google_id');

    if (googleEmail && googleId) {
      setFormData((prev) => ({
        ...prev,
        email: googleEmail,
        full_name: googleName || '',
      }));
      setGoogleData({ google_id: googleId });
      setMode('standard');
      // Clear URL params
      setSearchParams({});
    }
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  const isGoogleSignup = googleData !== null;

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (mode === 'standard' && !isValidEmail(formData.email)) {
      setError('Please enter a valid email address');
      return;
    }

    if (mode === 'student') {
      const trimmedUsername = formData.username.trim().toLowerCase();
      if (!trimmedUsername || trimmedUsername.length < 3 || trimmedUsername.length > 30) {
        setError('Username must be 3-30 characters');
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
      if (formData.email && !isValidEmail(formData.email)) {
        setError('Please enter a valid email address');
        return;
      }
      if (!formData.parent_email.trim()) {
        setError("Your parent or guardian's email is required");
        return;
      }
      if (!isValidEmail(formData.parent_email)) {
        setError('Please enter a valid email for your parent/guardian');
        return;
      }
    }

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsLoading(true);

    try {
      const registrationData: {
        email?: string;
        username?: string;
        parent_email?: string;
        password: string;
        full_name: string;
        roles: string[];
        google_id?: string;
      } = {
        password: formData.password,
        full_name: formData.full_name,
        roles: mode === 'student' ? ['student'] : [],
      };

      if (mode === 'student') {
        registrationData.username = formData.username.trim().toLowerCase();
        if (formData.email) registrationData.email = formData.email;
        registrationData.parent_email = formData.parent_email;
      } else {
        registrationData.email = formData.email;
      }

      if (googleData) registrationData.google_id = googleData.google_id;

      await register(registrationData);
      navigate(mode === 'student' ? '/dashboard' : '/onboarding');
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail) {
        setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      } else {
        setError('Registration failed. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const PasswordToggleIcon = ({ show }: { show: boolean }) =>
    show ? (
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
    );

  // Mode selection screen
  if (mode === 'choose') {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />
          <h1 className="auth-title">Join ClassBridge</h1>
          <p className="auth-subtitle">How will you use ClassBridge?</p>

          <div className="auth-mode-choices">
            <button
              className="auth-mode-btn"
              onClick={() => setMode('student')}
            >
              <span className="auth-mode-icon" aria-hidden="true">&#x1F393;</span>
              <span className="auth-mode-label">I'm a Student</span>
              <span className="auth-mode-desc">Register with a username</span>
            </button>

            <button
              className="auth-mode-btn"
              onClick={() => setMode('standard')}
            >
              <span className="auth-mode-icon" aria-hidden="true">&#x1F468;&#x200D;&#x1F469;&#x200D;&#x1F467;</span>
              <span className="auth-mode-label">Parent or Teacher</span>
              <span className="auth-mode-desc">Register with your email</span>
            </button>
          </div>

          <p className="auth-footer">
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />
        <h1 className="auth-title">
          {mode === 'student' ? 'Student Sign Up' : 'Join ClassBridge'}
        </h1>
        <p className="auth-subtitle">
          {isGoogleSignup
            ? 'Complete your Google account setup'
            : mode === 'student'
              ? 'Create your student account'
              : 'Create your account to get started'}
        </p>

        <button
          type="button"
          className="auth-back-btn"
          onClick={() => { setMode('choose'); setError(''); }}
        >
          &larr; Back
        </button>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
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

          {mode === 'student' ? (
            <>
              <div className="form-group">
                <label htmlFor="username">Username</label>
                <input
                  type="text"
                  id="username"
                  name="username"
                  value={formData.username}
                  onChange={handleUsernameChange}
                  placeholder="cool_student_123"
                  required
                  minLength={3}
                  maxLength={30}
                  autoComplete="username"
                />
                {formData.username.trim().length >= 3 && (
                  <div className={`username-status ${
                    usernameStatus.checking ? 'checking' :
                    usernameStatus.available === true ? 'available' :
                    usernameStatus.available === false ? 'taken' : ''
                  }`}>
                    {usernameStatus.message}
                  </div>
                )}
                <span className="form-hint">3-30 characters, letters, numbers, and underscores</span>
              </div>

              <div className="form-group">
                <label htmlFor="email">Email <span className="form-optional">(optional)</span></label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="you@example.com"
                />
              </div>

              <div className="form-group">
                <label htmlFor="parent_email">Parent/Guardian Email</label>
                <input
                  type="email"
                  id="parent_email"
                  name="parent_email"
                  value={formData.parent_email}
                  onChange={handleChange}
                  placeholder="parent@example.com"
                  required
                />
                <span className="form-hint">We'll invite your parent to connect with you on ClassBridge</span>
              </div>
            </>
          ) : (
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
                disabled={isGoogleSignup}
              />
            </div>
          )}

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <div className="password-input-wrapper">
              <input
                type={showPassword ? 'text' : 'password'}
                id="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                placeholder="&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;"
                required
                minLength={8}
              />
              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                <PasswordToggleIcon show={showPassword} />
              </button>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <div className="password-input-wrapper">
              <input
                type={showConfirmPassword ? 'text' : 'password'}
                id="confirmPassword"
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleChange}
                placeholder="&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;"
                required
              />
              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
              >
                <PasswordToggleIcon show={showConfirmPassword} />
              </button>
            </div>
          </div>

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
