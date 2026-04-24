import { screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useLocation } from 'react-router-dom';
import { renderWithProviders } from '../test/helpers';

/** Test helper: surfaces the current MemoryRouter location.search to the DOM
 *  so tests can assert directly on URL-sync behavior (#3991). */
function LocationProbe() {
  const loc = useLocation();
  return <div data-testid="current-search">{loc.search}</div>;
}

// ── Mocks ──────────────────────────────────────────────────────
const mockCreateSession = vi.fn();
const mockGenerateSlides = vi.fn();
const mockClassifyIntent = vi.fn();
const mockGetActiveSessions = vi.fn();
const mockGetContextData = vi.fn();
const mockIleCreateSession = vi.fn();
const mockIleGetTopics = vi.fn();
const mockIleGetSurpriseMe = vi.fn();
const mockIleCreateSessionFromStudyGuide = vi.fn();
const mockParentGetChildren = vi.fn();
const mockUseChildOverdueCounts = vi.fn();
const mockApiGet = vi.fn();
const mockAuthUser = { current: { role: 'student', roles: ['student'] } as { role: string; roles: string[] } };

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
    user: {
      id: 1,
      full_name: 'Test User',
      role: mockAuthUser.current.role,
      roles: mockAuthUser.current.roles,
    },
    logout: vi.fn(),
    switchRole: vi.fn(),
  }),
}));

vi.mock('../api/ile', () => ({
  ileApi: {
    createSession: (...args: unknown[]) => mockIleCreateSession(...args),
    getTopics: (...args: unknown[]) => mockIleGetTopics(...args),
    getSurpriseMe: (...args: unknown[]) => mockIleGetSurpriseMe(...args),
    createSessionFromStudyGuide: (...args: unknown[]) => mockIleCreateSessionFromStudyGuide(...args),
  },
}));

vi.mock('../api/parent', () => ({
  parentApi: {
    getChildren: (...args: unknown[]) => mockParentGetChildren(...args),
  },
}));

vi.mock('../hooks/useChildOverdueCounts', () => ({
  useChildOverdueCounts: (...args: unknown[]) => mockUseChildOverdueCounts(...args),
}));

// Feature-flag hook. Most tests keep `tutor_chat_enabled` OFF so the legacy
// ASGF form renders (existing tests were written against that tree). The
// #4095 mode-toggle integration tests flip the default in a nested describe.
const mockUseFeatureFlagEnabled = vi.fn<(key: string) => boolean>(() => false);
vi.mock('../hooks/useFeatureToggle', () => ({
  useFeatureFlagEnabled: (key: string) => mockUseFeatureFlagEnabled(key),
}));

