import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'

// ── Mock data ─────────────────────────────────────────────────

const mockSummary = {
  overall_average: 82.5,
  total_graded: 8,
  total_assignments: 10,
  completion_rate: 80,
  course_averages: [
    { course_id: 1, course_name: 'Math', average_percentage: 80, graded_count: 5, total_count: 6, completion_rate: 83.3 },
    { course_id: 2, course_name: 'Science', average_percentage: 85, graded_count: 3, total_count: 4, completion_rate: 75 },
  ],
  trend: 'improving',
}

const mockTrends = {
  points: [
    { date: '2026-01-10', percentage: 75, assignment_title: 'HW 1', course_name: 'Math' },
    { date: '2026-01-20', percentage: 85, assignment_title: 'HW 2', course_name: 'Math' },
  ],
  trend: 'improving',
}

const mockGrades = {
  grades: [
    { student_assignment_id: 1, assignment_id: 1, assignment_title: 'HW 1', course_id: 1, course_name: 'Math', grade: 80, max_points: 100, percentage: 80, status: 'graded', submitted_at: '2026-01-10T00:00:00', due_date: '2026-01-09T00:00:00' },
    { student_assignment_id: 2, assignment_id: 2, assignment_title: 'Lab 1', course_id: 2, course_name: 'Science', grade: 45, max_points: 50, percentage: 90, status: 'graded', submitted_at: '2026-01-15T00:00:00', due_date: '2026-01-14T00:00:00' },
  ],
  total: 2,
}

const mockChildren = [
  { student_id: 1, user_id: 10, full_name: 'Child One', email: null, grade_level: null, school_name: null, date_of_birth: null, phone: null },
  { student_id: 2, user_id: 11, full_name: 'Child Two', email: null, grade_level: null, school_name: null, date_of_birth: null, phone: null },
]

// ── Mocks ─────────────────────────────────────────────────────

const mockGetSummary = vi.fn().mockResolvedValue(mockSummary)
const mockGetTrends = vi.fn().mockResolvedValue(mockTrends)
const mockGetGrades = vi.fn().mockResolvedValue(mockGrades)
const mockGetAIInsight = vi.fn().mockResolvedValue({ insight: '## Great job!\nKeep it up.', generated_at: '2026-01-20T00:00:00' })
const mockGetChildren = vi.fn().mockResolvedValue(mockChildren)

vi.mock('../api/analytics', () => ({
  analyticsApi: {
    getSummary: (...args: unknown[]) => mockGetSummary(...args),
    getTrends: (...args: unknown[]) => mockGetTrends(...args),
    getGrades: (...args: unknown[]) => mockGetGrades(...args),
    getAIInsight: (...args: unknown[]) => mockGetAIInsight(...args),
    getWeeklyReport: vi.fn().mockResolvedValue({ id: 1, data: {} }),
    syncGrades: vi.fn().mockResolvedValue({ synced: 0, errors: 0, message: '' }),
  },
}))

vi.mock('../api/parent', () => ({
  parentApi: {
    getChildren: (...args: unknown[]) => mockGetChildren(...args),
  },
}))

vi.mock('../api/client', () => ({
  messagesApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }),
  },
  inspirationApi: {
    getRandom: vi.fn().mockRejectedValue(new Error('none')),
  },
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Test Parent', role: 'parent', roles: ['parent'] },
    logout: vi.fn(),
    switchRole: vi.fn(),
    resendVerification: vi.fn(),
  }),
}))

vi.mock('../components/NotificationBell', () => ({
  NotificationBell: () => <div data-testid="notification-bell" />,
}))

vi.mock('../components/GlobalSearch', () => ({
  GlobalSearch: () => <div data-testid="global-search" />,
}))

vi.mock('../components/ThemeToggle', () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}))

// Recharts uses ResizeObserver internally
class MockResizeObserver {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
}
vi.stubGlobal('ResizeObserver', MockResizeObserver)

// ── Import after mocks ──────────────────────────────────────

import { AnalyticsPage } from './AnalyticsPage'

// ── Tests ───────────────────────────────────────────────────

describe('AnalyticsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetSummary.mockResolvedValue(mockSummary)
    mockGetTrends.mockResolvedValue(mockTrends)
    mockGetGrades.mockResolvedValue(mockGrades)
    mockGetChildren.mockResolvedValue(mockChildren)
  })

  function renderPage() {
    return renderWithProviders(<AnalyticsPage />, { initialEntries: ['/analytics'] })
  }

  it('renders summary cards after loading', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('82.5%')).toBeInTheDocument()
    })
    expect(screen.getByText('Overall Average')).toBeInTheDocument()
    expect(screen.getByText('Completion Rate')).toBeInTheDocument()
    expect(screen.getByText('Assignments Graded')).toBeInTheDocument()
    expect(screen.getByText('Improving')).toBeInTheDocument()
  })

  it('shows child selector for parents with multiple children', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Student:')).toBeInTheDocument()
    })
    expect(screen.getByText('Child One')).toBeInTheDocument()
    expect(screen.getByText('Child Two')).toBeInTheDocument()
  })

  it('renders recent grades table', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Recent Grades')).toBeInTheDocument()
    })
    expect(screen.getByText('HW 1')).toBeInTheDocument()
    expect(screen.getByText('Lab 1')).toBeInTheDocument()
  })

  it('renders AI insight button and generates insight on click', async () => {
    const user = userEvent.setup()
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Generate AI Insights')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Generate AI Insights'))

    await waitFor(() => {
      expect(mockGetAIInsight).toHaveBeenCalledWith(1)
    })

    await waitFor(() => {
      expect(screen.getByText('Great job!')).toBeInTheDocument()
    })
  })

  it('shows loading state initially', () => {
    renderPage()
    expect(screen.getByText('Loading analytics...')).toBeInTheDocument()
  })

  it('shows error state on API failure', async () => {
    mockGetSummary.mockRejectedValue(new Error('Network error'))
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })
})
