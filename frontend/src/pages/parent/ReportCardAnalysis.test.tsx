import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/helpers';
import { createMockChild } from '../../test/mocks';
import { ReportCardAnalysis } from './ReportCardAnalysis';

// Mock fns
const mockGetChildren = vi.fn();
const mockList = vi.fn();
const mockListMy = vi.fn();
const mockAnalyze = vi.fn();
const mockGetAnalysis = vi.fn();
const mockCareerPath = vi.fn();
const mockUpload = vi.fn();
const mockDelete = vi.fn();

const mockUseAuth = vi.fn();

vi.mock('../../api/parent', () => ({
  parentApi: {
    getChildren: (...args: unknown[]) => mockGetChildren(...args),
  },
}));

vi.mock('../../api/schoolReportCards', () => ({
  schoolReportCardsApi: {
    list: (...args: unknown[]) => mockList(...args),
    listMy: (...args: unknown[]) => mockListMy(...args),
    analyze: (...args: unknown[]) => mockAnalyze(...args),
    getAnalysis: (...args: unknown[]) => mockGetAnalysis(...args),
    careerPath: (...args: unknown[]) => mockCareerPath(...args),
    upload: (...args: unknown[]) => mockUpload(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  },
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock('../../api/client', () => ({
  messagesApi: { getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }) },
  inspirationApi: { getRandom: vi.fn().mockRejectedValue(new Error('none')) },
}));

vi.mock('../../components/DashboardLayout', () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => <div data-testid="layout">{children}</div>,
}));

vi.mock('../../components/Skeleton', () => ({
  PageSkeleton: () => <div data-testid="skeleton" />,
}));

vi.mock('../../components/ChildSelectorTabs', () => ({
  ChildSelectorTabs: ({ children: kids, onSelectChild }: { children: Array<{ student_id: number; full_name: string }>; selectedChild: number | null; onSelectChild: (id: number | null) => void; childOverdueCounts: Map<number, number> }) => (
    <div data-testid="child-selector">
      {kids.map((c: { student_id: number; full_name: string }) => (
        <button key={c.student_id} onClick={() => onSelectChild(c.student_id)}>
          {c.full_name}
        </button>
      ))}
    </div>
  ),
}));

const child1 = createMockChild({ student_id: 10, full_name: 'Alice' });
const child2 = createMockChild({ student_id: 20, full_name: 'Bob' });

const mockReportCards = [
  {
    id: 1,
    student_id: 10,
    original_filename: 'report_term1.pdf',
    term: 'Term 1',
    grade_level: '5',
    school_name: 'Maple School',
    report_date: null,
    school_year: null,
    has_text_content: true,
    has_analysis: true,
    created_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 2,
    student_id: 10,
    original_filename: 'report_term2.pdf',
    term: 'Term 2',
    grade_level: '5',
    school_name: 'Maple School',
    report_date: null,
    school_year: null,
    has_text_content: true,
    has_analysis: false,
    created_at: '2026-03-15T10:00:00Z',
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  mockUseAuth.mockReturnValue({
    user: { id: 1, full_name: 'Test Parent', role: 'parent', roles: ['parent'] },
    logout: vi.fn(),
    switchRole: vi.fn(),
  });
  mockGetChildren.mockResolvedValue([child1, child2]);
  mockList.mockResolvedValue({ data: mockReportCards });
  mockListMy.mockResolvedValue({ data: mockReportCards });
});

