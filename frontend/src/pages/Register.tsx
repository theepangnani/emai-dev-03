import { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Auth.css';

export function Register() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    role: 'student',
    teacher_type: '',
  });
  const [googleData, setGoogleData] = useState<{
    google_id: string;
    google_access_token: string;
    google_refresh_token: string;
  } | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  // Handle Google OAuth redirect with pre-fill data
  useEffect(() => {
    const googleEmail = searchParams.get('google_email');
    const googleName = searchParams.get('google_name');
    const googleId = searchParams.get('google_id');
    const googleAccessToken = searchParams.get('google_access_token');
    const googleRefreshToken = searchParams.get('google_refresh_token');

    if (googleEmail && googleId) {
      setFormData((prev) => ({
        ...prev,
        email: googleEmail,
        full_name: googleName || '',
      }));
      setGoogleData({
        google_id: googleId,
        google_access_token: googleAccessToken || '',
        google_refresh_token: googleRefreshToken || '',
      });
      // Clear URL params
      setSearchParams({});
    }
  }, []);

  const isGoogleSignup = googleData !== null;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsLoading(true);

    try {
      await register({
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
        role: formData.role,
        ...(formData.role === 'teacher' && formData.teacher_type
          ? { teacher_type: formData.teacher_type }
          : {}),
        ...(googleData || {}),
      });
      navigate('/dashboard');
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const showDetails = import.meta.env.VITE_SHOW_ERROR_DETAILS !== 'false';
      if (detail && showDetails) {
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
          {isGoogleSignup ? 'Complete your Google account setup' : 'Create your account'}
        </p>

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

          <div className="form-group">
            <label htmlFor="role">I am a</label>
            <select id="role" name="role" value={formData.role} onChange={handleChange}>
              <option value="student">Student</option>
              <option value="parent">Parent</option>
              <option value="teacher">Teacher</option>
            </select>
          </div>

          {formData.role === 'teacher' && (
            <div className="form-group">
              <label htmlFor="teacher_type">Teacher Type</label>
              <select
                id="teacher_type"
                name="teacher_type"
                value={formData.teacher_type}
                onChange={handleChange}
              >
                <option value="">Select type...</option>
                <option value="school_teacher">School Teacher</option>
                <option value="private_tutor">Private Tutor</option>
              </select>
            </div>
          )}

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="••••••••"
              required
              minLength={6}
            />
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <input
              type="password"
              id="confirmPassword"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              placeholder="••••••••"
              required
            />
          </div>

          <button type="submit" className="auth-button" disabled={isLoading}>
            {isLoading ? 'Creating account...' : 'Create Account'}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
