import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { XpHistoryPage } from './XpHistoryPage';

// Mock modules
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, role: 'student', roles: ['student'], full_name: 'Test Student', needs_onboarding: false, onboarding_completed: true },
    isLoading: false,
  }),
}));

vi.mock('../components/DashboardLayout', () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => <div data-testid="layout">{children}</div>,
}));

vi.mock('../components/PageNav', () => ({
  PageNav: () => <nav data-testid="page-nav" />,
}));

vi.mock('../components/Skeleton', () => ({
  PageSkeleton: () => <div data-testid="skeleton" />,
}));

vi.mock('../utils/exportUtils', () => ({
  downloadAsPdf: vi.fn().mockResolvedValue(undefined),
}));

const mockLedgerEntries = [
  { action_type: 'upload', xp_awarded: 10, multiplier: 1.0, reason: null, created_at: '2026-03-18T10:00:00Z' },
  { action_type: 'study_guide', xp_awarded: 15, multiplier: 1.5, reason: null, created_at: '2026-03-17T09:00:00Z' },
  { action_type: 'brownie_points', xp_awarded: 5, multiplier: 1.0, reason: 'Great work on homework', created_at: '2026-03-16T08:00:00Z' },
  { action_type: 'daily_login', xp_awarded: 5, multiplier: 1.0, reason: null, created_at: '2026-03-15T07:00:00Z' },
];

const mockSummary = {
  total_xp: 135,
  level: 3,
  level_title: 'Rising Star',
  xp_in_level: 35,
  xp_for_next_level: 100,
  today_xp: 10,
  today_max_xp: 200,
  streak_days: 5,
  weekly_xp: 85,
  recent_badges: [],
};

const mockStreak = {
  current_streak: 5,
  longest_streak: 12,
  streak_start_date: '2026-03-13',
};

const mockGetLedger = vi.fn();
const mockGetSummary = vi.fn();
const mockGetStreak = vi.fn();

vi.mock('../api/xp', () => ({
  xpApi: {
    getLedger: (...args: unknown[]) => mockGetLedger(...args),
    getSummary: () => mockGetSummary(),
    getStreak: () => mockGetStreak(),
  },
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/xp/history']}>
        <XpHistoryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function waitForTableRendered() {
  // Wait for action pills to appear (they're in the table, not the filter dropdown)
  await waitFor(() => {
    expect(document.querySelector('.xph-action-pill')).toBeTruthy();
  }, { timeout: 3000 });
}

describe('XpHistoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetLedger.mockResolvedValue({ entries: mockLedgerEntries, total_count: 4 });
    mockGetSummary.mockResolvedValue(mockSummary);
    mockGetStreak.mockResolvedValue(mockStreak);
  });

  it('renders header and summary stats', async () => {
    renderPage();
    await waitForTableRendered();

    expect(screen.getByText('XP History')).toBeInTheDocument();
    // Level badge
    const badge = document.querySelector('.xph-level-badge');
    expect(badge).toBeTruthy();
    expect(badge!.textContent).toContain('3');
    expect(badge!.textContent).toContain('Rising Star');
    // Total XP in header
    const totalXp = document.querySelector('.xph-total-xp');
    expect(totalXp).toBeTruthy();
    expect(totalXp!.textContent).toContain('135');
  });

  it('renders ledger entries with correct labels', async () => {
    renderPage();
    await waitForTableRendered();

    const pills = document.querySelectorAll('.xph-action-pill');
    const pillTexts = Array.from(pills).map(p => p.textContent);
    expect(pillTexts).toContain('Uploaded Document');
    expect(pillTexts).toContain('Generated Study Guide');
    expect(pillTexts).toContain('Brownie Points');
    expect(pillTexts).toContain('Daily Login Bonus');
  });

  it('shows brownie points reason', async () => {
    renderPage();
    await waitForTableRendered();
    expect(screen.getByText('Great work on homework')).toBeInTheDocument();
  });

  it('displays multiplier correctly', async () => {
    renderPage();
    await waitForTableRendered();
    expect(screen.getByText('1.5x')).toBeInTheDocument();
  });

  it('shows load more button when there are more entries', async () => {
    mockGetLedger.mockResolvedValue({ entries: mockLedgerEntries, total_count: 100 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Load More/)).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('does not show load more when all entries loaded', async () => {
    renderPage();
    await waitForTableRendered();
    expect(screen.queryByText(/Load More/)).not.toBeInTheDocument();
  });

  it('loads more entries on click', async () => {
    const user = userEvent.setup();
    const secondBatch = [
      { action_type: 'quiz_complete', xp_awarded: 20, multiplier: 1.0, reason: null, created_at: '2026-03-14T06:00:00Z' },
    ];
    mockGetLedger
      .mockResolvedValueOnce({ entries: mockLedgerEntries, total_count: 5 })
      .mockResolvedValueOnce({ entries: secondBatch, total_count: 5 });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Load More/)).toBeInTheDocument();
    }, { timeout: 3000 });

    await user.click(screen.getByText(/Load More/));
    await waitFor(() => {
      expect(mockGetLedger).toHaveBeenCalledTimes(2);
      expect(mockGetLedger).toHaveBeenLastCalledWith(50, 4);
    });
  });

  it('filters entries by action type', async () => {
    const user = userEvent.setup();
    renderPage();
    await waitForTableRendered();

    const filterSelect = screen.getByLabelText('Filter by action type');
    await user.selectOptions(filterSelect, 'upload');

    // After filtering, only the upload pill should remain in the table
    const pills = document.querySelectorAll('.xph-action-pill');
    expect(pills).toHaveLength(1);
    expect(pills[0].textContent).toBe('Uploaded Document');
  });

  it('shows empty state when no entries', async () => {
    mockGetLedger.mockResolvedValue({ entries: [], total_count: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('No XP entries yet')).toBeInTheDocument();
    }, { timeout: 3000 });
  });
});
