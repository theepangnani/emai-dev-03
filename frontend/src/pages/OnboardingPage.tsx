import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Onboarding.css';

export function OnboardingPage() {
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [teacherType, setTeacherType] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { completeOnboarding } = useAuth();
  const navigate = useNavigate();

  const toggleRole = (role: string) => {
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

  const handleSubmit = async () => {
    setError('');

    if (selectedRoles.length === 0) {
      setError('Please select at least one role to continue.');
      return;
    }

    if (selectedRoles.includes('teacher') && !teacherType) {
      setError('Please select your teacher type.');
      return;
    }

    setIsLoading(true);
    try {
      await completeOnboarding(
        selectedRoles,
        selectedRoles.includes('teacher') ? teacherType : undefined,
      );
      navigate('/dashboard');
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(detail || 'Something went wrong. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card onboarding-card">
        <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />
        <h1 className="auth-title">Welcome to ClassBridge</h1>
        <p className="auth-subtitle">How will you use ClassBridge?</p>

        {error && <div className="auth-error">{error}</div>}

        <div className="onboarding-roles">
          <button
            type="button"
            className={`role-card role-card--parent ${selectedRoles.includes('parent') ? 'role-card--selected' : ''}`}
            onClick={() => toggleRole('parent')}
          >
            <span className="role-card__icon">&#127968;</span>
            <span className="role-card__label">Parent / Guardian</span>
            <span className="role-card__desc">Track your child's progress and stay connected</span>
            <span className="role-card__badge">Most common</span>
          </button>

          <button
            type="button"
            className={`role-card ${selectedRoles.includes('teacher') ? 'role-card--selected' : ''}`}
            onClick={() => toggleRole('teacher')}
          >
            <span className="role-card__icon">&#128218;</span>
            <span className="role-card__label">Teacher</span>
            <span className="role-card__desc">Manage classes and communicate with parents</span>
          </button>

          <button
            type="button"
            className={`role-card ${selectedRoles.includes('student') ? 'role-card--selected' : ''}`}
            onClick={() => toggleRole('student')}
          >
            <span className="role-card__icon">&#127891;</span>
            <span className="role-card__label">Student</span>
            <span className="role-card__desc">Access study tools and track assignments</span>
          </button>
        </div>

        {selectedRoles.includes('teacher') && (
          <div className="onboarding-teacher-type">
            <p className="onboarding-teacher-type__label">What type of teacher are you?</p>
            <div className="teacher-type-options">
              <button
                type="button"
                className={`teacher-type-btn ${teacherType === 'school_teacher' ? 'teacher-type-btn--selected' : ''}`}
                onClick={() => setTeacherType('school_teacher')}
              >
                <span className="teacher-type-btn__title">School Teacher</span>
                <span className="teacher-type-btn__desc">I teach at a school</span>
              </button>
              <button
                type="button"
                className={`teacher-type-btn ${teacherType === 'private_tutor' ? 'teacher-type-btn--selected' : ''}`}
                onClick={() => setTeacherType('private_tutor')}
              >
                <span className="teacher-type-btn__title">Private Tutor</span>
                <span className="teacher-type-btn__desc">I teach independently</span>
              </button>
            </div>
          </div>
        )}

        <button
          type="button"
          className="auth-button"
          disabled={isLoading || selectedRoles.length === 0}
          onClick={handleSubmit}
        >
          {isLoading ? 'Setting up...' : 'Continue'}
        </button>
      </div>
    </div>
  );
}
