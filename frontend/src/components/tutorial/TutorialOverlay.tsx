import { useState, useEffect, useCallback } from 'react';
import { useTutorialProgress } from '../../hooks/useTutorialProgress';
import type { TourStep } from '../OnboardingTour';
import './TutorialOverlay.css';

interface TutorialOverlayProps {
  /** Unique key identifying this tutorial set, e.g. "parent_dashboard" */
  tutorialKey: string;
  steps: TourStep[];
  /** If true, auto-show for users with no completed tutorials */
  autoShow?: boolean;
}

export function TutorialOverlay({ tutorialKey, steps, autoShow = true }: TutorialOverlayProps) {
  const { isStepCompleted, hasAnyCompleted, completeStep, isLoading } = useTutorialProgress();
  const [currentStep, setCurrentStep] = useState(0);
  const [visible, setVisible] = useState(false);
  const [tooltipStyle, setTooltipStyle] = useState<React.CSSProperties>({});

  // Auto-show logic: show if tutorial not completed and (autoShow + no tutorials done yet, OR manually triggered)
  useEffect(() => {
    if (isLoading) return;
    if (isStepCompleted(tutorialKey)) return;
    if (autoShow && !hasAnyCompleted) {
      const timer = setTimeout(() => setVisible(true), 1000);
      return () => clearTimeout(timer);
    }
  }, [isLoading, tutorialKey, autoShow, hasAnyCompleted, isStepCompleted]);

  const handleComplete = useCallback(async () => {
    setVisible(false);
    await completeStep(tutorialKey);
  }, [tutorialKey, completeStep]);

  const positionTooltip = useCallback(() => {
    if (!visible || currentStep >= steps.length) return;
    const step = steps[currentStep];
    const el = document.querySelector(step.target);
    if (!el) {
      if (currentStep < steps.length - 1) {
        setCurrentStep(prev => prev + 1);
      } else {
        handleComplete();
      }
      return;
    }

    const rect = el.getBoundingClientRect();
    const pos = step.position || 'bottom';
    const style: React.CSSProperties = { position: 'fixed', zIndex: 10001 };

    switch (pos) {
      case 'bottom':
        style.top = rect.bottom + 12;
        style.left = Math.max(16, Math.min(rect.left, window.innerWidth - 340));
        break;
      case 'top':
        style.bottom = window.innerHeight - rect.top + 12;
        style.left = Math.max(16, Math.min(rect.left, window.innerWidth - 340));
        break;
      case 'right':
        style.top = rect.top;
        style.left = rect.right + 12;
        break;
      case 'left':
        style.top = rect.top;
        style.right = window.innerWidth - rect.left + 12;
        break;
    }

    setTooltipStyle(style);
    el.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
  }, [visible, currentStep, steps, handleComplete]);

  useEffect(() => {
    positionTooltip();
    window.addEventListener('resize', positionTooltip);
    return () => window.removeEventListener('resize', positionTooltip);
  }, [positionTooltip]);

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(prev => prev + 1);
    } else {
      handleComplete();
    }
  };

  const handleSkip = () => {
    handleComplete();
  };

  /** Allow parent components to trigger this tutorial manually */
  const show = useCallback(() => {
    setCurrentStep(0);
    setVisible(true);
  }, []);

  // Expose show via a global registry so "Show Tutorial" buttons can trigger it
  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const w = window as any;
    w.__tutorialShow = { ...(w.__tutorialShow || {}), [tutorialKey]: show };
  }, [tutorialKey, show]);

  if (!visible || currentStep >= steps.length) return null;

  const step = steps[currentStep];
  const isLast = currentStep === steps.length - 1;

  return (
    <>
      <div className="tutorial-overlay-backdrop" onClick={handleSkip} />
      <div className="tutorial-tooltip" style={tooltipStyle}>
        <div className="tutorial-tooltip-title">{step.title}</div>
        <div className="tutorial-tooltip-content">{step.content}</div>
        <div className="tutorial-tooltip-footer">
          <span className="tutorial-tooltip-progress">
            {currentStep + 1} / {steps.length}
          </span>
          <div className="tutorial-tooltip-actions">
            <button className="tutorial-skip-btn" onClick={handleSkip}>Skip</button>
            <button className="tutorial-next-btn" onClick={handleNext}>
              {isLast ? 'Done' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

/** Trigger a tutorial replay from anywhere */
export function triggerTutorial(tutorialKey: string) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const registry = (window as any).__tutorialShow as Record<string, () => void> | undefined;
  registry?.[tutorialKey]?.();
}
