import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────
const mockNavigate = vi.fn()
const mockSearchParams = new URLSearchParams()
const mockSetSearchParams = vi.fn()

const mockGetStatus = vi.fn()
const mockGetConnectUrl = vi.fn()
const mockSyncCourses = vi.fn()
const mockDisconnect = vi.fn()
const mockCoursesList = vi.fn()
const mockAssignmentsList = vi.fn()
const mockListGuides = vi.fn()
const mockGetSupportedFormats = vi.fn()
const mockCheckDuplicate = vi.fn()
const mockGenerateGuide = vi.fn()
const mockGenerateQuiz = vi.fn()
const mockGenerateFlashcards = vi.fn()
const mockGenerateFromFile = vi.fn()
const mockDeleteGuide = vi.fn()
const mockUpdateGuide = vi.fn()

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Student User', role: 'student', roles: ['student'] },
    logout: vi.fn(),
    switchRole: vi.fn(),
  }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearchParams: () => [mockSearchParams, mockSetSearchParams],
  }
})

vi.mock('../api/client', () => ({
  googleApi: {
    getStatus: (...args: any[]) => mockGetStatus(...args),
    getConnectUrl: (...args: any[]) => mockGetConnectUrl(...args),
    syncCourses: (...args: any[]) => mockSyncCourses(...args),
    disconnect: (...args: any[]) => mockDisconnect(...args),
  },
  coursesApi: {
    list: (...args: any[]) => mockCoursesList(...args),
  },
  assignmentsApi: {
    list: (...args: any[]) => mockAssignmentsList(...args),
  },
  studyApi: {
    listGuides: (...args: any[]) => mockListGuides(...args),
    getSupportedFormats: (...args: any[]) => mockGetSupportedFormats(...args),
    checkDuplicate: (...args: any[]) => mockCheckDuplicate(...args),
    generateGuide: (...args: any[]) => mockGenerateGuide(...args),
    generateQuiz: (...args: any[]) => mockGenerateQuiz(...args),
    generateFlashcards: (...args: any[]) => mockGenerateFlashcards(...args),
    generateFromFile: (...args: any[]) => mockGenerateFromFile(...args),
    deleteGuide: (...args: any[]) => mockDeleteGuide(...args),
    updateGuide: (...args: any[]) => mockUpdateGuide(...args),
  },
  messagesApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }),
  },
  inspirationApi: {
    getRandom: vi.fn().mockRejectedValue(new Error('none')),
  },
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

vi.mock('../components/StudyToolsButton', () => ({
  StudyToolsButton: ({ assignmentTitle }: any) => (
    <button data-testid={`study-btn-${assignmentTitle}`}>Study</button>
  ),
}))

vi.mock('../utils/logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    logError: vi.fn(),
  },
}))

import { StudentDashboard } from './StudentDashboard'

function setupDefaults() {
  mockGetStatus.mockResolvedValue({ connected: false })
  mockCoursesList.mockResolvedValue([])
  mockAssignmentsList.mockResolvedValue([])
  mockListGuides.mockResolvedValue([])
  mockGetSupportedFormats.mockResolvedValue({ supported_types: ['pdf', 'docx', 'txt'], max_file_size_mb: 100 })
  mockCheckDuplicate.mockResolvedValue({ exists: false })
}

