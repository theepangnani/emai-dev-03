import { useState, useEffect } from 'react';
import { studyApi } from '../api/study';
import type { StudyGuide } from '../api/study';
import { quizAssignmentsApi } from '../api/quizAssignments';
import { useFocusTrap } from '../hooks/useFocusTrap';
import './AssignQuizModal.css';

export interface AssignQuizModalProps {
  open: boolean;
  onClose: () => void;
  /** The student (child) to assign the quiz to. */
  studentId: number;
  studentName: string;
  /** user_id of the child — used to fetch their quiz-type study guides. */
  childUserId: number;
  onAssigned?: () => void;
}

type Difficulty = 'easy' | 'medium' | 'hard';

const DIFFICULTY_CONFIG: Record<Difficulty, { label: string; description: string; color: string }> = {
  easy: {
    label: 'Easy',
    description: 'First 30% of questions — great for review and building confidence.',
    color: '#16a34a',
  },
  medium: {
    label: 'Medium',
    description: 'All questions at a steady pace — balanced practice.',
    color: '#d97706',
  },
  hard: {
    label: 'Hard',
    description: 'All questions with a 60-second time limit per question — a real challenge!',
    color: '#dc2626',
  },
};

export function AssignQuizModal({
  open,
  onClose,
  studentId,
  studentName,
  childUserId,
  onAssigned,
}: AssignQuizModalProps) {
  // Step 1 = select quiz, Step 2 = configure
  const [step, setStep] = useState<1 | 2>(1);

  // Step 1 state
  const [quizGuides, setQuizGuides] = useState<StudyGuide[]>([]);
  const [loadingGuides, setLoadingGuides] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedGuide, setSelectedGuide] = useState<StudyGuide | null>(null);

  // Step 2 state
  const [difficulty, setDifficulty] = useState<Difficulty>('medium');
  const [dueDate, setDueDate] = useState('');
  const [note, setNote] = useState('');
  const [assigning, setAssigning] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const modalRef = useFocusTrap<HTMLDivElement>(open, onClose);

  // Load the child's quiz-type study guides when the modal opens
  useEffect(() => {
    if (!open) return;
    setStep(1);
    setSelectedGuide(null);
    setSearch('');
    setDifficulty('medium');
    setDueDate('');
    setNote('');
    setError('');
    setSuccess(false);
    setAssigning(false);

    setLoadingGuides(true);
    studyApi
      .listGuides({ guide_type: 'quiz', student_user_id: childUserId })
      .then(setQuizGuides)
      .catch(() => setQuizGuides([]))
      .finally(() => setLoadingGuides(false));
  }, [open, childUserId]);

  const filteredGuides = quizGuides.filter(g =>
    g.title.toLowerCase().includes(search.toLowerCase())
  );

  const handleSelectGuide = (guide: StudyGuide) => {
    setSelectedGuide(guide);
    setStep(2);
  };

  const handleAssign = async () => {
    if (!selectedGuide || assigning) return;
    setAssigning(true);
    setError('');
    try {
      await quizAssignmentsApi.assign({
        student_id: studentId,
        study_guide_id: selectedGuide.id,
        difficulty,
        due_date: dueDate || null,
        note: note.trim() || null,
      });
      setSuccess(true);
      onAssigned?.();
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to assign quiz. Please try again.');
    } finally {
      setAssigning(false);
    }
  };

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal modal-md aqm-modal"
        role="dialog"
        aria-modal="true"
        aria-label={`Assign Quiz to ${studentName}`}
        ref={modalRef}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="aqm-header">
          <div className="aqm-header-left">
            {step === 2 && !success && (
              <button
                className="aqm-back-btn"
                onClick={() => setStep(1)}
                aria-label="Back to quiz selection"
                type="button"
              >
                &#8592;
              </button>
            )}
            <div>
              <h2 className="aqm-title">Assign Quiz</h2>
              <p className="aqm-subtitle">to {studentName}</p>
            </div>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close" type="button">
            &times;
          </button>
        </div>

        {/* Step indicators */}
        {!success && (
          <div className="aqm-steps" aria-label="Progress">
            <div className={`aqm-step ${step >= 1 ? 'active' : ''}`}>
              <span className="aqm-step-num">1</span>
              <span className="aqm-step-label">Select Quiz</span>
            </div>
            <div className="aqm-step-line" />
            <div className={`aqm-step ${step >= 2 ? 'active' : ''}`}>
              <span className="aqm-step-num">2</span>
              <span className="aqm-step-label">Configure</span>
            </div>
          </div>
        )}

        {/* Body */}
        <div className="aqm-body">
          {success ? (
            <div className="aqm-success">
              <div className="aqm-success-icon">&#10003;</div>
              <p className="aqm-success-text">
                Quiz assigned to {studentName}!
              </p>
              <p className="aqm-success-sub">They will see it in their dashboard.</p>
            </div>
          ) : step === 1 ? (
            /* ── Step 1: Select Quiz ── */
            <>
              <div className="aqm-search-row">
                <input
                  className="aqm-search"
                  type="search"
                  placeholder="Search quizzes..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  aria-label="Search quizzes"
                />
              </div>

              {loadingGuides ? (
                <div className="aqm-loading">Loading quizzes...</div>
              ) : filteredGuides.length === 0 ? (
                <div className="aqm-empty">
                  {quizGuides.length === 0
                    ? `${studentName} has no quiz-type study materials yet. Generate a quiz from their course materials first.`
                    : 'No quizzes match your search.'}
                </div>
              ) : (
                <ul className="aqm-guide-list" role="listbox" aria-label="Available quizzes">
                  {filteredGuides.map(guide => (
                    <li key={guide.id}>
                      <button
                        className="aqm-guide-item"
                        role="option"
                        aria-selected={selectedGuide?.id === guide.id}
                        onClick={() => handleSelectGuide(guide)}
                        type="button"
                      >
                        <span className="aqm-guide-icon" aria-hidden="true">&#128221;</span>
                        <span className="aqm-guide-title">{guide.title}</span>
                        <span className="aqm-guide-arrow" aria-hidden="true">&#8250;</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            /* ── Step 2: Configure ── */
            <>
              <div className="aqm-selected-quiz">
                <span className="aqm-selected-label">Quiz:</span>
                <span className="aqm-selected-title">{selectedGuide?.title}</span>
              </div>

              {/* Difficulty */}
              <fieldset className="aqm-fieldset">
                <legend className="aqm-legend">Difficulty</legend>
                <div className="aqm-difficulty-grid">
                  {(Object.entries(DIFFICULTY_CONFIG) as [Difficulty, typeof DIFFICULTY_CONFIG[Difficulty]][]).map(
                    ([key, cfg]) => (
                      <label
                        key={key}
                        className={`aqm-difficulty-card ${difficulty === key ? 'selected' : ''}`}
                        style={{ '--diff-color': cfg.color } as React.CSSProperties}
                      >
                        <input
                          type="radio"
                          name="difficulty"
                          value={key}
                          checked={difficulty === key}
                          onChange={() => setDifficulty(key)}
                        />
                        <span className="aqm-diff-label" style={{ color: cfg.color }}>{cfg.label}</span>
                        <span className="aqm-diff-desc">{cfg.description}</span>
                      </label>
                    )
                  )}
                </div>
              </fieldset>

              {/* Due date */}
              <div className="aqm-field">
                <label className="aqm-label" htmlFor="aqm-due-date">
                  Due Date <span className="aqm-optional">(optional)</span>
                </label>
                <input
                  id="aqm-due-date"
                  className="aqm-input"
                  type="date"
                  value={dueDate}
                  min={new Date().toISOString().slice(0, 10)}
                  onChange={e => setDueDate(e.target.value)}
                />
              </div>

              {/* Note */}
              <div className="aqm-field">
                <label className="aqm-label" htmlFor="aqm-note">
                  Note to {studentName} <span className="aqm-optional">(optional)</span>
                </label>
                <textarea
                  id="aqm-note"
                  className="aqm-textarea"
                  value={note}
                  onChange={e => setNote(e.target.value)}
                  placeholder={`e.g. "Focus on the vocabulary section"`}
                  maxLength={1000}
                  rows={3}
                />
              </div>

              {error && <div className="aqm-error" role="alert">{error}</div>}

              <div className="aqm-actions">
                <button
                  className="btn btn-secondary"
                  onClick={() => setStep(1)}
                  type="button"
                  disabled={assigning}
                >
                  Back
                </button>
                <button
                  className="btn btn-primary aqm-assign-btn"
                  onClick={handleAssign}
                  type="button"
                  disabled={assigning}
                >
                  {assigning ? 'Assigning...' : 'Assign Quiz'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
