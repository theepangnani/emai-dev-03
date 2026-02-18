import { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { isValidEmail } from '../utils/validation';
import './Auth.css';

export function Register() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    username: '',
    parent_email: '',
  });
  const [isStudentMode, setIsStudentMode] = useState(false);
  const [googleData, setGoogleData] = useState<{
    google_id: string;
  } | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

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
      // Clear URL params
      setSearchParams({});
    }
  }, []);

  const isGoogleSignup = googleData !== null;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (isStudentMode) {
      // Student mode validation
      if (!formData.email && !formData.username) {
        setError('Please provide either an email or a username');
        return;
      }
      if (formData.username && !formData.email && !formData.parent_email) {
        setError('Parent email is required when registering with a username');
        return;
      }
      if (formData.email && !isValidEmail(formData.email)) {
        setError('Please enter a valid email address');
        return;
      }
      if (formData.parent_email && !isValidEmail(formData.parent_email)) {
        setError('Please enter a valid parent email address');
        return;
      }
      if (formData.username && !/^[a-zA-Z0-9_]{3,30}$/.test(formData.username)) {
        setError('Username must be 3-30 characters, letters, numbers, and underscores only');
        return;
      }
    } else {
      if (!isValidEmail(formData.email)) {
        setError('Please enter a valid email address');
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
        roles: isStudentMode ? ['student'] : [],
      };

      if (formData.email) registrationData.email = formData.email;
      if (isStudentMode && formData.username) registrationData.username = formData.username;
      if (isStudentMode && formData.parent_email) registrationData.parent_email = formData.parent_email;
      if (googleData) registrationData.google_id = googleData.google_id;

      await register(registrationData);
      navigate(isStudentMode ? '/dashboard' : '/onboarding');
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

  return (
    <div className="auth-container">
      <div className="auth-card">
        <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />
        <h1 className="auth-title">Join ClassBridge</h1>
        <p className="auth-subtitle">
          {isGoogleSignup ? 'Complete your Google account setup' : 'Stay connected with your child\'s education'}
        </p>

        {error && <div className="auth-error">{error}</div>}

        {/* Student toggle */}
        {!isGoogleSignup && (
          <div className="form-group" style={{ marginBottom: '16px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '14px' }}>
              <input
                type="checkbox"
                checked={isStudentMode}
                onChange={(e) => setIsStudentMode(e.target.checked)}
                style={{ width: '18px', height: '18px' }}
              />
              I'm a student
            </label>
            {isStudentMode && (
              <p style={{ fontSize: '13px', color: '#6b7280', margin: '8px 0 0' }}>
                Students can register with a username. Your parent will receive a request to link accounts.
              </p>
            )}
          </div>
        )}

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

          {isStudentMode && (
            <div className="form-group">
              <label htmlFor="username">Username</label>
              <input
                type="text"
                id="username"
                name="username"
                value={formData.username}
                onChange={handleChange}
                placeholder="my_username"
              />
              <span style={{ fontSize: '12px', color: '#6b7280' }}>
                3-30 characters, letters, numbers, and underscores
              </span>
            </div>
          )}

          <div className="form-group">
            <label htmlFor="email">
              Email{isStudentMode ? ' (optional if username provided)' : ''}
            </label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="you@example.com"
              required={!isStudentMode || !formData.username}
              disabled={isGoogleSignup}
            />
          </div>

          {isStudentMode && (
            <div className="form-group">
              <label htmlFor="parent_email">
                Parent Email{formData.username && !formData.email ? '' : ' (optional)'}
              </label>
              <input
                type="email"
                id="parent_email"
                name="parent_email"
                value={formData.parent_email}
                onChange={handleChange}
                placeholder="parent@example.com"
                required={isStudentMode && !!formData.username && !formData.email}
              />
              <span style={{ fontSize: '12px', color: '#6b7280' }}>
                Your parent will receive an invitation to connect
              </span>
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
                placeholder="••••••••"
                required
                minLength={8}
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

          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <div className="password-input-wrapper">
              <input
                type={showConfirmPassword ? 'text' : 'password'}
                id="confirmPassword"
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleChange}
                placeholder="••••••••"
                required
              />
              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
              >
                {showConfirmPassword ? (
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
