/**
 * TutorPage — the unified ClassBridge Tutor (/tutor).
 *
 * Merges the previous Ask-a-Question flow (ASGF: slides + quiz from free-form
 * question/upload) and Flash Tutor flow (ILE: quiz-only drills on a course
 * topic) into a single Arc-led experience.
 *
 * Two modes:
 *   • "explain" (default) — conversational chat input → ASGF slides + quiz
 *   • "drill"             — course topic picker → ILE quiz session
 *
 * Subtle gamification: Arc mood transitions with stage, celebration ring +
 * XP pop on results. (XP/streak hero badge removed until real data is wired.)
 */
import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { asgfApi } from '../api/asgf';
import { ileApi, type ILETopic } from '../api/ile';
import { parentApi } from '../api/parent';
import type {
  IntentClassifyResponse,
  FileUploadResponse,
  CreateSessionResponse,
  ASGFQuizQuestion,
  ActiveSessionItem,
} from '../api/asgf';
import type { SlideData } from '../components/asgf/ASGFSlideCard';
import type { ComprehensionSignalType } from '../components/asgf/ASGFComprehensionSignal';
import type { QuizResults } from '../components/asgf/ASGFQuizBridge';
import type { ASGFContext } from '../components/asgf/ASGFContextPanel';
import { ASGFQuestionInput } from '../components/asgf/ASGFQuestionInput';
import ASGFUploadZone from '../components/asgf/ASGFUploadZone';
import { ASGFContextPanel } from '../components/asgf/ASGFContextPanel';
import ASGFProgressInterstitial from '../components/asgf/ASGFProgressInterstitial';
import { ASGFSlideRenderer } from '../components/asgf/ASGFSlideRenderer';
import { ASGFQuizBridge } from '../components/asgf/ASGFQuizBridge';
import ASGFAssignment from '../components/asgf/ASGFAssignment';
import ASGFResumePrompt from '../components/asgf/ASGFResumePrompt';
import { DashboardLayout } from '../components/DashboardLayout';
import { ChildSelectorTabs } from '../components/ChildSelectorTabs';
import { ArcMascot, type ArcMood } from '../components/arc';
import './TutorPage.css';

type ASGFStage = 'input' | 'processing' | 'slides' | 'quiz' | 'results';
type TutorMode = 'explain' | 'drill';
type DrillSubMode = 'learning' | 'testing' | 'parent_teaching';

const QUICK_PROMPTS = [
  { icon: '✏️', label: 'Explain a concept', seed: 'Explain ' },
  { icon: '📝', label: 'Help with homework', seed: 'Help me with this problem: ' },
  { icon: '📄', label: 'Summarize notes', seed: 'Summarize my notes on ' },
];

function greeting(firstName: string | undefined): string {
  const hour = new Date().getHours();
  const period = hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening';
  const name = firstName?.trim() ? firstName.split(' ')[0] : 'there';
  return `Good ${period}, ${name} —`;
}

