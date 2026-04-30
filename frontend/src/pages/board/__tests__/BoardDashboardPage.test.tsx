/**
 * CB-CMCP-001 M3-H 3H-1 (#4663) — BoardDashboardPage tests.
 *
 * Coverage:
 *   - Renders the heatmap when the catalog API returns artifacts.
 *   - Empty board (no artifacts) → empty-state message inside the heatmap.
 *   - Feature flag OFF → disabled card (no API call).
 *   - User without a board scope (and not ADMIN) → "no board assigned" card.
 *   - Loading state surfaces while the query is pending.
 *   - Coverage map derivation parses SE codes correctly.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement, ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ── Mocks ──────────────────────────────────────────────────────────────

const mockGetCatalog = vi.fn();
vi.mock('../../../api/boardCatalog', () => ({
  boardCatalogApi: {
    getCatalog: (...args: unknown[]) => mockGetCatalog(...args),
  },
}));

const mockFlagState = vi.fn();
vi.mock('../../../hooks/useFeatureToggle', () => ({
  useFeatureFlagState: (key: string) => mockFlagState(key),
}));

const mockUseAuth = vi.fn();
vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

import { BoardDashboardPage } from '../BoardDashboardPage';
import { deriveCoverageMap } from '../deriveCoverageMap';
import type { BoardCatalogArtifact } from '../../../api/boardCatalog';

// ── Helpers ────────────────────────────────────────────────────────────

function renderPage(ui: ReactElement, initialPath = '/board/dashboard') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialPath]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  return render(ui, { wrapper: Wrapper });
}

const sampleArtifact = (
  id: number,
  seFirst: string,
  grade: number | null = null,
): BoardCatalogArtifact => ({
  id,
  title: `Artifact ${id}`,
  content_type: 'STUDY_GUIDE',
  state: 'APPROVED',
  subject_code: 'MATH',
  grade,
  se_codes: [seFirst, 'extra'],
  alignment_score: 0.9,
  ai_engine: 'gpt-4o-mini',
  course_id: 1,
  created_at: '2026-04-29T10:00:00Z',
});

const boardAdminUser = {
  id: 1,
  email: 'admin@board.test',
  full_name: 'Board Admin',
  role: 'BOARD_ADMIN',
  roles: ['BOARD_ADMIN'],
  is_active: true,
  google_connected: false,
  needs_onboarding: false,
  onboarding_completed: true,
  email_verified: true,
  interests: [],
  board_id: 'TDSB',
};

const adminUser = {
  ...boardAdminUser,
  email: 'admin@cb.test',
  role: 'admin',
  roles: ['admin'],
  board_id: null,
};

const userNoBoard = {
  ...boardAdminUser,
  email: 'orphan@board.test',
  role: 'BOARD_ADMIN',
  roles: ['BOARD_ADMIN'],
  board_id: null,
};

beforeEach(() => {
  mockGetCatalog.mockReset();
  mockFlagState.mockReset();
  mockUseAuth.mockReset();
  // Default: flag ON, BOARD_ADMIN user with TDSB board.
  mockFlagState.mockReturnValue({ enabled: true, isLoading: false });
  mockUseAuth.mockReturnValue({ user: boardAdminUser, isLoading: false });
});

// ── deriveCoverageMap unit ─────────────────────────────────────────────

describe('deriveCoverageMap', () => {
  it('builds the strand × grade map from artifacts', () => {
    const map = deriveCoverageMap([
      sampleArtifact(1, 'MATH.5.A.1'),
      sampleArtifact(2, 'MATH.5.A.2'),
      sampleArtifact(3, 'MATH.6.A.1'),
      sampleArtifact(4, 'MATH.5.B.1'),
    ]);
    expect(map).toEqual({
      A: { 5: 2, 6: 1 },
      B: { 5: 1 },
    });
  });

  it('skips artifacts with malformed or missing SE codes', () => {
    const map = deriveCoverageMap([
      sampleArtifact(1, 'MATH.5.A.1'),
      // Too few segments — skipped.
      { ...sampleArtifact(2, 'MATH.5'), se_codes: ['MATH.5'] },
      // Empty SE codes — skipped.
      { ...sampleArtifact(3, 'MATH.5.A.1'), se_codes: [] },
      // Non-int grade segment — skipped.
      { ...sampleArtifact(4, 'MATH.X.A.1'), se_codes: ['MATH.X.A.1'], grade: null },
    ]);
    expect(map).toEqual({ A: { 5: 1 } });
  });

  it('prefers the typed grade column over the SE-code grade segment', () => {
    // Backend sometimes carries `grade` as a typed column (3E-1 surfaces
    // it). When present, it's preferred over the parse — guards against
    // a missing/wrong segment in the SE code.
    const map = deriveCoverageMap([
      // SE code says grade 5, typed column says 7 — typed column wins.
      sampleArtifact(1, 'MATH.5.A.1', 7),
    ]);
    expect(map).toEqual({ A: { 7: 1 } });
  });
});

// ── BoardDashboardPage component ───────────────────────────────────────

describe('BoardDashboardPage', () => {
  it('renders the heatmap with mocked catalog data', async () => {
    mockGetCatalog.mockResolvedValueOnce({
      artifacts: [
        sampleArtifact(1, 'MATH.5.A.1'),
        sampleArtifact(2, 'MATH.5.A.2'),
        sampleArtifact(3, 'MATH.5.A.3'),
        sampleArtifact(4, 'MATH.5.A.4'),
        sampleArtifact(5, 'MATH.6.B.1'),
      ],
      next_cursor: null,
    });

    renderPage(<BoardDashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId('coverage-heatmap')).toBeInTheDocument();
    });

    // 4+ artifacts at (A, 5) → covered bucket.
    const cellA5 = screen.getByTestId('coverage-cell-A-5');
    expect(cellA5).toHaveAttribute('data-count', '4');
    expect(cellA5).toHaveAttribute('data-bucket', 'covered');

    // Single artifact at (B, 6) → sparse bucket.
    const cellB6 = screen.getByTestId('coverage-cell-B-6');
    expect(cellB6).toHaveAttribute('data-count', '1');
    expect(cellB6).toHaveAttribute('data-bucket', 'sparse');

    // Mock receives the resolved board id.
    expect(mockGetCatalog).toHaveBeenCalledWith('TDSB', { limit: 200 });
  });

  it('shows empty-state when the board has no artifacts', async () => {
    mockGetCatalog.mockResolvedValueOnce({
      artifacts: [],
      next_cursor: null,
    });

    renderPage(<BoardDashboardPage />);

    await waitFor(() => {
      expect(
        screen.getByTestId('coverage-heatmap-empty'),
      ).toBeInTheDocument();
    });
    expect(screen.getByText('No coverage yet')).toBeInTheDocument();
    expect(screen.queryByTestId('coverage-heatmap')).not.toBeInTheDocument();
  });

  it('renders disabled card when cmcp.enabled flag is OFF', () => {
    mockFlagState.mockReturnValue({ enabled: false, isLoading: false });

    renderPage(<BoardDashboardPage />);

    expect(
      screen.getByText(/Curriculum-mapped content is currently disabled/),
    ).toBeInTheDocument();
    expect(mockGetCatalog).not.toHaveBeenCalled();
  });

  it('shows "no board assigned" when BOARD_ADMIN has no board_id', () => {
    mockUseAuth.mockReturnValue({ user: userNoBoard, isLoading: false });

    renderPage(<BoardDashboardPage />);

    expect(screen.getByText(/No board assigned/)).toBeInTheDocument();
    expect(mockGetCatalog).not.toHaveBeenCalled();
  });

  it('lets ADMIN supply a board_id via ?board_id= query param', async () => {
    mockUseAuth.mockReturnValue({ user: adminUser, isLoading: false });
    mockGetCatalog.mockResolvedValueOnce({
      artifacts: [sampleArtifact(1, 'MATH.5.A.1')],
      next_cursor: null,
    });

    renderPage(
      <BoardDashboardPage />,
      '/board/dashboard?board_id=PDSB',
    );

    await waitFor(() => {
      expect(mockGetCatalog).toHaveBeenCalledWith('PDSB', { limit: 200 });
    });
  });

  it('shows admin board picker when ADMIN has no board_id and no query param', () => {
    mockUseAuth.mockReturnValue({ user: adminUser, isLoading: false });

    renderPage(<BoardDashboardPage />);

    expect(screen.getByText(/Pick a board to inspect/)).toBeInTheDocument();
    const input = screen.getByLabelText(/Board id:/) as HTMLInputElement;
    expect(input).toBeInTheDocument();
    expect(input.value).toBe('');
    // Submit button must exist so the picker isn't a per-keystroke firehose.
    expect(
      screen.getByRole('button', { name: /Inspect/ }),
    ).toBeInTheDocument();
    expect(mockGetCatalog).not.toHaveBeenCalled();
  });

  it('admin board picker does not call the API on every keystroke', async () => {
    mockUseAuth.mockReturnValue({ user: adminUser, isLoading: false });
    mockGetCatalog.mockResolvedValue({ artifacts: [], next_cursor: null });

    const user = userEvent.setup();
    renderPage(<BoardDashboardPage />);

    const input = screen.getByLabelText(/Board id:/);
    // Type a 4-letter board id — must NOT fire one call per keystroke.
    await user.type(input, 'TDSB');
    expect(mockGetCatalog).not.toHaveBeenCalled();

    // Pressing Enter (form submit) commits the value; query fires once.
    await user.keyboard('{Enter}');
    await waitFor(() => {
      expect(mockGetCatalog).toHaveBeenCalledWith('TDSB', { limit: 200 });
    });
    expect(mockGetCatalog).toHaveBeenCalledTimes(1);
  });

  it('shows loading state while the query is pending', () => {
    // Never resolve — stuck loading.
    mockGetCatalog.mockImplementation(() => new Promise(() => {}));

    renderPage(<BoardDashboardPage />);

    expect(
      screen.getByTestId('board-dashboard-loading'),
    ).toBeInTheDocument();
  });

  it('shows error card when the catalog request fails', async () => {
    mockGetCatalog.mockRejectedValueOnce(new Error('Network down'));

    renderPage(<BoardDashboardPage />);

    await waitFor(() => {
      expect(
        screen.getByTestId('board-dashboard-error'),
      ).toBeInTheDocument();
    });
    expect(screen.getByText('Network down')).toBeInTheDocument();
  });
});
