import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'
import {
  createMockChild,
  createMockChildHighlight,
  createMockParentDashboard,
  createMockChildOverview,
  createMockInvite,
} from '../test/mocks'

// ── Mocks ──────────────────────────────────────────────────────
const mockNavigate = vi.fn()
const mockSearchParams = new URLSearchParams()
const mockSetSearchParams = vi.fn()

const mockGetDashboard = vi.fn()
const mockGetChildOverview = vi.fn()
const mockCreateChild = vi.fn()
const mockLinkChild = vi.fn()
const mockUpdateChild = vi.fn()
const mockDiscoverViaGoogle = vi.fn()
const mockLinkChildrenBulk = vi.fn()
const mockGetConnectUrl = vi.fn()
const mockDisconnect = vi.fn()
const mockInviteCreate = vi.fn()
const mockListSent = vi.fn()
const mockResend = vi.fn()
const mockTasksCreate = vi.fn()
const mockTasksUpdate = vi.fn()
const mockTasksDelete = vi.fn()
const mockGetSupportedFormats = vi.fn()
const mockCheckDuplicate = vi.fn()
const mockListGuides = vi.fn()
const mockGenerateFromFile = vi.fn()
const mockGenerateGuide = vi.fn()
const mockCoursesGetDefault = vi.fn()
const mockCourseContentsUploadFile = vi.fn()

