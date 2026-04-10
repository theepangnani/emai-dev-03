import { useEffect, useMemo } from 'react';

export function GmailOAuthCallbackPage() {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const code = params.get('code');
  const state = params.get('state');
  const error = params.get('error');

  const hasOpener = typeof window !== 'undefined' && !!window.opener;

  // Derive status from URL params (no setState needed)
  const status: 'success' | 'error' = error
    ? 'error'
    : !code
      ? 'error'
      : hasOpener
        ? 'success'
        : 'error';

  const errorMessage = error
    ? (error === 'access_denied' ? 'Gmail access was denied.' : `OAuth error: ${error}`)
    : !code
      ? 'No authorization code received from Google.'
      : !hasOpener
        ? 'This page should be opened from the Email Digest setup wizard. Please go back and try again.'
        : '';

  useEffect(() => {
    if (!code || error) return;

    // Send the code back to the opener (setup wizard) window
    if (window.opener) {
      window.opener.postMessage(
        { type: 'gmail-oauth-callback', code, state },
        window.location.origin
      );
      // Close popup after a short delay so user sees success
      setTimeout(() => window.close(), 1500);
    }
  }, [code, state, error]);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      padding: '24px',
      textAlign: 'center',
      background: '#f5f7fa',
    }}>
      {status === 'success' && (
        <>
          <div style={{ fontSize: '24px', marginBottom: '12px', color: '#10b981' }}>Gmail Connected!</div>
          <p style={{ color: '#6b7280' }}>This window will close automatically.</p>
        </>
      )}
      {status === 'error' && (
        <>
          <div style={{ fontSize: '24px', marginBottom: '12px', color: '#ef4444' }}>Connection Failed</div>
          <p style={{ color: '#6b7280', maxWidth: '400px' }}>{errorMessage}</p>
          <button
            onClick={() => window.close()}
            style={{
              marginTop: '16px',
              padding: '10px 24px',
              background: '#4A90D9',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '14px',
            }}
          >
            Close
          </button>
        </>
      )}
    </div>
  );
}
