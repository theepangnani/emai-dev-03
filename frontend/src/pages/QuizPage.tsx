import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, Link, useNavigate, useLocation } from 'react-router-dom';
import { studyApi } from '../api/client';
import type { StudyGuide, QuizQuestion, ResolvedStudent } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { MaterialContextMenu } from '../components/MaterialContextMenu';
import { EditStudyGuideModal } from '../components/EditStudyGuideModal';
import { PageNav } from '../components/PageNav';
import { useRegisterNotesFAB } from '../context/FABContext';
import { NotesPanel } from '../components/NotesPanel';
import './QuizPage.css';

export function QuizPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isParent = user?.role === 'parent' || (user?.roles ?? []).includes('parent');
  const [guide, setGuide] = useState<StudyGuide | null>(null);
  const [resolvedStudent, setResolvedStudent] = useState<ResolvedStudent | null>(null);
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [score, setScore] = useState(0);
  const [answers, setAnswers] = useState<{ [key: number]: string }>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const savedResultId = useRef<number | null>(null);
  const [notesOpen, setNotesOpen] = useState(false);
  const toggleNotes = useCallback(() => setNotesOpen(v => !v), []);
  useRegisterNotesFAB(guide?.course_content_id ? { courseContentId: guide.course_content_id, isOpen: notesOpen, onToggle: toggleNotes } : null);

  useEffect(() => {
    const fetchQuiz = async () => {
      if (!id) return;
      try {
        const data = await studyApi.getGuide(parseInt(id));
        setGuide(data);
        let parsedQuestions: QuizQuestion[];
        try {
          parsedQuestions = JSON.parse(data.content) as QuizQuestion[];
        } catch {
          setError('Quiz content is corrupted. Please try regenerating this quiz.');
          return;
        }
        if (!Array.isArray(parsedQuestions) || parsedQuestions.length === 0) {
          setError('Quiz content is corrupted. Please try regenerating this quiz.');
          return;
        }
        setQuestions(parsedQuestions);
      } catch (err) {
        setError('Failed to load quiz');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchQuiz();
  }, [id]);

  // Redirect to course-materials tab when quiz has a parent material (#1969)
  // Skip redirect if opened from class materials tab (fromMaterial state)
  const location = useLocation();
  const fromMaterial = (location.state as { fromMaterial?: boolean })?.fromMaterial;
  useEffect(() => {
    if (guide && guide.course_content_id && !fromMaterial) {
      navigate(`/course-materials/${guide.course_content_id}?tab=quiz`, { replace: true });
    }
  }, [guide, navigate, fromMaterial]);

  // Resolve which student this quiz is for (parents only)
  useEffect(() => {
    if (!isParent || !guide) return;
    studyApi.resolveStudent(
      guide.course_id ? { course_id: guide.course_id } : { study_guide_id: guide.id }
    ).then(setResolvedStudent).catch(() => {});
  }, [isParent, guide]);

  const handleAnswer = (answer: string) => {
    setSelectedAnswer(answer);
  };

  const handleSubmit = () => {
    if (!selectedAnswer) return;

    const isCorrect = selectedAnswer === questions[currentQuestion].correct_answer;
    if (isCorrect) {
      setScore(score + 1);
    }

    setAnswers({ ...answers, [currentQuestion]: selectedAnswer });
    setShowResult(true);
  };

  const handleNext = () => {
    if (currentQuestion < questions.length - 1) {
      setCurrentQuestion(currentQuestion + 1);
      setSelectedAnswer(null);
      setShowResult(false);
    }
  };

  const isQuizComplete = currentQuestion === questions.length - 1 && showResult;

  // Save quiz result when complete
  useEffect(() => {
    if (!isQuizComplete || !guide || savedResultId.current !== null) return;
    setSaving(true);
    setSaveError(null);
    studyApi.saveQuizResult({
      study_guide_id: guide.id,
      score,
      total_questions: questions.length,
      answers,
      ...(resolvedStudent ? { student_user_id: resolvedStudent.student_user_id } : {}),
    }).then((result) => {
      savedResultId.current = result.id;
    }).catch(() => {
      setSaveError('Could not save result');
    }).finally(() => {
      setSaving(false);
    });
  }, [isQuizComplete, guide, score, questions.length, answers]);

  if (loading) {
    return (
      <DashboardLayout showBackButton headerSlot={() => null}>
        <div className="quiz-page">
          <div className="quiz-header">
            <div className="skeleton" style={{ width: 120, height: 16 }} />
            <div className="skeleton" style={{ width: '50%', height: 28, marginTop: 8 }} />
            <div className="skeleton" style={{ width: 140, height: 14, marginTop: 8 }} />
          </div>
          <div className="quiz-content">
            <div className="question-card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div className="skeleton" style={{ width: '80%', height: 22 }} />
              <div className="skeleton" style={{ width: '100%', height: 48, borderRadius: 8 }} />
              <div className="skeleton" style={{ width: '100%', height: 48, borderRadius: 8 }} />
              <div className="skeleton" style={{ width: '100%', height: 48, borderRadius: 8 }} />
              <div className="skeleton" style={{ width: '100%', height: 48, borderRadius: 8 }} />
            </div>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !guide || questions.length === 0) {
    return (
      <DashboardLayout showBackButton headerSlot={() => null}>
        <div className="quiz-page">
          <PageNav items={[
            { label: 'Home', to: '/dashboard' },
            { label: 'Class Materials', to: '/course-materials' },
            ...(guide?.course_content_id
              ? [{ label: guide.title.replace(/^Quiz:\s*/i, ''), to: `/course-materials/${guide.course_content_id}?tab=quiz` }]
              : []),
            { label: 'Quiz' },
          ]} />
          <div className="error">{error || 'Quiz not found'}</div>
        </div>
      </DashboardLayout>
    );
  }

  const question = questions[currentQuestion];

  return (
    <DashboardLayout showBackButton headerSlot={() => null}>
    <div className="quiz-page">
      <div className="quiz-header">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Class Materials', to: '/course-materials' },
          ...(guide?.course_content_id
            ? [{ label: guide.title.replace(/^Quiz:\s*/i, ''), to: `/course-materials/${guide.course_content_id}?tab=quiz` }]
            : []),
          { label: 'Quiz' },
        ]} />
        <h1>
          {guide.title}
          {guide.version > 1 && <span style={{ background: '#e3f2fd', color: '#1565c0', padding: '1px 6px', borderRadius: '8px', fontSize: '0.75rem', marginLeft: '0.5rem', verticalAlign: 'middle' }}>v{guide.version}</span>}
        </h1>
        <div className="quiz-header-actions">
          <MaterialContextMenu items={[
            { label: 'Create Task', icon: <svg width="16" height="16" viewBox="0 0 20 20" fill="none"><rect x="3" y="2" width="14" height="16" rx="2" stroke="currentColor" strokeWidth="1.6"/><path d="M7 7h6M7 10.5h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/><circle cx="14.5" cy="14.5" r="4.5" fill="var(--color-accent-strong, #2a9fa8)"/><path d="M14.5 12.5v4M12.5 14.5h4" stroke="#fff" strokeWidth="1.4" strokeLinecap="round"/></svg>, onClick: () => setShowTaskModal(true) },
            { label: 'Edit Class Material', icon: <svg width="16" height="16" viewBox="0 0 20 20" fill="none"><path d="M13.586 3.586a2 2 0 112.828 2.828l-9.5 9.5L3 17l1.086-3.914 9.5-9.5z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>, onClick: () => setShowEditModal(true) },
          ]} />
          {/* Notes FAB at bottom-right */}
        </div>
        {isParent && (
          <div className={`quiz-student-banner ${resolvedStudent ? 'resolved' : 'unresolved'}`}>
            {resolvedStudent
              ? <>Taking quiz for: <strong>{resolvedStudent.student_name}</strong></>
              : 'This quiz is not linked to a student. Results will be saved under your account.'}
          </div>
        )}
        <div className="progress">
          Question {currentQuestion + 1} of {questions.length}
        </div>
        <div className="progress-bar">
          {questions.map((_, i) => (
            <div
              key={i}
              className={`progress-segment${
                i < currentQuestion ? ` answered ${answers[i] === questions[i].correct_answer ? 'correct' : 'incorrect'}` :
                i === currentQuestion && showResult ? ` answered ${selectedAnswer === questions[i].correct_answer ? 'correct' : 'incorrect'}` :
                i === currentQuestion ? ' current' : ''
              }`}
            />
          ))}
        </div>
      </div>

      {!isQuizComplete ? (
        <div className="quiz-content">
          <div className="question-card">
            <h2 className="question-text">{question.question}</h2>

            <div className="options">
              {Object.entries(question.options).map(([letter, text]) => (
                <button
                  key={letter}
                  className={`option ${selectedAnswer === letter ? 'selected' : ''} ${
                    showResult
                      ? letter === question.correct_answer
                        ? 'correct'
                        : selectedAnswer === letter
                        ? 'incorrect'
                        : ''
                      : ''
                  }`}
                  onClick={() => !showResult && handleAnswer(letter)}
                  disabled={showResult}
                >
                  <span className="option-letter">{letter}</span>
                  <span className="option-text">{text}</span>
                </button>
              ))}
            </div>

            {showResult && (
              <div className={`result ${selectedAnswer === question.correct_answer ? 'correct' : 'incorrect'}`}>
                <p className="result-status">
                  {selectedAnswer === question.correct_answer ? 'Correct!' : 'Incorrect'}
                </p>
                <p className="explanation">{question.explanation}</p>
              </div>
            )}

            <div className="actions">
              {!showResult ? (
                <button
                  className="submit-btn"
                  onClick={handleSubmit}
                  disabled={!selectedAnswer}
                >
                  Submit Answer
                </button>
              ) : (
                <button className="next-btn" onClick={handleNext}>
                  {currentQuestion < questions.length - 1 ? 'Next Question' : 'See Results'}
                </button>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="quiz-results">
          <div className="results-card">
            <h2>Quiz Complete!</h2>
            <div className="score">
              <span className="score-value">{score}</span>
              <span className="score-total">/ {questions.length}</span>
            </div>
            <p className="score-percent">
              {Math.round((score / questions.length) * 100)}% correct
            </p>
            <p className="quiz-encouragement">
              {(() => {
                const pct = Math.round((score / questions.length) * 100);
                if (pct === 100) return 'Perfect score! Outstanding work!';
                if (pct >= 80) return 'Great job! You really know this material!';
                if (pct >= 60) return 'Good effort! A bit more practice and you\'ll master it.';
                return 'Keep studying — every attempt makes you stronger!';
              })()}
            </p>
            {saving && <p className="save-status">Saving result...</p>}
            {saveError && <p className="save-status save-error">{saveError}</p>}
            {savedResultId.current !== null && !saving && !saveError && (
              <p className="save-status save-success">Result saved</p>
            )}
            <div className="results-actions">
              <button
                className="retry-btn"
                onClick={() => {
                  setCurrentQuestion(0);
                  setSelectedAnswer(null);
                  setShowResult(false);
                  setScore(0);
                  setAnswers({});
                  savedResultId.current = null;
                  setSaveError(null);
                }}
              >
                Try Again
              </button>
              <Link to={`/quiz-history?quiz=${guide.id}`} className="done-btn" style={{ background: '#e3f2fd', color: '#1565c0' }}>
                View History
              </Link>
              <Link to="/dashboard" className="done-btn">
                Done
              </Link>
            </div>
          </div>
        </div>
      )}
      <CreateTaskModal
        open={showTaskModal}
        onClose={() => setShowTaskModal(false)}
        prefillTitle={`Review: ${guide.title}`}
        studyGuideId={guide.id}
        courseId={guide.course_id ?? undefined}
        linkedEntityLabel={`Quiz: ${guide.title}`}
      />
      {showEditModal && (
        <EditStudyGuideModal
          guide={guide}
          onClose={() => setShowEditModal(false)}
          onSaved={(updated) => { setGuide(updated); setShowEditModal(false); }}
        />
      )}
      {guide.course_content_id && (
        <>
          <NotesPanel courseContentId={guide.course_content_id} isOpen={notesOpen} onClose={() => setNotesOpen(false)} />
        </>
      )}
    </div>
    </DashboardLayout>
  );
}
