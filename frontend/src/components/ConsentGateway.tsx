import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import './ConsentGateway.css';

interface ConsentStatus {
  student_id: number;
  consent_status: string;
  age: number | null;
  requires_parent_consent: boolean;
  requires_student_consent: boolean;
  parent_consent_given: boolean;
  student_consent_given: boolean;
}

/**
 * ConsentGateway — shown after login for students who haven't consented yet.
 * Wraps children and blocks access until consent is given.
 *
 * - Under 16: shows message to ask parent
 * - 16-17: shows consent form + note that parent must also consent
 * - 18+ / no DOB: shows standard consent form
 */
export function ConsentGateway({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const [status, setStatus] = useState<ConsentStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isStudent = user?.role === 'student' || user?.roles?.includes('student');

  useEffect(() => {
    if (!isStudent || !user) {
      setLoading(false);
      return;
    }

    const fetchStatus = async () => {
      try {
        // First get the student ID for this user
        const resp = await api.get('/api/students/me');
        const studentId = resp.data.id;
        const statusResp = await api.get(`/api/consent/status/${studentId}`);
        setStatus(statusResp.data);
      } catch {
        // If no student profile or endpoint fails, skip the gate
        setStatus(null);
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();
  }, [user, isStudent]);

  const handleGiveConsent = useCallback(async () => {
    setSubmitting(true);
    setError(null);
    try {
      await api.post('/api/consent/give', { accept: true });
      // Refresh status
      if (status) {
        const statusResp = await api.get(`/api/consent/status/${status.student_id}`);
        setStatus(statusResp.data);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to record consent. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }, [status]);

  // Non-student users or loading
  if (!isStudent || loading) {
    return <>{children}</>;
  }

  // No consent status found (no student profile or endpoint issue) — let through
  if (!status) {
    return <>{children}</>;
  }

  // Consent already given — let through
  if (status.consent_status === 'given') {
    return <>{children}</>;
  }

  // Under 16: parent must consent — student cannot proceed on their own
  if (status.age !== null && status.age < 16) {
    return (
      <div className="consent-gateway">
        <div className="consent-gateway__card">
          <div className="consent-gateway__icon">&#128101;</div>
          <h1>Parent Consent Required</h1>
          <p>
            Because you are under 16, your parent or guardian must provide consent before
            you can use ClassBridge. This is required under the Municipal Freedom of
            Information and Protection of Privacy Act (MFIPPA).
          </p>
          <div className="consent-gateway__under16-notice">
            <p>
              Please ask your parent or guardian to log in to their ClassBridge account
              and provide consent on your behalf.
            </p>
          </div>
          {status.parent_consent_given && (
            <p style={{ color: '#059669', fontWeight: 600, textAlign: 'center' }}>
              Parent consent has been given. You may now use ClassBridge.
            </p>
          )}
          <div className="consent-gateway__actions">
            <button className="consent-gateway__btn consent-gateway__btn--decline" onClick={logout}>
              Log Out
            </button>
          </div>
          <div className="consent-gateway__footer">
            <a href="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>
            {' | '}
            <a href="/terms" target="_blank" rel="noopener noreferrer">Terms of Service</a>
          </div>
        </div>
      </div>
    );
  }

  // 16-17: dual consent required
  if (status.consent_status === 'dual_required') {
    return (
      <div className="consent-gateway">
        <div className="consent-gateway__card">
          <div className="consent-gateway__icon">&#128220;</div>
          <h1>Consent Required</h1>
          <p>
            Before using ClassBridge, we need your consent to collect and process your
            educational data. This is required under the Municipal Freedom of Information
            and Protection of Privacy Act (MFIPPA).
          </p>

          <div className="consent-gateway__dual-notice">
            Because you are between 16 and 17, both you <strong>and</strong> your parent
            or guardian must provide consent. Your parent can consent from their ClassBridge
            account.
          </div>

          <div className="consent-gateway__info-box">
            <h3>What we collect and how we use it:</h3>
            <ul>
              <li>Your name, email, and school information for account management</li>
              <li>Course and assignment data from Google Classroom (when connected)</li>
              <li>Study materials and quiz responses to personalize AI study tools</li>
              <li>Usage patterns to improve the learning experience</li>
            </ul>
          </div>

          {error && <p style={{ color: '#dc2626', fontSize: 13, marginBottom: 12 }}>{error}</p>}

          <p style={{ fontSize: 13, color: '#718096', marginBottom: 4 }}>
            Parent consent: {status.parent_consent_given ? '  Given' : '  Pending'}
          </p>
          <p style={{ fontSize: 13, color: '#718096', marginBottom: 16 }}>
            Your consent: {status.student_consent_given ? '  Given' : '  Pending'}
          </p>

          <div className="consent-gateway__actions">
            <button className="consent-gateway__btn consent-gateway__btn--decline" onClick={logout}>
              Decline
            </button>
            <button
              className="consent-gateway__btn consent-gateway__btn--accept"
              onClick={handleGiveConsent}
              disabled={submitting || status.student_consent_given}
            >
              {submitting ? 'Saving...' : status.student_consent_given ? 'Consent Given' : 'I Consent'}
            </button>
          </div>

          <div className="consent-gateway__footer">
            <a href="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>
            {' | '}
            <a href="/terms" target="_blank" rel="noopener noreferrer">Terms of Service</a>
          </div>
        </div>
      </div>
    );
  }

  // 18+ or pending (standard consent)
  return (
    <div className="consent-gateway">
      <div className="consent-gateway__card">
        <div className="consent-gateway__icon">&#128220;</div>
        <h1>Consent Required</h1>
        <p>
          Before using ClassBridge, we need your consent to collect and process your
          educational data. This is required under the Municipal Freedom of Information
          and Protection of Privacy Act (MFIPPA).
        </p>

        <div className="consent-gateway__info-box">
          <h3>What we collect and how we use it:</h3>
          <ul>
            <li>Your name, email, and school information for account management</li>
            <li>Course and assignment data from Google Classroom (when connected)</li>
            <li>Study materials and quiz responses to personalize AI study tools</li>
            <li>Usage patterns to improve the learning experience</li>
          </ul>
        </div>

        {error && <p style={{ color: '#dc2626', fontSize: 13, marginBottom: 12 }}>{error}</p>}

        <div className="consent-gateway__actions">
          <button className="consent-gateway__btn consent-gateway__btn--decline" onClick={logout}>
            Decline
          </button>
          <button
            className="consent-gateway__btn consent-gateway__btn--accept"
            onClick={handleGiveConsent}
            disabled={submitting}
          >
            {submitting ? 'Saving...' : 'I Consent'}
          </button>
        </div>

        <div className="consent-gateway__footer">
          <a href="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>
          {' | '}
          <a href="/terms" target="_blank" rel="noopener noreferrer">Terms of Service</a>
        </div>
      </div>
    </div>
  );
}
