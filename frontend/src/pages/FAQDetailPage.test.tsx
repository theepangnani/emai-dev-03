import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────

const mockGetQuestion = vi.fn()
const mockSubmitAnswer = vi.fn()
const mockApproveAnswer = vi.fn()
const mockRejectAnswer = vi.fn()
const mockMarkOfficial = vi.fn()
const mockPinQuestion = vi.fn()
const mockDeleteAnswer = vi.fn()
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ id: '1' }),
  }
})

vi.mock('../api/client', () => ({
  faqApi: {
    getQuestion: (...args: any[]) => mockGetQuestion(...args),
    submitAnswer: (...args: any[]) => mockSubmitAnswer(...args),
    approveAnswer: (...args: any[]) => mockApproveAnswer(...args),
    rejectAnswer: (...args: any[]) => mockRejectAnswer(...args),
    markOfficial: (...args: any[]) => mockMarkOfficial(...args),
    pinQuestion: (...args: any[]) => mockPinQuestion(...args),
    deleteAnswer: (...args: any[]) => mockDeleteAnswer(...args),
  },
  messagesApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }),
  },
  inspirationApi: {
    getRandom: vi.fn().mockRejectedValue(new Error('none')),
  },
}))

let mockUser = { id: 1, full_name: 'Test Student', role: 'student', roles: ['student'] }

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
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
import { FAQDetailPage } from './FAQDetailPage'

const MOCK_ANSWER_APPROVED = {
  id: 10,
  question_id: 1,
  content: 'Go to Dashboard and click Connect Google Classroom.',
  created_by_user_id: 2,
  status: 'approved',
  reviewed_by_user_id: 3,
  reviewed_at: '2026-01-02T00:00:00Z',
  is_official: true,
  creator_name: 'Admin User',
  reviewer_name: 'FAQ Admin',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
}

const MOCK_ANSWER_PENDING = {
  id: 11,
  question_id: 1,
  content: 'I think you need to go to settings first.',
  created_by_user_id: 4,
  status: 'pending',
  reviewed_by_user_id: null,
  reviewed_at: null,
  is_official: false,
  creator_name: 'Some Student',
  reviewer_name: null,
  created_at: '2026-01-03T00:00:00Z',
  updated_at: null,
}

const MOCK_ANSWER_REJECTED = {
  id: 12,
  question_id: 1,
  content: 'This is incorrect information.',
  created_by_user_id: 5,
  status: 'rejected',
  reviewed_by_user_id: 3,
  reviewed_at: '2026-01-04T00:00:00Z',
  is_official: false,
  creator_name: 'Another User',
  reviewer_name: 'FAQ Admin',
  created_at: '2026-01-03T12:00:00Z',
  updated_at: null,
}

const MOCK_QUESTION = {
  id: 1,
  title: 'How do I connect Google Classroom?',
  description: 'Step by step guide for Google connection',
  category: 'google-classroom',
  status: 'answered',
  error_code: null,
  created_by_user_id: 2,
  is_pinned: true,
  view_count: 42,
  creator_name: 'Admin User',
  answer_count: 3,
  approved_answer_count: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
  archived_at: null,
  answers: [MOCK_ANSWER_APPROVED, MOCK_ANSWER_PENDING, MOCK_ANSWER_REJECTED],
}

