import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '../context/ThemeContext'
import { ToastProvider } from '../components/Toast'
import type { ReactElement, ReactNode } from 'react'

// ── Mocks ──────────────────────────────────────────────────────
const mockList = vi.fn()
const mockApprove = vi.fn()
const mockReject = vi.fn()
const mockBlocklist = vi.fn()
const mockCsv = vi.fn()

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

vi.mock('../api/admin', () => ({
  adminApi: {
    listDemoSessions: (...args: unknown[]) => mockList(...args),
    approveDemoSession: (...args: unknown[]) => mockApprove(...args),
    rejectDemoSession: (...args: unknown[]) => mockReject(...args),
    blocklistDemoSession: (...args: unknown[]) => mockBlocklist(...args),
    downloadDemoSessionsCsv: (...args: unknown[]) => mockCsv(...args),
  },
}))

vi.mock('../api/client', () => ({
  messagesApi: { getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }) },
  inspirationApi: { getRandom: vi.fn().mockRejectedValue(new Error('none')) },
}))

vi.mock('../components/NotificationBell', () => ({
  NotificationBell: () => <div data-testid="notification-bell" />,
}))

vi.mock('../components/ThemeToggle', () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}))

import { AdminDemoSessionsPage } from './AdminDemoSessionsPage'

function renderPage(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <ToastProvider>
            <MemoryRouter initialEntries={['/admin/demo-sessions']}>
              {children}
            </MemoryRouter>
          </ToastProvider>
        </QueryClientProvider>
      </ThemeProvider>
    )
  }
  return render(ui, { wrapper: Wrapper })
}

const baseItem = {
  id: 'sess-1',
  created_at: '2026-04-10T00:00:00Z',
  email: 'demo@example.com',
  full_name: 'Demo User',
  role: 'parent',
  verified: true,
  verified_ts: '2026-04-10T00:01:00Z',
  generations_count: 2,
  admin_status: 'pending',
  source_ip_hash: null,
  user_agent: null,
  archived_at: null,
  moat_engagement_json: null,
  moat_summary: { tm_beats_seen: 3, rs_roles_switched: 2, pw_viewport_reached: true },
}

describe('AdminDemoSessionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ items: [baseItem], total: 1, page: 1, per_page: 50 })
    mockApprove.mockResolvedValue({ ...baseItem, admin_status: 'approved' })
    mockReject.mockResolvedValue({ ...baseItem, admin_status: 'rejected' })
    mockBlocklist.mockResolvedValue({ ...baseItem, admin_status: 'blocklisted' })
    mockCsv.mockResolvedValue(new Blob(['id\n'], { type: 'text/csv' }))
  })

  it('fetches demo sessions on mount and renders row data', async () => {
    renderPage(<AdminDemoSessionsPage />)
    await waitFor(() => {
      expect(mockList).toHaveBeenCalled()
      expect(screen.getByText('demo@example.com')).toBeInTheDocument()
      expect(screen.getByText('Demo User')).toBeInTheDocument()
      expect(screen.getByText('TM:3 RS:2 PW:✓')).toBeInTheDocument()
    })
  })

  it('re-fetches when status filter changes', async () => {
    const user = userEvent.setup()
    renderPage(<AdminDemoSessionsPage />)
    await waitFor(() => expect(screen.getByText('demo@example.com')).toBeInTheDocument())
    mockList.mockClear()
    await user.selectOptions(screen.getByLabelText('Filter by status'), 'approved')
    await waitFor(() => {
      expect(mockList).toHaveBeenCalled()
      const call = mockList.mock.calls[0][0]
      expect(call.status).toBe('approved')
    })
  })

  it('approve updates row status optimistically', async () => {
    const user = userEvent.setup()
    renderPage(<AdminDemoSessionsPage />)
    await waitFor(() => expect(screen.getByText('demo@example.com')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    await waitFor(() => {
      expect(mockApprove).toHaveBeenCalledWith('sess-1')
      expect(screen.getByText('approved')).toBeInTheDocument()
    })
  })

  it('reject calls reject API', async () => {
    const user = userEvent.setup()
    renderPage(<AdminDemoSessionsPage />)
    await waitFor(() => expect(screen.getByText('demo@example.com')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Reject' }))
    await waitFor(() => expect(mockReject).toHaveBeenCalledWith('sess-1'))
  })

  it('blocklist calls blocklist API', async () => {
    const user = userEvent.setup()
    renderPage(<AdminDemoSessionsPage />)
    await waitFor(() => expect(screen.getByText('demo@example.com')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Blocklist' }))
    await waitFor(() => expect(mockBlocklist).toHaveBeenCalledWith('sess-1'))
  })

  it('downloads CSV when Download CSV button clicked', async () => {
    const origCreate = window.URL.createObjectURL
    const origRevoke = window.URL.revokeObjectURL
    window.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock')
    window.URL.revokeObjectURL = vi.fn()
    const user = userEvent.setup()
    renderPage(<AdminDemoSessionsPage />)
    await waitFor(() => expect(screen.getByText('demo@example.com')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /Download CSV/i }))
    await waitFor(() => expect(mockCsv).toHaveBeenCalled())
    window.URL.createObjectURL = origCreate
    window.URL.revokeObjectURL = origRevoke
  })

  it('renders empty state when no items', async () => {
    mockList.mockResolvedValueOnce({ items: [], total: 0, page: 1, per_page: 50 })
    renderPage(<AdminDemoSessionsPage />)
    await waitFor(() => {
      expect(screen.getByText('No demo sessions found.')).toBeInTheDocument()
    })
  })
})
