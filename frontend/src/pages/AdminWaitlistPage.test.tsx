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
const mockStats = vi.fn()
const mockRemind = vi.fn()

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

vi.mock('../api/adminWaitlist', () => ({
  adminWaitlistApi: {
    list: (...args: any[]) => mockList(...args),
    stats: (...args: any[]) => mockStats(...args),
    remind: (...args: any[]) => mockRemind(...args),
    approve: vi.fn().mockResolvedValue({}),
    decline: vi.fn().mockResolvedValue({}),
    updateNotes: vi.fn().mockResolvedValue({}),
    remove: vi.fn().mockResolvedValue({}),
    bulkApprove: vi.fn().mockResolvedValue({ approved: 0 }),
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

vi.mock('../components/NotificationBell', () => ({
  NotificationBell: () => <div data-testid="notification-bell" />,
}))


vi.mock('../components/ThemeToggle', () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}))

import { AdminWaitlistPage } from './AdminWaitlistPage'

function renderWithToast(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <ToastProvider>
            <MemoryRouter initialEntries={['/admin/waitlist']}>
              {children}
            </MemoryRouter>
          </ToastProvider>
        </QueryClientProvider>
      </ThemeProvider>
    )
  }
  return render(ui, { wrapper: Wrapper })
}

const approvedEntry = {
  id: 1,
  full_name: 'Pranavan P',
  email: 'pranavan@example.com',
  roles: ['parent'],
  status: 'approved',
  admin_notes: null,
  created_at: '2026-03-07T00:00:00Z',
  approved_at: '2026-03-07T00:00:00Z',
  registered_at: null,
}

describe('AdminWaitlistPage - Send Reminder', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockStats.mockResolvedValue({
      total: 1, pending: 0, approved: 1, registered: 0, declined: 0,
    })
    mockList.mockResolvedValue({ items: [approvedEntry], total: 1 })
  })

  it('shows success toast after sending reminder', async () => {
    mockRemind.mockResolvedValue({})
    const user = userEvent.setup()
    renderWithToast(<AdminWaitlistPage />)

    await waitFor(() => {
      expect(screen.getByText('Pranavan P')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Send Reminder' }))

    await waitFor(() => {
      expect(mockRemind).toHaveBeenCalledWith(1)
    })

    await waitFor(() => {
      expect(screen.getByText('Reminder sent to pranavan@example.com')).toBeInTheDocument()
    })
  })

  it('shows error toast when reminder fails', async () => {
    mockRemind.mockRejectedValue(new Error('Network error'))
    const user = userEvent.setup()
    renderWithToast(<AdminWaitlistPage />)

    await waitFor(() => {
      expect(screen.getByText('Pranavan P')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Send Reminder' }))

    await waitFor(() => {
      expect(screen.getByText('Failed to send reminder')).toBeInTheDocument()
    })
  })
})