describe('StudentDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams.delete('google_connected')
    mockSearchParams.delete('just_registered')
    mockSearchParams.delete('error')
    setupDefaults()
  })

  // ── Loading ──────────────────────────────────────────────────
  it('shows loading skeleton initially', () => {
    mockGetStatus.mockReturnValue(new Promise(() => {}))
    mockCoursesList.mockReturnValue(new Promise(() => {}))
    mockAssignmentsList.mockReturnValue(new Promise(() => {}))
    mockListGuides.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<StudentDashboard />)
    expect(document.querySelector('.skeleton')).toBeInTheDocument()
  })

  // ── Google Connect Banner ────────────────────────────────────
  it('shows connect banner when Google is not connected', async () => {
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Connect Google Classroom')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Connect Now' })).toBeInTheDocument()
  })

  it('shows welcome banner for just-registered users', async () => {
    mockSearchParams.set('just_registered', 'true')
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText(/welcome! connect your google classroom/i)).toBeInTheDocument()
    })
  })

  it('does not show connect banner when Google is connected', async () => {
    mockGetStatus.mockResolvedValue({ connected: true })
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument()
    })
    expect(screen.queryByText('Connect Google Classroom')).not.toBeInTheDocument()
  })

  // ── Dashboard Cards ──────────────────────────────────────────
  it('renders dashboard stat cards', async () => {
    mockCoursesList.mockResolvedValue([
      { id: 1, name: 'Math', google_classroom_id: null },
      { id: 2, name: 'Science', google_classroom_id: 'gc-1' },
    ])
    mockAssignmentsList.mockResolvedValue([
      { id: 1, title: 'HW 1', description: null, course_id: 1, due_date: '2026-02-15' },
    ])
    renderWithProviders(<StudentDashboard />)

    // Wait for loading to complete — check for a card label
    await waitFor(() => {
      expect(screen.getByText('Active courses')).toBeInTheDocument()
    })
    // Stat cards: Courses (2), Assignments (1), Study Materials (--), Google Classroom (Not Connected)
    expect(screen.getByText('Total assignments')).toBeInTheDocument()
    expect(screen.getByText('Study Materials')).toBeInTheDocument()
    expect(screen.getByText('Not Connected')).toBeInTheDocument()
  })

  it('shows Connected when Google is connected', async () => {
    mockGetStatus.mockResolvedValue({ connected: true })
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Sync Courses' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Disconnect' })).toBeInTheDocument()
  })

  // ── Google Actions ───────────────────────────────────────────
  it('handles Connect Now click', async () => {
    mockGetConnectUrl.mockResolvedValue({ authorization_url: 'https://accounts.google.com/auth' })
    const user = userEvent.setup()

    const originalLocation = window.location
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, href: '' },
      writable: true,
    })

    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Connect Now' })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Connect Now' }))

    await waitFor(() => {
      expect(mockGetConnectUrl).toHaveBeenCalled()
    })

    Object.defineProperty(window, 'location', { value: originalLocation, writable: true })
  })

  it('handles Sync Courses', async () => {
    mockGetStatus.mockResolvedValue({ connected: true })
    mockSyncCourses.mockResolvedValue({ message: 'Synced 3 courses' })
    const user = userEvent.setup()
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Sync Courses' })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Sync Courses' }))

    await waitFor(() => {
      expect(mockSyncCourses).toHaveBeenCalled()
    })
    await waitFor(() => {
      expect(screen.getByText('Synced 3 courses')).toBeInTheDocument()
    })
  })

  it('handles Disconnect', async () => {
    mockGetStatus.mockResolvedValue({ connected: true })
    mockDisconnect.mockResolvedValue({})
    const user = userEvent.setup()
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Disconnect' })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Disconnect' }))

    await waitFor(() => {
      expect(mockDisconnect).toHaveBeenCalled()
    })
    await waitFor(() => {
      expect(screen.getByText('Google Classroom disconnected')).toBeInTheDocument()
    })
  })

  // ── Assignments Section ──────────────────────────────────────
  it('renders assignments list', async () => {
    mockAssignmentsList.mockResolvedValue([
      { id: 1, title: 'Algebra Homework', description: null, course_id: 1, due_date: '2026-02-15T23:59:00Z' },
      { id: 2, title: 'Essay Draft', description: null, course_id: 2, due_date: null },
    ])
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Algebra Homework')).toBeInTheDocument()
    })
    expect(screen.getByText('Essay Draft')).toBeInTheDocument()
  })

  it('shows empty state for assignments', async () => {
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('No assignments yet')).toBeInTheDocument()
    })
  })

  // ── Courses Section ──────────────────────────────────────────
  it('renders courses list with Google badge', async () => {
    mockCoursesList.mockResolvedValue([
      { id: 1, name: 'Math 101', google_classroom_id: 'gc-1' },
      { id: 2, name: 'History', google_classroom_id: null },
    ])
    renderWithProviders(<StudentDashboard />)

    // Course names appear in both the course list AND course filter <option>s
    await waitFor(() => {
      expect(screen.getAllByText('Math 101').length).toBeGreaterThanOrEqual(1)
    })
    expect(screen.getAllByText('History').length).toBeGreaterThanOrEqual(1)
    // Google badge for courses with google_classroom_id
    expect(document.querySelector('.google-badge')).toBeInTheDocument()
  })

  it('shows empty state for courses', async () => {
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('No courses yet')).toBeInTheDocument()
    })
  })

  // ── Study Materials Section ──────────────────────────────────
  it('renders study guides list', async () => {
    mockListGuides.mockResolvedValue([
      { id: 1, title: 'Chapter 1 Notes', guide_type: 'study_guide', version: 1, course_id: null, created_at: '2026-02-14T12:00:00Z' },
      { id: 2, title: 'Quiz Practice', guide_type: 'quiz', version: 2, course_id: null, created_at: '2026-02-13T12:00:00Z' },
    ])
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Chapter 1 Notes')).toBeInTheDocument()
    })
    expect(screen.getByText('Quiz Practice')).toBeInTheDocument()
    expect(screen.getByText('v2')).toBeInTheDocument() // version badge
  })

  it('shows empty state for study materials', async () => {
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('No study materials yet')).toBeInTheDocument()
    })
  })

  it('renders + Create Custom button', async () => {
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /\+ create custom/i })).toBeInTheDocument()
    })
  })

  // ── Create Study Material Modal ──────────────────────────────
  it('opens create study material modal', async () => {
    const user = userEvent.setup()
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /\+ create custom/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /\+ create custom/i }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2, name: 'Create Study Material' })).toBeInTheDocument()
    })
    expect(screen.getByText('Paste Text')).toBeInTheDocument()
    expect(screen.getByText('Upload File')).toBeInTheDocument()
  })

  it('closes create modal on Cancel', async () => {
    const user = userEvent.setup()
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /\+ create custom/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /\+ create custom/i }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2, name: 'Create Study Material' })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => {
      expect(screen.queryByRole('heading', { level: 2, name: 'Create Study Material' })).not.toBeInTheDocument()
    })
  })

  // ── OAuth Callback ───────────────────────────────────────────
  it('handles google_connected search param', async () => {
    mockSearchParams.set('google_connected', 'true')
    mockGetStatus.mockResolvedValue({ connected: true })
    mockSyncCourses.mockResolvedValue({ message: 'Auto-synced!' })
    renderWithProviders(<StudentDashboard />)

    // After google_connected=true, auto-sync fires and status message changes to sync result
    await waitFor(() => {
      expect(mockSyncCourses).toHaveBeenCalled()
    })
    await waitFor(() => {
      expect(screen.getByText('Auto-synced!')).toBeInTheDocument()
    })
  })

  it('handles error search param', async () => {
    mockSearchParams.set('error', 'access_denied')
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText(/connection failed: access_denied/i)).toBeInTheDocument()
    })
  })

  // ── Course filter for study guides ───────────────────────────
  it('shows course filter when courses exist', async () => {
    mockCoursesList.mockResolvedValue([
      { id: 1, name: 'Biology' },
    ])
    mockListGuides.mockResolvedValue([
      { id: 1, title: 'Bio Notes', guide_type: 'study_guide', version: 1, course_id: 1, created_at: '2026-02-14T12:00:00Z' },
    ])
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Bio Notes')).toBeInTheDocument()
    })

    // Course filter select should be present
    expect(screen.getByDisplayValue('All Courses')).toBeInTheDocument()
  })
})
