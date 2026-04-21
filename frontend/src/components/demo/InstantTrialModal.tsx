import { useState } from 'react';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { InstantTrialSignupStep } from './InstantTrialSignupStep';
import { InstantTrialGenerateStep } from './InstantTrialGenerateStep';
import { DemoMascot } from './DemoMascot';
import { IconClose } from './icons';
import { DemoXPBar } from './gamification/DemoXPBar';
import { DemoQuestTracker } from './gamification/DemoQuestTracker';
import { DemoStreakFlame } from './gamification/DemoStreakFlame';
import { useDemoGameState } from './gamification/useDemoGameState';
import type { CreateDemoSessionResponse, DemoType } from '../../api/demo';
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
 *
 * Gamification (CB-DEMO-001 foundation, epic #3599): XP bar, quest tracker,
 * and streak flame live in the step-2 header, driven by `useDemoGameState`.
 * Wave 2 feature streams (#3784–#3787) will enrich the visual layer.
 */
export function InstantTrialModal({ onClose }: InstantTrialModalProps) {
  const [step, setStep] = useState<Step>(1);
  const [sessionJwt, setSessionJwt] = useState<string>('');
  const [waitlistPreview, setWaitlistPreview] = useState<number>(0);
  const [verifyEmail, setVerifyEmail] = useState<string>('');
  const [verifyNotice, setVerifyNotice] = useState<string>('');
  const [verifyShown, setVerifyShown] = useState<boolean>(false);
  const [maximized, setMaximized] = useState(false);
  const trapRef = useFocusTrap<HTMLDivElement>(true, onClose);

  const { state: gameState, actions: gameActions } = useDemoGameState();

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

  /**
   * Foundation-only: when a tab completes, mark its quest. Wave 2 feature
   * streams will layer XP awards, streaks, and achievement triggers here.
   *
   * Study Guide (#3787) gamification: on first completion, award 10 XP,
   * mark the quest, and pop the First Spark achievement if this is the
   * user's first generation of the session.
   */
  const handleTabGenerated = (tab: DemoType) => {
    const wasFirstGeneration = gameState.completedQuests.size === 0;
    gameActions.markQuest(tab);
    if (tab === 'study_guide') {
      gameActions.awardXP(10);
      if (wasFirstGeneration) {
        gameActions.earnAchievement('first-spark');
      }
    }
  };

  /**
   * #3787 curiosity reward — user opens a scoped chip upsell on the Study
   * Guide tab. Awards a small XP bump the first time each chip is opened.
   * Per-chip once-per-session enforcement lives in `DemoStudyGuideChips`.
   */
  const handleStudyGuideChipCuriosity = () => {
    gameActions.awardXP(5);
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
        className={`demo-modal${maximized ? ' demo-modal--maximized' : ''}`}
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
            {step === 2 && (
              <div className="demo-game-header">
                <DemoXPBar xp={gameState.xp} level={gameState.level} />
                <DemoQuestTracker completedQuests={gameState.completedQuests} />
                <DemoStreakFlame streak={gameState.streak} />
              </div>
            )}
          </div>
          <button
            type="button"
            className="demo-modal-maximize"
            aria-label={maximized ? 'Restore size' : 'Maximize'}
            title={maximized ? 'Restore size' : 'Maximize'}
            onClick={() => setMaximized((v) => !v)}
          >
            {maximized ? (
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                stroke="currentColor"
                fill="none"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M10 2v4h4" />
                <path d="M6 14v-4H2" />
              </svg>
            ) : (
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                stroke="currentColor"
                fill="none"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M9 2h5v5" />
                <path d="M7 14H2V9" />
              </svg>
            )}
          </button>
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
                onTabGenerated={handleTabGenerated}
                gameActions={gameActions}
                onStudyGuideChipCuriosity={handleStudyGuideChipCuriosity}
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