describe('ReportCardAnalysis', () => {
  it('renders loading skeleton initially', () => {
    // Make getChildren hang so loading stays true
    mockGetChildren.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<ReportCardAnalysis />);
    expect(screen.getByTestId('skeleton')).toBeInTheDocument();
  });

  it('renders "no children" empty state when parent has no children', async () => {
    mockGetChildren.mockResolvedValue([]);
    renderWithProviders(<ReportCardAnalysis />);
    await waitFor(() => {
      expect(screen.getByText('No children linked')).toBeInTheDocument();
    });
    expect(screen.getByText(/Link a child from the My Kids page/)).toBeInTheDocument();
  });

  it('renders child selector tabs', async () => {
    renderWithProviders(<ReportCardAnalysis />);
    await waitFor(() => {
      expect(screen.getByTestId('child-selector')).toBeInTheDocument();
    });
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
  });

  it('renders report card list after selecting a child', async () => {
    // With 1 child, auto-selects
    mockGetChildren.mockResolvedValue([child1]);
    renderWithProviders(<ReportCardAnalysis />);
    await waitFor(() => {
      expect(screen.getByText('report_term1.pdf')).toBeInTheDocument();
    });
    expect(screen.getByText('report_term2.pdf')).toBeInTheDocument();
  });

  it('shows "Analyzed" and "Not Analyzed" badges', async () => {
    mockGetChildren.mockResolvedValue([child1]);
    renderWithProviders(<ReportCardAnalysis />);
    await waitFor(() => {
      expect(screen.getByText('report_term1.pdf')).toBeInTheDocument();
    });
    expect(screen.getByText('Analyzed')).toBeInTheDocument();
    expect(screen.getByText('Not Analyzed')).toBeInTheDocument();
  });

  it('renders upload button when a child is selected', async () => {
    mockGetChildren.mockResolvedValue([child1]);
    renderWithProviders(<ReportCardAnalysis />);
    await waitFor(() => {
      expect(screen.getByText('Upload Report Card')).toBeInTheDocument();
    });
  });

  it('renders career path button when a child is selected', async () => {
    mockGetChildren.mockResolvedValue([child1]);
    renderWithProviders(<ReportCardAnalysis />);
    await waitFor(() => {
      expect(screen.getByText('Career Path Analysis')).toBeInTheDocument();
    });
  });

  it('renders page heading', async () => {
    renderWithProviders(<ReportCardAnalysis />);
    await waitFor(() => {
      expect(screen.getByText('School Report Cards')).toBeInTheDocument();
    });
  });
});

describe('ReportCardAnalysis — Student view', () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({
      user: { id: 5, full_name: 'Test Student', role: 'student', roles: ['student'] },
      logout: vi.fn(),
      switchRole: vi.fn(),
    });
  });

  it('loads report cards via listMy for students', async () => {
    renderWithProviders(<ReportCardAnalysis />);
    await waitFor(() => {
      expect(mockListMy).toHaveBeenCalled();
    });
    expect(mockGetChildren).not.toHaveBeenCalled();
    expect(screen.getByText('report_term1.pdf')).toBeInTheDocument();
  });

  it('shows student-specific subtitle', async () => {
    renderWithProviders(<ReportCardAnalysis />);
    await waitFor(() => {
      expect(screen.getByText('View your school report cards and analysis.')).toBeInTheDocument();
    });
  });

  it('does not show upload or career path buttons for students', async () => {
    renderWithProviders(<ReportCardAnalysis />);
    await waitFor(() => {
      expect(screen.getByText('report_term1.pdf')).toBeInTheDocument();
    });
    expect(screen.queryByText('Upload Report Card')).not.toBeInTheDocument();
    expect(screen.queryByText('Career Path Analysis')).not.toBeInTheDocument();
  });

  it('does not show delete buttons for students', async () => {
    renderWithProviders(<ReportCardAnalysis />);
    await waitFor(() => {
      expect(screen.getByText('report_term1.pdf')).toBeInTheDocument();
    });
    expect(screen.queryByText('Delete')).not.toBeInTheDocument();
  });

  it('does not show child selector tabs for students', async () => {
    renderWithProviders(<ReportCardAnalysis />);
    await waitFor(() => {
      expect(screen.getByText('report_term1.pdf')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('child-selector')).not.toBeInTheDocument();
  });

  it('shows empty state message for students with no report cards', async () => {
    mockListMy.mockResolvedValue({ data: [] });
    renderWithProviders(<ReportCardAnalysis />);
    await waitFor(() => {
      expect(screen.getByText(/Your parent can upload report cards for you/)).toBeInTheDocument();
    });
  });
});
