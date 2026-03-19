import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import './Auth.css';
import './SurveyPage.css';

export function SurveyPage() {
  const [phase, setPhase] = useState<'role' | 'questions' | 'thanks'>('role');
  const [role, setRole] = useState('');
  const [questions, setQuestions] = useState<any[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [otherTexts, setOtherTexts] = useState<Record<string, string>>({});
  const [sessionId] = useState(() => crypto.randomUUID());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleRoleSelect = async (selectedRole: string) => {
    setRole(selectedRole);
    setIsLoading(true);
    setError('');
    try {
      const res = await api.get(`/api/survey/questions/${selectedRole}`);
      setQuestions(res.data.questions || res.data);
      setPhase('questions');
    } catch {
      setError('Failed to load survey questions. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const currentQuestion = questions[currentIndex];

  const isAnswered = (): boolean => {
    if (!currentQuestion) return false;
    const answer = answers[currentQuestion.key];
    if (currentQuestion.type === 'free_text') return true; // optional
    if (currentQuestion.type === 'multi_select') return Array.isArray(answer) && answer.length > 0;
    if (currentQuestion.type === 'likert_matrix') {
      const subItems = currentQuestion.sub_items || [];
      return subItems.length > 0 && subItems.every((item: string) => answer?.[item] != null);
    }
    return answer != null && answer !== '';
  };

  const handleNext = async () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      // Submit
      setIsLoading(true);
      setError('');
      try {
        const formattedAnswers = questions.map((q) => {
          let value = answers[q.key];
          // For multi_select with "Other", append the other text
          if (q.type === 'multi_select' && Array.isArray(value) && value.includes('Other') && otherTexts[q.key]) {
            value = value.map((v: string) => v === 'Other' ? `Other: ${otherTexts[q.key]}` : v);
          }
          return { question_key: q.key, question_type: q.type, answer_value: value };
        }).filter((a) => a.answer_value != null && a.answer_value !== '' && !(Array.isArray(a.answer_value) && a.answer_value.length === 0));

        await api.post('/api/survey', { role, session_id: sessionId, answers: formattedAnswers });
        setPhase('thanks');
      } catch {
        setError('Failed to submit survey. Please try again.');
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleBack = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  const handleSingleSelect = (questionId: string, value: string) => {
    setAnswers({ ...answers, [questionId]: value });
  };

  const handleMultiSelect = (questionId: string, value: string) => {
    const current = (answers[questionId] as string[]) || [];
    const updated = current.includes(value)
      ? current.filter((v) => v !== value)
      : [...current, value];
    setAnswers({ ...answers, [questionId]: updated });
  };

  const handleLikert = (questionId: string, value: number) => {
    setAnswers({ ...answers, [questionId]: value });
  };

  const handleLikertMatrix = (questionId: string, subItem: string, value: number) => {
    const current = answers[questionId] || {};
    setAnswers({ ...answers, [questionId]: { ...current, [subItem]: value } });
  };

  const handleFreeText = (questionId: string, value: string) => {
    setAnswers({ ...answers, [questionId]: value });
  };

  const LIKERT_ICONS = ['😟', '😕', '😐', '🙂', '😍'];

  // Phase 3: Thank You
  if (phase === 'thanks') {
    return (
      <div className="auth-container">
        <div className="auth-card survey-thankyou">
          <div className="waitlist-success-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
          <h1 className="auth-title">Thank you for your feedback!</h1>
          <p className="survey-thankyou-text">
            Your responses will help us build better tools for education.
          </p>
          <Link to="/waitlist" className="survey-thankyou-cta">
            Interested? Join the ClassBridge Waitlist
          </Link>
          <p className="auth-footer">
            <a href="https://www.classbridge.ca/">Back to Home</a>
          </p>
        </div>
      </div>
    );
  }

  // Phase 1: Role Selection
  if (phase === 'role') {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />
          <div className="survey-intro">
            <h1 className="auth-title">Help Us Build Something Better</h1>
            <p>
              Take this quick 3-5 minute survey. Your feedback shapes the future of education technology.
            </p>
          </div>

          {error && <div className="auth-error">{error}</div>}

          <div className="survey-roles">
            <button
              className={`survey-role-card${role === 'parent' ? ' selected' : ''}`}
              onClick={() => handleRoleSelect('parent')}
              disabled={isLoading}
            >
              <div className="survey-role-icon">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </div>
              <div className="survey-role-label">Parent</div>
            </button>

            <button
              className={`survey-role-card${role === 'student' ? ' selected' : ''}`}
              onClick={() => handleRoleSelect('student')}
              disabled={isLoading}
            >
              <div className="survey-role-icon">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
                </svg>
              </div>
              <div className="survey-role-label">Student</div>
            </button>

            <button
              className={`survey-role-card${role === 'teacher' ? ' selected' : ''}`}
              onClick={() => handleRoleSelect('teacher')}
              disabled={isLoading}
            >
              <div className="survey-role-icon">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                  <line x1="8" y1="21" x2="16" y2="21" />
                  <line x1="12" y1="17" x2="12" y2="21" />
                </svg>
              </div>
              <div className="survey-role-label">Teacher</div>
            </button>
          </div>

          {isLoading && <p className="survey-loading">Loading questions...</p>}
        </div>
      </div>
    );
  }

  // Phase 2: Questions
  return (
    <div className="auth-container">
      <div className="auth-card survey-question-card">
        <div className="survey-progress">
          <div className="survey-progress-label">
            Question {currentIndex + 1} of {questions.length}
          </div>
          <div className="survey-progress-bar">
            <div
              className="survey-progress-fill"
              style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
            />
          </div>
        </div>

        {error && <div className="auth-error">{error}</div>}

        {currentQuestion && (
          <>
            <div className="survey-question-text">{currentQuestion.text}</div>

            {currentQuestion.type === 'single_select' && (
              <div className="survey-options">
                {(currentQuestion.options || []).map((opt: string) => (
                  <button
                    key={opt}
                    className={`survey-option${answers[currentQuestion.key] === opt ? ' selected' : ''}`}
                    onClick={() => handleSingleSelect(currentQuestion.key, opt)}
                  >
                    <span className="survey-option-radio">
                      {answers[currentQuestion.key] === opt ? (
                        <svg width="18" height="18" viewBox="0 0 18 18">
                          <circle cx="9" cy="9" r="8" fill="none" stroke="var(--color-accent)" strokeWidth="2" />
                          <circle cx="9" cy="9" r="4.5" fill="var(--color-accent)" />
                        </svg>
                      ) : (
                        <svg width="18" height="18" viewBox="0 0 18 18">
                          <circle cx="9" cy="9" r="8" fill="none" stroke="var(--color-border)" strokeWidth="2" />
                        </svg>
                      )}
                    </span>
                    {opt}
                  </button>
                ))}
              </div>
            )}

            {currentQuestion.type === 'multi_select' && (
              <div className="survey-options">
                {(currentQuestion.options || []).map((opt: string) => {
                  const selected = ((answers[currentQuestion.key] as string[]) || []).includes(opt);
                  return (
                    <div key={opt}>
                      <button
                        className={`survey-option${selected ? ' selected' : ''}`}
                        onClick={() => handleMultiSelect(currentQuestion.key, opt)}
                      >
                        <span className="survey-option-check">
                          {selected ? (
                            <svg width="18" height="18" viewBox="0 0 18 18">
                              <rect x="1" y="1" width="16" height="16" rx="3" fill="var(--color-accent)" stroke="var(--color-accent)" strokeWidth="2" />
                              <polyline points="4 9 7.5 12.5 14 5.5" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          ) : (
                            <svg width="18" height="18" viewBox="0 0 18 18">
                              <rect x="1" y="1" width="16" height="16" rx="3" fill="none" stroke="var(--color-border)" strokeWidth="2" />
                            </svg>
                          )}
                        </span>
                        {opt}
                      </button>
                      {opt === 'Other' && selected && (
                        <input
                          type="text"
                          className="survey-other-input"
                          placeholder="Please specify..."
                          value={otherTexts[currentQuestion.key] || ''}
                          onChange={(e) => setOtherTexts({ ...otherTexts, [currentQuestion.key]: e.target.value })}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {currentQuestion.type === 'likert' && (
              <div>
                <div className="survey-likert">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button
                      key={n}
                      className={`survey-likert-btn${answers[currentQuestion.key] === n ? ' selected' : ''}`}
                      onClick={() => handleLikert(currentQuestion.key, n)}
                    >
                      <span className="survey-likert-emoji">{LIKERT_ICONS[n - 1]}</span>
                      <span className="survey-likert-num">{n}</span>
                    </button>
                  ))}
                </div>
                <div className="survey-likert-labels">
                  <span>{currentQuestion.likert_min_label || 'Strongly Disagree'}</span>
                  <span>{currentQuestion.likert_max_label || 'Strongly Agree'}</span>
                </div>
              </div>
            )}

            {currentQuestion.type === 'likert_matrix' && (
              <div className="survey-matrix">
                <div className="survey-matrix-header">
                  <div className="survey-matrix-label" />
                  <div className="survey-matrix-ratings">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <div key={n} className="survey-matrix-header-num">
                        <span className="survey-matrix-header-emoji">{LIKERT_ICONS[n - 1]}</span>
                      </div>
                    ))}
                  </div>
                </div>
                {(currentQuestion.sub_items || []).map((item: string) => (
                  <div key={item} className="survey-matrix-row">
                    <div className="survey-matrix-label">{item}</div>
                    <div className="survey-matrix-ratings">
                      {[1, 2, 3, 4, 5].map((n) => (
                        <button
                          key={n}
                          className={`survey-likert-btn survey-matrix-btn${answers[currentQuestion.key]?.[item] === n ? ' selected' : ''}`}
                          onClick={() => handleLikertMatrix(currentQuestion.key, item, n)}
                          title={`${n} - ${LIKERT_ICONS[n - 1]}`}
                        >
                          {n}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
                <div className="survey-likert-labels">
                  <span>{currentQuestion.likert_min_label || 'Not Important'}</span>
                  <span>{currentQuestion.likert_max_label || 'Very Important'}</span>
                </div>
              </div>
            )}

            {currentQuestion.type === 'free_text' && (
              <div>
                <textarea
                  className="survey-textarea"
                  placeholder="Type your answer here (optional)..."
                  value={answers[currentQuestion.key] || ''}
                  onChange={(e) => handleFreeText(currentQuestion.key, e.target.value)}
                  maxLength={1000}
                />
                <div className="survey-char-count">
                  {(answers[currentQuestion.key] || '').length} / 1000
                </div>
              </div>
            )}
          </>
        )}

        <div className="survey-nav">
          {currentIndex > 0 ? (
            <button className="survey-nav-btn secondary" onClick={handleBack}>
              Back
            </button>
          ) : (
            <div />
          )}
          <button
            className="survey-nav-btn primary"
            disabled={!isAnswered() || isLoading}
            onClick={handleNext}
          >
            {isLoading
              ? 'Submitting...'
              : currentIndex === questions.length - 1
                ? 'Submit'
                : 'Next'}
          </button>
        </div>
      </div>
    </div>
  );
}