vi.mock('../api/client', () => ({
  api: {
    get: (...args: unknown[]) => mockApiGet(...args),
  },
  AI_TIMEOUT: { timeout: 120_000 },
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
import { TutorPage } from './TutorPage';

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
describe('TutorPage — ASGF (explain mode) eager SSE streaming (#3735)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuthUser.current = { role: 'student', roles: ['student'] };
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
    mockIleGetTopics.mockResolvedValue([]);
    mockParentGetChildren.mockResolvedValue([]);
    mockUseChildOverdueCounts.mockReturnValue(new Map());
    // Default: XP summary returns zero state so the hero badge is hidden.
    // URL-gated so unexpected api.get calls surface as test failures.
    mockApiGet.mockImplementation((url: string) => {
      if (url === '/api/xp/summary') {
        return Promise.resolve({ data: { xp_total: 0, streak_days: 0 } });
      }
      return Promise.reject(new Error(`Unexpected api.get: ${url}`));
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

    renderWithProviders(<TutorPage />);

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

    renderWithProviders(<TutorPage />);

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

    renderWithProviders(<TutorPage />);

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

// ── Round-1 review fixes (drill logic, URL sync, a11y) ─────────
describe('TutorPage — drill mode round-1 fixes', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuthUser.current = { role: 'parent', roles: ['parent'] };
    mockGetActiveSessions.mockResolvedValue({ sessions: [] });
    mockGetContextData.mockResolvedValue({ children: [], courses: [], upcoming_tasks: [] });
    mockIleGetTopics.mockResolvedValue([
      {
        subject: 'Math',
        topic: 'Fractions',
        course_id: 101,
        course_name: 'Grade 5 Math',
        is_weak_area: false,
      },
    ]);
    mockParentGetChildren.mockResolvedValue([
      {
        student_id: 77,
        user_id: 77,
        full_name: 'Kid A',
        email: null,
        grade_level: 5,
        school_name: null,
        date_of_birth: null,
        phone: null,
        address: null,
        city: null,
        province: null,
        postal_code: null,
        notes: null,
        interests: [],
        relationship_type: null,
        invite_link: null,
        course_count: 0,
        active_task_count: 0,
        invite_status: null,
      },
      {
        student_id: 88,
        user_id: 88,
        full_name: 'Kid B',
        email: null,
        grade_level: 7,
        school_name: null,
        date_of_birth: null,
        phone: null,
        address: null,
        city: null,
        province: null,
        postal_code: null,
        notes: null,
        interests: [],
        relationship_type: null,
        invite_link: null,
        course_count: 0,
        active_task_count: 0,
        invite_status: null,
      },
    ]);
    mockIleCreateSession.mockResolvedValue({ id: 999 });
    mockUseChildOverdueCounts.mockReturnValue(new Map());
    mockApiGet.mockImplementation((url: string) => {
      if (url === '/api/xp/summary') {
        return Promise.resolve({ data: { xp_total: 0, streak_days: 0 } });
      }
      return Promise.reject(new Error(`Unexpected api.get: ${url}`));
    });
  });

  it('#3975: handleStartDrill uses drillChildId (state) not URL child_id', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TutorPage />, { initialEntries: ['/tutor?mode=drill&submode=parent_teaching&child_id=77'] });

    // Both children render in the selector (grab Kid B's tab and click it).
    const kidB = await screen.findByRole('tab', { name: /Kid B/i });
    await act(async () => {
      await user.click(kidB);
    });

    // Pick the topic card then start the drill.
    const topicCard = await screen.findByRole('button', { name: /Fractions/i });
    await act(async () => {
      await user.click(topicCard);
    });

    const startBtn = screen.getByRole('button', { name: /Start Drill/i });
    await act(async () => {
      await user.click(startBtn);
    });

    await waitFor(() => {
      expect(mockIleCreateSession).toHaveBeenCalledTimes(1);
    });
    expect(mockIleCreateSession).toHaveBeenCalledWith(
      expect.objectContaining({ child_student_id: 88, mode: 'parent_teaching' }),
    );
  });

  it('#3976: ?submode=parent_teaching starts in parent_teaching sub-mode', async () => {
    renderWithProviders(<TutorPage />, { initialEntries: ['/tutor?mode=drill&submode=parent_teaching'] });

    // Find the "Teach" radio — it should be checked.
    const teachPill = await screen.findByRole('radio', { name: /Teach/i });
    expect(teachPill).toHaveAttribute('aria-checked', 'true');
  });

  it('#3981: mode tab click updates URL search params', async () => {
    const user = userEvent.setup();
    // Mount a LocationProbe alongside TutorPage so we can assert directly on
    // the MemoryRouter-managed location.search (#3991 — stronger than the
    // aria-pressed round-trip the original test used).
    renderWithProviders(
      <>
        <TutorPage />
        <LocationProbe />
      </>,
      { initialEntries: ['/tutor'] },
    );

    // Default mode is 'explain', Drill tab is aria-pressed=false.
    const drillTab = await screen.findByRole('button', { name: /Drill a topic/i });
    expect(drillTab).toHaveAttribute('aria-pressed', 'false');

    await act(async () => {
      await user.click(drillTab);
    });

    // After click, Drill tab is pressed AND the URL carries ?mode=drill.
    await waitFor(() => {
      expect(drillTab).toHaveAttribute('aria-pressed', 'true');
    });
    await waitFor(() => {
      expect(screen.getByTestId('current-search').textContent ?? '').toContain(
        'mode=drill',
      );
    });

    // Round-trip: click Explain back — URL must drop mode=drill.
    const explainTab = screen.getByRole('button', { name: /Explain & learn/i });
    await act(async () => {
      await user.click(explainTab);
    });
    await waitFor(() => {
      expect(explainTab).toHaveAttribute('aria-pressed', 'true');
    });
    expect(drillTab).toHaveAttribute('aria-pressed', 'false');
    await waitFor(() => {
      expect(screen.getByTestId('current-search').textContent ?? '').not.toContain(
        'mode=drill',
      );
    });
  });

  it('#3980: mode switcher exposes segmented-button (role=group) not tablist', async () => {
    renderWithProviders(<TutorPage />, { initialEntries: ['/tutor'] });
    await screen.findByRole('group', { name: /Choose a tutor mode/i });
    expect(screen.queryByRole('tablist', { name: /Choose a tutor mode/i })).toBeNull();
  });

  it('#4022: drill child selector renders overdue count badges from useChildOverdueCounts', async () => {
    // Return an overdue count of 3 for Kid A (student_id 77).
    mockUseChildOverdueCounts.mockReturnValue(new Map([[77, 3]]));

    renderWithProviders(<TutorPage />, { initialEntries: ['/tutor?mode=drill'] });

    // The hook is invoked with drill+parent gating enabled.
    await waitFor(() => {
      expect(mockUseChildOverdueCounts).toHaveBeenCalledWith({ enabled: true });
    });

    // Kid A's tab must expose an overdue badge labelled "3 overdue".
    await screen.findByRole('tab', { name: /Kid A/i });
    const overdueBadge = await screen.findByLabelText(/3 overdue/i);
    expect(overdueBadge).toHaveTextContent('3');
  });
});

// ── Hero XpStreakBadge wiring (#4019) ─────────────────────────
describe('TutorPage — hero XpStreakBadge (#4019)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuthUser.current = { role: 'student', roles: ['student'] };
    mockGetActiveSessions.mockResolvedValue({ sessions: [] });
    mockGetContextData.mockResolvedValue({ children: [], courses: [], upcoming_tasks: [] });
    mockIleGetTopics.mockResolvedValue([]);
    mockParentGetChildren.mockResolvedValue([]);
  });

  it('renders the XP badge when xp_total > 0', async () => {
    mockApiGet.mockImplementation((url: string) => {
      if (url === '/api/xp/summary') {
        return Promise.resolve({ data: { xp_total: 125, streak_days: 3 } });
      }
      return Promise.reject(new Error(`Unexpected api.get: ${url}`));
    });
    renderWithProviders(<TutorPage />, { initialEntries: ['/tutor'] });

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith('/api/xp/summary');
    });
    await waitFor(() => {
      expect(screen.getByText('125')).toBeInTheDocument();
    });
    expect(screen.getByText('XP')).toBeInTheDocument();
  });

  it('hides the XP badge for brand-new users (xp_total=0 AND streak_days<2)', async () => {
    mockApiGet.mockImplementation((url: string) => {
      if (url === '/api/xp/summary') {
        return Promise.resolve({ data: { xp_total: 0, streak_days: 0 } });
      }
      return Promise.reject(new Error(`Unexpected api.get: ${url}`));
    });
    renderWithProviders(<TutorPage />, { initialEntries: ['/tutor'] });

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith('/api/xp/summary');
    });
    // "XP" label must not render when the badge is hidden.
    expect(screen.queryByText('XP')).not.toBeInTheDocument();
  });

  it('renders the XP badge when streak_days >= 2 even if xp_total=0', async () => {
    // Defensive edge case: streak kept alive via non-XP actions.
    mockApiGet.mockImplementation((url: string) => {
      if (url === '/api/xp/summary') {
        return Promise.resolve({ data: { xp_total: 0, streak_days: 2 } });
      }
      return Promise.reject(new Error(`Unexpected api.get: ${url}`));
    });
    renderWithProviders(<TutorPage />, { initialEntries: ['/tutor'] });

    await waitFor(() => {
      expect(screen.getByText('XP')).toBeInTheDocument();
    });
  });
});

