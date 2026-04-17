/**
 * ASGFProgressInterstitial — 4-stage animated progress indicator shown while
 * a study session is being generated.
 *
 * Displays sequential stages with spinner/checkmark animations. When the plan
 * preview data arrives it renders a summary card (topic, slide count, quiz
 * count, estimated time). If any stage takes longer than 12 seconds a
 * reassuring message is shown.
 *
 * Issue: #3406
 */
import { useEffect, useRef, useState } from 'react';

import './ASGFProgressInterstitial.css';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface PlanPreview {
  topic: string;
  slideCount: number;
  quizCount: number;
  estimatedTimeMin: number;
}

export interface ASGFProgressInterstitialProps {
  /** 0-based index of the stage currently in progress (0-3). */
  currentStage: number;
  /** Optional preview data shown once the plan is ready. */
  planPreview?: PlanPreview | null;
  /** Called when all stages are complete and the user is ready to proceed. */
  onComplete?: () => void;
}

/* ------------------------------------------------------------------ */
/* Stage definitions                                                   */
/* ------------------------------------------------------------------ */

interface StageDefinition {
  label: string;
  icon: string;
}

const STAGES: StageDefinition[] = [
  { label: 'Reading your documents...', icon: '\uD83D\uDCC4' },
  { label: 'Identifying key concepts...', icon: '\uD83D\uDCA1' },
  { label: 'Building your study plan...', icon: '\uD83D\uDCD0' },
  { label: 'Generating your lesson...', icon: '\uD83D\uDCCA' },
];

const SLOW_THRESHOLD_MS = 12_000;

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export default function ASGFProgressInterstitial({
  currentStage,
  planPreview = null,
  onComplete,
}: ASGFProgressInterstitialProps) {
  const [slowStage, setSlowStage] = useState(-1);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /* Slow-message timer — resets each time the stage advances */
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setSlowStage(currentStage), SLOW_THRESHOLD_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [currentStage]);

  const showSlowMessage = slowStage === currentStage;

  /* Auto-complete when all stages done and preview ready */
  const allDone = currentStage >= STAGES.length;
  useEffect(() => {
    if (allDone && planPreview && onComplete) {
      const id = setTimeout(onComplete, 800);
      return () => clearTimeout(id);
    }
  }, [allDone, planPreview, onComplete]);

  return (
    <div className="asgf-progress-interstitial">
      <div className="asgf-progress-interstitial__stages">
        {STAGES.map((stage, idx) => {
          const isComplete = idx < currentStage;
          const isActive = idx === currentStage;

          const cls = [
            'asgf-progress-interstitial__stage',
            isActive ? 'asgf-progress-interstitial__stage--active' : '',
            isComplete ? 'asgf-progress-interstitial__stage--complete' : '',
          ]
            .filter(Boolean)
            .join(' ');

          return (
            <div key={idx} className={cls}>
              <span className="asgf-progress-interstitial__icon">
                {isComplete ? (
                  <span className="asgf-progress-interstitial__check" aria-hidden="true">
                    &#x2713;
                  </span>
                ) : isActive ? (
                  <span className="asgf-progress-interstitial__spinner" aria-hidden="true" />
                ) : (
                  <span aria-hidden="true">{stage.icon}</span>
                )}
              </span>
              {stage.label}
            </div>
          );
        })}
      </div>

      {showSlowMessage && !allDone && (
        <p className="asgf-progress-interstitial__slow-msg">
          This is a detailed session &mdash; almost ready!
        </p>
      )}

      {planPreview && (
        <div className="asgf-progress-interstitial__preview">
          <p className="asgf-progress-interstitial__preview-title">{planPreview.topic}</p>
          <div className="asgf-progress-interstitial__preview-stats">
            <span className="asgf-progress-interstitial__preview-stat">
              <span className="asgf-progress-interstitial__preview-stat-icon" aria-hidden="true">
                &#x1F4CA;
              </span>
              {planPreview.slideCount} slide{planPreview.slideCount !== 1 ? 's' : ''}
            </span>
            <span className="asgf-progress-interstitial__preview-stat">
              <span className="asgf-progress-interstitial__preview-stat-icon" aria-hidden="true">
                &#x2753;
              </span>
              {planPreview.quizCount} quiz{planPreview.quizCount !== 1 ? 'zes' : ''}
            </span>
            <span className="asgf-progress-interstitial__preview-stat">
              <span className="asgf-progress-interstitial__preview-stat-icon" aria-hidden="true">
                &#x23F1;
              </span>
              ~{planPreview.estimatedTimeMin} min
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
