import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useToast } from '../components/Toast';
import { waitlistApi } from '../api/waitlist';
import { useBotProtection } from '../hooks/useBotProtection';
import './Auth.css';
import './WaitlistPage.css';

const ROLE_OPTIONS = [
  { value: 'parent', label: 'Parent' },
  { value: 'student', label: 'Student' },
  { value: 'teacher', label: 'Teacher' },
];

export function WaitlistPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [roles, setRoles] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const { toast } = useToast();
  const botProtection = useBotProtection();

  const isValidEmail = (value: string) =>
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

  const toggleRole = (role: string) => {
    setRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role],
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!name.trim()) {
      setError('Please enter your full name.');
      return;
    }
    if (!email.trim() || !isValidEmail(email)) {
      setError('Please enter a valid email address.');
      return;
    }
    if (roles.length === 0) {
      setError('Please select at least one role.');
      return;
    }

    setIsLoading(true);
    try {
      const { website, started_at } = botProtection.getFields();
      await waitlistApi.join({ name: name.trim(), email: email.trim(), roles, website, started_at });
      setSubmitted(true);
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      if (status === 409) {
        setError(detail || 'This email is already on the waitlist.');
      } else {
        toast('Something went wrong. Please try again later.', 'error');
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="auth-container">
        <div className="auth-card waitlist-success">
          <div className="waitlist-success-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
          <h1 className="auth-title">Thank you for joining the ClassBridge waitlist!</h1>
          <p className="waitlist-confirm-text">
            We've sent a confirmation email to <strong>{email}</strong>.
          </p>
          <p className="waitlist-confirm-text">
            You'll hear from us soon when your account is ready.
          </p>
          <Link to="/" className="auth-button waitlist-home-btn">
            Back to Home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />
        <h1 className="auth-title">Join the Waitlist</h1>
        <p className="auth-subtitle">
          Be the first to know when ClassBridge is ready for you.
        </p>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <input {...botProtection.honeypotProps} />
          <div className="form-group">
            <label htmlFor="waitlist-name">Full Name</label>
            <input
              type="text"
              id="waitlist-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your full name"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="waitlist-email">Email</label>
            <input
              type="email"
              id="waitlist-email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </div>

          <div className="form-group">
            <label>I am a...</label>
            <div className="checkbox-group">
              {ROLE_OPTIONS.map((opt) => (
                <label key={opt.value} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={roles.includes(opt.value)}
                    onChange={() => toggleRole(opt.value)}
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </div>

          <button
            type="submit"
            className="auth-button"
            disabled={isLoading}
          >
            {isLoading ? 'Submitting...' : 'Join Waitlist'}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
