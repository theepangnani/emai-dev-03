import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../../test/helpers';
import { ToastProvider } from '../../../components/Toast';
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

// #4268: EveningSummaryPage now gates the summary fetch on consent being
// present. Default to ai_ok=true so existing tests still see the summary;
// the redirect-bound tests live in ConsentRedirect / ConsentGating files.
const mockGetConsent = vi.fn();
vi.mock('../../../api/dciConsent', () => ({
  dciConsentApi: {
    list: vi.fn(),
    get: (kidId: number) => mockGetConsent(kidId),
    upsert: vi.fn(),
  },
}));

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

/**
 * Render the page wrapped in ToastProvider — the conversation-starter
 * feedback hook calls `useToast()` for the S-6 (#4219) error toast.
 */
function renderPage() {
  return renderWithProviders(
    <ToastProvider>
      <EveningSummaryPage />
    </ToastProvider>,
  );
}

// ── Tests ────────────────────────────────────────────────────────────────
describe('EveningSummaryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetChildren.mockResolvedValue([buildChild()]);
    // Default: consent present + ai_ok so the summary fetch is unblocked.
    mockGetConsent.mockResolvedValue({
      parent_id: 1,
      kid_id: 42,
      photo_ok: true,
      voice_ok: true,
      ai_ok: true,
      retention_days: 90,
      dci_enabled: true,
      muted: false,
      kid_push_time: '15:15',
      parent_push_time: '19:00',
      allowed_retention_days: [90, 365, 1095],
    });
  });

  it('renders shimmer while loading the summary', async () => {
    // Hold the promise open so the loading state stays visible long enough
    // for the assertion. The children fetch resolves immediately; only the
    // summary fetch is held.
    mockGetSummary.mockReturnValue(new Promise<DciSummaryResponse>(() => {}));

    renderPage();

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

    renderPage();

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

    renderPage();

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

    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText(/We're learning about your kid/),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/Check back in 30 days/)).toBeInTheDocument();
  });

  it('shows the empty "no kids linked" state when the parent has no children', async () => {
    mockGetChildren.mockResolvedValue([]);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/No kids linked yet/)).toBeInTheDocument();
    });
    // Summary endpoint must not have been called when there are no kids.
    expect(mockGetSummary).not.toHaveBeenCalled();
  });

  it('shows a distinct error state when getChildren fails', async () => {
    mockGetChildren.mockRejectedValue(new Error('network'));

    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText(/We couldn't load your kids/),
      ).toBeInTheDocument();
    });
    // Should NOT show the "no kids linked" copy — that's misleading on a
    // network failure.
    expect(screen.queryByText(/No kids linked yet/)).not.toBeInTheDocument();
    expect(mockGetSummary).not.toHaveBeenCalled();
  });

  // S-7 (#4220): the children-load error state offers a Retry button that
  // re-runs the children query without forcing a page reload.
  it('shows a Retry button on the children-load error state and re-runs getChildren on click', async () => {
    mockGetChildren.mockRejectedValueOnce(new Error('network'));

    renderPage();

    const retryBtn = await screen.findByRole('button', { name: /retry/i });
    expect(mockGetChildren).toHaveBeenCalledTimes(1);

    // Make the next call succeed so we can verify it's actually invoked.
    mockGetChildren.mockResolvedValueOnce([buildChild()]);
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(mockGetChildren).toHaveBeenCalledTimes(2);
    });
  });

  // S-5 (#4218): clicking "I used this" while the starter is already
  // marked as used must send the explicit `'undo_used'` feedback so the
  // backend can clear `was_used`.
  it('sends undo_used feedback when toggling an already-used starter off', async () => {
    const summary = buildSummary({
      conversation_starter: {
        id: 11,
        text: 'What surprised you in science today?',
        was_used: true,
      },
    });
    mockGetSummary.mockResolvedValue({
      summary,
      state: 'ready',
    } satisfies DciSummaryResponse);
    mockSubmitFeedback.mockResolvedValue({ starter: summary.conversation_starter });

    renderPage();

    const usedBtn = await screen.findByRole('button', { name: /I used this/i });
    fireEvent.click(usedBtn);

    await waitFor(() => {
      expect(mockSubmitFeedback).toHaveBeenCalledWith(11, 'undo_used');
    });
  });

  // S-5 (#4218) — companion: clicking "I used this" while NOT yet used
  // still sends `'thumbs_up'`. Locks down the chosen toggle semantics.
  it('sends thumbs_up feedback when toggling a not-yet-used starter on', async () => {
    const summary = buildSummary();
    mockGetSummary.mockResolvedValue({
      summary,
      state: 'ready',
    } satisfies DciSummaryResponse);
    mockSubmitFeedback.mockResolvedValue({ starter: summary.conversation_starter });

    renderPage();

    const usedBtn = await screen.findByRole('button', { name: /I used this/i });
    fireEvent.click(usedBtn);

    await waitFor(() => {
      expect(mockSubmitFeedback).toHaveBeenCalledWith(11, 'thumbs_up');
    });
  });

  // S-6 (#4219): on feedback failure, the page surfaces an inline Retry
  // affordance that re-runs the same mutation.
  it('surfaces an inline Retry on feedback failure and re-fires the mutation when clicked', async () => {
    const summary = buildSummary();
    mockGetSummary.mockResolvedValue({
      summary,
      state: 'ready',
    } satisfies DciSummaryResponse);
    mockSubmitFeedback.mockRejectedValueOnce(new Error('network'));

    renderPage();

    const usedBtn = await screen.findByRole('button', { name: /I used this/i });
    fireEvent.click(usedBtn);

    // First call fails — Retry should appear.
    const retryBtn = await screen.findByRole('button', { name: /^retry$/i });
    expect(retryBtn).toBeInTheDocument();

    // Re-fire — make the second attempt succeed.
    mockSubmitFeedback.mockResolvedValueOnce({ starter: summary.conversation_starter });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(mockSubmitFeedback).toHaveBeenCalledTimes(2);
    });
  });

  // S-1 (#4214): due_date is now exposed via a <time> element so screen
  // readers and tooltips can read the actual date.
  it('renders the deadline due_date as a <time> element', async () => {
    mockGetSummary.mockResolvedValue({
      summary: buildSummary(),
      state: 'ready',
    } satisfies DciSummaryResponse);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Math quiz Friday')).toBeInTheDocument();
    });
    // At least one <time dateTime="..."> should render with the ISO date.
    const times = document.querySelectorAll('time[datetime]');
    const dateTimes = Array.from(times).map((t) => t.getAttribute('datetime'));
    expect(dateTimes).toContain('2026-04-28');
    expect(dateTimes).toContain('2026-04-22');
  });
});
