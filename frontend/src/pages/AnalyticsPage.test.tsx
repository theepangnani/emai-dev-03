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

// react-markdown is lazy-loaded; provide a lightweight stub
vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => <div data-testid="react-markdown">{children}</div>,
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
      expect(screen.getByTestId('react-markdown')).toBeInTheDocument()
      expect(screen.getByTestId('react-markdown').textContent).toContain('Great job!')
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

  // ═══════════════════════════════════════════════════════════════
  // EXPANDED TEST COVERAGE (Issue #474)
  // ═══════════════════════════════════════════════════════════════

  // ── Empty data rendering ────────────────────────────────────

  it('shows empty state when no graded assignments', async () => {
    const emptySummary = {
      overall_average: 0,
      total_graded: 0,
      total_assignments: 0,
      completion_rate: 0,
      course_averages: [],
      trend: 'stable',
    }
    const emptyGrades = { grades: [], total: 0 }
    const emptyTrends = { points: [], trend: 'stable' }

    mockGetSummary.mockResolvedValue(emptySummary)
    mockGetGrades.mockResolvedValue(emptyGrades)
    mockGetTrends.mockResolvedValue(emptyTrends)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText(/No graded assignments yet/)).toBeInTheDocument()
    })
  })

  it('does not render recent grades table when grades list is empty', async () => {
    const emptyGrades = { grades: [], total: 0 }
    mockGetGrades.mockResolvedValue(emptyGrades)

    renderPage()

    // Wait for data to load (summary still returns data, just grades are empty)
    await waitFor(() => {
      expect(screen.getByText('Overall Average')).toBeInTheDocument()
    })

    // "Recent Grades" heading should not be present when grades array is empty
    expect(screen.queryByText('Recent Grades')).not.toBeInTheDocument()
  })

  // ── Child selector visibility ───────────────────────────────

  it('hides child selector when parent has only one child', async () => {
    const singleChild = [
      { student_id: 1, user_id: 10, full_name: 'Only Child', email: null, grade_level: null, school_name: null, date_of_birth: null, phone: null },
    ]
    mockGetChildren.mockResolvedValue(singleChild)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('82.5%')).toBeInTheDocument()
    })

    // "Student:" label should not appear for a single child
    expect(screen.queryByText('Student:')).not.toBeInTheDocument()
  })

  it('shows child selector when parent has multiple children', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Student:')).toBeInTheDocument()
    })

    // Both children should appear as options
    expect(screen.getByText('Child One')).toBeInTheDocument()
    expect(screen.getByText('Child Two')).toBeInTheDocument()
  })

  it('changes selected child when dropdown changes', async () => {
    const user = userEvent.setup()
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Student:')).toBeInTheDocument()
    })

    // Select the second child
    const select = screen.getByDisplayValue('Child One')
    await user.selectOptions(select, '2')

    // Verify that API was called again with the new student_id
    await waitFor(() => {
      expect(mockGetSummary).toHaveBeenCalledWith(2)
    })
  })

  // ── Time range filter changes ───────────────────────────────

  it('renders time range filter buttons', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Grade Trends')).toBeInTheDocument()
    })

    expect(screen.getByText('30d')).toBeInTheDocument()
    expect(screen.getByText('60d')).toBeInTheDocument()
    expect(screen.getByText('90d')).toBeInTheDocument()
    expect(screen.getByText('All')).toBeInTheDocument()
  })

  it('reloads trends when time range button is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Grade Trends')).toBeInTheDocument()
    })

    // Clear mocks to isolate the filter-change call
    mockGetTrends.mockClear()

    await user.click(screen.getByText('30d'))

    await waitFor(() => {
      expect(mockGetTrends).toHaveBeenCalled()
    })

    // The call should include days=30
    const callArgs = mockGetTrends.mock.calls[0]
    expect(callArgs[2]).toBe(30)
  })

  // ── Course filter changes ───────────────────────────────────

  it('renders course filter dropdown with All Courses option', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Grade Trends')).toBeInTheDocument()
    })

    // The course filter dropdown should have "All Courses" option
    expect(screen.getByText('All Courses')).toBeInTheDocument()
    // And course options from the summary
    expect(screen.getByRole('option', { name: 'Math' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Science' })).toBeInTheDocument()
  })

  it('reloads trends when course filter changes', async () => {
    const user = userEvent.setup()
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Grade Trends')).toBeInTheDocument()
    })

    mockGetTrends.mockClear()

    // Select a specific course by its value (course_id=1)
    const courseSelect = screen.getByDisplayValue('All Courses')
    await user.selectOptions(courseSelect, '1')

    await waitFor(() => {
      expect(mockGetTrends).toHaveBeenCalled()
    })

    // The call should include courseId=1
    const callArgs = mockGetTrends.mock.calls[0]
    expect(callArgs[1]).toBe(1)
  })

  // ── AI Insights: loading state ──────────────────────────────

  it('shows Generating... text while AI insight loads', async () => {
    const user = userEvent.setup()

    // Make the AI insight take a while to resolve
    let resolveInsight: (value: unknown) => void
    const pendingPromise = new Promise((resolve) => { resolveInsight = resolve })
    mockGetAIInsight.mockReturnValue(pendingPromise)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Generate AI Insights')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Generate AI Insights'))

    // Should show loading text
    await waitFor(() => {
      expect(screen.getByText('Generating...')).toBeInTheDocument()
    })

    // The button should be disabled while loading
    expect(screen.getByText('Generating...')).toBeDisabled()

    // Resolve the promise to clean up
    resolveInsight!({ insight: 'Done', generated_at: '2026-01-20T00:00:00' })

    await waitFor(() => {
      expect(screen.queryByText('Generating...')).not.toBeInTheDocument()
    })
  })

  it('shows fallback message when AI insight request fails', async () => {
    const user = userEvent.setup()
    mockGetAIInsight.mockRejectedValue(new Error('AI service down'))

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Generate AI Insights')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Generate AI Insights'))

    await waitFor(() => {
      expect(screen.getByText('Failed to generate insights. Please try again.')).toBeInTheDocument()
    })
  })

  // ── Error states ────────────────────────────────────────────

  it('shows generic error message for non-Error exceptions', async () => {
    mockGetSummary.mockRejectedValue('string error')
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Failed to load analytics')).toBeInTheDocument()
    })
  })

  it('shows error when trends API fails but summary succeeds', async () => {
    mockGetTrends.mockRejectedValue(new Error('Trends fetch failed'))
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Trends fetch failed')).toBeInTheDocument()
    })
  })

  it('shows error when grades API fails but summary succeeds', async () => {
    mockGetGrades.mockRejectedValue(new Error('Grades unavailable'))
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Grades unavailable')).toBeInTheDocument()
    })
  })

  // ── Summary cards display ───────────────────────────────────

  it('displays stable trend badge when trend is stable', async () => {
    const stableSummary = { ...mockSummary, trend: 'stable' }
    mockGetSummary.mockResolvedValue(stableSummary)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Stable')).toBeInTheDocument()
    })
  })

  it('displays declining trend badge when trend is declining', async () => {
    const decliningSummary = { ...mockSummary, trend: 'declining' }
    mockGetSummary.mockResolvedValue(decliningSummary)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Declining')).toBeInTheDocument()
    })
  })

  it('displays total graded count in summary', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('8')).toBeInTheDocument()
    })
    expect(screen.getByText('Assignments Graded')).toBeInTheDocument()
  })

  it('displays completion rate as percentage', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('80%')).toBeInTheDocument()
    })
    expect(screen.getByText('Completion Rate')).toBeInTheDocument()
  })

  // ── Grades table structure ──────────────────────────────────

  it('renders grade values with percentage in table', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Recent Grades')).toBeInTheDocument()
    })

    // Check that grade/max and percentage are shown
    expect(screen.getByText('80/100 (80.0%)')).toBeInTheDocument()
    expect(screen.getByText('45/50 (90.0%)')).toBeInTheDocument()
  })

  it('renders course names in grades table', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Recent Grades')).toBeInTheDocument()
    })

    // Course names should appear in the table
    expect(screen.getAllByText('Math').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Science').length).toBeGreaterThan(0)
  })
})
