/**
 * CB-DCI-001 fast-follows (#4268, #4269) — additional gating + timing tests.
 *
 * #4268: useDciSummary must NOT fire when consent is missing/absent —
 *        otherwise we waste one backend cycle on every redirect-bound
 *        /parent/today visit.
 * #4269: ConsentScreen Saved-flash must remain visible for ≥400ms before
 *        the host's auto-navigate fires.
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

import { EveningSummaryPage } from '../EveningSummaryPage';
import { ConsentScreen } from '../ConsentScreen';

function LocationProbe() {
  const location = useLocation();
  return (
    <div
      data-testid="location-probe"
      data-pathname={location.pathname}
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
                <Route path="/dci/consent" element={<ConsentScreen />} />
                <Route path="/" element={<div data-testid="home">home</div>} />
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
});

describe('useDciSummary consent gate (#4268)', () => {
  it('does NOT call the summary endpoint when consent is missing (404)', async () => {
    mockGetConsent.mockRejectedValue(
      Object.assign(new Error('not found'), { response: { status: 404 } }),
    );

    renderRoutes(<EveningSummaryPage />, ['/parent/today']);

    // Wait for the redirect to /dci/consent to fire, then assert summary
    // was never called.
    await waitFor(() => {
      expect(
        screen.getByTestId('location-probe').getAttribute('data-pathname'),
      ).toBe('/dci/consent');
    });
    expect(mockGetSummary).not.toHaveBeenCalled();
  });

  it('does NOT call the summary endpoint when ai_ok is false', async () => {
    mockGetConsent.mockResolvedValue({ ...baseConsent, ai_ok: false });

    renderRoutes(<EveningSummaryPage />, ['/parent/today']);

    await waitFor(() => {
      expect(
        screen.getByTestId('location-probe').getAttribute('data-pathname'),
      ).toBe('/dci/consent');
    });
    expect(mockGetSummary).not.toHaveBeenCalled();
  });

  it('DOES call the summary endpoint when consent is present', async () => {
    mockGetConsent.mockResolvedValue({ ...baseConsent, ai_ok: true });

    renderRoutes(<EveningSummaryPage />, ['/parent/today']);

    await waitFor(() => {
      expect(mockGetSummary).toHaveBeenCalled();
    });
  });
});

describe('ConsentScreen saved-flash timing (#4269)', () => {
  it('keeps the Saved status visible for at least 400ms before navigating', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      mockGetConsent.mockResolvedValue({ ...baseConsent, ai_ok: false });
      mockUpsertConsent.mockResolvedValue({ ...baseConsent, ai_ok: true });

      renderRoutes(
        <div data-testid="never-rendered" />,
        ['/dci/consent?return_to=%2Fparent%2Ftoday'],
      );

      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      const aiToggle = await screen.findByLabelText(/AI processing OK/);
      if (!(aiToggle as HTMLInputElement).checked) {
        await user.click(aiToggle);
      }
      await user.click(screen.getByTestId('dci-consent-save'));

      // After save resolves the green Saved flash should appear.
      await screen.findByTestId('dci-consent-saved');

      // The location should NOT have changed yet — the host's auto-navigate
      // is deferred so the parent can read the flash.
      expect(
        screen.getByTestId('location-probe').getAttribute('data-pathname'),
      ).toBe('/dci/consent');

      // After the timer fires, navigate happens.
      vi.advanceTimersByTime(700);
      await waitFor(() => {
        expect(
          screen.getByTestId('location-probe').getAttribute('data-pathname'),
        ).toBe('/parent/today');
      });
    } finally {
      vi.useRealTimers();
    }
  });

  // #4282: regression guard — if a future refactor removes the navTimerRef
  // unmount cleanup, the deferred navigate would still fire after the
  // component is gone. We spy on window.setTimeout/clearTimeout to
  // positively assert the cleanup ran with the timer id ConsentScreen
  // armed for its 600ms post-save bounce. (A pure "no route change after
  // unmount" check would silently pass even if cleanup were removed,
  // because the MemoryRouter is gone too.)
  it('cancels the pending navigate timer when the screen unmounts mid-flash', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const setTimeoutSpy = vi.spyOn(window, 'setTimeout');
    const clearTimeoutSpy = vi.spyOn(window, 'clearTimeout');
    try {
      mockGetConsent.mockResolvedValue({ ...baseConsent, ai_ok: false });
      mockUpsertConsent.mockResolvedValue({ ...baseConsent, ai_ok: true });

      const { unmount } = renderRoutes(
        <div data-testid="never-rendered" />,
        ['/dci/consent?return_to=%2Fparent%2Ftoday'],
      );

      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      const aiToggle = await screen.findByLabelText(/AI processing OK/);
      if (!(aiToggle as HTMLInputElement).checked) {
        await user.click(aiToggle);
      }
      await user.click(screen.getByTestId('dci-consent-save'));

      // Saved flash appears — ConsentScreen has now armed the 600ms timer.
      await screen.findByTestId('dci-consent-saved');

      // Find the post-save bounce timer (the only 600ms setTimeout call
      // ConsentScreen makes in this flow). React-internal timers use
      // different delays, so this filter reliably picks ours.
      const bounceCalls = setTimeoutSpy.mock.results.filter(
        (_, idx) => setTimeoutSpy.mock.calls[idx][1] === 600,
      );
      expect(bounceCalls).toHaveLength(1);
      const bounceTimerId = bounceCalls[0].value as number;

      // Unmount BEFORE the 600ms timer fires (parent taps Cancel, route
      // swap, modal close, etc.). Cleanup must call clearTimeout with
      // the id the component armed — that's the contract this test guards.
      clearTimeoutSpy.mockClear();
      unmount();

      expect(clearTimeoutSpy).toHaveBeenCalledWith(bounceTimerId);

      // Sanity: advancing past the window does not produce a late
      // navigate (the route never swaps to the return_to path).
      vi.advanceTimersByTime(700);
      expect(screen.queryByTestId('home')).not.toBeInTheDocument();
    } finally {
      setTimeoutSpy.mockRestore();
      clearTimeoutSpy.mockRestore();
      vi.useRealTimers();
    }
  });

  it('disables the save button after a successful save (no double-tap)', async () => {
    mockGetConsent.mockResolvedValue({ ...baseConsent, ai_ok: false });
    mockUpsertConsent.mockResolvedValue({ ...baseConsent, ai_ok: true });

    renderRoutes(
      <div data-testid="never-rendered" />,
      ['/dci/consent?return_to=%2Fparent%2Ftoday'],
    );

    const user = userEvent.setup();

    const aiToggle = await screen.findByLabelText(/AI processing OK/);
    if (!(aiToggle as HTMLInputElement).checked) {
      await user.click(aiToggle);
    }
    const saveBtn = screen.getByTestId('dci-consent-save');
    await user.click(saveBtn);

    await screen.findByTestId('dci-consent-saved');

    // Save button is now disabled — protects against double-tap during the
    // saved-flash delay window.
    expect(saveBtn).toBeDisabled();
  });
});
