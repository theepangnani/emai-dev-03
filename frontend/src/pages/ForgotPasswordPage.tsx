import { useState } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../api/client';
import { useBotProtection } from '../hooks/useBotProtection';
import './Auth.css';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const botProtection = useBotProtection();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      const { website, started_at } = botProtection.getFields();
      await authApi.forgotPassword(email, { website, started_at });
      setSubmitted(true);
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />
        <h1 className="auth-title">Forgot Password</h1>

        {submitted ? (
          <>
            <p className="auth-subtitle">
              If an account with that email exists, we've sent a password reset link. Check your inbox.
            </p>
            <p className="auth-footer">
              <Link to="/login">Back to Sign In</Link>
            </p>
          </>
        ) : (
          <>
            <p className="auth-subtitle">Enter your email and we'll send you a reset link.</p>

            {error && <div className="auth-error">{error}</div>}

            <form onSubmit={handleSubmit} className="auth-form">
              <input {...botProtection.honeypotProps} />
              <div className="form-group">
                <label htmlFor="email">Email</label>
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                />
              </div>

              <button type="submit" className="auth-button" disabled={isLoading}>
                {isLoading ? 'Sending...' : 'Send Reset Link'}
              </button>
            </form>

            <p className="auth-footer">
              Remember your password? <Link to="/login">Sign in</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
