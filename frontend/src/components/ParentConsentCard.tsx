import { useState, useCallback } from 'react';
import { api } from '../api/client';
import './ConsentGateway.css';

interface ChildConsentInfo {
  student_id: number;
  full_name: string;
  consent_status: string;
  requires_parent_consent: boolean;
  parent_consent_given: boolean;
}

interface Props {
  child: ChildConsentInfo;
  onConsentGiven: () => void;
}

/**
 * ParentConsentCard — shown on the parent dashboard when a linked child
 * needs parent consent under MFIPPA (#783).
 */
export function ParentConsentCard({ child, onConsentGiven }: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const handleConsent = useCallback(async () => {
    setSubmitting(true);
    setError(null);
    try {
      await api.post(`/api/consent/give-for-child/${child.student_id}`);
      setDone(true);
      onConsentGiven();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to record consent.');
    } finally {
      setSubmitting(false);
    }
  }, [child.student_id, onConsentGiven]);

  if (done || child.parent_consent_given) {
    return null;
  }

  return (
    <div className="parent-consent-card">
      <div className="parent-consent-card__header">
        <span>&#9888;&#65039;</span>
        <h3>Consent Required for {child.full_name}</h3>
      </div>
      <p>
        Under the Municipal Freedom of Information and Protection of Privacy Act (MFIPPA),
        your consent is required before{' '}
        <span className="parent-consent-card__child-name">{child.full_name}</span> can
        use ClassBridge. By consenting, you agree that ClassBridge may collect and process
        your child's educational data including:
      </p>
      <ul style={{ fontSize: 13, color: 'var(--text-secondary, #718096)', paddingLeft: 20, marginBottom: 12, lineHeight: 1.6 }}>
        <li>Name, email, and school information</li>
        <li>Course and assignment data</li>
        <li>Study materials and quiz responses for AI-powered learning tools</li>
      </ul>
      {error && <p style={{ color: '#dc2626', fontSize: 13, marginBottom: 8 }}>{error}</p>}
      <div className="parent-consent-card__actions">
        <button
          className="cookie-banner__btn cookie-banner__btn--accept"
          onClick={handleConsent}
          disabled={submitting}
        >
          {submitting ? 'Recording...' : 'I Consent'}
        </button>
      </div>
      <p style={{ fontSize: 11, color: 'var(--text-muted, #a0aec0)', marginTop: 10 }}>
        <a href="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>
        {' | '}
        <a href="/terms" target="_blank" rel="noopener noreferrer">Terms of Service</a>
      </p>
    </div>
  );
}
