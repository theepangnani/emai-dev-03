import { useState, useEffect, useCallback } from 'react';

export interface TourStep {
  target: string; // CSS selector for the element to highlight
  title: string;
  content: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
}

interface OnboardingTourProps {
  steps: TourStep[];
  storageKey: string;
  onComplete?: () => void;
}

export function OnboardingTour({ steps, storageKey, onComplete }: OnboardingTourProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [visible, setVisible] = useState(false);
  const [tooltipStyle, setTooltipStyle] = useState<React.CSSProperties>({});

  useEffect(() => {
    const completed = localStorage.getItem(storageKey);
    if (!completed) {
      // Delay to let the dashboard render
      const timer = setTimeout(() => setVisible(true), 800);
      return () => clearTimeout(timer);
    }
  }, [storageKey]);

  const handleComplete = useCallback(() => {
    localStorage.setItem(storageKey, '1');
    setVisible(false);
    onComplete?.();
  }, [storageKey, onComplete]);

  const positionTooltip = useCallback(() => {
    if (!visible || currentStep >= steps.length) return;
    const step = steps[currentStep];
    const el = document.querySelector(step.target);
    if (!el) {
      // Element not found, skip step
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
        style.left = Math.max(16, Math.min(rect.left, window.innerWidth - 320));
        break;
      case 'top':
        style.bottom = window.innerHeight - rect.top + 12;
        style.left = Math.max(16, Math.min(rect.left, window.innerWidth - 320));
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

    // Scroll element into view if needed
    el.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
  }, [visible, currentStep, steps, handleComplete]);

  useEffect(() => {
    // positionTooltip updates tooltip position state - synchronous setState in effect is intentional here
    // eslint-disable-next-line react-hooks/set-state-in-effect
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

  if (!visible || currentStep >= steps.length) return null;

  const step = steps[currentStep];
  const isLast = currentStep === steps.length - 1;

  return (
    <>
      <div className="tour-overlay" onClick={handleSkip} />
      <div className="tour-tooltip" style={tooltipStyle}>
        <div className="tour-tooltip-title">{step.title}</div>
        <div className="tour-tooltip-content">{step.content}</div>
        <div className="tour-tooltip-footer">
          <span className="tour-tooltip-progress">
            {currentStep + 1} / {steps.length}
          </span>
          <div className="tour-tooltip-actions">
            <button className="tour-skip-btn" onClick={handleSkip}>Skip</button>
            <button className="tour-next-btn" onClick={handleNext}>
              {isLast ? 'Done' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

// Role-specific tour steps
// eslint-disable-next-line react-refresh/only-export-components
export const PARENT_TOUR_STEPS: TourStep[] = [
  {
    target: '.sidebar-nav .sidebar-link:first-child',
    title: 'Overview',
    content: 'Your dashboard shows an at-a-glance view of all children, tasks, and a calendar for scheduling.',
    position: 'right',
  },
  {
    target: '.sidebar-nav .sidebar-link:nth-child(2)',
    title: 'Child Profiles',
    content: 'View detailed profiles for each child including courses, teachers, and study materials.',
    position: 'right',
  },
  {
    target: '.header-right .notification-bell-btn',
    title: 'Notifications',
    content: 'Check notifications for assignment updates, messages, and reminders.',
    position: 'bottom',
  },
];

// eslint-disable-next-line react-refresh/only-export-components
export const STUDENT_TOUR_STEPS: TourStep[] = [
  {
    target: '.sidebar-nav .sidebar-link:nth-child(2)',
    title: 'Your Courses',
    content: 'View all your courses from Google Classroom. Connect your account to sync automatically.',
    position: 'right',
  },
  {
    target: '.sidebar-nav .sidebar-link:nth-child(3)',
    title: 'Class Materials',
    content: 'Access study guides, quizzes, and flashcards generated from your assignments.',
    position: 'right',
  },
  {
    target: '.header-right .notification-bell-btn',
    title: 'Notifications',
    content: 'Stay updated with assignment reminders and new study materials.',
    position: 'bottom',
  },
];

// eslint-disable-next-line react-refresh/only-export-components
export const TEACHER_TOUR_STEPS: TourStep[] = [
  {
    target: '.sidebar-nav .sidebar-link:nth-child(2)',
    title: 'Courses',
    content: 'Create courses or sync from Google Classroom. Manage students and assignments here.',
    position: 'right',
  },
  {
    target: '.sidebar-nav .sidebar-link:last-child',
    title: 'Teacher Communications',
    content: 'Monitor parent emails synced from Gmail. You can read and reply to messages.',
    position: 'right',
  },
  {
    target: '.header-right .notification-bell-btn',
    title: 'Notifications',
    content: 'Get notified about new parent messages and student activity.',
    position: 'bottom',
  },
];
