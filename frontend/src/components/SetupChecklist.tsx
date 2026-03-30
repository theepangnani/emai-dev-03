import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useFeature } from '../hooks/useFeatureToggle';
import './SetupChecklist.css';

interface OnboardingProgress {
  account_created: boolean;
  email_verified: boolean;
  child_added: boolean;
  classroom_connected: boolean;
  material_uploaded: boolean;
  task_created: boolean;
  dismissed: boolean;
}

interface Step {
  key: keyof Omit<OnboardingProgress, 'dismissed'>;
  label: string;
  description: string;
  path: string;
  icon: string;
}

const STEPS: Step[] = [
  {
    key: 'account_created',
    label: 'Create your account',
    description: 'Sign up for ClassBridge',
    path: '/dashboard',
    icon: '\u2713',
  },
  {
    key: 'email_verified',
    label: 'Verify your email',
    description: 'Check your inbox for a verification link',
    path: '/dashboard',
    icon: '\u2709',
  },
  {
    key: 'child_added',
    label: 'Add your child',
    description: 'Link or create a student profile',
    path: '/my-kids',
    icon: '\uD83D\uDC64',
  },
  {
    key: 'classroom_connected',
    label: 'Connect a classroom',
    description: 'Import classes from Google Classroom',
    path: '/courses',
    icon: '\uD83C\uDFEB',
  },
  {
    key: 'material_uploaded',
    label: 'Upload course material',
    description: 'Add notes, syllabi, or study resources',
    path: '/course-materials',
    icon: '\uD83D\uDCC4',
  },
  {
    key: 'task_created',
    label: 'Create a task',
    description: 'Set up a to-do for you or your child',
    path: '/tasks',
    icon: '\u2610',
  },
];

export function SetupChecklist() {
  const navigate = useNavigate();
  const gcEnabled = useFeature('google_classroom');
  const [progress, setProgress] = useState<OnboardingProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .get<OnboardingProgress>('/api/onboarding/progress')
      .then((res) => {
        if (!cancelled) {
          setProgress(res.data);
          setDismissed(res.data.dismissed);
        }
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const visibleSteps = useMemo(
    () => (gcEnabled ? STEPS : STEPS.filter((s) => s.key !== 'classroom_connected')),
    [gcEnabled],
  );

  const completedCount = useMemo(() => {
    if (!progress) return 0;
    return visibleSteps.filter((s) => progress[s.key]).length;
  }, [progress, visibleSteps]);

  const allComplete = completedCount === visibleSteps.length;
  const pct = Math.round((completedCount / visibleSteps.length) * 100);

  const handleDismiss = async () => {
    setDismissed(true);
    try {
      await api.post('/api/onboarding/dismiss');
    } catch {
      // Best-effort — the UI already hides it
    }
  };

  // Don't render while loading, on error, if all complete, or if dismissed
  if (loading || error || !progress || allComplete || dismissed) {
    return null;
  }

  return (
    <div className="setup-checklist" role="region" aria-label="Setup checklist">
      <div className="setup-checklist__header">
        <div className="setup-checklist__title-row">
          <h3 className="setup-checklist__title">Get started with ClassBridge</h3>
          <button
            className="setup-checklist__dismiss"
            onClick={handleDismiss}
            aria-label="Dismiss setup checklist"
            type="button"
          >
            I'll do this later
          </button>
        </div>
        <p className="setup-checklist__subtitle">
          {completedCount} of {visibleSteps.length} steps complete
        </p>
        <div className="setup-checklist__progress-track" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div className="setup-checklist__progress-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <ul className="setup-checklist__steps">
        {visibleSteps.map((step) => {
          const done = progress[step.key];
          return (
            <li key={step.key} className={`setup-checklist__step ${done ? 'setup-checklist__step--done' : ''}`}>
              <button
                className="setup-checklist__step-btn"
                onClick={() => {
                  if (!done) navigate(step.path);
                }}
                disabled={done}
                type="button"
                aria-label={done ? `${step.label} (complete)` : step.label}
              >
                <span className={`setup-checklist__check ${done ? 'setup-checklist__check--done' : ''}`} aria-hidden="true">
                  {done ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : (
                    <span className="setup-checklist__step-icon">{step.icon}</span>
                  )}
                </span>
                <span className="setup-checklist__step-text">
                  <span className="setup-checklist__step-label">{step.label}</span>
                  {!done && <span className="setup-checklist__step-desc">{step.description}</span>}
                </span>
                {!done && (
                  <svg className="setup-checklist__arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
