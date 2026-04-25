import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../../test/helpers';
import { EveningSummaryPage } from '../EveningSummaryPage';
import type {
  DciSummaryResponse,
  DciDailySummary,
} from '../../../api/dciSummary';
import type { ChildSummary } from '../../../api/parent';

// ── Mocks ────────────────────────────────────────────────────────────────
const mockGetSummary = vi.fn();
const mockSubmitFeedback = vi.fn();

vi.mock('../../../api/dciSummary', async () => {
  const actual = await vi.importActual<typeof import('../../../api/dciSummary')>(
    '../../../api/dciSummary',
  );
  return {
    ...actual,
    dciSummaryApi: {
      getSummary: (...args: unknown[]) => mockGetSummary(...args),
      submitStarterFeedback: (...args: unknown[]) => mockSubmitFeedback(...args),
    },
  };
});

const mockGetChildren = vi.fn();
vi.mock('../../../api/parent', async () => {
  const actual = await vi.importActual<typeof import('../../../api/parent')>(
    '../../../api/parent',
  );
  return {
    ...actual,
    parentApi: {
      ...actual.parentApi,
      getChildren: (...args: unknown[]) => mockGetChildren(...args),
    },
  };
});

// Stub DashboardLayout and ChildSelectorTabs to keep test focused on the
// page body — both are exercised by their own dedicated tests.
vi.mock('../../../components/DashboardLayout', () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

vi.mock('../../../components/ChildSelectorTabs', () => ({
  ChildSelectorTabs: () => <div data-testid="child-tabs" />,
}));

// Telemetry helper — verify it's called but stub side effects
const mockTrack = vi.fn();
vi.mock('../../../utils/dciTelemetry', () => ({
  trackDciTelemetry: (...args: unknown[]) => mockTrack(...args),
}));

// ── Fixtures ─────────────────────────────────────────────────────────────
function buildChild(overrides: Partial<ChildSummary> = {}): ChildSummary {
  return {
    student_id: 42,
    user_id: 100,
    full_name: 'Haashini Doe',
    email: 'haashini@example.com',
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
    invite_status: 'active',
    invite_id: null,
    ...overrides,
  };
}

function buildSummary(overrides: Partial<DciDailySummary> = {}): DciDailySummary {
  return {
    id: 7,
    kid_id: 42,
    kid_name: 'Haashini',
    summary_date: '2026-04-25',
    bullets: [
      { subject: 'Math', text: 'Multi-digit multiplication; mastered carrying.' },
      { subject: 'Science', text: 'Matter states — solid → liquid → gas demo.' },
      { subject: 'Reading', text: 'Charlotte’s Web ch. 4; teacher praised inferences.' },
    ],
    upcoming: [
      {
        id: 1,
        label: 'Math quiz Friday',
        due_date: '2026-04-28',
        urgency: 'amber',
      },
      {
        id: 2,
        label: 'Science handout overdue',
        due_date: '2026-04-22',
        urgency: 'red',
        not_yet_on_classroom: true,
      },
    ],
    conversation_starter: {
      id: 11,
      text: 'What surprised you in science today?',
      was_used: false,
    },
    artifacts: [
      {
        id: 101,
        artifact_type: 'photo',
        preview: 'Math handout — long division',
      },
    ],
    generated_at: '2026-04-25T19:00:00Z',
    ...overrides,
  };
}

// ── Tests ────────────────────────────────────────────────────────────────
describe('EveningSummaryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetChildren.mockResolvedValue([buildChild()]);
  });

  it('renders shimmer while loading the summary', async () => {
    // Hold the promise open so the loading state stays visible long enough
    // for the assertion. The children fetch resolves immediately; only the
    // summary fetch is held.
    mockGetSummary.mockReturnValue(new Promise<DciSummaryResponse>(() => {}));

    renderWithProviders(<EveningSummaryPage />);

    await waitFor(() => {
      expect(
        screen.getByLabelText("Loading tonight's summary"),
      ).toBeInTheDocument();
    });
  });

  it('renders all three blocks: hero, conversation starter, artifact strip', async () => {
    const summary = buildSummary();
    mockGetSummary.mockResolvedValue({
      summary,
      state: 'ready',
    } satisfies DciSummaryResponse);

    renderWithProviders(<EveningSummaryPage />);

    // Block 1: EveningSummaryHero — kid name in the hero heading + each
    // subject bullet. Match the hero's <h2> by id rather than a loose text
    // match (kid name also appears in the pattern stub at the bottom).
    await waitFor(() => {
      const hero = screen.getByRole('heading', { level: 2 });
      expect(hero).toHaveTextContent(/Haashini/);
    });
    expect(screen.getByText('Math')).toBeInTheDocument();
    expect(screen.getByText('Science')).toBeInTheDocument();
    expect(screen.getByText('Reading')).toBeInTheDocument();
    expect(
      screen.getByText(/Multi-digit multiplication/),
    ).toBeInTheDocument();

    // Deadline chips — amber (≤7d) + red (overdue) + Not-yet-on-Classroom badge
    expect(screen.getByText('Math quiz Friday')).toBeInTheDocument();
    expect(screen.getByText('Science handout overdue')).toBeInTheDocument();
    expect(
      screen.getByText('Not yet on Google Classroom'),
    ).toBeInTheDocument();

    // Block 2: Conversation Starter card — italic text + buttons
    expect(
      screen.getByText('What surprised you in science today?'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /I used this/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Regenerate/i }),
    ).toBeInTheDocument();

    // Block 3: Artifact strip — tap-to-deep-dive button
    expect(
      screen.getByRole('button', {
        name: /Open photo artifact: Math handout — long division/,
      }),
    ).toBeInTheDocument();

    // Telemetry: summary_viewed fires once on first render of a real summary
    await waitFor(() => {
      expect(mockTrack).toHaveBeenCalledWith(
        'dci.parent.summary_viewed',
        expect.objectContaining({
          kid_id: 42,
          summary_id: 7,
        }),
      );
    });
  });

  it('renders the no-checkin-today empty state', async () => {
    mockGetSummary.mockResolvedValue({
      summary: null,
      state: 'no_checkin_today',
    } satisfies DciSummaryResponse);

    renderWithProviders(<EveningSummaryPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/hasn't checked in yet today/i),
      ).toBeInTheDocument();
    });
  });

  it('renders the first-30-days pattern stub state', async () => {
    mockGetSummary.mockResolvedValue({
      summary: null,
      state: 'first_30_days',
    } satisfies DciSummaryResponse);

    renderWithProviders(<EveningSummaryPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/We're learning about your kid/),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/Check back in 30 days/)).toBeInTheDocument();
  });

  it('shows the empty "no kids linked" state when the parent has no children', async () => {
    mockGetChildren.mockResolvedValue([]);

    renderWithProviders(<EveningSummaryPage />);

    await waitFor(() => {
      expect(screen.getByText(/No kids linked yet/)).toBeInTheDocument();
    });
    // Summary endpoint must not have been called when there are no kids.
    expect(mockGetSummary).not.toHaveBeenCalled();
  });
});
