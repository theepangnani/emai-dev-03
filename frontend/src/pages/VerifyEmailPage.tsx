import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { authApi } from '../api/auth';
import './Auth.css';

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      // Intentional synchronous state update — we want immediate error rendering
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStatus('error');
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMessage('No verification token provided.');
      return;
    }

    authApi
      .verifyEmail(token)
      .then((data) => {
        setStatus('success');
        setMessage(data.message);
      })
      .catch((err) => {
        setStatus('error');
        const detail = err?.response?.data?.detail;
        setMessage(detail || 'Verification failed. The link may have expired.');
      });
  }, [searchParams]);

  return (
    <div className="auth-container">
      <div className="auth-card">
        <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />
        <h1 className="auth-title">Email Verification</h1>

        {status === 'loading' && (
          <p className="auth-subtitle">Verifying your email...</p>
        )}

        {status === 'success' && (
          <>
            <p className="auth-subtitle" style={{ color: 'var(--color-success, #16a34a)' }}>
              {message}
            </p>
            <Link to="/dashboard" className="auth-button" style={{ display: 'inline-block', textAlign: 'center', textDecoration: 'none', marginTop: '16px' }}>
              Go to Dashboard
            </Link>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="auth-error">{message}</div>
            <Link to="/login" className="auth-button" style={{ display: 'inline-block', textAlign: 'center', textDecoration: 'none', marginTop: '16px' }}>
              Go to Login
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
