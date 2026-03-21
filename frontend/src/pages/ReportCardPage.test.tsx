import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ReportCardPage } from './ReportCardPage';

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

const mockReportCard = {
  student_name: 'Test Student',
  term: 'Winter 2026',
  subjects_studied: [
    { name: 'Math', guides: 5, quizzes: 3 },
    { name: 'Science', guides: 2, quizzes: 1 },
  ],
  total_uploads: 8,
  total_guides: 7,
  total_quizzes: 4,
  total_xp: 350,
  level_reached: { level: 3, title: 'Study Starter' },
  badges_earned: [{ name: 'First Upload', date: '2026-01-15T10:00:00Z' }],
  longest_streak: 12,
  most_reviewed_topics: ['Quadratic Equations', 'Cell Division'],
  study_sessions: 15,
  total_study_minutes: 375,
};

const mockGet = vi.fn();

vi.mock('../api/reportCard', () => ({
  reportCardApi: {
    get: (...args: unknown[]) => mockGet(...args),
    getForChild: vi.fn(),
  },
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/report-card']}>
        <ReportCardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ReportCardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue(mockReportCard);
  });

  it('renders report card header with student name and term', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Test Student')).toBeInTheDocument();
    });
    expect(screen.getByText('Winter 2026')).toBeInTheDocument();
    expect(screen.getByText('Report Card')).toBeInTheDocument();
  });

  it('renders overview stats', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('8')).toBeInTheDocument(); // uploads
    });
    expect(screen.getByText('7')).toBeInTheDocument(); // guides
    expect(screen.getByText('350')).toBeInTheDocument(); // xp
  });

  it('renders subjects table', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Math')).toBeInTheDocument();
    });
    expect(screen.getByText('Science')).toBeInTheDocument();
  });

  it('renders achievements section with level and badges', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Lv. 3')).toBeInTheDocument();
    });
    expect(screen.getByText('Study Starter')).toBeInTheDocument();
    expect(screen.getByText('First Upload')).toBeInTheDocument();
  });

  it('renders streaks and study sessions', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('12')).toBeInTheDocument(); // longest streak
    });
    expect(screen.getByText('15')).toBeInTheDocument(); // sessions
    expect(screen.getByText('375')).toBeInTheDocument(); // minutes
  });

  it('renders most reviewed topics', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Quadratic Equations')).toBeInTheDocument();
    });
    expect(screen.getByText('Cell Division')).toBeInTheDocument();
  });

  it('renders download and share buttons', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Download PDF')).toBeInTheDocument();
    });
    expect(screen.getByText('Share')).toBeInTheDocument();
  });

  it('shows error state on failure', async () => {
    mockGet.mockRejectedValue(new Error('Network error'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Failed to load report card.')).toBeInTheDocument();
    });
  });
});