export function TutorPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Mode: 'explain' (chat → slides + quiz) | 'drill' (topic picker → ILE quiz)
  const initialMode = (searchParams.get('mode') === 'drill' ? 'drill' : 'explain') as TutorMode;
  const [mode, setMode] = useState<TutorMode>(initialMode);

  // Stage state
  const [stage, setStage] = useState<ASGFStage>('input');

  // Input stage state
  const [question, setQuestion] = useState(searchParams.get('question') || '');

  // Drill mode — deep-link params (#3969, #3970, #3971)
  const contentIdParam = searchParams.get('content_id');
  const queryChildId = searchParams.get('child_id');
  const autoStartRef = useRef(false);

  // Drill mode state
  const [drillTopic, setDrillTopic] = useState<ILETopic | null>(null);
  const [drillCustom, setDrillCustom] = useState({ subject: '', topic: '' });
  const [drillUseCustom, setDrillUseCustom] = useState(false);
  const [drillQuestionCount, setDrillQuestionCount] = useState(5);
  const [drillDifficulty, setDrillDifficulty] = useState<'easy' | 'medium' | 'challenging'>('medium');
  const [drillTopicSearch, setDrillTopicSearch] = useState('');
  const [drillStarting, setDrillStarting] = useState(false);
  const [drillError, setDrillError] = useState<string | null>(null);
  const [drillSubMode, setDrillSubMode] = useState<DrillSubMode>(
    searchParams.get('submode') === 'parent_teaching' && user?.role === 'parent'
      ? 'parent_teaching'
      : 'learning',
  );
  const [drillChildId, setDrillChildId] = useState<number | null>(
    queryChildId ? parseInt(queryChildId, 10) : null,
  );
  const [showAllDrillTopics, setShowAllDrillTopics] = useState(false);
  const [intentResult, setIntentResult] = useState<IntentClassifyResponse | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<FileUploadResponse[]>([]);
  const [context, setContext] = useState<ASGFContext | null>(null);
  const [attachOpen, setAttachOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);

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

  // Context data
  const [contextChildren, setContextChildren] = useState<
    { id: string; name: string; grade: string; board: string }[]
  >([]);
  const [contextCourses, setContextCourses] = useState<
    { id: string; name: string; teacher: string }[]
  >([]);
  const [contextTasks, setContextTasks] = useState<
    { id: string; title: string; due_date: string }[]
  >([]);

  const userRole = (user?.role || user?.roles?.[0] || 'student') as 'parent' | 'student' | 'teacher';

  // Drill mode — fetch available course topics (#3970: scoped to drillChildId for parents)
  const { data: drillTopics = [], isLoading: drillTopicsLoading } = useQuery({
    queryKey: ['tutor-ile-topics', drillChildId],
    queryFn: () => ileApi.getTopics(drillChildId ?? undefined),
    enabled: mode === 'drill',
  });

  // Drill mode — parent child selector (#3970)
  const { data: parentChildren = [] } = useQuery({
    queryKey: ['tutor-parent-children'],
    queryFn: () => parentApi.getChildren(),
    enabled: mode === 'drill' && user?.role === 'parent',
  });

  // #3978: When a parent switches into Parent Teaching sub-mode, auto-select
  // the first linked child so the API call carries a valid child_student_id
  // (the backend silently rejects parent_teaching without one).
  useEffect(() => {
    if (
      drillSubMode === 'parent_teaching' &&
      drillChildId === null &&
      parentChildren.length > 0
    ) {
      setDrillChildId(parentChildren[0].student_id);
    }
  }, [drillSubMode, drillChildId, parentChildren]);

  const filteredDrillTopics = useMemo(() => {
    if (!drillTopicSearch.trim()) return drillTopics;
    const q = drillTopicSearch.toLowerCase();
    return drillTopics.filter(
      (t) =>
        t.topic.toLowerCase().includes(q) ||
        t.subject.toLowerCase().includes(q) ||
        (t.course_name && t.course_name.toLowerCase().includes(q)),
    );
  }, [drillTopics, drillTopicSearch]);

  // Drill mode — sorted + paginated topic list (#3972)
  const displayedDrillTopics = useMemo(() => {
    const sorted = [...filteredDrillTopics].sort((a, b) => {
      if (a.is_weak_area !== b.is_weak_area) return a.is_weak_area ? -1 : 1;
      return a.topic.localeCompare(b.topic);
    });
    return showAllDrillTopics ? sorted : sorted.slice(0, 10);
  }, [filteredDrillTopics, showAllDrillTopics]);

  // Reset "show all" when search changes (#3972)
  useEffect(() => {
    setShowAllDrillTopics(false);
  }, [drillTopicSearch]);

  // Auto-start session from study-guide deep link (#3969). We sync ?mode=drill
  // into the URL BEFORE firing the API call so that a failure + refresh lands
  // the user back on the drill picker (not the explain chat) — #3979.
  useEffect(() => {
    if (!contentIdParam || autoStartRef.current) return;
    autoStartRef.current = true;
    setMode('drill');
    setSearchParams(
      (prev) => {
        prev.set('mode', 'drill');
        return prev;
      },
      { replace: true },
    );
    setDrillStarting(true);
    setDrillError(null);
    ileApi
      .createSessionFromStudyGuide({
        course_content_id: parseInt(contentIdParam, 10),
        mode: 'learning',
      })
      .then((session) => navigate(`/tutor/session/${session.id}`, { replace: true }))
      .catch((err: unknown) => {
        const msg =
          err && typeof err === 'object' && 'response' in err
            ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
            : undefined;
        setDrillError(msg || 'Failed to start session from content.');
      })
      .finally(() => setDrillStarting(false));
  }, [contentIdParam]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleStartDrill = useCallback(async () => {
    const subject = drillUseCustom ? drillCustom.subject : drillTopic?.subject;
    const topic = drillUseCustom ? drillCustom.topic : drillTopic?.topic;
    if (!subject || !topic) {
      setDrillError('Pick a topic or enter one to drill on.');
      return;
    }
    setDrillError(null);
    setDrillStarting(true);
    try {
      const session = await ileApi.createSession({
        mode: drillSubMode,
        subject,
        topic,
        question_count: drillQuestionCount,
        difficulty: drillDifficulty,
        course_id: drillTopic?.course_id ?? undefined,
        timer_enabled: drillSubMode === 'parent_teaching' ? false : undefined,
        child_student_id:
          drillSubMode === 'parent_teaching' ? (drillChildId ?? undefined) : undefined,
      });
      navigate(`/tutor/session/${session.id}`);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setDrillError(msg || 'Could not start drill. Please try again.');
    } finally {
      setDrillStarting(false);
    }
  }, [
    drillUseCustom,
    drillCustom,
    drillTopic,
    drillQuestionCount,
    drillDifficulty,
    drillSubMode,
    drillChildId,
    navigate,
  ]);

  const handleSurpriseMe = useCallback(async () => {
    setDrillError(null);
    try {
      const result = await ileApi.getSurpriseMe();
      setDrillTopic(result.topic);
      setDrillUseCustom(false);
    } catch {
      setDrillError('No surprise topic available yet — pick one or make up your own.');
    }
  }, []);

  const arcMood: ArcMood = useMemo(() => {
    if (error) return 'thinking';
    switch (stage) {
      case 'input':
        return question.trim().length > 0 ? 'thinking' : 'waving';
      case 'processing':
        return 'thinking';
      case 'slides':
        return 'happy';
      case 'quiz':
        return 'thinking';
      case 'results':
        return 'celebrating';
    }
  }, [stage, error, question]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

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
        /* non-critical */
      }
    }
    fetchContextData();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleIntentClassified = useCallback((result: IntentClassifyResponse | null) => {
    setIntentResult(result);
  }, []);

  const handleFilesUploaded = useCallback((files: FileUploadResponse[]) => {
    setUploadedFiles((prev) => [...prev, ...files]);
  }, []);

  const handleContextConfirmed = useCallback((ctx: ASGFContext) => {
    setContext(ctx);
    setContextOpen(false);
  }, []);

  const streamSlides = useCallback(async (sessionId: string) => {
    const controller = new AbortController();
    abortRef.current = controller;
    let firstSlideReceived = false;

    try {
      for await (const event of asgfApi.generateSlides(sessionId, controller.signal)) {
        if (controller.signal.aborted) break;

        if (event.event === 'slide') {
          try {
            const slideData = JSON.parse(event.data) as SlideData;
            if (!firstSlideReceived) {
              firstSlideReceived = true;
              setProcessingStage(4);
            }
            setSlides((prev) => [...prev, slideData]);
          } catch {
            /* skip malformed */
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
  }, []);

  const handleStartSession = useCallback(async () => {
    if (!question.trim()) return;
    setError(null);
    abortRef.current?.abort();
    abortRef.current = null;
    setStage('processing');
    setProcessingStage(0);

    try {
      setProcessingStage(1);

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
      setProcessingStage(3);
      setSlides([]);
      setIsGeneratingSlides(true);
      void streamSlides(session.session_id);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(msg || 'Failed to create session. Please try again.');
      setStage('input');
    }
  }, [question, uploadedFiles, context, intentResult, streamSlides]);

  const handleProcessingComplete = useCallback(() => {
    if (!sessionData) return;
    setStage('slides');
  }, [sessionData]);

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
          /* silent */
        }
      }
    },
    [sessionData],
  );

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

  const handleQuizComplete = useCallback((results: QuizResults) => {
    setQuizResults(results);
    setStage('results');
  }, []);

  const handleResume = useCallback(async (session: ActiveSessionItem) => {
    setError(null);
    setStage('processing');
    setProcessingStage(1);

    try {
      const resumeData = await asgfApi.resumeSession(session.session_id);

      setSessionData({
        session_id: resumeData.session_id,
        topic: session.subject,
        subject: session.subject,
        grade_level: '',
        slide_count: resumeData.slides.length,
        quiz_count: 0,
        estimated_time_min: 0,
      });

      const restoredSlides: SlideData[] = resumeData.slides.map((s, i) => ({
        slideNumber: i + 1,
        title: (s as { title?: string }).title || `Slide ${i + 1}`,
        body: (s as { body?: string }).body || '',
      }));
      setSlides(restoredSlides);

      const restoredSignals: Record<number, ComprehensionSignalType> = {};
      for (const sig of resumeData.signals_given) {
        restoredSignals[sig.slide_number] = sig.signal as ComprehensionSignalType;
      }
      setSignalState(restoredSignals);

      setQuestion(session.question);
      setProcessingStage(4);
      setStage('slides');
    } catch {
      setError('Failed to resume session. Starting fresh.');
      setStage('input');
    }
  }, []);

  const handleDone = useCallback(() => {
    navigate('/dashboard');
  }, [navigate]);

  const handleRetry = useCallback(() => {
    setError(null);
    if (stage === 'processing') {
      handleStartSession();
    }
  }, [stage, handleStartSession]);

  const resetForNewSession = useCallback(() => {
    abortRef.current?.abort();
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
    setAttachOpen(false);
    setContextOpen(false);
  }, []);

  const canStartSession = question.trim().length >= 15;
  const firstName =
    user?.full_name?.split(' ')[0] ??
    (user as { first_name?: string } | null)?.first_name ??
    '';

  return (
    <DashboardLayout>
      <div className="ask-arc-page">
        <div className="ask-arc-page__container">
          {/* ── HERO ───────────────────────────────────────────── */}
          <header className="ask-arc-hero">
            <div className="ask-arc-hero__mascot">
              <ArcMascot size={88} mood={arcMood} glow animate />
            </div>
            <div className="ask-arc-hero__text">
              <p className="ask-arc-hero__greeting">{greeting(firstName)}</p>
              <h1 className="ask-arc-hero__title">
                {stage === 'input' && mode === 'explain' && 'what should we learn today?'}
                {stage === 'input' && mode === 'drill' && 'pick a topic to drill.'}
                {stage === 'processing' && 'building your lesson…'}
                {stage === 'slides' && 'here’s your mini-lesson.'}
                {stage === 'quiz' && 'quick quiz time.'}
                {stage === 'results' && 'nice work!'}
              </h1>
            </div>
          </header>

          {/* ── ERROR BANNER ───────────────────────────────────── */}
          {error && (
            <div className="ask-arc-error" role="alert">
              <span className="ask-arc-error__icon" aria-hidden="true">⚠️</span>
              <p>{error}</p>
              {stage === 'processing' && (
                <button className="ask-arc-error__retry" onClick={handleRetry} type="button">
                  Try Again
                </button>
              )}
              <button
                className="ask-arc-error__dismiss"
                onClick={() => setError(null)}
                type="button"
                aria-label="Dismiss error"
              >
                ×
              </button>
            </div>
          )}

          {/* ── MODE SWITCHER (input stage only) ─────────────────
              #3980: Segmented-button semantics (role=group + aria-pressed)
              match the drill sub-mode pill group and sidestep the
              tablist+arrow-key keyboard contract a `role=tab` group owes.
              #3981: Both onClicks sync the active mode to the URL. */}
          {stage === 'input' && (
            <div className="tutor-mode-switcher" role="group" aria-label="Choose a tutor mode">
              <button
                aria-pressed={mode === 'explain'}
                className={`tutor-mode-tab ${mode === 'explain' ? 'tutor-mode-tab--active' : ''}`}
                onClick={() => {
                  setMode('explain');
                  setSearchParams(
                    (prev) => {
                      prev.delete('mode');
                      return prev;
                    },
                    { replace: true },
                  );
                }}
                type="button"
              >
                <span className="tutor-mode-tab__icon" aria-hidden="true">💬</span>
                <div className="tutor-mode-tab__text">
                  <span className="tutor-mode-tab__title">Explain & learn</span>
                  <span className="tutor-mode-tab__desc">Ask anything → slides + quiz</span>
                </div>
              </button>
              <button
                aria-pressed={mode === 'drill'}
                className={`tutor-mode-tab ${mode === 'drill' ? 'tutor-mode-tab--active' : ''}`}
                onClick={() => {
                  setMode('drill');
                  setSearchParams(
                    (prev) => {
                      prev.set('mode', 'drill');
                      return prev;
                    },
                    { replace: true },
                  );
                }}
                type="button"
              >
                <span className="tutor-mode-tab__icon" aria-hidden="true">🎯</span>
                <div className="tutor-mode-tab__text">
                  <span className="tutor-mode-tab__title">Drill a topic</span>
                  <span className="tutor-mode-tab__desc">Pick a course topic → quick quiz</span>
                </div>
              </button>
            </div>
          )}

          {/* ── STAGE: INPUT · EXPLAIN MODE (conversational) ───── */}
          {stage === 'input' && mode === 'explain' && (
            <section className="ask-arc-convo" aria-label="Ask a question">
              <ASGFResumePrompt onResume={handleResume} />

              <div className="ask-arc-msg ask-arc-msg--arc">
                <p className="ask-arc-msg__bubble">
                  Hey! I'm Arc. Tell me what's on your mind and I'll build a quick mini-lesson + quiz around it. You can attach notes or a worksheet too.
                </p>
              </div>

              {!question && (
                <div className="ask-arc-chiprow" role="list" aria-label="Quick prompts">
                  {QUICK_PROMPTS.map((p) => (
                    <button
                      key={p.label}
                      role="listitem"
                      className="ask-arc-chip"
                      type="button"
                      onClick={() => setQuestion(p.seed)}
                    >
                      <span className="ask-arc-chip__icon">{p.icon}</span>
                      <span>{p.label}</span>
                    </button>
                  ))}
                </div>
              )}

              <div className="ask-arc-input-shell">
                <ASGFQuestionInput
                  value={question}
                  onChange={setQuestion}
                  onIntentClassified={handleIntentClassified}
                />

                <div className="ask-arc-input-actions">
                  <button
                    type="button"
                    className={`ask-arc-tool ${attachOpen ? 'ask-arc-tool--active' : ''}`}
                    onClick={() => setAttachOpen((v) => !v)}
                    aria-pressed={attachOpen}
                    aria-label="Attach class materials"
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path
                        d="M21 11.5l-8.5 8.5a5 5 0 1 1-7-7L14 4.5a3.5 3.5 0 1 1 4.9 5L10 18.5a2 2 0 0 1-2.8-2.8l7.8-7.8"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    <span>Attach{uploadedFiles.length > 0 ? ` (${uploadedFiles.length})` : ''}</span>
                  </button>

                  <button
                    type="button"
                    className={`ask-arc-tool ${contextOpen || context ? 'ask-arc-tool--active' : ''}`}
                    onClick={() => setContextOpen((v) => !v)}
                    aria-pressed={contextOpen}
                    aria-label="Refine study context"
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path
                        d="M3 7h18M6 12h12M10 17h4"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    <span>Context{context ? ' ✓' : ''}</span>
                  </button>

                  <button
                    type="button"
                    className="ask-arc-send"
                    onClick={handleStartSession}
                    disabled={!canStartSession}
                    aria-label="Start Learning Session"
                  >
                    Start Learning Session
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path
                        d="M5 12h14M13 6l6 6-6 6"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                </div>

                {!canStartSession && question.trim().length > 0 && (
                  <p className="ask-arc-hint">
                    Add a bit more detail (at least 15 characters) and I'll get going.
                  </p>
                )}
              </div>

              {attachOpen && (
                <div className="ask-arc-drawer" role="region" aria-label="Attach materials">
                  <ASGFUploadZone onFilesUploaded={handleFilesUploaded} />
                </div>
              )}

              {contextOpen && (
                <div className="ask-arc-drawer" role="region" aria-label="Study context">
                  <ASGFContextPanel
                    intentResult={intentResult || undefined}
                    userRole={userRole}
                    children={contextChildren}
                    courses={contextCourses}
                    upcomingTasks={contextTasks}
                    onContextConfirmed={handleContextConfirmed}
                  />
                </div>
              )}
            </section>
          )}

          {/* ── STAGE: INPUT · DRILL MODE ──────────────────────── */}
          {stage === 'input' && mode === 'drill' && (
            <section className="tutor-drill" aria-label="Drill a course topic">
              <div className="ask-arc-msg ask-arc-msg--arc">
                <p className="ask-arc-msg__bubble">
                  Pick a topic and I'll fire a quick {drillQuestionCount}-question drill at you. Weak areas float to the top.
                </p>
              </div>

              {drillError && (
                <div className="ask-arc-error" role="alert">
                  <span className="ask-arc-error__icon" aria-hidden="true">⚠️</span>
                  <p>{drillError}</p>
                  <button
                    className="ask-arc-error__dismiss"
                    onClick={() => setDrillError(null)}
                    type="button"
                    aria-label="Dismiss error"
                  >
                    ×
                  </button>
                </div>
              )}

              {/* Sub-mode pills (#3971) */}
              <div
                className="tutor-drill__setting tutor-drill__submode"
                role="radiogroup"
                aria-label="Drill sub-mode"
              >
                <span className="tutor-drill__setting-label">Mode</span>
                <div className="tutor-drill__pill-group">
                  <button
                    type="button"
                    role="radio"
                    aria-checked={drillSubMode === 'learning'}
                    className={`tutor-drill__pill ${drillSubMode === 'learning' ? 'tutor-drill__pill--active' : ''}`}
                    onClick={() => setDrillSubMode('learning')}
                  >
                    Learning
                  </button>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={drillSubMode === 'testing'}
                    className={`tutor-drill__pill ${drillSubMode === 'testing' ? 'tutor-drill__pill--active' : ''}`}
                    onClick={() => setDrillSubMode('testing')}
                  >
                    Testing
                  </button>
                  {user?.role === 'parent' && (
                    <button
                      type="button"
                      role="radio"
                      aria-checked={drillSubMode === 'parent_teaching'}
                      className={`tutor-drill__pill ${drillSubMode === 'parent_teaching' ? 'tutor-drill__pill--active' : ''}`}
                      onClick={() => setDrillSubMode('parent_teaching')}
                    >
                      Teach
                    </button>
                  )}
                </div>
              </div>

              {/* Parent child selector (#3970). Overdue counts are
                  intentionally omitted here — the drill flow doesn't surface
                  task pressure and the prop is optional on ChildSelectorTabs
                  (#3984). */}
              {user?.role === 'parent' && parentChildren.length >= 2 && (
                <div className="tutor-drill__children">
                  <ChildSelectorTabs
                    children={parentChildren}
                    selectedChild={drillChildId}
                    onSelectChild={setDrillChildId}
                  />
                </div>
              )}

              <div className="tutor-drill__toolbar">
                {drillTopics.length > 5 && (
                  <input
                    type="text"
                    className="tutor-drill__search"
                    placeholder="Search topics…"
                    value={drillTopicSearch}
                    onChange={(e) => setDrillTopicSearch(e.target.value)}
                    aria-label="Search topics"
                  />
                )}
                <button
                  type="button"
                  className="tutor-drill__surprise"
                  onClick={handleSurpriseMe}
                >
                  🎲 Surprise me
                </button>
              </div>

              {!drillUseCustom && (
                <>
                  <div className="tutor-drill__grid">
                    {drillTopicsLoading && <p className="tutor-drill__empty">Loading topics…</p>}
                    {!drillTopicsLoading && filteredDrillTopics.length === 0 && (
                      <p className="tutor-drill__empty">
                        {drillTopicSearch
                          ? 'No topics match your search.'
                          : 'No course topics yet — enter your own below.'}
                      </p>
                    )}
                    {!drillTopicsLoading &&
                      displayedDrillTopics.map((t, i) => {
                        const selected =
                          drillTopic?.subject === t.subject && drillTopic?.topic === t.topic;
                        return (
                          <button
                            key={`${t.subject}-${t.topic}-${i}`}
                            type="button"
                            className={`tutor-drill__topic ${selected ? 'tutor-drill__topic--selected' : ''} ${t.is_weak_area ? 'tutor-drill__topic--weak' : ''}`}
                            onClick={() => {
                              setDrillTopic(t);
                              setDrillUseCustom(false);
                            }}
                          >
                            <span className="tutor-drill__topic-subject">{t.subject}</span>
                            <span className="tutor-drill__topic-name">{t.topic}</span>
                            {t.is_weak_area && (
                              <span className="tutor-drill__topic-badge">Needs review</span>
                            )}
                          </button>
                        );
                      })}
                  </div>
                  {filteredDrillTopics.length > 10 && (
                    <button
                      type="button"
                      className="tutor-drill__show-all"
                      onClick={() => setShowAllDrillTopics((v) => !v)}
                    >
                      {showAllDrillTopics
                        ? 'Show less'
                        : `Show all ${filteredDrillTopics.length} topics`}
                    </button>
                  )}
                </>
              )}

              <button
                type="button"
                className={`tutor-drill__custom-toggle ${drillUseCustom ? 'tutor-drill__custom-toggle--active' : ''}`}
                onClick={() => setDrillUseCustom((v) => !v)}
              >
                {drillUseCustom ? '← Back to my course topics' : '✏️ Or enter a custom topic…'}
              </button>

              {drillUseCustom && (
                <div className="tutor-drill__custom">
                  <input
                    type="text"
                    placeholder="Subject (e.g. Math, Science)"
                    value={drillCustom.subject}
                    onChange={(e) => setDrillCustom((c) => ({ ...c, subject: e.target.value }))}
                    maxLength={100}
                  />
                  <input
                    type="text"
                    placeholder="Topic (e.g. Fractions, Cell Division)"
                    value={drillCustom.topic}
                    onChange={(e) => setDrillCustom((c) => ({ ...c, topic: e.target.value }))}
                    maxLength={200}
                  />
                </div>
              )}

              <div className="tutor-drill__settings">
                <div className="tutor-drill__setting">
                  <span className="tutor-drill__setting-label">Questions</span>
                  <div className="tutor-drill__pill-group">
                    {[3, 5, 7].map((n) => (
                      <button
                        key={n}
                        type="button"
                        className={`tutor-drill__pill ${drillQuestionCount === n ? 'tutor-drill__pill--active' : ''}`}
                        onClick={() => setDrillQuestionCount(n)}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="tutor-drill__setting">
                  <span className="tutor-drill__setting-label">Difficulty</span>
                  <div className="tutor-drill__pill-group">
                    {(['easy', 'medium', 'challenging'] as const).map((d) => (
                      <button
                        key={d}
                        type="button"
                        className={`tutor-drill__pill ${drillDifficulty === d ? 'tutor-drill__pill--active' : ''}`}
                        onClick={() => setDrillDifficulty(d)}
                      >
                        {d[0].toUpperCase() + d.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <button
                type="button"
                className="ask-arc-send tutor-drill__start"
                onClick={handleStartDrill}
                disabled={
                  drillStarting ||
                  (drillUseCustom
                    ? !drillCustom.subject.trim() || !drillCustom.topic.trim()
                    : !drillTopic) ||
                  (drillSubMode === 'parent_teaching' && !drillChildId)
                }
              >
                {drillStarting ? 'Starting drill…' : 'Start Drill'}
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M5 12h14M13 6l6 6-6 6"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </section>
          )}

          {/* ── STAGE: PROCESSING ──────────────────────────────── */}
          {stage === 'processing' && (
            <section className="ask-arc-stage-wrap">
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
            </section>
          )}

          {/* ── STAGE: SLIDES ──────────────────────────────────── */}
          {stage === 'slides' && (
            <section className="ask-arc-stage-wrap">
              <button
                className="ask-arc-back"
                onClick={() => {
                  abortRef.current?.abort();
                  setStage('input');
                  setSlides([]);
                  setIsGeneratingSlides(false);
                }}
                type="button"
              >
                ← Back to question
              </button>

              <div className="ask-arc-card ask-arc-card--slides">
                <ASGFSlideRenderer
                  slides={slides}
                  isGenerating={isGeneratingSlides}
                  signalState={signalState}
                  onSignalChange={handleSignalChange}
                />
              </div>

              {!isGeneratingSlides && slides.length > 0 && (
                <div className="ask-arc-stage-actions">
                  <button className="ask-arc-continue" onClick={handleContinueToQuiz} type="button">
                    Continue to Quiz
                    <svg viewBox="0 0 16 16" fill="none" aria-hidden="true" width="16" height="16">
                      <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                  <button
                    className="ask-arc-linkbtn"
                    onClick={() => navigate('/course-materials')}
                    type="button"
                  >
                    Just give me a study guide instead
                  </button>
                </div>
              )}
            </section>
          )}

          {/* ── STAGE: QUIZ ────────────────────────────────────── */}
          {stage === 'quiz' && (
            <section className="ask-arc-stage-wrap">
              {quizLoading && (
                <div className="ask-arc-quizloading">
                  <div className="ask-arc-spinner" />
                  <p>Picking the right questions…</p>
                </div>
              )}
              {!quizLoading && quizQuestions.length > 0 && sessionData && (
                <div className="ask-arc-card ask-arc-card--quiz">
                  <ASGFQuizBridge
                    questions={quizQuestions}
                    sessionId={sessionData.session_id}
                    onComplete={handleQuizComplete}
                  />
                </div>
              )}
            </section>
          )}

          {/* ── STAGE: RESULTS ─────────────────────────────────── */}
          {stage === 'results' && (
            <section className="ask-arc-stage-wrap ask-arc-stage-wrap--results">
              {quizResults && (
                <div className="ask-arc-results">
                  <div className="ask-arc-results__ring" aria-hidden="true">
                    <svg viewBox="0 0 120 120" width="160" height="160">
                      <circle cx="60" cy="60" r="52" fill="none" stroke="var(--color-border)" strokeWidth="8" />
                      <circle
                        cx="60"
                        cy="60"
                        r="52"
                        fill="none"
                        stroke="var(--color-accent-warm)"
                        strokeWidth="8"
                        strokeLinecap="round"
                        strokeDasharray={`${(quizResults.correctFirstTry / Math.max(quizResults.totalQuestions, 1)) * 326.7} 326.7`}
                        transform="rotate(-90 60 60)"
                        style={{ transition: 'stroke-dasharray 0.9s ease' }}
                      />
                    </svg>
                    <div className="ask-arc-results__ring-label">
                      <span className="ask-arc-results__score">
                        {quizResults.correctFirstTry}/{quizResults.totalQuestions}
                      </span>
                      <span className="ask-arc-results__label">first try</span>
                    </div>
                  </div>
                  <div className="ask-arc-results__xp">+{quizResults.totalXp} XP earned</div>
                  <p className="ask-arc-results__blurb">
                    Keep that streak alive — Arc will remember where you left off.
                  </p>
                </div>
              )}

              {sessionData && (
                <div className="ask-arc-card">
                  <ASGFAssignment sessionId={sessionData.session_id} onAssigned={() => { /* noop */ }} />
                </div>
              )}

              <div className="ask-arc-stage-actions">
                <button className="ask-arc-continue" onClick={resetForNewSession} type="button">
                  Ask Another Question
                </button>
                <button className="ask-arc-linkbtn" onClick={handleDone} type="button">
                  Back to Dashboard
                </button>
              </div>
            </section>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

export default TutorPage;