// ── Tests ──────────────────────────────────────────────────────
describe('FAQDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUser = { id: 1, full_name: 'Test Student', role: 'student', roles: ['student'] }
    mockGetQuestion.mockResolvedValue(MOCK_QUESTION)
    mockSubmitAnswer.mockResolvedValue(MOCK_ANSWER_PENDING)
  })

  function renderDetail() {
    return renderWithProviders(<FAQDetailPage />, { initialEntries: ['/faq/1'] })
  }

  it('renders question title and description', async () => {
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText('How do I connect Google Classroom?')).toBeInTheDocument()
    })
    expect(screen.getByText('Step by step guide for Google connection')).toBeInTheDocument()
  })

  it('renders question badges (pinned, category, answered)', async () => {
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText('Pinned')).toBeInTheDocument()
    })
    expect(screen.getByText('google classroom')).toBeInTheDocument()
    expect(screen.getByText('Answered')).toBeInTheDocument()
  })

  it('renders question metadata', async () => {
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText('Asked by Admin User')).toBeInTheDocument()
    })
    expect(screen.getByText('42 views')).toBeInTheDocument()
  })

  it('renders approved answers for non-admin', async () => {
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText('Go to Dashboard and click Connect Google Classroom.')).toBeInTheDocument()
    })
    expect(screen.getByText('Official Answer')).toBeInTheDocument()
    expect(screen.getByText('1 Answer')).toBeInTheDocument()
  })

  it('does NOT show pending/rejected answers to non-admin', async () => {
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText('1 Answer')).toBeInTheDocument()
    })
    expect(screen.queryByText('Pending Review')).not.toBeInTheDocument()
    expect(screen.queryByText('Rejected')).not.toBeInTheDocument()
    expect(screen.queryByText('I think you need to go to settings first.')).not.toBeInTheDocument()
  })

  it('shows pending and rejected answers for admin', async () => {
    mockUser = { id: 3, full_name: 'Admin', role: 'admin', roles: ['admin'] }
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText('1 Pending Answer')).toBeInTheDocument()
    })
    expect(screen.getByText('1 Rejected')).toBeInTheDocument()
    expect(screen.getByText('Pending Review')).toBeInTheDocument()
  })

  it('shows admin controls (pin/unpin, approve/reject)', async () => {
    mockUser = { id: 3, full_name: 'Admin', role: 'admin', roles: ['admin'] }
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText('Unpin')).toBeInTheDocument()
    })
    // Multiple approve buttons possible (pending + rejected answer sections)
    const approveButtons = screen.getAllByText('Approve')
    expect(approveButtons.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Reject')).toBeInTheDocument()
  })

  it('does NOT show admin controls for non-admin', async () => {
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText('1 Answer')).toBeInTheDocument()
    })
    expect(screen.queryByText('Unpin')).not.toBeInTheDocument()
    expect(screen.queryByText('Approve')).not.toBeInTheDocument()
  })

  it('renders "Back to FAQ" button', async () => {
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText(/Back to FAQ/)).toBeInTheDocument()
    })
  })

  it('navigates back on "Back to FAQ" click', async () => {
    const user = userEvent.setup()
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText(/Back to FAQ/)).toBeInTheDocument()
    })
    await user.click(screen.getByText(/Back to FAQ/))
    expect(mockNavigate).toHaveBeenCalledWith('/faq')
  })

  it('shows answer form with minimum character warning', async () => {
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText('Your Answer')).toBeInTheDocument()
    })
    expect(screen.getByPlaceholderText('Write your answer (minimum 10 characters)...')).toBeInTheDocument()
    expect(screen.getByText('10 more characters needed')).toBeInTheDocument()
  })

  it('disables submit button when answer is too short', async () => {
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText('Submit Answer')).toBeInTheDocument()
    })
    expect(screen.getByText('Submit Answer')).toBeDisabled()
  })

  it('enables submit button when answer has 10+ characters', async () => {
    const user = userEvent.setup()
    renderDetail()
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Write your answer (minimum 10 characters)...')).toBeInTheDocument()
    })
    await user.type(
      screen.getByPlaceholderText('Write your answer (minimum 10 characters)...'),
      'This is a valid answer.'
    )
    expect(screen.getByText('Submit Answer')).toBeEnabled()
  })

  it('submits an answer and reloads', async () => {
    const user = userEvent.setup()
    renderDetail()
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Write your answer (minimum 10 characters)...')).toBeInTheDocument()
    })
    await user.type(
      screen.getByPlaceholderText('Write your answer (minimum 10 characters)...'),
      'This is a valid answer text.'
    )
    await user.click(screen.getByText('Submit Answer'))
    await waitFor(() => {
      expect(mockSubmitAnswer).toHaveBeenCalledWith(1, { content: 'This is a valid answer text.' })
    })
  })

  it('shows moderation note for non-admin users', async () => {
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText('Your answer will be reviewed before being published.')).toBeInTheDocument()
    })
  })

  it('does NOT show moderation note for admin', async () => {
    mockUser = { id: 3, full_name: 'Admin', role: 'admin', roles: ['admin'] }
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText('Your Answer')).toBeInTheDocument()
    })
    expect(screen.queryByText('Your answer will be reviewed before being published.')).not.toBeInTheDocument()
  })

  it('shows empty answers state when no approved answers', async () => {
    mockGetQuestion.mockResolvedValue({
      ...MOCK_QUESTION,
      answers: [],
    })
    renderDetail()
    await waitFor(() => {
      expect(screen.getByText('No answers yet. Be the first to help!')).toBeInTheDocument()
    })
  })

  it('navigates to /faq on fetch error', async () => {
    mockGetQuestion.mockRejectedValue(new Error('Not found'))
    renderDetail()
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/faq')
    })
  })
})
