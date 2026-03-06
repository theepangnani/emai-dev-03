import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { accountDeletionApi } from '../api/accountDeletion';
import type { DeletionStatus } from '../api/accountDeletion';
import './Auth.css';

export function ConfirmDeletionPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [result, setResult] = useState<DeletionStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setErrorMessage('Missing confirmation token. Please use the link from your email.');
      return;
    }

    accountDeletionApi.confirmDeletion(token)
      .then((data) => {
        setResult(data);
        setStatus('success');
      })
      .catch((err) => {
        setStatus('error');
        setErrorMessage(
          err?.response?.data?.detail || 'Failed to confirm deletion. The link may have expired.'
        );
      });
  }, [token]);

  return (
    <div className="auth-container">
      <div className="auth-card" style={{ maxWidth: 480, textAlign: 'center' }}>
        <h1 style={{ fontSize: '1.5rem', marginBottom: 16 }}>Account Deletion</h1>

        {status === 'loading' && (
          <p style={{ color: '#6b7280' }}>Processing your confirmation...</p>
        )}

        {status === 'success' && result && (
          <>
            <div style={{
              background: '#fee2e2',
              border: '1px solid #f87171',
              borderRadius: 8,
              padding: 16,
              marginBottom: 16,
              color: '#991b1b',
            }}>
              <p style={{ margin: '0 0 8px 0', fontWeight: 600 }}>
                Account deletion confirmed
              </p>
              <p style={{ margin: 0, fontSize: '0.9rem' }}>
                {result.message}
              </p>
            </div>
            <p style={{ color: '#6b7280', fontSize: '0.9rem' }}>
              You can still cancel this within 30 days by logging in and visiting Account Settings.
            </p>
            <Link
              to="/login"
              style={{
                display: 'inline-block',
                marginTop: 16,
                padding: '10px 24px',
                background: '#4f46e5',
                color: 'white',
                borderRadius: 8,
                textDecoration: 'none',
                fontWeight: 600,
              }}
            >
              Back to Login
            </Link>
          </>
        )}

        {status === 'error' && (
          <>
            <div style={{
              background: '#fef3c7',
              border: '1px solid #fbbf24',
              borderRadius: 8,
              padding: 16,
              marginBottom: 16,
              color: '#92400e',
            }}>
              <p style={{ margin: 0 }}>{errorMessage}</p>
            </div>
            <Link
              to="/login"
              style={{
                display: 'inline-block',
                marginTop: 16,
                padding: '10px 24px',
                background: '#4f46e5',
                color: 'white',
                borderRadius: 8,
                textDecoration: 'none',
                fontWeight: 600,
              }}
            >
              Back to Login
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