vi.mock('../api/courses', () => ({
  coursesApi: { getDefault: (...args: any[]) => mockCoursesGetDefault(...args), list: vi.fn().mockResolvedValue([]) },
  courseContentsApi: {
    uploadFile: (...args: any[]) => mockCourseContentsUploadFile(...args),
    create: vi.fn().mockResolvedValue({}),
    listAll: vi.fn().mockResolvedValue([]),
  },
  assignmentsApi: { list: vi.fn().mockResolvedValue([]) },
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Parent User', role: 'parent', roles: ['parent'] },
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
  parentApi: {
    getDashboard: (...args: any[]) => mockGetDashboard(...args),
    getChildOverview: (...args: any[]) => mockGetChildOverview(...args),
    createChild: (...args: any[]) => mockCreateChild(...args),
    linkChild: (...args: any[]) => mockLinkChild(...args),
    updateChild: (...args: any[]) => mockUpdateChild(...args),
    discoverViaGoogle: (...args: any[]) => mockDiscoverViaGoogle(...args),
    linkChildrenBulk: (...args: any[]) => mockLinkChildrenBulk(...args),
  },
  googleApi: {
    getConnectUrl: (...args: any[]) => mockGetConnectUrl(...args),
    disconnect: (...args: any[]) => mockDisconnect(...args),
  },
  invitesApi: {
    create: (...args: any[]) => mockInviteCreate(...args),
    listSent: (...args: any[]) => mockListSent(...args),
    resend: (...args: any[]) => mockResend(...args),
  },
  studyApi: {
    getSupportedFormats: (...args: any[]) => mockGetSupportedFormats(...args),
    checkDuplicate: (...args: any[]) => mockCheckDuplicate(...args),
    listGuides: (...args: any[]) => mockListGuides(...args),
    generateFromFile: (...args: any[]) => mockGenerateFromFile(...args),
    generateGuide: (...args: any[]) => mockGenerateGuide(...args),
  },
  tasksApi: {
    create: (...args: any[]) => mockTasksCreate(...args),
    update: (...args: any[]) => mockTasksUpdate(...args),
    delete: (...args: any[]) => mockTasksDelete(...args),
    remind: vi.fn().mockResolvedValue({ success: true, reminded_at: new Date().toISOString() }),
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

vi.mock('../components/calendar/CalendarView', () => ({
  CalendarView: ({ assignments }: any) => (
    <div data-testid="calendar-view">Calendar ({assignments.length} items)</div>
  ),
}))

vi.mock('../components/SetupChecklist', () => ({
  SetupChecklist: () => <div data-testid="setup-checklist" />,
}))

vi.mock('../components/GoogleClassroomPrompt', () => ({
  GoogleClassroomPrompt: () => <div data-testid="google-classroom-prompt" />,
}))

vi.mock('../components/RoleQuickActions', () => ({
  RoleQuickActions: ({ actions }: { actions: Array<{ label: string; onClick: () => void }> }) => (
    <div data-testid="quick-action-bar">
      {actions.map((a: any) => (
        <button key={a.label} onClick={a.onClick}>{a.label}</button>
      ))}
    </div>
  ),
}))

vi.mock('./StudyGuidesPage', () => ({
  queueStudyGeneration: vi.fn(),
}))

import { ParentDashboard } from './ParentDashboard'

const child1 = createMockChild({
  student_id: 100,
  user_id: 1100,
  full_name: 'Alex Smith',
  grade_level: 5,
  course_count: 3,
  active_task_count: 2,
})

const child2 = createMockChild({
  student_id: 200,
  user_id: 1200,
  full_name: 'Jamie Smith',
  grade_level: 8,
  course_count: 4,
  active_task_count: 1,
})

const highlight1 = createMockChildHighlight({
  student_id: 100,
  user_id: 1100,
  full_name: 'Alex Smith',
  grade_level: 5,
  overdue_count: 1,
  due_today_count: 2,
  upcoming_count: 3,
  courses: [{ id: 10, name: 'Math' }] as any,
  overdue_items: [{ title: 'Homework 1', course_name: 'Math' }] as any,
  due_today_items: [],
})

const highlight2 = createMockChildHighlight({
  student_id: 200,
  user_id: 1200,
  full_name: 'Jamie Smith',
  grade_level: 8,
  overdue_count: 0,
  due_today_count: 0,
  courses: [{ id: 20, name: 'Science' }] as any,
})

function defaultDashboard() {
  return createMockParentDashboard({
    children: [child1],
    child_highlights: [highlight1],
    google_connected: false,
    unread_messages: 2,
    total_overdue: 1,
    total_due_today: 2,
    total_tasks: 5,
    all_assignments: [],
    all_tasks: [],
  })
}

function setupDefaults() {
  mockGetDashboard.mockResolvedValue(defaultDashboard())
  mockGetChildOverview.mockResolvedValue(
    createMockChildOverview({ student_id: 100, full_name: 'Alex Smith', courses: [], assignments: [] }),
  )
  mockListSent.mockResolvedValue([])
  mockGetSupportedFormats.mockResolvedValue({ supported_types: ['pdf', 'docx', 'txt'], max_file_size_mb: 100 })
  mockListGuides.mockResolvedValue([])
}

describe('ParentDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams.delete('google_connected')
    setupDefaults()
  })

  // ── No Children State ────────────────────────────────────────
  it('shows empty state when no children', async () => {
    mockGetDashboard.mockResolvedValue(
      createMockParentDashboard({ children: [], child_highlights: [] }),
    )
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Welcome to ClassBridge!')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /Get Started/ })).toBeInTheDocument()
  })

  // ── Dashboard with Children ──────────────────────────────────
  it('renders student detail panel', async () => {
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      // With 1 child, auto-selects Alex Smith → "Alex Smith's Details"
      // Text appears in both CollapsibleSection title and StudentDetailPanel header
      expect(screen.getAllByText(/Alex Smith's Details/).length).toBeGreaterThanOrEqual(1)
    })
  })

  it('renders child tab with name and grade', async () => {
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      // "Alex Smith" appears in both child tab and highlight card
      expect(screen.getAllByText('Alex Smith').length).toBeGreaterThanOrEqual(1)
    })
    expect(screen.getAllByText('Grade 5').length).toBeGreaterThanOrEqual(1)
  })

  it('renders child tabs when multiple children', async () => {
    mockGetDashboard.mockResolvedValue(
      createMockParentDashboard({
        children: [child1, child2],
        child_highlights: [highlight1, highlight2],
      }),
    )
    renderWithProviders(<ParentDashboard />)

    // Names appear in both child tabs and highlight cards
    await waitFor(() => {
      expect(screen.getAllByText('Alex Smith').length).toBeGreaterThanOrEqual(1)
    })
    expect(screen.getAllByText('Jamie Smith').length).toBeGreaterThanOrEqual(1)
  })

  it('renders student detail panel with tasks section', async () => {
    mockGetDashboard.mockResolvedValue(
      createMockParentDashboard({
        children: [child1, child2],
        child_highlights: [highlight1, highlight2],
      }),
    )
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      // StudentDetailPanel shows Tasks section header
      expect(screen.getAllByText('Tasks').length).toBeGreaterThanOrEqual(1)
    })
  })

  // ── Alert Banner Navigation ─────────────────────────────────
  it('does not show overdue alert banner (overdue shown in Today Focus only)', async () => {
    mockGetDashboard.mockResolvedValue(
      createMockParentDashboard({
        children: [child1],
        child_highlights: [highlight1],
        all_tasks: [{ id: 1, title: 'Late HW', due_date: '2020-01-01', is_completed: false, archived_at: null, created_by_user_id: 1, assigned_to_user_id: 1100, assignee_name: 'Alex Smith', creator_name: 'Parent', description: null, priority: null, category: null, completed_at: null, course_id: null, course_content_id: null, study_guide_id: null, course_name: null, course_content_title: null, study_guide_title: null, study_guide_type: null, created_at: '2020-01-01', updated_at: null }],
      }),
    )
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.queryByText(/overdue item/i)).not.toBeInTheDocument()
    })
  })

  // ── Calendar moved to TasksPage ──────────────────────────────

  // ── Quick Action Cards ────────────────────────────────────
  it('renders quick action cards for Class Material and Create Task', async () => {
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Class Material')).toBeInTheDocument()
    })
    expect(screen.getAllByText('Create Task').length).toBeGreaterThanOrEqual(1)
  })

  it('opens study modal from Class Material action card', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Class Material')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Class Material'))

    await waitFor(() => {
      // Study material modal should open
      expect(screen.getByRole('heading', { level: 2, name: 'Upload Documents' })).toBeInTheDocument()
    })
  })

  // ── Add Child Modal — Create New Tab ─────────────────────────
  it('opens Add Child modal with Create New tab', async () => {
    mockGetDashboard.mockResolvedValue(
      createMockParentDashboard({ children: [], child_highlights: [] }),
    )
    const user = userEvent.setup()
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Get Started/ })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /Get Started/ }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2, name: 'Add Child' })).toBeInTheDocument()
    })
    expect(screen.getByText('Create New')).toBeInTheDocument()
    expect(screen.getByText('Link by Email')).toBeInTheDocument()
    expect(screen.getByText('Google Classroom')).toBeInTheDocument()
  })

  it('creates a child successfully', async () => {
    mockGetDashboard
      .mockResolvedValueOnce(createMockParentDashboard({ children: [], child_highlights: [] }))
      .mockResolvedValueOnce(defaultDashboard())
    mockCreateChild.mockResolvedValue({ student_id: 100, invite_link: null })
    const user = userEvent.setup()
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Get Started/ })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /Get Started/ }))

    await waitFor(() => {
      expect(screen.getByPlaceholderText('e.g. Alex Smith')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('e.g. Alex Smith'), 'New Kid')
    await user.click(screen.getByRole('button', { name: 'Add Child' }))

    await waitFor(() => {
      expect(mockCreateChild).toHaveBeenCalledWith('New Kid', 'guardian', undefined)
    })
  })

  it('shows invite link after creating a child', async () => {
    mockGetDashboard
      .mockResolvedValueOnce(createMockParentDashboard({ children: [], child_highlights: [] }))
      .mockResolvedValueOnce(defaultDashboard())
    mockCreateChild.mockResolvedValue({ student_id: 100, invite_link: 'https://example.com/invite/abc' })
    const user = userEvent.setup()
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Get Started/ })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /Get Started/ }))

    await waitFor(() => {
      expect(screen.getByPlaceholderText('e.g. Alex Smith')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('e.g. Alex Smith'), 'New Kid')
    await user.click(screen.getByRole('button', { name: 'Add Child' }))

    await waitFor(() => {
      expect(screen.getByText(/child added successfully/i)).toBeInTheDocument()
    })
    expect(screen.getByText('https://example.com/invite/abc')).toBeInTheDocument()
  })

  it('shows error on create child failure', async () => {
    mockGetDashboard.mockResolvedValue(
      createMockParentDashboard({ children: [], child_highlights: [] }),
    )
    mockCreateChild.mockRejectedValue({
      response: { data: { detail: 'Child already exists' } },
    })
    const user = userEvent.setup()
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Get Started/ })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /Get Started/ }))

    await waitFor(() => {
      expect(screen.getByPlaceholderText('e.g. Alex Smith')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('e.g. Alex Smith'), 'Dup Kid')
    await user.click(screen.getByRole('button', { name: 'Add Child' }))

    await waitFor(() => {
      expect(screen.getByText('Child already exists')).toBeInTheDocument()
    })
  })

  // ── Add Child Modal — Link by Email Tab ──────────────────────
  it('links child by email', async () => {
    mockGetDashboard
      .mockResolvedValueOnce(createMockParentDashboard({ children: [], child_highlights: [] }))
      .mockResolvedValueOnce(defaultDashboard())
    mockLinkChild.mockResolvedValue({ invite_link: null })
    const user = userEvent.setup()
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Get Started/ })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /Get Started/ }))

    await waitFor(() => {
      expect(screen.getByText('Link by Email')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Link by Email'))
    await user.type(screen.getByPlaceholderText('child@school.edu'), 'kid@school.edu')
    await user.click(screen.getByRole('button', { name: 'Link Child' }))

    await waitFor(() => {
      // Third arg is linkName.trim() || undefined — empty name becomes undefined
      expect(mockLinkChild).toHaveBeenCalledWith('kid@school.edu', 'guardian', undefined)
    })
  })

  // ── Add Child Modal — Google Classroom Tab ───────────────────
  it('shows Google connect prompt when not connected', async () => {
    mockGetDashboard.mockResolvedValue(
      createMockParentDashboard({ children: [], child_highlights: [], google_connected: false }),
    )
    const user = userEvent.setup()
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Get Started/ })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /Get Started/ }))
    await user.click(screen.getByText('Google Classroom'))

    await waitFor(() => {
      // "Connect Google Account" appears as both h3 heading and button
      expect(screen.getByRole('button', { name: 'Connect Google Account' })).toBeInTheDocument()
    })
  })

  // ── Pending Invites ──────────────────────────────────────────
  it('shows pending invites in alert banner', async () => {
    const futureDate = new Date(Date.now() + 86400000 * 7).toISOString()
    mockListSent.mockResolvedValue([
      createMockInvite({ id: 1, email: 'pending@example.com', accepted_at: null, expires_at: futureDate }),
    ])
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.getAllByText(/pending invite/i).length).toBeGreaterThanOrEqual(1)
    })
    expect(screen.getByText('pending@example.com')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Resend' })).toBeInTheDocument()
  })

  it('resends invite', async () => {
    const futureDate = new Date(Date.now() + 86400000 * 7).toISOString()
    mockListSent.mockResolvedValue([
      createMockInvite({ id: 5, email: 'pending@example.com', accepted_at: null, expires_at: futureDate }),
    ])
    mockResend.mockResolvedValue(
      createMockInvite({ id: 5, email: 'pending@example.com', expires_at: futureDate }),
    )
    const user = userEvent.setup()
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Resend' })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Resend' }))

    await waitFor(() => {
      expect(mockResend).toHaveBeenCalledWith(5)
    })
  })

  // Edit child modal is now accessed from the My Kids page, not the dashboard

  // ── Study Tools Modal ────────────────────────────────────────
  it('opens study tools modal from Course Material action card', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Class Material')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Class Material'))

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2, name: 'Upload Documents' })).toBeInTheDocument()
    })
  })

  it('shows file drop zone and text area simultaneously in study modal (#891)', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Class Material')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Class Material'))

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2, name: 'Upload Documents' })).toBeInTheDocument()
      // File drop zone and text area render together with the modal
      expect(screen.getByText(/Drag & drop files here/)).toBeInTheDocument()
      expect(screen.getByPlaceholderText(/Paste notes/)).toBeInTheDocument()
    })
    // Mode toggle buttons should NOT exist
    expect(screen.queryByText('Paste Text')).not.toBeInTheDocument()
    expect(screen.queryByText('Upload File')).not.toBeInTheDocument()
  })

  // ── Dashboard loads successfully ─────────────────────────────
  it('loads dashboard data and renders child name', async () => {
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => {
      expect(screen.getAllByText('Alex Smith').length).toBeGreaterThanOrEqual(1)
    })
  })

  // ── Regression: modal closes immediately on submit (#1010) ───
  it('closes Upload Documents modal immediately when Generate is clicked with a file (#1010)', async () => {
    // generateFromFile resolves slowly — modal must NOT wait for it
    mockGenerateFromFile.mockImplementation(
      () => new Promise(resolve => setTimeout(() => resolve({ id: 99, guide_type: 'study_guide' }), 500)),
    )
    mockCoursesGetDefault.mockResolvedValue({ id: 1, name: 'Default' })

    const user = userEvent.setup()
    renderWithProviders(<ParentDashboard />)

    await waitFor(() => expect(screen.getByText('Class Material')).toBeInTheDocument())
    await user.click(screen.getByText('Class Material'))
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 2, name: 'Upload Documents' })).toBeInTheDocument(),
    )

    // Attach a file and select Study Guide
    const file = new File(['content'], 'notes.pdf', { type: 'application/pdf' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, file)

    await user.click(screen.getByLabelText('Study Guide'))

    await user.click(screen.getByRole('button', { name: /Upload & Generate/i }))

    // Modal must close immediately — NOT stay open showing "Generating..."
    await waitFor(() =>
      expect(screen.queryByRole('heading', { level: 2, name: 'Upload Documents' })).not.toBeInTheDocument(),
    )
  })
})
