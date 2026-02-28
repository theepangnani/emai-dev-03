import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Onboarding.css';

type Step = 'role' | 'teacher_type' | 'confirm';

const ROLE_LABELS: Record<string, string> = {
  parent: 'Parent / Guardian',
  teacher: 'Teacher',
  student: 'Student',
};

const TEACHER_TYPE_LABELS: Record<string, string> = {
  school_teacher: 'School Teacher',
  private_tutor: 'Private Tutor',
};

export function OnboardingPage() {
  const [step, setStep] = useState<Step>('role');
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [teacherType, setTeacherType] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { user, completeOnboarding } = useAuth();
  const navigate = useNavigate();

  const toggleRole = (role: string) => {
    setError('');
    setSelectedRoles(prev => {
      const next = prev.includes(role)
        ? prev.filter(r => r !== role)
        : [...prev, role];
      // Clear teacher type if teacher is deselected
      if (role === 'teacher' && prev.includes('teacher')) {
        setTeacherType('');
      }
      return next;
    });
  };

  const canAdvanceFromRole = selectedRoles.length > 0;
  const needsTeacherType = selectedRoles.includes('teacher');
  const canAdvanceFromTeacherType = !needsTeacherType || !!teacherType;

  const handleNext = () => {
    setError('');
    if (step === 'role') {
      if (!canAdvanceFromRole) {
        setError('Please select at least one role to continue.');
        return;
      }
      if (needsTeacherType) {
        setStep('teacher_type');
      } else {
        setStep('confirm');
      }
    } else if (step === 'teacher_type') {
      if (!canAdvanceFromTeacherType) {
        setError('Please select your teacher type.');
        return;
      }
      setStep('confirm');
    }
  };

  const handleBack = () => {
    setError('');
    if (step === 'confirm') {
      if (needsTeacherType) {
        setStep('teacher_type');
      } else {
        setStep('role');
      }
    } else if (step === 'teacher_type') {
      setStep('role');
    }
  };

  const handleSubmit = async () => {
    setError('');
    setIsLoading(true);
    try {
      await completeOnboarding(
        selectedRoles,
        needsTeacherType ? teacherType : undefined,
      );
      navigate('/dashboard');
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(detail || 'Something went wrong. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const stepNumber = step === 'role' ? 1 : step === 'teacher_type' ? 2 : needsTeacherType ? 3 : 2;
  const totalSteps = needsTeacherType ? 3 : 2;

  return (
    <div className="auth-container">
      <div className="auth-card onboarding-card">
        <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />

        {/* Progress indicator */}
        <div className="onboarding-progress">
          <div className="onboarding-progress__bar">
            <div
              className="onboarding-progress__fill"
              style={{ width: `${(stepNumber / totalSteps) * 100}%` }}
            />
          </div>
          <span className="onboarding-progress__label">Step {stepNumber} of {totalSteps}</span>
        </div>

        {error && <div className="auth-error">{error}</div>}

        {/* Step 1: Role Selection */}
        {step === 'role' && (
          <div className="onboarding-step">
            <h1 className="auth-title">
              Welcome{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}!
            </h1>
            <p className="auth-subtitle">How will you use ClassBridge? Select your role to get started.</p>

            <div className="onboarding-roles">
              <button
                type="button"
                className={`role-card role-card--parent ${selectedRoles.includes('parent') ? 'role-card--selected' : ''}`}
                onClick={() => toggleRole('parent')}
              >
                <span className="role-card__icon" role="img" aria-label="Home">&#127968;</span>
                <span className="role-card__label">Parent / Guardian</span>
                <span className="role-card__desc">Track your child's progress, communicate with teachers, and stay connected with their education</span>
                <span className="role-card__badge">Most common</span>
              </button>

              <button
                type="button"
                className={`role-card ${selectedRoles.includes('student') ? 'role-card--selected' : ''}`}
                onClick={() => toggleRole('student')}
              >
                <span className="role-card__icon" role="img" aria-label="Graduation cap">&#127891;</span>
                <span className="role-card__label">Student</span>
                <span className="role-card__desc">Access AI-powered study tools, track assignments, and manage your learning</span>
              </button>

              <button
                type="button"
                className={`role-card ${selectedRoles.includes('teacher') ? 'role-card--selected' : ''}`}
                onClick={() => toggleRole('teacher')}
              >
                <span className="role-card__icon" role="img" aria-label="Books">&#128218;</span>
                <span className="role-card__label">Teacher</span>
                <span className="role-card__desc">Manage classes, share resources, and communicate with parents</span>
              </button>
            </div>

            <button
              type="button"
              className="auth-button"
              disabled={!canAdvanceFromRole}
              onClick={handleNext}
            >
              Continue
            </button>
          </div>
        )}

        {/* Step 2: Teacher Type Selection (only if teacher role selected) */}
        {step === 'teacher_type' && (
          <div className="onboarding-step">
            <h1 className="auth-title">What kind of teacher are you?</h1>
            <p className="auth-subtitle">This helps us tailor your experience.</p>

            <div className="onboarding-teacher-type">
              <div className="teacher-type-options">
                <button
                  type="button"
                  className={`teacher-type-btn ${teacherType === 'school_teacher' ? 'teacher-type-btn--selected' : ''}`}
                  onClick={() => { setTeacherType('school_teacher'); setError(''); }}
                >
                  <span className="teacher-type-btn__icon" role="img" aria-label="School">&#127979;</span>
                  <span className="teacher-type-btn__title">School Teacher</span>
                  <span className="teacher-type-btn__desc">I teach at a school or educational institution</span>
                </button>
                <button
                  type="button"
                  className={`teacher-type-btn ${teacherType === 'private_tutor' ? 'teacher-type-btn--selected' : ''}`}
                  onClick={() => { setTeacherType('private_tutor'); setError(''); }}
                >
                  <span className="teacher-type-btn__icon" role="img" aria-label="Person teaching">&#129489;&#8205;&#127979;</span>
                  <span className="teacher-type-btn__title">Private Tutor</span>
                  <span className="teacher-type-btn__desc">I teach independently or run my own tutoring practice</span>
                </button>
              </div>
            </div>

            <div className="onboarding-nav-buttons">
              <button type="button" className="auth-button auth-button--secondary" onClick={handleBack}>
                Back
              </button>
              <button
                type="button"
                className="auth-button"
                disabled={!canAdvanceFromTeacherType}
                onClick={handleNext}
              >
                Continue
              </button>
            </div>
          </div>
        )}

        {/* Step 3 (or 2): Confirmation */}
        {step === 'confirm' && (
          <div className="onboarding-step">
            <h1 className="auth-title">You're all set!</h1>
            <p className="auth-subtitle">Here's a summary of your setup. You can always change this later in settings.</p>

            <div className="onboarding-summary">
              <div className="onboarding-summary__item">
                <span className="onboarding-summary__label">Your role{selectedRoles.length > 1 ? 's' : ''}</span>
                <span className="onboarding-summary__value">
                  {selectedRoles.map(r => ROLE_LABELS[r] || r).join(', ')}
                </span>
              </div>

              {needsTeacherType && teacherType && (
                <div className="onboarding-summary__item">
                  <span className="onboarding-summary__label">Teacher type</span>
                  <span className="onboarding-summary__value">
                    {TEACHER_TYPE_LABELS[teacherType] || teacherType}
                  </span>
                </div>
              )}
            </div>

            <div className="onboarding-nav-buttons">
              <button type="button" className="auth-button auth-button--secondary" onClick={handleBack}>
                Back
              </button>
              <button
                type="button"
                className="auth-button auth-button--primary"
                disabled={isLoading}
                onClick={handleSubmit}
              >
                {isLoading ? 'Setting up your account...' : 'Get Started'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
