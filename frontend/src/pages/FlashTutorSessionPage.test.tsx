/**
 * Regression tests for #4020 — render true_false and fill_blank
 * quiz question types in the Flash Tutor session runner.
 * Regression tests for #4037 — T/F + MCQ auto-submit parity.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders } from '../test/helpers';
import { FlashTutorSessionPage } from './FlashTutorSessionPage';

// ── Mocks ──────────────────────────────────────────────────────
const mockGetSession = vi.fn();
const mockGetCurrentQuestion = vi.fn();
const mockSubmitAnswer = vi.fn();
const mockCompleteSession = vi.fn();
const mockGetSessionResults = vi.fn();
const mockAbandonSession = vi.fn();
const mockGetCareerConnect = vi.fn();

// Per-test-scoped useParams — set id inside each test's beforeEach
// to prevent cross-test leakage of the id value.
const mockUseParams = vi.fn<[], { id?: string }>(() => ({ id: '42' }));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useParams: () => mockUseParams(),
  };
});

vi.mock('../api/ile', () => ({
  ileApi: {
    getSession: (...args: unknown[]) => mockGetSession(...args),
    getCurrentQuestion: (...args: unknown[]) => mockGetCurrentQuestion(...args),
    submitAnswer: (...args: unknown[]) => mockSubmitAnswer(...args),
    completeSession: (...args: unknown[]) => mockCompleteSession(...args),
    getSessionResults: (...args: unknown[]) => mockGetSessionResults(...args),
    abandonSession: (...args: unknown[]) => mockAbandonSession(...args),
    getCareerConnect: (...args: unknown[]) => mockGetCareerConnect(...args),
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

vi.mock('../components/ile/CareerConnectCard', () => ({
  CareerConnectCard: () => <div data-testid="career-connect" />,
}));

vi.mock('../components/ile/AhaMomentCelebration', () => ({
  AhaMomentCelebration: () => <div data-testid="aha-moment" />,
}));

// ── Fixtures ───────────────────────────────────────────────────
const baseSession = {
  id: 42,
  student_id: 1,
  parent_id: null,
  mode: 'learning',
  subject: 'Math',
  topic: 'Fractions',
  grade_level: 5,
  question_count: 5,
  difficulty: 'easy',
  blooms_tier: 'recall',
  timer_enabled: false,
  timer_seconds: null,
  is_private_practice: false,
  status: 'active',
  current_question_index: 0,
  score: null,
  total_correct: null,
  xp_awarded: null,
  started_at: '2026-04-23T12:00:00Z',
  completed_at: null,
  expires_at: null,
  course_id: null,
  course_content_id: null,
};

function makeQuestion(overrides: Record<string, unknown>) {
  return {
    session_id: 42,
    question: {
      index: 0,
      question: 'Is the sky blue?',
      options: null,
      format: 'true_false',
      difficulty: 'easy',
      blooms_tier: 'recall',
      ...overrides,
    },
    question_index: 0,
    total_questions: 5,
    mode: 'learning',
    attempt_number: 1,
    disabled_options: [],
    streak_count: 0,
  };
}

// ── Tests ──────────────────────────────────────────────────────
describe('FlashTutorSessionPage — #4020 true_false + fill_blank rendering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Each test sets its own id explicitly so future tests can't
    // silently inherit a value from prior tests (#4037 S5).
    mockUseParams.mockReturnValue({ id: '42' });
    mockGetSession.mockResolvedValue(baseSession);
    mockSubmitAnswer.mockResolvedValue({
      is_correct: true,
      attempt_number: 1,
      xp_earned: 10,
      hint: null,
      parent_hint_note: null,
      explanation: 'Correct!',
      correct_answer: 'True',
      question_complete: true,
      session_complete: false,
      streak_count: 1,
      streak_broken: false,
    });
  });

  it('true_false: renders 2 buttons and clicking True auto-submits "True"', async () => {
    mockUseParams.mockReturnValue({ id: '42' });
    mockGetCurrentQuestion.mockResolvedValue(
      makeQuestion({ question: 'The Earth orbits the Sun.', format: 'true_false' }),
    );

    renderWithProviders(<FlashTutorSessionPage />);

    // Wait for question to render
    await waitFor(() => {
      expect(screen.getByText('The Earth orbits the Sun.')).toBeInTheDocument();
    });

    // Exactly 2 radio buttons labelled True and False
    const trueBtn = screen.getByRole('radio', { name: 'True' });
    const falseBtn = screen.getByRole('radio', { name: 'False' });
    expect(trueBtn).toBeInTheDocument();
    expect(falseBtn).toBeInTheDocument();
    expect(screen.getByRole('radiogroup', { name: 'True or False' })).toBeInTheDocument();

    // No separate "Submit Answer" button — T/F auto-submits on click (#4037).
    expect(screen.queryByRole('button', { name: /submit answer/i })).toBeNull();

    // Click True → auto-submits "True" immediately
    const user = userEvent.setup();
    await user.click(trueBtn);

    await waitFor(() => {
      expect(mockSubmitAnswer).toHaveBeenCalled();
    });
    // Second positional arg is the answer string
    expect(mockSubmitAnswer.mock.calls[0][1]).toBe('True');
  });

  it('true_false: clicking False auto-submits "False" (#4037)', async () => {
    mockUseParams.mockReturnValue({ id: '99' });
    mockGetCurrentQuestion.mockResolvedValue(
      makeQuestion({ question: 'The sky is green.', format: 'true_false' }),
    );
    mockSubmitAnswer.mockResolvedValue({
      is_correct: true,
      attempt_number: 1,
      xp_earned: 10,
      hint: null,
      parent_hint_note: null,
      explanation: 'Correct!',
      correct_answer: 'False',
      question_complete: true,
      session_complete: false,
      streak_count: 1,
      streak_broken: false,
    });

    renderWithProviders(<FlashTutorSessionPage />);

    await waitFor(() => {
      expect(screen.getByText('The sky is green.')).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('radio', { name: 'False' }));

    await waitFor(() => {
      expect(mockSubmitAnswer).toHaveBeenCalled();
    });
    expect(mockSubmitAnswer.mock.calls[0][1]).toBe('False');
    // First positional arg is the session id → proves per-test useParams scope.
    expect(mockSubmitAnswer.mock.calls[0][0]).toBe(99);
  });

  it('mcq: clicking an option auto-submits the option key (#4037 parity)', async () => {
    mockUseParams.mockReturnValue({ id: '42' });
    mockGetCurrentQuestion.mockResolvedValue(
      makeQuestion({
        question: 'What is 2 + 2?',
        format: 'mcq',
        options: { A: '3', B: '4', C: '5', D: '6' },
      }),
    );
    mockSubmitAnswer.mockResolvedValue({
      is_correct: true,
      attempt_number: 1,
      xp_earned: 10,
      hint: null,
      parent_hint_note: null,
      explanation: 'Correct!',
      correct_answer: 'B',
      question_complete: true,
      session_complete: false,
      streak_count: 1,
      streak_broken: false,
    });

    renderWithProviders(<FlashTutorSessionPage />);

    await waitFor(() => {
      expect(screen.getByText('What is 2 + 2?')).toBeInTheDocument();
    });

    // No separate Submit button — MCQ auto-submits on click (#4037).
    expect(screen.queryByRole('button', { name: /submit answer/i })).toBeNull();

    const user = userEvent.setup();
    // Click the button containing option B → auto-submits "B"
    await user.click(screen.getByText('4').closest('button')!);

    await waitFor(() => {
      expect(mockSubmitAnswer).toHaveBeenCalled();
    });
    expect(mockSubmitAnswer.mock.calls[0][1]).toBe('B');
  });

  it('fill_blank: renders text input and typing + submit sends raw text', async () => {
    mockUseParams.mockReturnValue({ id: '42' });
    mockGetCurrentQuestion.mockResolvedValue(
      makeQuestion({
        question: 'The capital of France is ____.',
        format: 'fill_blank',
      }),
    );
    mockSubmitAnswer.mockResolvedValue({
      is_correct: true,
      attempt_number: 1,
      xp_earned: 15,
      hint: null,
      parent_hint_note: null,
      explanation: 'Correct!',
      correct_answer: 'Paris',
      question_complete: true,
      session_complete: false,
      streak_count: 1,
      streak_broken: false,
    });

    renderWithProviders(<FlashTutorSessionPage />);

    await waitFor(() => {
      expect(screen.getByText('The capital of France is ____.')).toBeInTheDocument();
    });

    const input = screen.getByLabelText(/your answer/i);
    expect(input).toBeInTheDocument();

    const user = userEvent.setup();
    await user.type(input, 'Paris');
    await user.click(screen.getByRole('button', { name: /submit answer/i }));

    await waitFor(() => {
      expect(mockSubmitAnswer).toHaveBeenCalled();
    });
    expect(mockSubmitAnswer.mock.calls[0][1]).toBe('Paris');
  });
});
