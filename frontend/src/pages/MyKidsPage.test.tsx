import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '../context/ThemeContext'
import { ToastProvider } from '../components/Toast'
import type { ReactNode } from 'react'

// ── Mocks ──────────────────────────────────────────────────────
const mockGetChildren = vi.fn()
const mockCreateChild = vi.fn()
const mockLinkChild = vi.fn()

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Test Parent', role: 'parent', roles: ['parent'] },
    logout: vi.fn(),
    switchRole: vi.fn(),
  }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

vi.mock('../api/client', () => ({
  parentApi: {
    getChildren: (...args: any[]) => mockGetChildren(...args),
    createChild: (...args: any[]) => mockCreateChild(...args),
    linkChild: (...args: any[]) => mockLinkChild(...args),
    getChildOverview: vi.fn().mockResolvedValue({ full_name: '', courses: [], assignments: [], grades: [] }),
    getLinkedTeachers: vi.fn().mockResolvedValue([]),
    assignCoursesToChild: vi.fn().mockResolvedValue({}),
  },
  courseContentsApi: {
    listAll: vi.fn().mockResolvedValue([]),
    update: vi.fn().mockResolvedValue({}),
  },
  coursesApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue({ id: 1, name: 'Test' }),
  },
  tasksApi: {
    list: vi.fn().mockResolvedValue([]),
  },
  invitesApi: {
    listPending: vi.fn().mockResolvedValue([]),
    resend: vi.fn().mockResolvedValue({}),
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

import { MyKidsPage } from './MyKidsPage'

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <ToastProvider>
            <MemoryRouter initialEntries={['/my-kids']}>
              {children}
            </MemoryRouter>
          </ToastProvider>
        </QueryClientProvider>
      </ThemeProvider>
    )
  }
  return render(<MyKidsPage />, { wrapper: Wrapper })
}

describe('MyKidsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows empty state when parent has no children', async () => {
    mockGetChildren.mockResolvedValue([])
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('No children linked yet')).toBeInTheDocument()
    })
    expect(document.querySelector('.mykids-btn')).toBeInTheDocument()
  })

  // Regression test for #1351: clicking Add Child in empty state must not crash.
  // Before the fix, the early return at the top of the component called
  // renderAddChildModal() which referenced const handler functions declared
  // AFTER the early return, causing a TDZ error in minified production builds.
  it('opens Add Child modal from empty state without crashing (#1351)', async () => {
    mockGetChildren.mockResolvedValue([])
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('No children linked yet')).toBeInTheDocument()
    })

    const user = userEvent.setup()
    // Click the main content button (not the sidebar one)
    const addBtn = document.querySelector('.mykids-btn') as HTMLElement
    await user.click(addBtn)

    // Modal should be visible with both tabs and form fields
    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: /add child/i })).toBeInTheDocument()
    })
    expect(screen.getByText('Create New')).toBeInTheDocument()
    expect(screen.getByText('Link by Email')).toBeInTheDocument()
  })

  it('can create a child from the empty state modal (#1351)', async () => {
    mockGetChildren
      .mockResolvedValueOnce([])  // initial load: empty
      .mockResolvedValueOnce([{ student_id: 10, user_id: 20, full_name: 'Alex Smith', course_count: 0 }])  // after create
    mockCreateChild.mockResolvedValue({ id: 10, full_name: 'Alex Smith' })

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('No children linked yet')).toBeInTheDocument()
    })

    const user = userEvent.setup()
    const addBtn = document.querySelector('.mykids-btn') as HTMLElement
    await user.click(addBtn)

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: /add child/i })).toBeInTheDocument()
    })

    // Fill in the name and submit
    const nameInput = screen.getByPlaceholderText('e.g. Alex Smith')
    await user.type(nameInput, 'Alex Smith')
    await user.click(document.querySelector('.generate-btn') as HTMLElement)

    await waitFor(() => {
      expect(mockCreateChild).toHaveBeenCalledWith('Alex Smith', 'guardian', undefined)
    })
  })
})
