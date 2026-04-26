/**
 * CB-DCI-001 M0-13 (#4260) — consent redirect tests.
 *
 * Three locked-down behaviours from the issue acceptance criteria:
 *   1. /parent/today and /checkin redirect to /dci/consent when the
 *      consent row is missing (404) or AI processing is off.
 *   2. No redirect fires when consent is present (ai_ok = true).
 *   3. ConsentScreen honours ?return_to= and bounces back after the parent
 *      saves consent.
 *
 * The consent endpoint is parent-only — for the kid /checkin scenario the
 * hook will surface an error which still triggers the redirect (which is
 * the issue's defined behaviour: stop the flow, hand off to /dci/consent).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import type { ReactElement } from 'react';

import { ThemeProvider } from '../../../context/ThemeContext';
import { FABProvider } from '../../../context/FABContext';
import { ToastProvider } from '../../../components/Toast';

// ── Mocks ────────────────────────────────────────────────────────────────
const mockGetChildren = vi.fn();
const mockGetSummary = vi.fn();
const mockSubmitFeedback = vi.fn();
const mockGetConsent = vi.fn();
const mockUpsertConsent = vi.fn();
const mockGetStreak = vi.fn();

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

vi.mock('../../../api/dciConsent', () => ({
  dciConsentApi: {
    list: vi.fn(),
    get: (kidId: number) => mockGetConsent(kidId),
    upsert: (update: unknown) => mockUpsertConsent(update),
  },
}));

vi.mock('../../../api/dci', () => ({
  dciApi: {
    submitCheckin: vi.fn(),
    getStatus: vi.fn(),
    correct: vi.fn(),
    getStreak: (...args: unknown[]) => mockGetStreak(...args),
  },
}));

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 42,
      full_name: 'Haashini Sharma',
      role: 'student',
      roles: ['student'],
    },
    logout: vi.fn(),
  }),
}));

// Stub heavy chrome — keeps the redirect-under-test the only assertion.
vi.mock('../../../components/DashboardLayout', () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));
vi.mock('../../../components/ChildSelectorTabs', () => ({
  ChildSelectorTabs: () => <div data-testid="child-tabs" />,
}));
vi.mock('../../../utils/dciTelemetry', () => ({
  trackDciTelemetry: vi.fn(),
}));

// Lazy import after mocks so the page modules pick up the mocked deps.
import { EveningSummaryPage } from '../EveningSummaryPage';
import { CheckInIntroPage } from '../CheckInIntroPage';
import { ConsentScreen } from '../ConsentScreen';

// ── Helpers ──────────────────────────────────────────────────────────────
function LocationProbe() {
  const location = useLocation();
  return (
    <div
      data-testid="location-probe"
      data-pathname={location.pathname}
      data-search={location.search}
    />
  );
}

function renderRoutes(ui: ReactElement, initialEntries: string[]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const Wrapper = () => (
    <ThemeProvider>
      <FABProvider>
        <ToastProvider>
          <QueryClientProvider client={queryClient}>
            <MemoryRouter initialEntries={initialEntries}>
              <Routes>
                <Route path="/parent/today" element={ui} />
                <Route path="/checkin" element={ui} />
                <Route path="/dci/consent" element={<ConsentScreen />} />
                <Route
                  path="/"
                  element={<div data-testid="home">home</div>}
                />
              </Routes>
              <LocationProbe />
            </MemoryRouter>
          </QueryClientProvider>
        </ToastProvider>
      </FABProvider>
    </ThemeProvider>
  );
  return render(<Wrapper />);
}

const baseChild = {
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
  invite_status: 'active' as const,
  invite_id: null,
};

const baseConsent = {
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
};

beforeEach(() => {
  vi.clearAllMocks();
  mockGetChildren.mockResolvedValue([baseChild]);
  mockGetSummary.mockResolvedValue({ summary: null, state: 'no_checkin_today' });
  mockGetStreak.mockResolvedValue({
    kid_id: 42,
    current_streak: 0,
    longest_streak: 0,
    last_checkin_date: null,
    last_voice_sentiment: null,
  });
});

// ── Tests ────────────────────────────────────────────────────────────────
describe('CB-DCI-001 M0-13 — consent redirect (#4260)', () => {
  it('redirects /parent/today to /dci/consent when consent is missing (404)', async () => {
    mockGetConsent.mockRejectedValue(
      Object.assign(new Error('not found'), { response: { status: 404 } }),
    );

    renderRoutes(<EveningSummaryPage />, ['/parent/today']);

    await waitFor(() => {
      const probe = screen.getByTestId('location-probe');
      expect(probe.getAttribute('data-pathname')).toBe('/dci/consent');
      expect(probe.getAttribute('data-search')).toContain(
        'return_to=%2Fparent%2Ftoday',
      );
    });
  });

  it('does NOT redirect when consent is present (ai_ok = true)', async () => {
    mockGetConsent.mockResolvedValue({ ...baseConsent, ai_ok: true });

    renderRoutes(<EveningSummaryPage />, ['/parent/today']);

    // Wait for the children + consent + summary queries to settle, then
    // assert the path stayed on /parent/today.
    await waitFor(() => {
      expect(mockGetSummary).toHaveBeenCalled();
    });
    expect(screen.getByTestId('location-probe').getAttribute('data-pathname')).toBe(
      '/parent/today',
    );
  });

  it('redirects /checkin to /dci/consent when ai_ok is false', async () => {
    mockGetConsent.mockResolvedValue({ ...baseConsent, ai_ok: false });

    renderRoutes(<CheckInIntroPage />, ['/checkin']);

    await waitFor(() => {
      const probe = screen.getByTestId('location-probe');
      expect(probe.getAttribute('data-pathname')).toBe('/dci/consent');
      expect(probe.getAttribute('data-search')).toContain(
        'return_to=%2Fcheckin',
      );
    });
  });

  it('honours ?return_to= and navigates back after a successful save', async () => {
    // Initial GET returns ai_ok=false so the editor shows. Upsert succeeds
    // and ConsentScreen should navigate back to the supplied return_to.
    mockGetConsent.mockResolvedValue({ ...baseConsent, ai_ok: false });
    mockUpsertConsent.mockResolvedValue({ ...baseConsent, ai_ok: true });

    renderRoutes(
      <div data-testid="never-rendered" />,
      ['/dci/consent?return_to=%2Fparent%2Ftoday'],
    );

    const user = userEvent.setup();
    // Ensure ai_ok is checked, then save.
    const aiToggle = await screen.findByLabelText(/AI processing OK/);
    if (!(aiToggle as HTMLInputElement).checked) {
      await user.click(aiToggle);
    }
    await user.click(screen.getByTestId('dci-consent-save'));

    await waitFor(() => {
      expect(mockUpsertConsent).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(
        screen.getByTestId('location-probe').getAttribute('data-pathname'),
      ).toBe('/parent/today');
    });
  });
});
