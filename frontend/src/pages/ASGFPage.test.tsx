import { screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders } from '../test/helpers';

// ── Mocks ──────────────────────────────────────────────────────
const mockCreateSession = vi.fn();
const mockGenerateSlides = vi.fn();
const mockClassifyIntent = vi.fn();
const mockGetActiveSessions = vi.fn();
const mockGetContextData = vi.fn();

vi.mock('../api/asgf', () => ({
  asgfApi: {
    classifyIntent: (...args: unknown[]) => mockClassifyIntent(...args),
    createSession: (...args: unknown[]) => mockCreateSession(...args),
    generateSlides: (...args: unknown[]) => mockGenerateSlides(...args),
    getActiveSessions: (...args: unknown[]) => mockGetActiveSessions(...args),
    getContextData: (...args: unknown[]) => mockGetContextData(...args),
    sendComprehensionSignal: vi.fn(),
    generateQuiz: vi.fn(),
    resumeSession: vi.fn(),
    uploadDocuments: vi.fn(),
  },
}));

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Test User', role: 'student', roles: ['student'] },
    logout: vi.fn(),
    switchRole: vi.fn(),
  }),
}));

vi.mock('../components/DashboardLayout', () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

// Mock the progress interstitial so we can observe stage transitions synchronously.
vi.mock('../components/asgf/ASGFProgressInterstitial', () => ({
  default: ({
    currentStage,
    onComplete,
  }: {
    currentStage: number;
    onComplete?: () => void;
  }) => {
    // Fire onComplete synchronously when stage >= 4, mirroring prod behavior (minus the 800ms delay).
    if (currentStage >= 4 && onComplete) {
      queueMicrotask(onComplete);
    }
    return <div data-testid="progress-interstitial" data-stage={currentStage} />;
  },
}));

vi.mock('../components/asgf/ASGFSlideRenderer', () => ({
  ASGFSlideRenderer: ({ slides }: { slides: { title: string }[] }) => (
    <div data-testid="slide-renderer">
      {slides.map((s, i) => (
        <div key={i} data-testid={`slide-${i}`}>
          {s.title}
        </div>
      ))}
    </div>
  ),
}));

vi.mock('../components/asgf/ASGFResumePrompt', () => ({
  default: () => <div data-testid="resume-prompt" />,
}));

vi.mock('../components/asgf/ASGFUploadZone', () => ({
  default: () => <div data-testid="upload-zone" />,
}));

vi.mock('../components/asgf/ASGFContextPanel', () => ({
  ASGFContextPanel: () => <div data-testid="context-panel" />,
}));

// ── Import after mocks ────────────────────────────────────────
import { ASGFPage } from './ASGFPage';

// ── Helpers ────────────────────────────────────────────────────
const MOCK_SESSION = {
  session_id: 'sess-123',
  topic: 'Fractions',
  subject: 'Math',
  grade_level: '5',
  slide_count: 7,
  quiz_count: 3,
  estimated_time_min: 10,
};

function makeSlideGenerator(slides: { event: string; data: string }[]) {
  return async function* () {
    for (const s of slides) {
      yield s;
    }
  };
}

// ── Tests ──────────────────────────────────────────────────────
describe('ASGFPage — eager SSE streaming (#3735)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetActiveSessions.mockResolvedValue({ sessions: [] });
    mockGetContextData.mockResolvedValue({
      children: [],
      courses: [],
      upcoming_tasks: [],
    });
    mockClassifyIntent.mockResolvedValue({
      subject: 'Math',
      grade_level: '5',
      topic: 'Fractions',
      confidence: 0.9,
      bloom_tier: 'apply',
      alternatives: [],
    });
  });

  it('opens SSE eagerly after createSession (before stage reaches 4)', async () => {
    const user = userEvent.setup();

    mockCreateSession.mockResolvedValue(MOCK_SESSION);

    // SSE generator — we track whether it was called before stage reached 4.
    let stageAtGeneratorCall = -99;
    mockGenerateSlides.mockImplementation(() => {
      // Read the stage attribute from the interstitial at the moment SSE opens.
      const el = document.querySelector('[data-testid="progress-interstitial"]');
      stageAtGeneratorCall = el ? Number(el.getAttribute('data-stage')) : -1;
      return makeSlideGenerator([
        {
          event: 'slide',
          data: JSON.stringify({
            slideNumber: 1,
            title: 'Intro to Fractions',
            body: 'A fraction is...',
          }),
        },
        { event: 'done', data: '' },
      ])();
    });

    renderWithProviders(<ASGFPage />);

    // Fill the question input (>= 15 chars required)
    const textarea = await screen.findByRole('textbox');
    await user.type(textarea, 'How do fractions work in math?');

    // Click "Start Learning Session"
    const startBtn = screen.getByRole('button', { name: /Start Learning Session/i });
    await act(async () => {
      await user.click(startBtn);
    });

    // createSession must have been called
    await waitFor(() => {
      expect(mockCreateSession).toHaveBeenCalledTimes(1);
    });

    // SSE generator must be called eagerly (before stage 4)
    await waitFor(() => {
      expect(mockGenerateSlides).toHaveBeenCalledTimes(1);
    });
    expect(mockGenerateSlides).toHaveBeenCalledWith('sess-123', expect.any(AbortSignal));

    // Critical: stage was < 4 when generateSlides was invoked (i.e. SSE is
    // opened BEFORE the interstitial's onComplete callback can fire).
    expect(stageAtGeneratorCall).toBeGreaterThanOrEqual(0);
    expect(stageAtGeneratorCall).toBeLessThan(4);
  });

  // Regression for #3741 — stale SSE from a previous session must not leak
  // into a new session's slides state when the user clicks Try Again.
  it('aborts prior SSE when a new session starts via retry', async () => {
    const user = userEvent.setup();

    mockCreateSession.mockResolvedValue(MOCK_SESSION);

    // Capture the AbortSignal passed to each generateSlides call.
    const capturedSignals: AbortSignal[] = [];

    // Session A: emit an 'error' event (keeps us in processing stage with
    // Try Again visible) and do NOT explicitly abort. Then block indefinitely
    // unless the signal aborts — simulating a lingering connection.
    function makeErrorThenBlockGenerator(signal: AbortSignal) {
      return (async function* () {
        yield { event: 'error', data: 'transient' };
        await new Promise<void>((resolve) => {
          if (signal.aborted) {
            resolve();
            return;
          }
          signal.addEventListener('abort', () => resolve(), { once: true });
        });
      })();
    }

    mockGenerateSlides.mockImplementation((_sessionId: string, signal: AbortSignal) => {
      capturedSignals.push(signal);
      if (capturedSignals.length === 1) {
        return makeErrorThenBlockGenerator(signal);
      }
      return makeSlideGenerator([
        {
          event: 'slide',
          data: JSON.stringify({
            slideNumber: 1,
            title: 'Session B slide',
            body: 'Second session body',
          }),
        },
        { event: 'done', data: '' },
      ])();
    });

    renderWithProviders(<ASGFPage />);

    // Session A — fill textarea and start.
    const textarea = await screen.findByRole('textbox');
    await user.type(textarea, 'How do fractions work in math?');

    const startBtn = screen.getByRole('button', { name: /Start Learning Session/i });
    await act(async () => {
      await user.click(startBtn);
    });

    // Session A's SSE opens.
    await waitFor(() => {
      expect(mockGenerateSlides).toHaveBeenCalledTimes(1);
    });
    // The error event surfaces the Try Again button in the processing stage.
    const retryBtn = await screen.findByRole('button', { name: /Try Again/i });

    // Session A's controller is still live at this point — streamSlides breaks
    // on error but does not call .abort() itself.
    expect(capturedSignals[0].aborted).toBe(false);

    // Click Try Again — this invokes handleStartSession for session B while
    // session A's controller is still unreferenced-but-alive.
    await act(async () => {
      await user.click(retryBtn);
    });

    // Session A's captured AbortSignal must now be aborted — the fix ensures
    // handleStartSession aborts the prior controller before opening a new one.
    await waitFor(() => {
      expect(capturedSignals[0].aborted).toBe(true);
    });

    // Session B should have been opened with a fresh, unaborted signal.
    await waitFor(() => {
      expect(mockGenerateSlides).toHaveBeenCalledTimes(2);
    });
    expect(capturedSignals[1]).not.toBe(capturedSignals[0]);
    expect(capturedSignals[1].aborted).toBe(false);
  });

  it('advances processingStage to 4 and transitions to slides after first slide event', async () => {
    const user = userEvent.setup();

    mockCreateSession.mockResolvedValue(MOCK_SESSION);
    mockGenerateSlides.mockImplementation(() =>
      makeSlideGenerator([
        {
          event: 'slide',
          data: JSON.stringify({
            slideNumber: 1,
            title: 'Intro to Fractions',
            body: 'A fraction is...',
          }),
        },
        { event: 'done', data: '' },
      ])(),
    );

    renderWithProviders(<ASGFPage />);

    const textarea = await screen.findByRole('textbox');
    await user.type(textarea, 'How do fractions work in math?');

    const startBtn = screen.getByRole('button', { name: /Start Learning Session/i });
    await act(async () => {
      await user.click(startBtn);
    });

    // After the first slide event, onComplete should fire and transition to the slides view.
    await waitFor(() => {
      expect(screen.getByTestId('slide-renderer')).toBeInTheDocument();
    });

    // And the rendered slide appears
    await waitFor(() => {
      expect(screen.getByText('Intro to Fractions')).toBeInTheDocument();
    });
  });
});
