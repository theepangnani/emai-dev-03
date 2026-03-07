import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'
import { createMockInvite } from '../test/mocks'

// ── Mocks ──────────────────────────────────────────────────────
const mockNavigate = vi.fn()
const mockTeachingList = vi.fn()
const mockTeachingManagement = vi.fn()
const mockGetStatus = vi.fn()
const mockGetConnectUrl = vi.fn()
const mockSyncCourses = vi.fn()
const mockGetTeacherAccounts = vi.fn()
const mockUpdateTeacherAccount = vi.fn()
const mockRemoveTeacherAccount = vi.fn()
const mockCoursesCreate = vi.fn()
const mockListSent = vi.fn()
const mockResend = vi.fn()
const mockInviteParent = vi.fn()

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Teacher User', role: 'teacher', roles: ['teacher'] },
    logout: vi.fn(),
    switchRole: vi.fn(),
  }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../api/client', () => ({
  coursesApi: {
    teachingList: (...args: any[]) => mockTeachingList(...args),
    teachingManagement: (...args: any[]) => mockTeachingManagement(...args),
    create: (...args: any[]) => mockCoursesCreate(...args),
  },
  googleApi: {
    getStatus: (...args: any[]) => mockGetStatus(...args),
    getConnectUrl: (...args: any[]) => mockGetConnectUrl(...args),
    syncCourses: (...args: any[]) => mockSyncCourses(...args),
    getTeacherAccounts: (...args: any[]) => mockGetTeacherAccounts(...args),
    updateTeacherAccount: (...args: any[]) => mockUpdateTeacherAccount(...args),
    removeTeacherAccount: (...args: any[]) => mockRemoveTeacherAccount(...args),
  },
  invitesApi: {
    listSent: (...args: any[]) => mockListSent(...args),
    resend: (...args: any[]) => mockResend(...args),
    inviteParent: (...args: any[]) => mockInviteParent(...args),
  },
  messagesApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }),
    listConversations: vi.fn().mockResolvedValue([]),
  },
  assignmentsApi: {
    list: vi.fn().mockResolvedValue([]),
  },
  courseContentsApi: {
    uploadFile: vi.fn().mockResolvedValue({}),
  },
  studyApi: {
    getSupportedFormats: vi.fn().mockResolvedValue({ formats: [] }),
    extractTextFromFile: vi.fn().mockResolvedValue({ text: '' }),
    checkDuplicate: vi.fn().mockResolvedValue({ exists: false }),
    generateGuide: vi.fn().mockResolvedValue({ id: 1 }),
    generateQuiz: vi.fn().mockResolvedValue({ id: 1 }),
    generateFlashcards: vi.fn().mockResolvedValue({ id: 1 }),
    generateFromFile: vi.fn().mockResolvedValue({ id: 1 }),
    generateFromTextAndImages: vi.fn().mockResolvedValue({ id: 1 }),
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

vi.mock('../hooks/useFeatureToggle', () => ({
  useFeature: () => true,
  useFeatureToggles: () => ({ google_classroom: true }),
}))

import { TeacherDashboard } from './TeacherDashboard'

function setupDefaults() {
  mockTeachingList.mockResolvedValue([])
  mockTeachingManagement.mockResolvedValue([])
  mockGetStatus.mockResolvedValue({ connected: false })
  mockGetTeacherAccounts.mockResolvedValue([])
  mockListSent.mockResolvedValue([])
}

// Helper to create a management-style course object (matches TeacherCourseManagement type)
function mockMgmtCourse(overrides: Record<string, any> = {}) {
  return {
    id: 1,
    name: 'Algebra I',
    description: null,
    subject: 'Math',
    google_classroom_id: null,
    classroom_type: null,
    teacher_id: 1,
    teacher_name: 'Teacher User',
    created_by_user_id: 1,
    is_private: false,
    is_default: false,
    student_count: 0,
    assignment_count: 0,
    material_count: 0,
    last_activity: null,
    source: 'manual',
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('TeacherDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupDefaults()
  })

  // ── Loading & Data ───────────────────────────────────────────
  it('renders My Classes quick action and course list after loading', async () => {
    mockTeachingList.mockResolvedValue([
      { id: 1, name: 'Algebra I', description: null, subject: 'Math', google_classroom_id: null, student_count: 0 },
      { id: 2, name: 'Geometry', description: 'Shapes', subject: null, google_classroom_id: 'gc-1', student_count: 0 },
    ])
    mockTeachingManagement.mockResolvedValue([
      mockMgmtCourse({ id: 1, name: 'Algebra I', subject: 'Math' }),
      mockMgmtCourse({ id: 2, name: 'Geometry', description: 'Shapes', subject: null, google_classroom_id: 'gc-1', source: 'google' }),
    ])
    renderWithProviders(<TeacherDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'My Classes' })).toBeInTheDocument()
    })
    // Courses appear in the Course Management section (loaded via teachingManagement)
    await waitFor(() => {
      expect(screen.getByText('Algebra I')).toBeInTheDocument()
    })
    expect(screen.getByText('Geometry')).toBeInTheDocument()
  })

  it('renders courses list after loading', async () => {
    mockTeachingList.mockResolvedValue([
      { id: 1, name: 'Algebra I', description: null, subject: 'Math', google_classroom_id: null },
      { id: 2, name: 'Geometry', description: 'All about shapes', subject: null, google_classroom_id: 'gc-1' },
    ])
    mockTeachingManagement.mockResolvedValue([
      mockMgmtCourse({ id: 1, name: 'Algebra I', subject: 'Math' }),
      mockMgmtCourse({ id: 2, name: 'Geometry', description: 'All about shapes', subject: null, google_classroom_id: 'gc-1', source: 'google' }),
    ])
    renderWithProviders(<TeacherDashboard />)

    // Wait for TeacherCourseManagement to load its data via teachingManagement()
    await waitFor(() => {
      expect(screen.getByText('Algebra I')).toBeInTheDocument()
    })
    expect(screen.getByText('Math')).toBeInTheDocument()
    expect(screen.getByText('Geometry')).toBeInTheDocument()
    expect(screen.getByText('All about shapes')).toBeInTheDocument()
    // Source badge and filter pill both show "Google Classroom"
    expect(screen.getAllByText('Google Classroom').length).toBeGreaterThanOrEqual(1)
  })

  it('shows empty state when no courses', async () => {
    renderWithProviders(<TeacherDashboard />)

    await waitFor(() => {
      expect(screen.getByText('No classes yet')).toBeInTheDocument()
    })
  })

  // ── Google Connection ────────────────────────────────────────
  it('shows "Google Classroom" action when not connected', async () => {
    renderWithProviders(<TeacherDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Google Classroom' })).toBeInTheDocument()
    })
  })

  it('shows "Sync Classes" action when Google is connected', async () => {
    mockGetStatus.mockResolvedValue({ connected: true })
    renderWithProviders(<TeacherDashboard />)

    await waitFor(() => {
      const syncButtons = screen.getAllByRole('button', { name: 'Sync Classes' })
      expect(syncButtons.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('handles Connect Google click', async () => {
    mockGetConnectUrl.mockResolvedValue({ authorization_url: 'https://accounts.google.com/auth' })
    const user = userEvent.setup()
    renderWithProviders(<TeacherDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Google Classroom' })).toBeInTheDocument()
    })

    // Mock window.location.href
    const originalLocation = window.location
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, href: '' },
      writable: true,
    })

    await user.click(screen.getByRole('button', { name: 'Google Classroom' }))

    await waitFor(() => {
      expect(mockGetConnectUrl).toHaveBeenCalled()
    })

    // Restore
    Object.defineProperty(window, 'location', { value: originalLocation, writable: true })
  })

  it('handles Sync Classes click', async () => {
    mockGetStatus.mockResolvedValue({ connected: true })
    mockSyncCourses.mockResolvedValue({})
    mockTeachingList
      .mockResolvedValueOnce([]) // initial load
      .mockResolvedValueOnce([{ id: 1, name: 'Synced Course', description: null, subject: null, google_classroom_id: 'gc-1' }]) // after sync
    mockTeachingManagement
      .mockResolvedValueOnce([]) // initial load
      .mockResolvedValueOnce([mockMgmtCourse({ id: 1, name: 'Synced Course', google_classroom_id: 'gc-1', source: 'google' })]) // after sync
    const user = userEvent.setup()
    renderWithProviders(<TeacherDashboard />)

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: 'Sync Classes' }).length).toBeGreaterThanOrEqual(1)
    })

    // Click the first Sync Classes button (in the card)
    await user.click(screen.getAllByRole('button', { name: 'Sync Classes' })[0])

    await waitFor(() => {
      expect(mockSyncCourses).toHaveBeenCalled()
    })
    await waitFor(() => {
      expect(screen.getByText('Synced Course')).toBeInTheDocument()
    })
  })

  // ── Create Class Modal ──────────────────────────────────────
  it('opens and closes create class modal', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TeacherDashboard />)

    // Wait for TeacherCourseManagement to finish loading (button appears after load)
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /\+ Create Class/i }).length).toBeGreaterThanOrEqual(1)
    }, { timeout: 3000 })

    const createButtons = screen.getAllByRole('button', { name: /\+ Create Class/i })
    await user.click(createButtons[0])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Class' })).toBeInTheDocument()
    })

    // Close modal via Cancel
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: 'Create Class' })).not.toBeInTheDocument()
    })
  })

  it('creates a class successfully', async () => {
    mockCoursesCreate.mockResolvedValue({ id: 10, name: 'New Course', description: null, subject: 'Science' })
    mockTeachingList
      .mockResolvedValueOnce([]) // initial load
      .mockResolvedValueOnce([{ id: 10, name: 'New Course', description: null, subject: 'Science', google_classroom_id: null }])
    mockTeachingManagement
      .mockResolvedValueOnce([]) // initial load
      .mockResolvedValueOnce([mockMgmtCourse({ id: 10, name: 'New Course', subject: 'Science' })]) // after create
    const user = userEvent.setup()
    renderWithProviders(<TeacherDashboard />)

    // Wait for TeacherCourseManagement to finish loading (button appears after load)
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /\+ Create Class/i }).length).toBeGreaterThanOrEqual(1)
    }, { timeout: 3000 })

    // Open modal - use first button (section header)
    await user.click(screen.getAllByRole('button', { name: /\+ Create Class/i })[0])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Class' })).toBeInTheDocument()
    })

    // Fill out form
    await user.type(screen.getByPlaceholderText('e.g. Algebra I'), 'New Course')
    await user.type(screen.getByPlaceholderText('e.g. Mathematics'), 'Science')

    // Submit
    await user.click(screen.getByRole('button', { name: 'Create Class' }))

    await waitFor(() => {
      expect(mockCoursesCreate).toHaveBeenCalledWith({
        name: 'New Course',
        description: undefined,
        subject: 'Science',
      })
    })
    await waitFor(() => {
      expect(screen.getByText('New Course')).toBeInTheDocument()
    })
  })

  it('shows error on create class failure', async () => {
    mockCoursesCreate.mockRejectedValue({
      response: { data: { detail: 'Course name already exists' } },
    })
    const user = userEvent.setup()
    renderWithProviders(<TeacherDashboard />)

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /\+ Create Class/i }).length).toBeGreaterThanOrEqual(1)
    }, { timeout: 3000 })

    await user.click(screen.getAllByRole('button', { name: /\+ Create Class/i })[0])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Class' })).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('e.g. Algebra I'), 'Dup Course')
    await user.click(screen.getByRole('button', { name: 'Create Class' }))

    await waitFor(() => {
      expect(screen.getByText('Course name already exists')).toBeInTheDocument()
    })
  })

  it('disables Create Class button when name is empty', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TeacherDashboard />)

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /\+ Create Class/i }).length).toBeGreaterThanOrEqual(1)
    }, { timeout: 3000 })

    await user.click(screen.getAllByRole('button', { name: /\+ Create Class/i })[0])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Class' })).toBeInTheDocument()
    })

    // The Create Class button inside modal should be disabled
    const submitBtn = screen.getByRole('button', { name: 'Create Class' })
    expect(submitBtn).toBeDisabled()
  })

  // ── Invite Parent Modal ──────────────────────────────────────
  // Helper: open the "More" dropdown and click "Invite Parents"
  async function openInviteParentViaMore(user: ReturnType<typeof userEvent.setup>) {
    // Wait for the More dropdown trigger to appear
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'More' })).toBeInTheDocument()
    })
    // Open "More" dropdown
    await user.click(screen.getByRole('button', { name: 'More' }))
    // Click "Invite Parents" in the dropdown
    await waitFor(() => {
      expect(screen.getByRole('menuitem', { name: 'Invite Parents' })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('menuitem', { name: 'Invite Parents' }))
  }

  it('opens invite parent modal from More dropdown', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TeacherDashboard />)

    await openInviteParentViaMore(user)

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2, name: 'Invite Parent' })).toBeInTheDocument()
    })
  })

  it('sends invite successfully', async () => {
    mockInviteParent.mockResolvedValue({
      action: 'invite_sent',
      invite_id: 99,
    })
    const user = userEvent.setup()
    renderWithProviders(<TeacherDashboard />)

    await openInviteParentViaMore(user)

    await waitFor(() => {
      expect(screen.getByPlaceholderText('parent@example.com')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('parent@example.com'), 'mom@example.com')
    await user.click(screen.getByRole('button', { name: 'Send Invitation' }))

    await waitFor(() => {
      expect(mockInviteParent).toHaveBeenCalledWith('mom@example.com')
    })
    await waitFor(() => {
      expect(screen.getByText(/invitation sent to mom@example.com/i)).toBeInTheDocument()
    })
  })

  it('shows message_sent result when parent is already registered', async () => {
    mockInviteParent.mockResolvedValue({
      action: 'message_sent',
      message: 'Message sent to Jane Doe',
      recipient_name: 'Jane Doe',
    })
    const user = userEvent.setup()
    renderWithProviders(<TeacherDashboard />)

    await openInviteParentViaMore(user)

    await waitFor(() => {
      expect(screen.getByPlaceholderText('parent@example.com')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('parent@example.com'), 'existing@example.com')
    await user.click(screen.getByRole('button', { name: 'Send Invitation' }))

    await waitFor(() => {
      expect(screen.getByText('Message sent to Jane Doe')).toBeInTheDocument()
    })
  })

  it('shows error on invite failure', async () => {
    mockInviteParent.mockRejectedValue({
      response: { data: { detail: 'Invalid email' } },
    })
    const user = userEvent.setup()
    renderWithProviders(<TeacherDashboard />)

    await openInviteParentViaMore(user)

    await waitFor(() => {
      expect(screen.getByPlaceholderText('parent@example.com')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('parent@example.com'), 'bad')
    await user.click(screen.getByRole('button', { name: 'Send Invitation' }))

    await waitFor(() => {
      expect(screen.getByText('Please enter a valid email address')).toBeInTheDocument()
    })
  })

  // ── Google Accounts ──────────────────────────────────────────
  it('shows Google Accounts section when connected', async () => {
    mockGetStatus.mockResolvedValue({ connected: true })
    mockGetTeacherAccounts.mockResolvedValue([
      { id: 1, google_email: 'teacher@gmail.com', display_name: 'Teacher', account_label: null, is_primary: true, last_sync_at: '2026-02-14T12:00:00Z' },
      { id: 2, google_email: 'alt@gmail.com', display_name: null, account_label: 'Work', is_primary: false, last_sync_at: null },
    ])
    renderWithProviders(<TeacherDashboard />)

    await waitFor(() => {
      expect(screen.getByText(/Google Accounts/)).toBeInTheDocument()
    })
    expect(screen.getByText('teacher@gmail.com')).toBeInTheDocument()
    expect(screen.getByText('Primary')).toBeInTheDocument()
    expect(screen.getByText('alt@gmail.com')).toBeInTheDocument()
    expect(screen.getByText('Work')).toBeInTheDocument()
  })

  it('handles remove Google account', async () => {
    mockGetStatus.mockResolvedValue({ connected: true })
    mockGetTeacherAccounts.mockResolvedValue([
      { id: 1, google_email: 'teacher@gmail.com', display_name: null, account_label: null, is_primary: true, last_sync_at: null },
      { id: 2, google_email: 'alt@gmail.com', display_name: null, account_label: null, is_primary: false, last_sync_at: null },
    ])
    mockRemoveTeacherAccount.mockResolvedValue({})
    const user = userEvent.setup()
    renderWithProviders(<TeacherDashboard />)

    await waitFor(() => {
      expect(screen.getByText('alt@gmail.com')).toBeInTheDocument()
    })

    const removeButtons = screen.getAllByRole('button', { name: /remove/i })
    // Click the second remove button (for alt account) - there are two
    await user.click(removeButtons[removeButtons.length - 1])

    await waitFor(() => {
      expect(mockRemoveTeacherAccount).toHaveBeenCalledWith(2)
    })
    await waitFor(() => {
      expect(screen.queryByText('alt@gmail.com')).not.toBeInTheDocument()
    })
  })

  it('handles set primary Google account', async () => {
    mockGetStatus.mockResolvedValue({ connected: true })
    mockGetTeacherAccounts.mockResolvedValue([
      { id: 1, google_email: 'teacher@gmail.com', display_name: null, account_label: null, is_primary: true, last_sync_at: null },
      { id: 2, google_email: 'alt@gmail.com', display_name: null, account_label: null, is_primary: false, last_sync_at: null },
    ])
    mockUpdateTeacherAccount.mockResolvedValue({})
    const user = userEvent.setup()
    renderWithProviders(<TeacherDashboard />)

    await waitFor(() => {
      expect(screen.getByText('alt@gmail.com')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /set primary/i }))

    await waitFor(() => {
      expect(mockUpdateTeacherAccount).toHaveBeenCalledWith(2, undefined, true)
    })
  })

  // ── Sent Invites ──────────────────────────────────────────
  it('shows sent invites section', async () => {
    const futureDate = new Date(Date.now() + 86400000 * 7).toISOString()
    mockListSent.mockResolvedValue([
      createMockInvite({ id: 1, email: 'pending@example.com', invite_type: 'student', accepted_at: null, expires_at: futureDate }),
      createMockInvite({ id: 2, email: 'accepted@example.com', invite_type: 'student', accepted_at: '2026-02-13T12:00:00Z', status: 'accepted', expires_at: futureDate }),
    ])
    renderWithProviders(<TeacherDashboard />)

    await waitFor(() => {
      expect(screen.getByText(/Sent Invites/)).toBeInTheDocument()
    })
    expect(screen.getByText('pending@example.com')).toBeInTheDocument()
    // All invites are shown (both pending and accepted)
    expect(screen.getByText('accepted@example.com')).toBeInTheDocument()
  })

  it('handles resend invite', async () => {
    const futureDate = new Date(Date.now() + 86400000 * 7).toISOString()
    mockListSent.mockResolvedValue([
      createMockInvite({ id: 5, email: 'pending@example.com', invite_type: 'student', accepted_at: null, status: 'pending', expires_at: futureDate }),
    ])
    const updatedInvite = createMockInvite({ id: 5, email: 'pending@example.com', invite_type: 'student', status: 'pending', expires_at: futureDate, last_resent_at: new Date().toISOString() })
    mockResend.mockResolvedValue(updatedInvite)
    const user = userEvent.setup()
    renderWithProviders(<TeacherDashboard />)

    await waitFor(() => {
      expect(screen.getByText('pending@example.com')).toBeInTheDocument()
    })

    // Click the Resend button inside the sent-invite-actions section
    const resendBtn = document.querySelector('.sent-invite-actions .text-btn') as HTMLElement
    expect(resendBtn).toBeTruthy()
    await user.click(resendBtn)

    await waitFor(() => {
      expect(mockResend).toHaveBeenCalledWith(5)
    })
  })

  // ── Navigation cards ─────────────────────────────────────────
  it('navigates to messages on Messages quick action click', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TeacherDashboard />)

    // Wait specifically for the rqa-card Messages button (not just the sidebar nav item)
    let messagesBtn!: HTMLElement
    await waitFor(() => {
      const card = Array.from(document.querySelectorAll('.rqa-card')).find(
        el => el.textContent?.includes('Messages')
      ) as HTMLElement | undefined
      expect(card).toBeTruthy()
      messagesBtn = card!
    })
    await user.click(messagesBtn)

    expect(mockNavigate).toHaveBeenCalledWith('/messages')
  })
})
