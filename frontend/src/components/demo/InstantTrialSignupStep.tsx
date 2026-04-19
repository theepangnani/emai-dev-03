import { useState, type FormEvent } from 'react';
import { createSession, type DemoRole, type CreateDemoSessionResponse } from '../../api/demo';
import {
  IconArrowRight,
  IconOther,
  IconParent,
  IconShield,
  IconStudent,
  IconTeacher,
} from './icons';

const ROLES: { value: DemoRole; label: string; Icon: typeof IconParent }[] = [
  { value: 'parent', label: 'Parent', Icon: IconParent },
  { value: 'student', label: 'Student', Icon: IconStudent },
  { value: 'teacher', label: 'Teacher', Icon: IconTeacher },
  { value: 'other', label: 'Other', Icon: IconOther },
];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface Props {
  onSuccess: (res: CreateDemoSessionResponse, email: string) => void;
}

/** Step 1 — collect name/email/role/consent and create the demo session. */
export function InstantTrialSignupStep({ onSuccess }: Props) {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<DemoRole | ''>('');
  const [consent, setConsent] = useState(false);
  const [honeypot, setHoneypot] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string>('');

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!fullName.trim()) errs.full_name = 'Please enter your full name.';
    if (!email.trim() || !EMAIL_RE.test(email.trim())) {
      errs.email = 'That looks off. Try checking for a missing "@" or TLD.';
    }
    if (!role) errs.role = 'Please pick the role that fits best.';
    if (!consent) errs.consent = 'Please accept the consent statement to continue.';
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError('');
    if (!validate()) return;
    setSubmitting(true);
    setTimedOut(false);

    const timer = window.setTimeout(() => setTimedOut(true), 10_000);
    try {
      const res = await createSession({
        full_name: fullName.trim(),
        email: email.trim(),
        role: role as DemoRole,
        consent,
        // Honeypot is forwarded only if non-empty (bot signal).
        _hp: honeypot,
      });
      onSuccess(res, email.trim());
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: unknown } }; message?: string };
      const detail = axiosErr?.response?.data?.detail;
      const message =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail) && detail[0]?.msg
            ? String(detail[0].msg)
            : axiosErr?.message ?? 'Something went wrong. Please try again.';
      setFormError(message);
    } finally {
      window.clearTimeout(timer);
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate>
      {/* Honeypot — screen-reader + keyboard users skip it. */}
      <input
        type="text"
        name="_hp"
        className="demo-honeypot"
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        value={honeypot}
        onChange={(e) => setHoneypot(e.target.value)}
      />

      {formError && <div className="demo-form-error" role="alert">{formError}</div>}

      <p className="demo-signup-greeting">Hi! Who&rsquo;s trying the demo?</p>

      <div className="demo-form-group">
        <label htmlFor="demo-full-name">Full name</label>
        <input
          id="demo-full-name"
          type="text"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          autoComplete="name"
          aria-invalid={!!fieldErrors.full_name}
          aria-describedby={fieldErrors.full_name ? 'demo-err-name' : undefined}
        />
        {fieldErrors.full_name && <div id="demo-err-name" className="demo-field-error">{fieldErrors.full_name}</div>}
      </div>

      <div className="demo-form-group">
        <label htmlFor="demo-email">Email</label>
        <input
          id="demo-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          aria-invalid={!!fieldErrors.email}
          aria-describedby={fieldErrors.email ? 'demo-err-email' : undefined}
        />
        {fieldErrors.email && <div id="demo-err-email" className="demo-field-error">{fieldErrors.email}</div>}
      </div>

      <fieldset className="demo-form-group" aria-describedby={fieldErrors.role ? 'demo-err-role' : undefined}>
        <legend>I am a...</legend>
        <div className="demo-role-grid" role="radiogroup" aria-label="Role">
          {ROLES.map(({ value, label, Icon }) => (
            <label
              key={value}
              className={`demo-role-card${role === value ? ' is-checked' : ''}`}
            >
              <input
                type="radio"
                name="demo-role"
                value={value}
                checked={role === value}
                onChange={() => setRole(value)}
              />
              <span className="demo-role-card__icon" aria-hidden="true">
                <Icon size={22} aria-hidden />
              </span>
              <span className="demo-role-card__label">{label}</span>
            </label>
          ))}
        </div>
        {fieldErrors.role && <div id="demo-err-role" className="demo-field-error">{fieldErrors.role}</div>}
        {role === 'student' && (
          <div className="demo-student-notice" role="note">
            <IconShield size={16} aria-hidden />
            <span>
              If you&rsquo;re under 13, please ask a parent or guardian to try the demo with you.
            </span>
          </div>
        )}
      </fieldset>

      <div className="demo-form-group">
        <label className="demo-consent-row">
          <IconShield size={16} aria-hidden />
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            aria-invalid={!!fieldErrors.consent}
          />
          <span>
            I agree to ClassBridge&rsquo;s <a href="/terms" target="_blank" rel="noreferrer">terms</a> and <a href="/privacy" target="_blank" rel="noreferrer">privacy policy</a>. I understand this is a demo and my email will be added to the waitlist.
          </span>
        </label>
        {fieldErrors.consent && <div className="demo-field-error">{fieldErrors.consent}</div>}
      </div>

      <div className="demo-modal-actions">
        {timedOut && (
          <a className="demo-btn-secondary" href="/waitlist">Join the waitlist instead</a>
        )}
        <button type="submit" className="demo-btn-primary" disabled={submitting}>
          {submitting ? (
            'Setting up your demo...'
          ) : (
            <>
              <span>Start demo</span>
              <IconArrowRight size={18} aria-hidden />
            </>
          )}
        </button>
      </div>
    </form>
  );
}

export default InstantTrialSignupStep;
