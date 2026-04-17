/**
 * ASGFPage — Full Ask-a-Question to Flash Study flow.
 *
 * Composes all ASGF components into a 5-stage wizard:
 *   1. Input   — question + upload + context
 *   2. Processing — animated progress interstitial
 *   3. Slides  — 7-slide mini-lesson with comprehension signals
 *   4. Quiz    — slide-anchored MCQ quiz
 *   5. Results — score summary + assignment options
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { asgfApi } from '../api/asgf';
import type {
  IntentClassifyResponse,
  FileUploadResponse,
  CreateSessionResponse,
  ASGFQuizQuestion,
} from '../api/asgf';
import type { SlideData } from '../components/asgf/ASGFSlideCard';
import type { ComprehensionSignalType } from '../components/asgf/ASGFComprehensionSignal';
import type { QuizResults } from '../components/asgf/ASGFQuizBridge';
import type { ASGFContext } from '../components/asgf/ASGFContextPanel';
import type { ActiveSessionItem } from '../api/asgf';
import { ASGFQuestionInput } from '../components/asgf/ASGFQuestionInput';
import ASGFUploadZone from '../components/asgf/ASGFUploadZone';
import { ASGFContextPanel } from '../components/asgf/ASGFContextPanel';
import ASGFProgressInterstitial from '../components/asgf/ASGFProgressInterstitial';
import { ASGFSlideRenderer } from '../components/asgf/ASGFSlideRenderer';
import { ASGFQuizBridge } from '../components/asgf/ASGFQuizBridge';
import ASGFAssignment from '../components/asgf/ASGFAssignment';
import ASGFResumePrompt from '../components/asgf/ASGFResumePrompt';
import { DashboardLayout } from '../components/DashboardLayout';
import './ASGFPage.css';

type ASGFStage = 'input' | 'processing' | 'slides' | 'quiz' | 'results';

export function ASGFPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Stage state
  const [stage, setStage] = useState<ASGFStage>('input');

  // Input stage state
  const [question, setQuestion] = useState(searchParams.get('question') || '');
  const [intentResult, setIntentResult] = useState<IntentClassifyResponse | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<FileUploadResponse[]>([]);
  const [context, setContext] = useState<ASGFContext | null>(null);

  // Processing stage state
  const [processingStage, setProcessingStage] = useState(0);
  const [sessionData, setSessionData] = useState<CreateSessionResponse | null>(null);

  // Slides stage state
  const [slides, setSlides] = useState<SlideData[]>([]);
  const [isGeneratingSlides, setIsGeneratingSlides] = useState(false);
  const [signalState, setSignalState] = useState<Record<number, ComprehensionSignalType>>({});
  const abortRef = useRef<AbortController | null>(null);

  // Quiz stage state
  const [quizQuestions, setQuizQuestions] = useState<ASGFQuizQuestion[]>([]);
  const [quizLoading, setQuizLoading] = useState(false);

  // Results stage state
  const [quizResults, setQuizResults] = useState<QuizResults | null>(null);

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Context data (fetched from API)
  const [contextChildren, setContextChildren] = useState<{ id: string; name: string; grade: string; board: string }[]>([]);
  const [contextCourses, setContextCourses] = useState<{ id: string; name: string; teacher: string }[]>([]);
  const [contextTasks, setContextTasks] = useState<{ id: string; title: string; due_date: string }[]>([]);

  const userRole = (user?.role || user?.roles?.[0] || 'student') as 'parent' | 'student' | 'teacher';

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  // Fetch context data (children, courses, tasks) on mount
  useEffect(() => {
    let cancelled = false;
    async function fetchContextData() {
      try {
        const data = await asgfApi.getContextData();
        if (!cancelled) {
          setContextChildren(data.children || []);
          setContextCourses(data.courses || []);
          setContextTasks(data.upcoming_tasks || []);
        }
      } catch {
        // Non-critical — context panel works without pre-populated data
      }
    }
    fetchContextData();
    return () => { cancelled = true; };
  }, []);

  // Handle intent classification
  const handleIntentClassified = useCallback((result: IntentClassifyResponse | null) => {
    setIntentResult(result);
  }, []);

  // Handle file upload completion
  const handleFilesUploaded = useCallback((files: FileUploadResponse[]) => {
    setUploadedFiles((prev) => [...prev, ...files]);
  }, []);

  // Handle context confirmation
  const handleContextConfirmed = useCallback((ctx: ASGFContext) => {
    setContext(ctx);
  }, []);

  // Start the learning session
  const handleStartSession = useCallback(async () => {
    if (!question.trim()) return;
    setError(null);
    setStage('processing');
    setProcessingStage(0);

    try {
      // Stage 0: Intent classified (already done in input)
      setProcessingStage(1);

      // Stage 1: Create session
      const session = await asgfApi.createSession({
        question: question.trim(),
        file_ids: uploadedFiles.map((f) => f.file_id),
        child_id: context?.childId,
        subject: context?.subject || intentResult?.subject,
        grade: context?.gradeLevel || intentResult?.grade_level,
        course_id: context?.courseId,
      });

      setSessionData(session);
      setProcessingStage(2);

      // Stage 2-3: Slides generating
      setProcessingStage(3);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(msg || 'Failed to create session. Please try again.');
      setStage('input');
    }
  }, [question, uploadedFiles, context, intentResult]);

  // Transition from processing to slides
  const handleProcessingComplete = useCallback(async () => {
    if (!sessionData) return;
    setStage('slides');
    setIsGeneratingSlides(true);
    setSlides([]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const event of asgfApi.generateSlides(sessionData.session_id, controller.signal)) {
        if (controller.signal.aborted) break;

        if (event.event === 'slide') {
          try {
            const slideData = JSON.parse(event.data) as SlideData;
            setSlides((prev) => [...prev, slideData]);
          } catch {
            // Skip malformed slide data
          }
        } else if (event.event === 'done' || event.event === 'complete') {
          break;
        } else if (event.event === 'error') {
          setError('An error occurred while generating slides. You can continue with what was generated.');
          break;
        }
      }
    } catch {
      if (!controller.signal.aborted) {
        setError('Connection lost while generating slides. You can continue with what was generated.');
      }
    } finally {
      setIsGeneratingSlides(false);
    }
  }, [sessionData]);

  // Handle comprehension signal
  const handleSignalChange = useCallback(
    async (slideIndex: number, signal: ComprehensionSignalType) => {
      setSignalState((prev) => ({ ...prev, [slideIndex]: signal }));

      if (sessionData) {
        try {
          await asgfApi.sendComprehensionSignal(sessionData.session_id, {
            slide_number: slideIndex,
            signal,
          });
        } catch {
          // Silently fail — signal is tracked locally
        }
      }
    },
    [sessionData],
  );

  // Continue to quiz
  const handleContinueToQuiz = useCallback(async () => {
    if (!sessionData) return;
    setError(null);
    setStage('quiz');
    setQuizLoading(true);

    try {
      const quizData = await asgfApi.generateQuiz(sessionData.session_id);
      setQuizQuestions(quizData.questions);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(msg || 'Failed to generate quiz. Please try again.');
      setStage('slides');
    } finally {
      setQuizLoading(false);
    }
  }, [sessionData]);

  // Handle quiz completion
  const handleQuizComplete = useCallback((results: QuizResults) => {
    setQuizResults(results);
    setStage('results');
  }, []);

  // Handle session resume
  const handleResume = useCallback(
    async (session: ActiveSessionItem) => {
      setError(null);
      setStage('processing');
      setProcessingStage(1);

      try {
        const resumeData = await asgfApi.resumeSession(session.session_id);

        // Reconstruct session data
        setSessionData({
          session_id: resumeData.session_id,
          topic: session.subject,
          subject: session.subject,
          grade_level: '',
          slide_count: resumeData.slides.length,
          quiz_count: 0,
          estimated_time_min: 0,
        });

        // Restore slides
        const restoredSlides: SlideData[] = resumeData.slides.map((s, i) => ({
          slideNumber: i + 1,
          title: (s as { title?: string }).title || `Slide ${i + 1}`,
          body: (s as { body?: string }).body || '',
        }));
        setSlides(restoredSlides);

        // Restore comprehension signals
        const restoredSignals: Record<number, ComprehensionSignalType> = {};
        for (const sig of resumeData.signals_given) {
          restoredSignals[sig.slide_number] = sig.signal as ComprehensionSignalType;
        }
        setSignalState(restoredSignals);

        setQuestion(session.question);
        setProcessingStage(4);

        // Go directly to slides
        setStage('slides');
      } catch {
        setError('Failed to resume session. Starting fresh.');
        setStage('input');
      }
    },
    [],
  );

  // Done — return to dashboard
  const handleDone = useCallback(() => {
    navigate('/dashboard');
  }, [navigate]);

  // Retry from error
  const handleRetry = useCallback(() => {
    setError(null);
    if (stage === 'processing') {
      handleStartSession();
    }
  }, [stage, handleStartSession]);

  const canStartSession = question.trim().length >= 15;

  return (
    <DashboardLayout>
      <div className="asgf-page">
        <div className="asgf-page__container">
          {/* Header */}
          <div className="asgf-page__header">
            <h1 className="asgf-page__title">
              {stage === 'input' && 'Ask a Question'}
              {stage === 'processing' && 'Preparing Your Session'}
              {stage === 'slides' && 'Your Mini-Lesson'}
              {stage === 'quiz' && 'Quick Quiz'}
              {stage === 'results' && 'Session Complete'}
            </h1>
            {stage === 'input' && (
              <p className="asgf-page__subtitle">
                Ask anything and we will build a personalized study session around it.
              </p>
            )}
          </div>

          {/* Error banner */}
          {error && (
            <div className="asgf-page__error" role="alert">
              <p>{error}</p>
              {stage === 'processing' && (
                <button className="asgf-page__error-retry" onClick={handleRetry} type="button">
                  Try Again
                </button>
              )}
              <button
                className="asgf-page__error-dismiss"
                onClick={() => setError(null)}
                type="button"
                aria-label="Dismiss error"
              >
                &times;
              </button>
            </div>
          )}

          {/* Stage 1: Input */}
          {stage === 'input' && (
            <div className="asgf-page__input-stage">
              <ASGFResumePrompt onResume={handleResume} />

              <ASGFQuestionInput
                value={question}
                onChange={setQuestion}
                onIntentClassified={handleIntentClassified}
              />

              <ASGFUploadZone onFilesUploaded={handleFilesUploaded} />

              <ASGFContextPanel
                intentResult={intentResult || undefined}
                userRole={userRole}
                children={contextChildren}
                courses={contextCourses}
                upcomingTasks={contextTasks}
                onContextConfirmed={handleContextConfirmed}
              />

              <div className="asgf-page__start-wrapper">
                <button
                  className="asgf-page__start-btn"
                  onClick={handleStartSession}
                  disabled={!canStartSession}
                  type="button"
                >
                  Start Learning Session
                </button>
                {!canStartSession && question.trim().length > 0 && (
                  <p className="asgf-page__start-hint">
                    Add a bit more detail to your question (at least 15 characters)
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Stage 2: Processing */}
          {stage === 'processing' && (
            <div className="asgf-page__processing-stage">
              <ASGFProgressInterstitial
                currentStage={processingStage}
                planPreview={
                  sessionData
                    ? {
                        topic: sessionData.topic,
                        slideCount: sessionData.slide_count,
                        quizCount: sessionData.quiz_count,
                        estimatedTimeMin: sessionData.estimated_time_min,
                      }
                    : null
                }
                onComplete={handleProcessingComplete}
              />
            </div>
          )}

          {/* Stage 3: Slides */}
          {stage === 'slides' && (
            <div className="asgf-page__slides-stage">
              <button
                className="asgf-page__back-btn"
                onClick={() => { abortRef.current?.abort(); setStage('input'); setSlides([]); setIsGeneratingSlides(false); }}
                type="button"
              >
                &larr; Back to question
              </button>
              <ASGFSlideRenderer
                slides={slides}
                isGenerating={isGeneratingSlides}
                signalState={signalState}
                onSignalChange={handleSignalChange}
              />

              {!isGeneratingSlides && slides.length > 0 && (
                <div className="asgf-page__slides-actions">
                  <button
                    className="asgf-page__continue-btn"
                    onClick={handleContinueToQuiz}
                    type="button"
                  >
                    Continue to Quiz
                    <svg
                      viewBox="0 0 16 16"
                      fill="none"
                      aria-hidden="true"
                      width="16"
                      height="16"
                    >
                      <path
                        d="M6 4l4 4-4 4"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                  <button
                    className="asgf-page__study-guide-link"
                    onClick={() => navigate('/course-materials')}
                    type="button"
                    aria-label="Go to course materials for a study guide"
                  >
                    Just give me a study guide instead
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Stage 4: Quiz */}
          {stage === 'quiz' && (
            <div className="asgf-page__quiz-stage">
              {quizLoading && (
                <div className="asgf-page__quiz-loading">
                  <div className="asgf-page__quiz-spinner" />
                  <p>Generating quiz questions...</p>
                </div>
              )}
              {!quizLoading && quizQuestions.length > 0 && sessionData && (
                <ASGFQuizBridge
                  questions={quizQuestions}
                  sessionId={sessionData.session_id}
                  onComplete={handleQuizComplete}
                />
              )}
            </div>
          )}

          {/* Stage 5: Results */}
          {stage === 'results' && (
            <div className="asgf-page__results-stage">
              {quizResults && (
                <div className="asgf-page__results-summary">
                  <div className="asgf-page__results-score">
                    {quizResults.correctFirstTry}/{quizResults.totalQuestions}
                  </div>
                  <p className="asgf-page__results-label">correct on first try</p>
                  <div className="asgf-page__results-xp">+{quizResults.totalXp} XP earned</div>
                </div>
              )}

              {sessionData && (
                <ASGFAssignment
                  sessionId={sessionData.session_id}
                  onAssigned={() => {
                    // Assignment confirmed
                  }}
                />
              )}

              <div className="asgf-page__done-wrapper">
                <button
                  className="asgf-page__done-btn"
                  onClick={handleDone}
                  type="button"
                >
                  Back to Dashboard
                </button>
                <button
                  className="asgf-page__new-session-btn"
                  onClick={() => {
                    setStage('input');
                    setQuestion('');
                    setIntentResult(null);
                    setUploadedFiles([]);
                    setContext(null);
                    setSessionData(null);
                    setSlides([]);
                    setSignalState({});
                    setQuizQuestions([]);
                    setQuizResults(null);
                    setError(null);
                    setProcessingStage(0);
                  }}
                  type="button"
                >
                  Ask Another Question
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

export default ASGFPage;
