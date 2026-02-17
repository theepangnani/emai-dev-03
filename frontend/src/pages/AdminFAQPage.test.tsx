import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────

const mockListPendingAnswers = vi.fn()
const mockListQuestions = vi.fn()
const mockApproveAnswer = vi.fn()
const mockRejectAnswer = vi.fn()
const mockPinQuestion = vi.fn()
const mockDeleteQuestion = vi.fn()
const mockCreateOfficialQuestion = vi.fn()
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../api/client', () => ({
  faqApi: {
    listPendingAnswers: (...args: any[]) => mockListPendingAnswers(...args),
    listQuestions: (...args: any[]) => mockListQuestions(...args),
    approveAnswer: (...args: any[]) => mockApproveAnswer(...args),
    rejectAnswer: (...args: any[]) => mockRejectAnswer(...args),
    pinQuestion: (...args: any[]) => mockPinQuestion(...args),
    deleteQuestion: (...args: any[]) => mockDeleteQuestion(...args),
    createOfficialQuestion: (...args: any[]) => mockCreateOfficialQuestion(...args),
  },
  messagesApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }),
  },
  inspirationApi: {
    getRandom: vi.fn().mockRejectedValue(new Error('none')),
  },
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Admin User', role: 'admin', roles: ['admin'] },
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

// ── Import after mocks ────────────────────────────────────────
import { AdminFAQPage } from './AdminFAQPage'

const MOCK_PENDING = [
  {
    id: 10,
    question_id: 1,
    content: 'Pending answer awaiting review.',
    created_by_user_id: 5,
    status: 'pending',
    reviewed_by_user_id: null,
    reviewed_at: null,
    is_official: false,
    creator_name: 'Student User',
    reviewer_name: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
  },
]

const MOCK_QUESTIONS = [
  {
    id: 1,
    title: 'How do I connect Google?',
    description: null,
    category: 'google-classroom',
    status: 'answered',
    error_code: null,
    created_by_user_id: 2,
    is_pinned: true,
    view_count: 42,
    creator_name: 'Admin',
    answer_count: 1,
    approved_answer_count: 1,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    archived_at: null,
  },
  {
    id: 2,
    title: 'How do I create a study guide?',
    description: null,
    category: 'study-tools',
    status: 'open',
    error_code: null,
    created_by_user_id: 3,
    is_pinned: false,
    view_count: 5,
    creator_name: 'Student',
    answer_count: 0,
    approved_answer_count: 0,
    created_at: '2026-01-02T00:00:00Z',
    updated_at: null,
    archived_at: null,
  },
]

