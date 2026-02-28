import { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { studyApi, type StudyGuide, type ResolvedStudent } from '../../api/client';
import type { TaskItem } from '../../api/tasks';
import { printElement, downloadAsPdf } from '../../utils/exportUtils';
import { LinkedTasksBanner } from './LinkedTasksBanner';

interface ParsedQuestion {
  question: string;
  options: Record<string, string>;
  correct_answer: string;
  explanation?: string;
}

interface QuizTabProps {
  quiz: StudyGuide | undefined;
  generating: string | null;
  focusPrompt: string;
  onFocusPromptChange: (value: string) => void;
  onGenerate: () => void;
  onDelete: (guide: StudyGuide) => void;
  hasSourceContent: boolean;
  isParent: boolean;
  resolvedStudent: ResolvedStudent | null;
  linkedTasks?: TaskItem[];
}

export function QuizTab({
  quiz,
  generating,
  focusPrompt,
  onFocusPromptChange,
  onGenerate,
  onDelete,
  hasSourceContent,
  isParent,
  resolvedStudent,
  linkedTasks = [],
}: QuizTabProps) {
  const [quizIndex, setQuizIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [quizScore, setQuizScore] = useState(0);
  const [quizAnswers, setQuizAnswers] = useState<Record<number, string>>({});
  const [quizFinished, setQuizFinished] = useState(false);
  const [quizSaving, setQuizSaving] = useState(false);
  const [quizSaveError, setQuizSaveError] = useState<string | null>(null);
  const [quizSavedId, setQuizSavedId] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);
  const printRef = useRef<HTMLDivElement>(null);

  const parsedQuiz: ParsedQuestion[] = quiz ? (() => {
    try { return JSON.parse(quiz.content); } catch { return []; }
  })() : [];

  const handleAnswer = (answer: string) => {
    if (showResult) return;
    setSelectedAnswer(answer);
  };

  const handleSubmit = () => {
    if (!selectedAnswer || !parsedQuiz[quizIndex]) return;
    const correct = parsedQuiz[quizIndex].correct_answer === selectedAnswer;
    if (correct) setQuizScore(s => s + 1);
    setQuizAnswers(prev => ({ ...prev, [quizIndex]: selectedAnswer }));
    setShowResult(true);
  };

  const saveQuizResult = (finalScore: number, finalAnswers: Record<number, string>) => {
    if (!quiz) return;
    setQuizSaving(true);
    setQuizSaveError(null);
    studyApi.saveQuizResult({
      study_guide_id: quiz.id,
      score: finalScore,
      total_questions: parsedQuiz.length,
      answers: finalAnswers,
      ...(resolvedStudent ? { student_user_id: resolvedStudent.student_user_id } : {}),
    }).then((result) => {
      setQuizSavedId(result.id);
    }).catch(() => {
      setQuizSaveError('Could not save result');
    }).finally(() => {
      setQuizSaving(false);
    });
  };

  const handleNext = () => {
    if (quizIndex < parsedQuiz.length - 1) {
      setQuizIndex(i => i + 1);
      setSelectedAnswer(null);
      setShowResult(false);
    } else {
      setQuizFinished(true);
      saveQuizResult(quizScore, quizAnswers);
    }
  };

  const resetQuiz = () => {
    setQuizIndex(0);
    setSelectedAnswer(null);
    setShowResult(false);
    setQuizScore(0);
    setQuizAnswers({});
    setQuizFinished(false);
    setQuizSavedId(null);
    setQuizSaveError(null);
  };

  const handlePrint = () => {
    if (printRef.current) printElement(printRef.current, quiz?.title || 'Quiz');
  };

  const handleDownloadPdf = async () => {
    if (!printRef.current) return;
    setExporting(true);
    try {
      const filename = (quiz?.title || 'Quiz').replace(/[^a-zA-Z0-9 _-]/g, '');
      await downloadAsPdf(printRef.current, filename);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="cm-quiz-tab">
      {isParent && (
        <div className={`cm-student-banner ${resolvedStudent ? 'resolved' : 'unresolved'}`}>
          {resolvedStudent
            ? <>Taking quiz for: <strong>{resolvedStudent.student_name}</strong></>
            : 'This quiz is not linked to a student. Results will be saved under your account.'}
        </div>
      )}
      <div className="cm-focus-prompt">
        <input
          type="text"
          value={focusPrompt}
          onChange={(e) => onFocusPromptChange(e.target.value)}
          placeholder="Focus on... (e.g., photosynthesis and the Calvin cycle)"
          disabled={generating !== null}
        />
      </div>
      {quiz && parsedQuiz.length > 0 ? (
        <>
          <div className="cm-guide-actions">
            <button className="cm-action-btn" onClick={handlePrint} title="Print">{'\u{1F5A8}\uFE0F'} Print</button>
            <button className="cm-action-btn" onClick={handleDownloadPdf} disabled={exporting} title="Download PDF">{'\u{1F4E5}'} {exporting ? 'Exporting...' : 'Download PDF'}</button>
            <button className="cm-action-btn" onClick={resetQuiz}>{'\u{1F504}'} Reset</button>
            <button className="cm-action-btn" onClick={onGenerate} disabled={generating !== null}>{'\u2728'} Regenerate</button>
            <button className="cm-action-btn danger" onClick={() => onDelete(quiz)}>{'\u{1F5D1}\uFE0F'} Delete</button>
          </div>
          <LinkedTasksBanner tasks={linkedTasks} />
          {generating === 'quiz' && (
            <div className="cm-regen-status">
              <div className="cm-inline-spinner" />
              <span>Regenerating quiz...</span>
            </div>
          )}
          {/* Hidden print-ready view with all questions */}
          <div ref={printRef} className="cm-print-view">
            <h1 className="print-title">{quiz.title}</h1>
            <p className="print-subtitle">Practice Quiz &middot; {parsedQuiz.length} questions</p>
            {parsedQuiz.map((q, i) => (
              <div key={i} className="print-quiz-item">
                <p className="print-quiz-question">Q{i + 1}. {q.question}</p>
                <ul className="print-quiz-options">
                  {Object.entries(q.options || {}).map(([k, v]) => (
                    <li key={k} className={k === q.correct_answer ? 'correct' : ''}>
                      <strong>{k}.</strong> {v as string}
                    </li>
                  ))}
                </ul>
                {q.explanation && <p className="print-quiz-explanation">{q.explanation}</p>}
              </div>
            ))}
          </div>
          {quizFinished ? (
            <div className="cm-quiz-results">
              <h3>Quiz Complete!</h3>
              <div className="cm-quiz-score">
                {quizScore} / {parsedQuiz.length}
                <span className="cm-quiz-pct">
                  ({Math.round((quizScore / parsedQuiz.length) * 100)}%)
                </span>
              </div>
              {quizSaving && <p className="save-status">Saving result...</p>}
              {quizSaveError && <p className="save-status save-error">{quizSaveError}</p>}
              {quizSavedId !== null && !quizSaving && !quizSaveError && (
                <p className="save-status save-success">Result saved</p>
              )}
              <div className="cm-quiz-result-actions">
                <button className="generate-btn" onClick={resetQuiz}>Try Again</button>
                <Link to={`/quiz-history?quiz=${quiz.id}`} className="cm-action-btn cm-history-link">View History</Link>
              </div>
            </div>
          ) : (
            <div className="cm-quiz-question">
              <div className="cm-quiz-progress">
                Question {quizIndex + 1} of {parsedQuiz.length}
              </div>
              <h3>{parsedQuiz[quizIndex].question}</h3>
              <div className="cm-quiz-options">
                {Object.entries(parsedQuiz[quizIndex].options || {}).map(([key, value]) => (
                  <button
                    key={key}
                    className={`cm-quiz-option${selectedAnswer === key ? ' selected' : ''}${
                      showResult && key === parsedQuiz[quizIndex].correct_answer ? ' correct' : ''
                    }${showResult && selectedAnswer === key && key !== parsedQuiz[quizIndex].correct_answer ? ' incorrect' : ''}`}
                    onClick={() => handleAnswer(key)}
                    disabled={showResult}
                  >
                    <span className="cm-option-key">{key}</span>
                    <span>{value as string}</span>
                  </button>
                ))}
              </div>
              {showResult && parsedQuiz[quizIndex].explanation && (
                <div className="cm-quiz-explanation">
                  <strong>Explanation:</strong> {parsedQuiz[quizIndex].explanation}
                </div>
              )}
              <div className="cm-quiz-actions">
                {!showResult ? (
                  <button className="generate-btn" onClick={handleSubmit} disabled={!selectedAnswer}>
                    Submit Answer
                  </button>
                ) : (
                  <button className="generate-btn" onClick={handleNext}>
                    {quizIndex < parsedQuiz.length - 1 ? 'Next Question' : 'See Results'}
                  </button>
                )}
              </div>
            </div>
          )}
        </>
      ) : generating === 'quiz' ? (
        <div className="cm-inline-generating">
          <div className="cm-inline-spinner" />
          <p>Generating quiz... This may take a moment.</p>
        </div>
      ) : (
        <div className="cm-empty-tab">
          <p>No quiz generated yet.</p>
          <button
            className="generate-btn"
            onClick={onGenerate}
            disabled={generating !== null || !hasSourceContent}
          >
            Generate Quiz
          </button>
          {!hasSourceContent && (
            <p className="cm-hint">Add content or upload a document first to generate a quiz.</p>
          )}
        </div>
      )}
    </div>
  );
}
