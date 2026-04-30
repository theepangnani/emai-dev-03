/**
 * CB-CMCP-001 M3-H 3H-2 (#4666) — BoardCatalogPage tests.
 *
 * Coverage:
 *   - Table renders with mocked artifact data.
 *   - Filter narrows results (re-issues GET with applied params).
 *   - Sorting toggles direction on header click.
 *   - "Export CSV" click triggers POST + opens download_url (window.open mock).
 *   - Pagination loads next page (cursor advances).
 *   - Feature flag OFF → disabled card (no API call).
 *   - User without a board scope (and not ADMIN) → "no board assigned" card.
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement, ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ── Mocks ──────────────────────────────────────────────────────────────

const mockGetCatalog = vi.fn();
const mockExportCatalogCsv = vi.fn();
vi.mock('../../../api/boardCatalog', () => ({
  boardCatalogApi: {
    getCatalog: (...args: unknown[]) => mockGetCatalog(...args),
    exportCatalogCsv: (...args: unknown[]) => mockExportCatalogCsv(...args),
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

import { BoardCatalogPage } from '../BoardCatalogPage';
import type { BoardCatalogArtifact } from '../../../api/boardCatalog';

// ── Helpers ────────────────────────────────────────────────────────────

function renderPage(ui: ReactElement, initialPath = '/board/catalog') {
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
  overrides: Partial<BoardCatalogArtifact> = {},
): BoardCatalogArtifact => ({
  id,
  title: `Artifact ${id}`,
  content_type: 'STUDY_GUIDE',
  state: 'APPROVED',
  subject_code: 'MATH',
  grade: 5,
  se_codes: ['MATH.5.A.1'],
  alignment_score: 0.9,
  ai_engine: 'gpt-4o-mini',
  course_id: 1,
  created_at: '2026-04-29T10:00:00Z',
  ...overrides,
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
  mockExportCatalogCsv.mockReset();
  mockFlagState.mockReset();
  mockUseAuth.mockReset();
  // Default: flag ON, BOARD_ADMIN user with TDSB board.
  mockFlagState.mockReturnValue({ enabled: true, isLoading: false });
  mockUseAuth.mockReturnValue({ user: boardAdminUser, isLoading: false });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── BoardCatalogPage component ─────────────────────────────────────────

describe('BoardCatalogPage', () => {
  it('renders the artifact table with mocked catalog data', async () => {
    mockGetCatalog.mockResolvedValueOnce({
      artifacts: [
        sampleArtifact(1, { title: 'Alpha guide' }),
        sampleArtifact(2, { title: 'Beta guide', subject_code: 'SCIE', grade: 6 }),
      ],
      next_cursor: null,
    });

    renderPage(<BoardCatalogPage />);

    await waitFor(() => {
      expect(screen.getByTestId('board-catalog-table')).toBeInTheDocument();
    });

    expect(screen.getByTestId('catalog-row-1')).toBeInTheDocument();
    expect(screen.getByTestId('catalog-row-2')).toBeInTheDocument();
    expect(screen.getByText('Alpha guide')).toBeInTheDocument();
    expect(screen.getByText('Beta guide')).toBeInTheDocument();

    // Initial fetch params: cursor=null, limit=50, no filters.
    expect(mockGetCatalog).toHaveBeenCalledWith('TDSB', {
      cursor: null,
      limit: 50,
      subject_code: null,
      grade: null,
      content_type: null,
    });
  });

  it('shows empty-state when the board has no artifacts', async () => {
    mockGetCatalog.mockResolvedValueOnce({
      artifacts: [],
      next_cursor: null,
    });

    renderPage(<BoardCatalogPage />);

    await waitFor(() => {
      expect(
        screen.getByTestId('board-catalog-empty'),
      ).toBeInTheDocument();
    });
    expect(screen.queryByTestId('board-catalog-table')).not.toBeInTheDocument();
  });

  it('applies filters and re-fetches with the typed values', async () => {
    mockGetCatalog
      .mockResolvedValueOnce({
        artifacts: [
          sampleArtifact(1),
          sampleArtifact(2, { subject_code: 'SCIE', grade: 6 }),
        ],
        next_cursor: null,
      })
      .mockResolvedValueOnce({
        artifacts: [sampleArtifact(2, { subject_code: 'SCIE', grade: 6 })],
        next_cursor: null,
      });

    const user = userEvent.setup();
    renderPage(<BoardCatalogPage />);

    await waitFor(() => {
      expect(screen.getByTestId('board-catalog-table')).toBeInTheDocument();
    });
    // Both rows present initially.
    expect(screen.getByTestId('catalog-row-1')).toBeInTheDocument();
    expect(screen.getByTestId('catalog-row-2')).toBeInTheDocument();

    // Type into subject + grade — should not refetch on each keystroke.
    await user.type(screen.getByLabelText(/Subject:/), 'SCIE');
    await user.type(screen.getByLabelText(/Grade:/), '6');
    expect(mockGetCatalog).toHaveBeenCalledTimes(1);

    // Apply triggers a single new fetch with the applied filters.
    await user.click(screen.getByTestId('apply-filters-btn'));
    await waitFor(() => {
      expect(mockGetCatalog).toHaveBeenCalledTimes(2);
    });
    expect(mockGetCatalog).toHaveBeenLastCalledWith('TDSB', {
      cursor: null,
      limit: 50,
      subject_code: 'SCIE',
      grade: 6,
      content_type: null,
    });

    // Filtered table now shows only the matching row.
    await waitFor(() => {
      expect(screen.queryByTestId('catalog-row-1')).not.toBeInTheDocument();
    });
    expect(screen.getByTestId('catalog-row-2')).toBeInTheDocument();
  });

  it('toggles sort direction when a column header is clicked', async () => {
    mockGetCatalog.mockResolvedValue({
      artifacts: [
        sampleArtifact(1, { title: 'Alpha' }),
        sampleArtifact(3, { title: 'Charlie' }),
        sampleArtifact(2, { title: 'Bravo' }),
      ],
      next_cursor: null,
    });

    const user = userEvent.setup();
    renderPage(<BoardCatalogPage />);

    await waitFor(() => {
      expect(screen.getByTestId('board-catalog-table')).toBeInTheDocument();
    });

    // Default sort is id desc — first body row should be id=3.
    const tableInitial = screen.getByTestId('board-catalog-table');
    const rowsInitial = within(tableInitial).getAllByRole('row');
    // First row is the header.
    expect(rowsInitial[1]).toHaveAttribute('data-testid', 'catalog-row-3');

    // Click Title header — switches to title asc.
    await user.click(screen.getByTestId('sort-title'));
    const rowsAfter = within(screen.getByTestId('board-catalog-table'))
      .getAllByRole('row');
    expect(rowsAfter[1]).toHaveAttribute('data-testid', 'catalog-row-1');
    expect(rowsAfter[3]).toHaveAttribute('data-testid', 'catalog-row-3');

    // Click Title again — flips to title desc.
    await user.click(screen.getByTestId('sort-title'));
    const rowsDesc = within(screen.getByTestId('board-catalog-table'))
      .getAllByRole('row');
    expect(rowsDesc[1]).toHaveAttribute('data-testid', 'catalog-row-3');
  });

  it('exports CSV: POST → window.open(download_url, _blank, …)', async () => {
    mockGetCatalog.mockResolvedValue({
      artifacts: [sampleArtifact(1)],
      next_cursor: null,
    });
    mockExportCatalogCsv.mockResolvedValue({
      download_url: 'https://signed.example.test/csv?sig=xyz',
      expires_at: '2026-04-29T11:00:00Z',
    });
    const openSpy = vi
      .spyOn(window, 'open')
      .mockImplementation(() => null);

    const user = userEvent.setup();
    renderPage(<BoardCatalogPage />);

    await waitFor(() => {
      expect(screen.getByTestId('board-catalog-table')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('export-csv-btn'));

    await waitFor(() => {
      expect(mockExportCatalogCsv).toHaveBeenCalledWith('TDSB');
    });
    expect(openSpy).toHaveBeenCalledWith(
      'https://signed.example.test/csv?sig=xyz',
      '_blank',
      'noopener,noreferrer',
    );
    // No error banner.
    expect(screen.queryByTestId('export-error')).not.toBeInTheDocument();
  });

  it('surfaces an export error when the POST fails', async () => {
    mockGetCatalog.mockResolvedValue({
      artifacts: [sampleArtifact(1)],
      next_cursor: null,
    });
    mockExportCatalogCsv.mockRejectedValue(new Error('413 Payload too large'));
    const openSpy = vi
      .spyOn(window, 'open')
      .mockImplementation(() => null);

    const user = userEvent.setup();
    renderPage(<BoardCatalogPage />);

    await waitFor(() => {
      expect(screen.getByTestId('board-catalog-table')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('export-csv-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('export-error')).toBeInTheDocument();
    });
    expect(screen.getByText(/413 Payload too large/)).toBeInTheDocument();
    expect(openSpy).not.toHaveBeenCalled();
  });

  it('paginates: Next advances cursor; Previous restores it', async () => {
    mockGetCatalog
      // Page 1
      .mockResolvedValueOnce({
        artifacts: [sampleArtifact(10), sampleArtifact(9)],
        next_cursor: 'cursor-page-2',
      })
      // Page 2
      .mockResolvedValueOnce({
        artifacts: [sampleArtifact(8), sampleArtifact(7)],
        next_cursor: null,
      })
      // Back to page 1
      .mockResolvedValueOnce({
        artifacts: [sampleArtifact(10), sampleArtifact(9)],
        next_cursor: 'cursor-page-2',
      });

    const user = userEvent.setup();
    renderPage(<BoardCatalogPage />);

    await waitFor(() => {
      expect(screen.getByTestId('catalog-row-10')).toBeInTheDocument();
    });
    expect(screen.getByTestId('prev-page-btn')).toBeDisabled();
    expect(screen.getByTestId('next-page-btn')).not.toBeDisabled();

    // Click Next → fires query with cursor-page-2.
    await user.click(screen.getByTestId('next-page-btn'));
    await waitFor(() => {
      expect(mockGetCatalog).toHaveBeenCalledTimes(2);
    });
    expect(mockGetCatalog).toHaveBeenLastCalledWith('TDSB', {
      cursor: 'cursor-page-2',
      limit: 50,
      subject_code: null,
      grade: null,
      content_type: null,
    });
    await waitFor(() => {
      expect(screen.getByTestId('catalog-row-8')).toBeInTheDocument();
    });
    // Page 2 indicator + Next disabled (no further cursor).
    expect(screen.getByText('Page 2')).toBeInTheDocument();
    expect(screen.getByTestId('next-page-btn')).toBeDisabled();
    expect(screen.getByTestId('prev-page-btn')).not.toBeDisabled();

    // Click Previous → restores page 1 cursor (null).
    await user.click(screen.getByTestId('prev-page-btn'));
    await waitFor(() => {
      expect(mockGetCatalog).toHaveBeenCalledTimes(3);
    });
    expect(mockGetCatalog).toHaveBeenLastCalledWith('TDSB', {
      cursor: null,
      limit: 50,
      subject_code: null,
      grade: null,
      content_type: null,
    });
  });

  it('renders disabled card when cmcp.enabled flag is OFF', () => {
    mockFlagState.mockReturnValue({ enabled: false, isLoading: false });

    renderPage(<BoardCatalogPage />);

    expect(
      screen.getByText(/Curriculum-mapped content is currently disabled/),
    ).toBeInTheDocument();
    expect(mockGetCatalog).not.toHaveBeenCalled();
  });

  it('shows "no board assigned" when BOARD_ADMIN has no board_id', () => {
    mockUseAuth.mockReturnValue({ user: userNoBoard, isLoading: false });

    renderPage(<BoardCatalogPage />);

    expect(screen.getByText(/No board assigned/)).toBeInTheDocument();
    expect(mockGetCatalog).not.toHaveBeenCalled();
  });

  it('lets ADMIN supply a board_id via ?board_id= query param', async () => {
    mockUseAuth.mockReturnValue({ user: adminUser, isLoading: false });
    mockGetCatalog.mockResolvedValueOnce({
      artifacts: [sampleArtifact(1)],
      next_cursor: null,
    });

    renderPage(<BoardCatalogPage />, '/board/catalog?board_id=PDSB');

    await waitFor(() => {
      expect(mockGetCatalog).toHaveBeenCalledWith('PDSB', {
        cursor: null,
        limit: 50,
        subject_code: null,
        grade: null,
        content_type: null,
      });
    });
  });

  it('shows admin board picker when ADMIN has no board_id and no query param', () => {
    mockUseAuth.mockReturnValue({ user: adminUser, isLoading: false });

    renderPage(<BoardCatalogPage />);

    expect(screen.getByText(/Pick a board to inspect/)).toBeInTheDocument();
    expect(mockGetCatalog).not.toHaveBeenCalled();
  });

  it('clears filters resets pagination + applied params', async () => {
    mockGetCatalog.mockResolvedValue({
      artifacts: [sampleArtifact(1)],
      next_cursor: null,
    });

    const user = userEvent.setup();
    renderPage(<BoardCatalogPage />);

    await waitFor(() => {
      expect(screen.getByTestId('board-catalog-table')).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/Subject:/), 'MATH');
    await user.click(screen.getByTestId('apply-filters-btn'));
    await waitFor(() => {
      expect(mockGetCatalog).toHaveBeenLastCalledWith('TDSB', {
        cursor: null,
        limit: 50,
        subject_code: 'MATH',
        grade: null,
        content_type: null,
      });
    });

    await user.click(screen.getByTestId('clear-filters-btn'));
    await waitFor(() => {
      expect(mockGetCatalog).toHaveBeenLastCalledWith('TDSB', {
        cursor: null,
        limit: 50,
        subject_code: null,
        grade: null,
        content_type: null,
      });
    });
  });

  it('shows loading state while the query is pending', () => {
    mockGetCatalog.mockImplementation(() => new Promise(() => {}));

    renderPage(<BoardCatalogPage />);

    expect(
      screen.getByTestId('board-catalog-loading'),
    ).toBeInTheDocument();
  });

  it('shows error card when the catalog request fails', async () => {
    mockGetCatalog.mockRejectedValueOnce(new Error('Network down'));

    renderPage(<BoardCatalogPage />);

    await waitFor(() => {
      expect(
        screen.getByTestId('board-catalog-error'),
      ).toBeInTheDocument();
    });
    expect(screen.getByText('Network down')).toBeInTheDocument();
  });
});
