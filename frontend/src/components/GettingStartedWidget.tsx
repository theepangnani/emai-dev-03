import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './GettingStartedWidget.css';

const LS_DISMISSED_KEY = 'getting_started_dismissed';
const LS_FIRST_VISIT_KEY = 'getting_started_first_visit';
const DAYS_TO_SHOW = 14;

interface Step {
  id: string;
  label: string;
  path: string;
  done: boolean;
}

interface GettingStartedWidgetProps {
  /** Steps already completed — derived by the parent dashboard */
  completedStepIds: string[];
}

function getParentSteps(): Omit<Step, 'done'>[] {
  return [
    { id: 'add_child', label: 'Add your first child', path: '/my-kids' },
    { id: 'upload_material', label: 'Upload a course material', path: '/courses' },
    { id: 'explore_dashboard', label: 'Explore your dashboard', path: '/dashboard' },
    { id: 'message_teacher', label: 'Message a teacher', path: '/messages' },
  ];
}

function getStudentSteps(): Omit<Step, 'done'>[] {
  return [
    { id: 'generate_guide', label: 'Generate a study guide', path: '/study-guides' },
    { id: 'take_quiz', label: 'Take a practice quiz', path: '/quiz' },
    { id: 'try_flashcards', label: 'Try flashcards or mind maps', path: '/flashcards' },
    { id: 'check_dashboard', label: 'Check your dashboard', path: '/dashboard' },
  ];
}

function getTeacherSteps(): Omit<Step, 'done'>[] {
  return [
    { id: 'create_class', label: 'Create your first class', path: '/courses' },
    { id: 'add_students', label: 'Add students', path: '/courses' },
    { id: 'upload_materials', label: 'Upload materials', path: '/courses' },
  ];
}

export function GettingStartedWidget({ completedStepIds }: GettingStartedWidgetProps) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(() =>
    localStorage.getItem(LS_DISMISSED_KEY) === 'true'
  );

  // Record first visit timestamp
  useEffect(() => {
    if (!localStorage.getItem(LS_FIRST_VISIT_KEY)) {
      localStorage.setItem(LS_FIRST_VISIT_KEY, String(Date.now()));
    }
  }, []);

  // Mark "explore/check dashboard" as done on mount
  useEffect(() => {
    const key = 'getting_started_dashboard_visited';
    if (!localStorage.getItem(key)) {
      localStorage.setItem(key, 'true');
    }
  }, []);

  const role = user?.role?.toUpperCase() ?? '';

  const steps: Step[] = useMemo(() => {
    let base: Omit<Step, 'done'>[];
    if (role === 'PARENT') base = getParentSteps();
    else if (role === 'STUDENT') base = getStudentSteps();
    else if (role === 'TEACHER') base = getTeacherSteps();
    else return [];

    // Dashboard visit is always done if we're rendering this widget
    const dashboardVisited = localStorage.getItem('getting_started_dashboard_visited') === 'true';
    const completedSet = new Set(completedStepIds);

    return base.map(s => ({
      ...s,
      done:
        completedSet.has(s.id) ||
        ((s.id === 'explore_dashboard' || s.id === 'check_dashboard') && dashboardVisited),
    }));
  }, [role, completedStepIds]);

  const completedCount = steps.filter(s => s.done).length;
  const allComplete = completedCount === steps.length;
  const pct = steps.length > 0 ? Math.round((completedCount / steps.length) * 100) : 0;

  // Auto-hide after 14 days (computed once on mount)
  const [expired] = useState(() => {
    const firstVisit = localStorage.getItem(LS_FIRST_VISIT_KEY);
    if (!firstVisit) return false;
    return Date.now() - Number(firstVisit) > DAYS_TO_SHOW * 24 * 60 * 60 * 1000;
  });

  if (dismissed || allComplete || expired || steps.length === 0) {
    return null;
  }

  const handleDismiss = () => {
    setDismissed(true);
    localStorage.setItem(LS_DISMISSED_KEY, 'true');
  };

  return (
    <div className="gs-widget" role="region" aria-label="Getting started">
      <div className="gs-widget__header">
        <div className="gs-widget__title-row">
          <h3 className="gs-widget__title">Getting Started</h3>
          <button
            className="gs-widget__dismiss"
            onClick={handleDismiss}
            aria-label="Dismiss getting started widget"
            type="button"
          >
            Dismiss
          </button>
        </div>
        <p className="gs-widget__subtitle">
          {completedCount} of {steps.length} steps complete
        </p>
        <div
          className="gs-widget__progress-track"
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div className="gs-widget__progress-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <ul className="gs-widget__steps">
        {steps.map(step => (
          <li key={step.id} className={`gs-widget__step ${step.done ? 'gs-widget__step--done' : ''}`}>
            <button
              className="gs-widget__step-btn"
              onClick={() => { if (!step.done) navigate(step.path); }}
              disabled={step.done}
              type="button"
              aria-label={step.done ? `${step.label} (complete)` : step.label}
            >
              <span className={`gs-widget__check ${step.done ? 'gs-widget__check--done' : ''}`} aria-hidden="true">
                {step.done ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  <span className="gs-widget__step-num" />
                )}
              </span>
              <span className="gs-widget__step-label">{step.label}</span>
              {!step.done && (
                <svg className="gs-widget__arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
