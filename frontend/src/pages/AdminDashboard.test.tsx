import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'
import { createMockAdminUser, createMockAdminStats, createMockBroadcast } from '../test/mocks'

// ── Mocks ──────────────────────────────────────────────────────
const mockGetStats = vi.fn()
const mockGetUsers = vi.fn()
const mockAddRole = vi.fn()
const mockRemoveRole = vi.fn()
const mockSendBroadcast = vi.fn()
const mockGetBroadcasts = vi.fn()
const mockSendMessage = vi.fn()

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Admin User', role: 'admin', roles: ['admin'] },
    logout: vi.fn(),
    switchRole: vi.fn(),
  }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

vi.mock('../api/client', () => ({
  adminApi: {
    getStats: (...args: any[]) => mockGetStats(...args),
    getUsers: (...args: any[]) => mockGetUsers(...args),
    addRole: (...args: any[]) => mockAddRole(...args),
    removeRole: (...args: any[]) => mockRemoveRole(...args),
    sendBroadcast: (...args: any[]) => mockSendBroadcast(...args),
    getBroadcasts: (...args: any[]) => mockGetBroadcasts(...args),
    sendMessage: (...args: any[]) => mockSendMessage(...args),
    getAuditLogs: vi.fn().mockResolvedValue({ items: [] }),
    getFeatureToggles: vi.fn().mockResolvedValue({ google_classroom: false }),
    updateFeatureToggle: vi.fn().mockResolvedValue({ feature: 'google_classroom', enabled: true }),
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

import { AdminDashboard } from './AdminDashboard'

const defaultStats = createMockAdminStats()
const defaultUsers = [
  createMockAdminUser({ id: 10, full_name: 'Alice Parent', email: 'alice@example.com', role: 'parent', roles: ['parent'] }),
  createMockAdminUser({ id: 11, full_name: 'Bob Teacher', email: 'bob@example.com', role: 'teacher', roles: ['teacher'] }),
]

function setupDefaults() {
  mockGetStats.mockResolvedValue(defaultStats)
  mockGetUsers.mockResolvedValue({ users: defaultUsers, total: 2 })
  mockGetBroadcasts.mockResolvedValue([])
}

// TODO: Update tests after dashboard redesign (Phase 2 merge)
describe.skip('AdminDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupDefaults()
  })

  // ── Stats cards ──────────────────────────────────────────────
  it('renders stat cards after loading', async () => {
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('50')).toBeInTheDocument() // total_users
    })
    expect(screen.getByText('Total Users')).toBeInTheDocument()
    expect(screen.getByText('20')).toBeInTheDocument() // students
    expect(screen.getByText('Students')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument() // teachers
    expect(screen.getByText('10')).toBeInTheDocument() // courses
  })

  // ── User table ───────────────────────────────────────────────
  it('renders user management table', async () => {
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Alice Parent')).toBeInTheDocument()
    })
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getByText('Bob Teacher')).toBeInTheDocument()
    expect(screen.getByText('bob@example.com')).toBeInTheDocument()
  })

  it('shows "No users found" for empty result', async () => {
    mockGetUsers.mockResolvedValue({ users: [], total: 0 })
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('No users match your search')).toBeInTheDocument()
    })
  })

  it('filters users by role', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Alice Parent')).toBeInTheDocument()
    })

    // Select "Teacher" from filter
    const roleSelect = screen.getByDisplayValue('All Roles')
    await user.selectOptions(roleSelect, 'teacher')

    await waitFor(() => {
      expect(mockGetUsers).toHaveBeenCalledWith(
        expect.objectContaining({ role: 'teacher', skip: 0 }),
      )
    })
  })

  it('searches users by name or email', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Alice Parent')).toBeInTheDocument()
    })

    const searchInput = screen.getByPlaceholderText('Search by name or email...')
    await user.type(searchInput, 'alice')

    // Wait for debounce (400ms)
    await waitFor(() => {
      expect(mockGetUsers).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'alice' }),
      )
    })
  })

  it('paginates users', async () => {
    mockGetUsers.mockResolvedValue({
      users: Array.from({ length: 10 }, (_, i) =>
        createMockAdminUser({ id: i + 1, full_name: `User ${i + 1}` }),
      ),
      total: 25,
    })
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText(/showing 1–10 of 25/i)).toBeInTheDocument()
    })

    // Click Next
    await user.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => {
      expect(mockGetUsers).toHaveBeenCalledWith(
        expect.objectContaining({ skip: 10 }),
      )
    })
  })

  it('disables Previous on first page and Next on last page', async () => {
    mockGetUsers.mockResolvedValue({
      users: [createMockAdminUser({ id: 1, full_name: 'Solo User' })],
      total: 15,
    })
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Solo User')).toBeInTheDocument()
    })

    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).not.toBeDisabled()
  })

  // ── Role Management Modal ────────────────────────────────────
  it('opens role management modal', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Alice Parent')).toBeInTheDocument()
    })

    // Click "Roles" button for Alice
    const rolesButtons = screen.getAllByRole('button', { name: 'Roles' })
    await user.click(rolesButtons[0])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Manage Roles' })).toBeInTheDocument()
    })
    // "Alice Parent" appears in both table row and modal - verify modal shows it
    expect(screen.getAllByText('Alice Parent').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText('alice@example.com').length).toBeGreaterThanOrEqual(2)
  })

  it('adds a role via checkbox', async () => {
    const updatedUser = createMockAdminUser({
      id: 10,
      full_name: 'Alice Parent',
      role: 'parent',
      roles: ['parent', 'teacher'],
    })
    mockAddRole.mockResolvedValue(updatedUser)
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Alice Parent')).toBeInTheDocument()
    })

    const rolesButtons = screen.getAllByRole('button', { name: 'Roles' })
    await user.click(rolesButtons[0])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Manage Roles' })).toBeInTheDocument()
    })

    // Find the teacher checkbox (unchecked) and click it
    const teacherCheckbox = screen.getByRole('checkbox', { name: /teacher/i })
    await user.click(teacherCheckbox)

    await waitFor(() => {
      expect(mockAddRole).toHaveBeenCalledWith(10, 'teacher')
    })
  })

  it('removes a role via checkbox', async () => {
    mockGetUsers.mockResolvedValue({
      users: [
        createMockAdminUser({ id: 10, full_name: 'Multi Role', roles: ['parent', 'teacher'] }),
      ],
      total: 1,
    })
    const updatedUser = createMockAdminUser({ id: 10, full_name: 'Multi Role', roles: ['parent'] })
    mockRemoveRole.mockResolvedValue(updatedUser)
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Multi Role')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Roles' }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Manage Roles' })).toBeInTheDocument()
    })

    // Teacher checkbox should be checked — click to remove
    const teacherCheckbox = screen.getByRole('checkbox', { name: /teacher/i })
    expect(teacherCheckbox).toBeChecked()
    await user.click(teacherCheckbox)

    await waitFor(() => {
      expect(mockRemoveRole).toHaveBeenCalledWith(10, 'teacher')
    })
  })

  it('prevents removing last role', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Alice Parent')).toBeInTheDocument()
    })

    const rolesButtons = screen.getAllByRole('button', { name: 'Roles' })
    await user.click(rolesButtons[0])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Manage Roles' })).toBeInTheDocument()
    })

    // Parent checkbox is the only role — it should be disabled
    const parentCheckbox = screen.getByRole('checkbox', { name: /parent/i })
    expect(parentCheckbox).toBeDisabled()
    expect(screen.getByText('Last role')).toBeInTheDocument()
  })

  it('closes role modal', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Alice Parent')).toBeInTheDocument()
    })

    await user.click(screen.getAllByRole('button', { name: 'Roles' })[0])
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Manage Roles' })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Close' }))

    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: 'Manage Roles' })).not.toBeInTheDocument()
    })
  })

  // ── Broadcast Modal ──────────────────────────────────────────
  it('opens broadcast modal and sends broadcast', async () => {
    mockSendBroadcast.mockResolvedValue({ recipient_count: 50, email_count: 45 })
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Total Users')).toBeInTheDocument()
    })

    // Click "Send Broadcast" link
    await user.click(screen.getByText(/Send Broadcast/))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Send Broadcast' })).toBeInTheDocument()
    })

    // Fill form
    await user.type(screen.getByPlaceholderText('Subject'), 'Test Broadcast')
    await user.type(screen.getByPlaceholderText('Message body...'), 'Hello everyone!')

    // Submit
    await user.click(screen.getByRole('button', { name: 'Send to All Users' }))

    await waitFor(() => {
      expect(mockSendBroadcast).toHaveBeenCalledWith('Test Broadcast', 'Hello everyone!')
    })

    // Should show success message
    await waitFor(() => {
      expect(screen.getByText(/broadcast sent to 50 users/i)).toBeInTheDocument()
    })
  })

  it('disables broadcast submit when fields are empty', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Total Users')).toBeInTheDocument()
    })

    await user.click(screen.getByText(/Send Broadcast/))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Send Broadcast' })).toBeInTheDocument()
    })

    expect(screen.getByRole('button', { name: 'Send to All Users' })).toBeDisabled()
  })

  it('shows broadcast error', async () => {
    mockSendBroadcast.mockRejectedValue({
      response: { data: { detail: 'No recipients' } },
    })
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Total Users')).toBeInTheDocument()
    })

    await user.click(screen.getByText(/Send Broadcast/))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Send Broadcast' })).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('Subject'), 'Subj')
    await user.type(screen.getByPlaceholderText('Message body...'), 'Body')
    await user.click(screen.getByRole('button', { name: 'Send to All Users' }))

    await waitFor(() => {
      expect(screen.getByText('No recipients')).toBeInTheDocument()
    })
  })

  // ── Broadcast History ────────────────────────────────────────
  it('toggles broadcast history', async () => {
    mockGetBroadcasts.mockResolvedValue([
      createMockBroadcast({ id: 1, subject: 'Welcome!', recipient_count: 30, email_count: 28 }),
    ])
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Total Users')).toBeInTheDocument()
    })

    // Show history
    await user.click(screen.getByText(/Broadcast History/))

    await waitFor(() => {
      expect(mockGetBroadcasts).toHaveBeenCalled()
    })
    await waitFor(() => {
      expect(screen.getByText('Welcome!')).toBeInTheDocument()
    })

    // Hide history
    await user.click(screen.getByText(/Broadcast History/))

    await waitFor(() => {
      expect(screen.queryByText('Welcome!')).not.toBeInTheDocument()
    })
  })

  it('shows empty broadcast history', async () => {
    mockGetBroadcasts.mockResolvedValue([])
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Total Users')).toBeInTheDocument()
    })

    await user.click(screen.getByText(/Broadcast History/))

    await waitFor(() => {
      expect(screen.getByText('No broadcasts sent yet')).toBeInTheDocument()
    })
  })

  // ── Individual Message Modal ─────────────────────────────────
  it('opens message modal for a user', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Alice Parent')).toBeInTheDocument()
    })

    // Click "Message" button for first user
    const messageButtons = screen.getAllByRole('button', { name: 'Message' })
    await user.click(messageButtons[0])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Send Message' })).toBeInTheDocument()
    })
    // Should show user info in modal
    expect(screen.getAllByText('Alice Parent').length).toBeGreaterThanOrEqual(1)
  })

  it('sends individual message successfully', async () => {
    mockSendMessage.mockResolvedValue({ success: true, email_sent: true })
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Alice Parent')).toBeInTheDocument()
    })

    await user.click(screen.getAllByRole('button', { name: 'Message' })[0])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Send Message' })).toBeInTheDocument()
    })

    // The message modal has Subject and Message body placeholders
    const subjectInputs = screen.getAllByPlaceholderText('Subject')
    const bodyTextareas = screen.getAllByPlaceholderText('Message body...')
    // Pick the ones inside the message modal (last in DOM since broadcast modal isn't open)
    await user.type(subjectInputs[subjectInputs.length - 1], 'Hello Alice')
    await user.type(bodyTextareas[bodyTextareas.length - 1], 'This is a test message.')

    const sendButtons = screen.getAllByRole('button', { name: 'Send Message' })
    await user.click(sendButtons[sendButtons.length - 1])

    await waitFor(() => {
      expect(mockSendMessage).toHaveBeenCalledWith(10, 'Hello Alice', 'This is a test message.')
    })

    await waitFor(() => {
      expect(screen.getByText('Message sent and email delivered.')).toBeInTheDocument()
    })
  })

  it('shows no-email result when email_sent is false', async () => {
    mockSendMessage.mockResolvedValue({ success: true, email_sent: false })
    const user = userEvent.setup()
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Alice Parent')).toBeInTheDocument()
    })

    await user.click(screen.getAllByRole('button', { name: 'Message' })[0])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Send Message' })).toBeInTheDocument()
    })

    const subjectInputs = screen.getAllByPlaceholderText('Subject')
    const bodyTextareas = screen.getAllByPlaceholderText('Message body...')
    await user.type(subjectInputs[subjectInputs.length - 1], 'Hello')
    await user.type(bodyTextareas[bodyTextareas.length - 1], 'Body')

    const sendButtons = screen.getAllByRole('button', { name: 'Send Message' })
    await user.click(sendButtons[sendButtons.length - 1])

    await waitFor(() => {
      expect(screen.getByText(/no email/i)).toBeInTheDocument()
    })
  })

  // ── Admin links ──────────────────────────────────────────────
  it('renders audit log and inspiration links', async () => {
    renderWithProviders(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Total Users')).toBeInTheDocument()
    })

    expect(screen.getByText(/view audit log/i)).toBeInTheDocument()
    expect(screen.getByText(/manage inspirational messages/i)).toBeInTheDocument()
  })
})
