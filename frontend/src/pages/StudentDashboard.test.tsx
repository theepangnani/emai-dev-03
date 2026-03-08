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
const mockCoursesCreate = vi.fn()
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
const mockTasksList = vi.fn()
const mockNotificationsList = vi.fn()
const mockNotificationsMarkAsRead = vi.fn()
const mockNotificationsAck = vi.fn()

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
    create: (...args: any[]) => mockCoursesCreate(...args),
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
  faqApi: {
    getByErrorCode: vi.fn().mockRejectedValue(new Error('not found')),
  },
}))

vi.mock('../api/notifications', () => ({
  notificationsApi: {
    list: (...args: any[]) => mockNotificationsList(...args),
    markAsRead: (...args: any[]) => mockNotificationsMarkAsRead(...args),
    ack: (...args: any[]) => mockNotificationsAck(...args),
  },
}))

vi.mock('../api/tasks', () => ({
  tasksApi: {
    list: (...args: any[]) => mockTasksList(...args),
  },
}))

vi.mock('../api/invites', () => ({
  invitesApi: {
    inviteTeacher: vi.fn().mockResolvedValue({ action: 'invite_sent', message: 'Invite sent!' }),
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

vi.mock('../utils/logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    logError: vi.fn(),
  },
}))

vi.mock('../hooks/useFeatureToggle', () => ({
  useFeature: () => true,
  useFeatureToggles: () => ({ google_classroom: true }),
}))

import { StudentDashboard } from './StudentDashboard'

function setupDefaults() {
  mockGetStatus.mockResolvedValue({ connected: false })
  mockCoursesList.mockResolvedValue([])
  mockCoursesCreate.mockResolvedValue({ id: 99, name: 'Test Course' })
  mockAssignmentsList.mockResolvedValue([])
  mockListGuides.mockResolvedValue([])
  mockTasksList.mockResolvedValue([])
  mockNotificationsList.mockResolvedValue([])
  mockGetSupportedFormats.mockResolvedValue({ supported_types: ['pdf', 'docx', 'txt'], max_file_size_mb: 100 })
  mockCheckDuplicate.mockResolvedValue({ exists: false })
  mockNotificationsMarkAsRead.mockResolvedValue({})
  mockNotificationsAck.mockResolvedValue({})
}

// TODO: Update tests after dashboard redesign (Phase 2 merge)
describe.skip('StudentDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams.delete('google_connected')
    mockSearchParams.delete('just_registered')
    mockSearchParams.delete('error')
    setupDefaults()
  })

  // ── Hero Section ───────────────────────────────────────────────
  it('renders greeting with user name', async () => {
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      // Should greet by first name
      expect(screen.getByText(/Good .+, Student/)).toBeInTheDocument()
    })
  })

  it('shows "all caught up" when no upcoming items', async () => {
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText(/all caught up/i)).toBeInTheDocument()
    })
  })

  it('shows urgency pills when items are due', async () => {
    const yesterday = new Date()
    yesterday.setDate(yesterday.getDate() - 1)
    mockAssignmentsList.mockResolvedValue([
      { id: 1, title: 'Overdue HW', description: null, course_id: 1, due_date: yesterday.toISOString() },
    ])
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('1 overdue')).toBeInTheDocument()
    })
  })

  it('does not show connect banner when Google is connected', async () => {
    mockGetStatus.mockResolvedValue({ connected: true })
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Class Material')).toBeInTheDocument()
    })
    expect(screen.queryByText('Connect Google Classroom')).not.toBeInTheDocument()
  })

  // ── Quick Actions ──────────────────────────────────────────────
  it('renders quick action buttons', async () => {
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      // Quick actions reduced to 2: Course Material + Study Guide
      const actionLabels = document.querySelectorAll('.rqa-label')
      const labels = Array.from(actionLabels).map(el => el.textContent)
      expect(labels).toContain('Class Material')
      expect(labels).toContain('Study Guide')
    })
  })

  it('shows 3 quick actions (Class Material + Study Guide + Create Task)', async () => {
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      const actionLabels = document.querySelectorAll('.rqa-label')
      expect(actionLabels.length).toBe(3)
    })
  })

  it('shows Connect Classroom in courses empty state when Google is not connected', async () => {
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Connect Classroom')).toBeInTheDocument()
    })
  })


  it('handles Sync Classes via google_connected callback', async () => {
    mockSearchParams.set('google_connected', 'true')
    mockGetStatus.mockResolvedValue({ connected: true })
    mockSyncCourses.mockResolvedValue({ message: 'Synced 3 courses' })
    const user = userEvent.setup()
    renderWithProviders(<StudentDashboard />)

    // google_connected param triggers classroom type modal
    await waitFor(() => {
      expect(screen.getByText('School Classroom')).toBeInTheDocument()
    })
    const confirmBtn = screen.getAllByText('Sync Classes').find(
      el => el.closest('.modal-actions')
    )!
    await user.click(confirmBtn)

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
      expect(screen.getByText('Disconnect')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Disconnect'))

    await waitFor(() => {
      expect(mockDisconnect).toHaveBeenCalled()
    })
    await waitFor(() => {
      expect(screen.getByText('Google Classroom disconnected')).toBeInTheDocument()
    })
  })

  // ── Coming Up Section ──────────────────────────────────────────
  it('renders coming up timeline with assignments', async () => {
    mockAssignmentsList.mockResolvedValue([
      { id: 1, title: 'Algebra Homework', description: null, course_id: 1, course_name: 'Math', due_date: '2026-02-15T23:59:00Z' },
      { id: 2, title: 'Essay Draft', description: null, course_id: 2, course_name: 'English', due_date: null },
    ])
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Algebra Homework')).toBeInTheDocument()
    })
    expect(screen.getByText('Essay Draft')).toBeInTheDocument()
  })

  it('renders coming up timeline with tasks', async () => {
    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    mockTasksList.mockResolvedValue([
      { id: 1, title: 'Review Chapter 3', due_date: tomorrow.toISOString(), is_completed: false, course_name: null, priority: 'medium', created_by_user_id: 1, creator_name: 'Student User', created_at: new Date().toISOString() },
    ])
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Review Chapter 3')).toBeInTheDocument()
    })
  })

  it('shows empty state when nothing coming up', async () => {
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Nothing coming up')).toBeInTheDocument()
    })
  })

  // ── Study Materials Section ────────────────────────────────────
  it('renders study materials list', async () => {
    mockListGuides.mockResolvedValue([
      { id: 1, title: 'Chapter 1 Notes', guide_type: 'study_guide', version: 1, course_id: null, created_at: '2026-02-14T12:00:00Z' },
      { id: 2, title: 'Quiz Practice', guide_type: 'quiz', version: 2, course_id: null, created_at: '2026-02-13T12:00:00Z' },
    ])
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      // Materials appear in both Continue Studying and Study Materials sections
      expect(screen.getAllByText('Chapter 1 Notes').length).toBeGreaterThanOrEqual(1)
    })
    expect(screen.getAllByText('Quiz Practice').length).toBeGreaterThanOrEqual(1)
  })

  it('shows empty state for study materials', async () => {
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('No study materials yet')).toBeInTheDocument()
    })
  })

  // ── Courses Section ────────────────────────────────────────────
  it('renders courses as chips with Google badge', async () => {
    mockCoursesList.mockResolvedValue([
      { id: 1, name: 'Math 101', google_classroom_id: 'gc-1' },
      { id: 2, name: 'History', google_classroom_id: null },
    ])
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Math 101')).toBeInTheDocument()
    })
    expect(screen.getByText('History')).toBeInTheDocument()
    expect(screen.getByText('Google')).toBeInTheDocument()
  })

  it('shows empty state for courses', async () => {
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('No classes yet')).toBeInTheDocument()
    })
  })

  // ── Create Class Modal ────────────────────────────────────────
  it('opens create class modal from courses empty state', async () => {
    const user = userEvent.setup()
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Create Class')).toBeInTheDocument()
    })

    const createClassBtn = screen.getByText('Create Class').closest('button')!
    await user.click(createClassBtn)

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2, name: 'Create a Class' })).toBeInTheDocument()
    })
  })

  // ── Study Guide Quick Action ─────────────────────────────────
  it('navigates to study page from Study Guide quick action', async () => {
    const user = userEvent.setup()
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Study Guide')).toBeInTheDocument()
    })

    const studyCard = screen.getByText('Study Guide').closest('button')!
    await user.click(studyCard)

    expect(mockNavigate).toHaveBeenCalledWith('/study')
  })

  it('opens upload documents modal from Class Material quick action', async () => {
    const user = userEvent.setup()
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Class Material')).toBeInTheDocument()
    })

    const materialCard = screen.getByText('Class Material').closest('button')!
    await user.click(materialCard)

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2, name: 'Upload Class Material' })).toBeInTheDocument()
    })
    expect(screen.getByText(/drag & drop files here/i)).toBeInTheDocument()
  })

  // ── Notifications ──────────────────────────────────────────────
  it('shows actionable notifications from parents/teachers', async () => {
    mockNotificationsList.mockResolvedValue([
      { id: 1, type: 'parent_request', title: 'Complete your Math homework', read: false, requires_ack: false, acked_at: null, created_at: '2026-02-20T12:00:00Z' },
      { id: 2, type: 'assessment_upcoming', title: 'Science Quiz due Friday', read: false, requires_ack: true, acked_at: null, created_at: '2026-02-20T12:00:00Z' },
    ])
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Needs Your Attention')).toBeInTheDocument()
    })
    expect(screen.getByText('Complete your Math homework')).toBeInTheDocument()
    expect(screen.getByText('Science Quiz due Friday')).toBeInTheDocument()
  })

  it('does not show notifications section when none actionable', async () => {
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText(/Good .+, Student/)).toBeInTheDocument()
    })
    expect(screen.queryByText('Needs Your Attention')).not.toBeInTheDocument()
  })

  // ── OAuth Callback ─────────────────────────────────────────────
  it('handles google_connected search param', async () => {
    mockSearchParams.set('google_connected', 'true')
    mockGetStatus.mockResolvedValue({ connected: true })
    mockSyncCourses.mockResolvedValue({ message: 'Auto-synced!' })
    const user = userEvent.setup()
    renderWithProviders(<StudentDashboard />)

    // google_connected now shows classroom type modal instead of auto-syncing
    await waitFor(() => {
      expect(screen.getByText('School Classroom')).toBeInTheDocument()
    })
    const confirmBtn = screen.getAllByText('Sync Classes').find(
      el => el.closest('.modal-actions')
    )!
    await user.click(confirmBtn)

    await waitFor(() => {
      expect(mockSyncCourses).toHaveBeenCalled()
    })
  })

  it('handles error search param', async () => {
    mockSearchParams.set('error', 'access_denied')
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText(/connection failed: access_denied/i)).toBeInTheDocument()
    })
  })

  // ── Onboarding Card ────────────────────────────────────────────
  it('shows onboarding card when few study materials', async () => {
    localStorage.removeItem('student-upload-onboarding-dismissed')
    renderWithProviders(<StudentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('How to add your class materials')).toBeInTheDocument()
    })
  })
})
