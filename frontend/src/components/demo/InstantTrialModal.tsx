import { useState } from 'react';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { InstantTrialSignupStep } from './InstantTrialSignupStep';
import { InstantTrialGenerateStep } from './InstantTrialGenerateStep';
import { DemoMascot } from './DemoMascot';
import { IconClose } from './icons';
import type { CreateDemoSessionResponse } from '../../api/demo';
import './InstantTrialModal.css';

interface InstantTrialModalProps {
  onClose: () => void;
}

type Step = 1 | 2;

/**
 * Two-step modal:
 *   Step 1 — signup (full_name, email, role, consent, honeypot).
 *   Step 2 — tabs (Ask / Study Guide / Flash Tutor) + streaming output.
 * Esc closes, focus is trapped, aria-modal + aria-labelledby per WCAG 2.1 AA.
 */
export function InstantTrialModal({ onClose }: InstantTrialModalProps) {
  const [step, setStep] = useState<Step>(1);
  const [sessionJwt, setSessionJwt] = useState<string>('');
  const [waitlistPreview, setWaitlistPreview] = useState<number>(0);
  const [verifyEmail, setVerifyEmail] = useState<string>('');
  const [verifyNotice, setVerifyNotice] = useState<string>('');
  const [verifyShown, setVerifyShown] = useState<boolean>(false);
  const trapRef = useFocusTrap<HTMLDivElement>(true, onClose);

  const handleStep1Success = (res: CreateDemoSessionResponse, email: string) => {
    setSessionJwt(res.session_jwt);
    setWaitlistPreview(res.waitlist_preview_position ?? 0);
    setVerifyEmail(email);
    setStep(2);
  };

  const handleVerify = () => {
    // A verification email was sent on step 1 — point the user at it.
    setVerifyNotice(
      `We've sent a verification link and a 6-digit code to ${verifyEmail}. ` +
        'Click the link in your email to confirm your waitlist spot.',
    );
    setVerifyShown(true);
  };

  const titleId = 'demo-modal-title';
  const subtitleId = 'demo-modal-subtitle';
  const title = step === 1 ? 'Try ClassBridge now' : 'Your instant demo';
  const subtitle =
    step === 1
      ? 'Takes ~30 seconds. No password required.'
      : 'Pick a tab, hit Generate, and watch it stream.';

  const mascotMood: 'greeting' | 'thinking' | 'complete' =
    verifyShown ? 'complete' : step === 1 ? 'greeting' : 'thinking';

  return (
    <div className="demo-modal-overlay">
      <div
        ref={trapRef}
        className="demo-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={subtitleId}
      >
        <header className="demo-modal-header">
          <div className="demo-mascot-header" aria-hidden="true">
            <DemoMascot size={40} mood={mascotMood} />
          </div>
          <div className="demo-modal-header-text">
            <h2 id={titleId} className="demo-modal-title">{title}</h2>
            <p id={subtitleId} className="demo-modal-subtitle">{subtitle}</p>
            <div
              className="demo-progress-dots"
              role="group"
              aria-label={`Step ${step} of 2`}
            >
              <span
                className={`demo-progress-dot${step === 1 ? ' demo-progress-dot--active' : ''}`}
                aria-hidden="true"
              />
              <span
                className={`demo-progress-dot${step === 2 ? ' demo-progress-dot--active' : ''}`}
                aria-hidden="true"
              />
            </div>
          </div>
          <button
            type="button"
            className="demo-modal-close"
            aria-label="Close demo"
            onClick={onClose}
          >
            <IconClose size={20} aria-hidden />
          </button>
        </header>

        <div className="demo-modal-body">
          {step === 1 ? (
            <InstantTrialSignupStep onSuccess={handleStep1Success} />
          ) : (
            <>
              <InstantTrialGenerateStep
                sessionJwt={sessionJwt}
                waitlistPreviewPosition={waitlistPreview}
                onVerify={handleVerify}
              />
              {verifyNotice && (
                <div className="demo-form-success" role="status">
                  {verifyNotice}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default InstantTrialModal;