// ── Tests ──────────────────────────────────────────────────────
describe('AdminFAQPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListPendingAnswers.mockResolvedValue(MOCK_PENDING)
    mockListQuestions.mockResolvedValue(MOCK_QUESTIONS)
    mockApproveAnswer.mockResolvedValue({})
    mockRejectAnswer.mockResolvedValue({})
    mockCreateOfficialQuestion.mockResolvedValue({
      ...MOCK_QUESTIONS[0],
      answers: [{
        id: 100,
        content: 'Official answer',
        status: 'approved',
        is_official: true,
        creator_name: 'Admin',
        created_at: '2026-01-01T00:00:00Z',
      }],
    })
  })

  function renderAdmin() {
    return renderWithProviders(<AdminFAQPage />, { initialEntries: ['/admin/faq'] })
  }

  // ── Pending Tab ──────────────────────────────────────────────

  it('renders page title and tabs', async () => {
    renderAdmin()
    await waitFor(() => {
      expect(screen.getByText('Manage FAQ')).toBeInTheDocument()
    })
    expect(screen.getByText('Pending Answers')).toBeInTheDocument()
    expect(screen.getByText('All Questions')).toBeInTheDocument()
    expect(screen.getByText('Create Official FAQ')).toBeInTheDocument()
  })

  it('shows pending answers on default tab', async () => {
    renderAdmin()
    await waitFor(() => {
      expect(screen.getByText('Pending answer awaiting review.')).toBeInTheDocument()
    })
    expect(screen.getByText(/Student User/)).toBeInTheDocument()
  })

  it('shows empty state when no pending answers', async () => {
    mockListPendingAnswers.mockResolvedValue([])
    renderAdmin()
    await waitFor(() => {
      expect(screen.getByText('No pending answers to review.')).toBeInTheDocument()
    })
  })

  it('approves a pending answer', async () => {
    const user = userEvent.setup()
    renderAdmin()
    await waitFor(() => {
      expect(screen.getByText('Pending answer awaiting review.')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Approve'))
    await waitFor(() => {
      expect(mockApproveAnswer).toHaveBeenCalledWith(10)
    })
  })

  it('rejects a pending answer', async () => {
    const user = userEvent.setup()
    renderAdmin()
    await waitFor(() => {
      expect(screen.getByText('Pending answer awaiting review.')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Reject'))
    await waitFor(() => {
      expect(mockRejectAnswer).toHaveBeenCalledWith(10)
    })
  })

  it('navigates to question detail via View Question button', async () => {
    const user = userEvent.setup()
    renderAdmin()
    await waitFor(() => {
      expect(screen.getByText('View Question')).toBeInTheDocument()
    })
    await user.click(screen.getByText('View Question'))
    expect(mockNavigate).toHaveBeenCalledWith('/faq/1')
  })

  // ── All Questions Tab ────────────────────────────────────────

  it('switches to All Questions tab and shows table', async () => {
    const user = userEvent.setup()
    renderAdmin()
    await waitFor(() => {
      expect(screen.getByText('Manage FAQ')).toBeInTheDocument()
    })
    await user.click(screen.getByText('All Questions'))
    await waitFor(() => {
      expect(screen.getByText('How do I connect Google?')).toBeInTheDocument()
    })
    expect(screen.getByText('How do I create a study guide?')).toBeInTheDocument()
  })

  it('shows pin/unpin and delete buttons in all questions table', async () => {
    const user = userEvent.setup()
    renderAdmin()
    await user.click(screen.getByText('All Questions'))
    await waitFor(() => {
      expect(screen.getByText('How do I connect Google?')).toBeInTheDocument()
    })
    // First question is pinned, so should have "Unpin"
    expect(screen.getByText('Unpin')).toBeInTheDocument()
    // Second question is not pinned, so should have "Pin"
    expect(screen.getByText('Pin')).toBeInTheDocument()
    // Both should have delete
    const deleteButtons = screen.getAllByText('Delete')
    expect(deleteButtons.length).toBe(2)
  })

  it('shows View Public FAQ button', async () => {
    renderAdmin()
    await waitFor(() => {
      expect(screen.getByText('View Public FAQ')).toBeInTheDocument()
    })
  })

  // ── Create Official FAQ Tab ──────────────────────────────────

  it('switches to Create tab and shows form', async () => {
    const user = userEvent.setup()
    renderAdmin()
    await user.click(screen.getByText('Create Official FAQ'))
    expect(screen.getByPlaceholderText('How do I...?')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Write the official answer...')).toBeInTheDocument()
    expect(screen.getByText('Create FAQ')).toBeInTheDocument()
  })

  it('disables Create FAQ button when fields are empty', async () => {
    const user = userEvent.setup()
    renderAdmin()
    await user.click(screen.getByText('Create Official FAQ'))
    expect(screen.getByText('Create FAQ')).toBeDisabled()
  })

  it('submits create official FAQ form', async () => {
    const user = userEvent.setup()
    renderAdmin()
    await user.click(screen.getByText('Create Official FAQ'))

    await user.type(screen.getByPlaceholderText('How do I...?'), 'How do I reset my password?')
    await user.type(screen.getByPlaceholderText('Write the official answer...'), 'Use the forgot password link on the login page.')

    await user.click(screen.getByText('Create FAQ'))

    await waitFor(() => {
      expect(mockCreateOfficialQuestion).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'How do I reset my password?',
          answer_content: 'Use the forgot password link on the login page.',
          is_official: true,
        })
      )
    })
  })

  it('shows success message after creating FAQ', async () => {
    const user = userEvent.setup()
    renderAdmin()
    await user.click(screen.getByText('Create Official FAQ'))

    await user.type(screen.getByPlaceholderText('How do I...?'), 'Test title')
    await user.type(screen.getByPlaceholderText('Write the official answer...'), 'Test answer content')
    await user.click(screen.getByText('Create FAQ'))

    await waitFor(() => {
      expect(screen.getByText('Official FAQ created successfully!')).toBeInTheDocument()
    })
  })

  it('shows error message on create failure', async () => {
    mockCreateOfficialQuestion.mockRejectedValue(new Error('Server error'))
    const user = userEvent.setup()
    renderAdmin()
    await user.click(screen.getByText('Create Official FAQ'))

    await user.type(screen.getByPlaceholderText('How do I...?'), 'Test title')
    await user.type(screen.getByPlaceholderText('Write the official answer...'), 'Test answer content')
    await user.click(screen.getByText('Create FAQ'))

    await waitFor(() => {
      expect(screen.getByText('Failed to create FAQ.')).toBeInTheDocument()
    })
  })
})