// ── #4095 Phase 1.1 hotfixes — mode-toggle state persistence + carry-topic ──
describe('TutorPage — #4095 mode-toggle integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuthUser.current = { role: 'student', roles: ['student'] };
    mockGetActiveSessions.mockResolvedValue({ sessions: [] });
    mockGetContextData.mockResolvedValue({ children: [], courses: [], upcoming_tasks: [] });
    mockIleGetTopics.mockResolvedValue([]);
    mockParentGetChildren.mockResolvedValue([]);
    mockUseChildOverdueCounts.mockReturnValue(new Map());
    mockApiGet.mockImplementation((url: string) => {
      if (url === '/api/xp/summary') {
        return Promise.resolve({ data: { xp_total: 0, streak_days: 0 } });
      }
      return Promise.reject(new Error(`Unexpected api.get: ${url}`));
    });
    // Flip tutor_chat_enabled ON so <TutorChat /> mounts.
    mockUseFeatureFlagEnabled.mockImplementation(
      (key: string) => key === 'tutor_chat_enabled',
    );
  });

  function makeSSEStream(lines: string[]): ReadableStream<Uint8Array> {
    const encoder = new TextEncoder();
    return new ReadableStream({
      start(controller) {
        for (const line of lines) controller.enqueue(encoder.encode(line));
        controller.close();
      },
    });
  }

  it('Bug 2 — chat messages survive Explain → Drill → Explain toggle', async () => {
    // Mock the /api/tutor/chat/stream fetch so sendMessage resolves.
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"Sure thing."}\n\n',
        'data: {"type":"done","conversation_id":"conv-xyz"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);
    localStorage.setItem('token', 'test-token');

    try {
      const user = userEvent.setup();
      renderWithProviders(<TutorPage />, { initialEntries: ['/tutor'] });

      // Type in the chat input and hit Enter.
      const chatInput = await screen.findByRole('textbox', { name: /message arc/i });
      await act(async () => {
        await user.type(chatInput, 'How do fractions work?{Enter}');
      });

      // User bubble shows the message.
      await waitFor(() => {
        expect(screen.getByText('How do fractions work?')).toBeInTheDocument();
      });

      // Switch to drill mode.
      const drillTab = screen.getByRole('button', { name: /Drill a topic/i });
      await act(async () => {
        await user.click(drillTab);
      });
      await waitFor(() => {
        expect(drillTab).toHaveAttribute('aria-pressed', 'true');
      });

      // Switch back to explain mode.
      const explainTab = screen.getByRole('button', { name: /Explain & learn/i });
      await act(async () => {
        await user.click(explainTab);
      });
      await waitFor(() => {
        expect(explainTab).toHaveAttribute('aria-pressed', 'true');
      });

      // The original user message must still be on screen — state survived
      // the toggle because <TutorChat> is display:none hidden (still mounted).
      expect(screen.getByText('How do fractions work?')).toBeInTheDocument();
    } finally {
      vi.unstubAllGlobals();
      localStorage.removeItem('token');
    }
  });

  it('Bug 4 — switching Explain → Drill pre-fills custom-topic with last user msg', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"ok"}\n\n',
        'data: {"type":"done","conversation_id":"conv-1"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);
    localStorage.setItem('token', 'test-token');

    try {
      const user = userEvent.setup();
      renderWithProviders(<TutorPage />, { initialEntries: ['/tutor'] });

      const chatInput = await screen.findByRole('textbox', { name: /message arc/i });
      await act(async () => {
        await user.type(chatInput, 'Explain photosynthesis{Enter}');
      });
      await waitFor(() => {
        expect(screen.getByText('Explain photosynthesis')).toBeInTheDocument();
      });

      // Flip to drill mode — the custom-topic toggle should auto-open and
      // be pre-populated with the last user message.
      const drillTab = screen.getByRole('button', { name: /Drill a topic/i });
      await act(async () => {
        await user.click(drillTab);
      });

      // Custom topic input shows the pre-filled value (truncated to 200 chars;
      // our message is well under).
      const topicInput = await screen.findByPlaceholderText(/Topic \(e\.g\./i);
      expect(topicInput).toHaveValue('Explain photosynthesis');
    } finally {
      vi.unstubAllGlobals();
      localStorage.removeItem('token');
    }
  });
});
