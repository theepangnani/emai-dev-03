import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────

const mockListQuestions = vi.fn()
const mockCreateQuestion = vi.fn()

vi.mock('../api/client', () => ({
  faqApi: {
    listQuestions: (...args: any[]) => mockListQuestions(...args),
    createQuestion: (...args: any[]) => mockCreateQuestion(...args),
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
    user: { id: 1, full_name: 'Test User', role: 'student', roles: ['student'] },
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
import { FAQPage } from './FAQPage'

const MOCK_QUESTIONS = [
  {
    id: 1,
    title: 'How do I connect Google Classroom?',
    description: 'Step by step guide',
    category: 'google-classroom',
    status: 'answered',
    error_code: null,
    created_by_user_id: 2,
    is_pinned: true,
    view_count: 42,
    creator_name: 'Admin',
    answer_count: 2,
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
describe('FAQPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListQuestions.mockResolvedValue(MOCK_QUESTIONS)
    mockCreateQuestion.mockResolvedValue(MOCK_QUESTIONS[0])
  })

  function renderFAQ() {
    return renderWithProviders(<FAQPage />, { initialEntries: ['/faq'] })
  }

  it('renders page title and ask button', async () => {
    renderFAQ()
    await waitFor(() => {
      expect(screen.getByText('FAQ / Knowledge Base')).toBeInTheDocument()
    })
    expect(screen.getByText('Ask a Question')).toBeInTheDocument()
  })

  it('renders question list after loading', async () => {
    renderFAQ()
    await waitFor(() => {
      expect(screen.getByText('How do I connect Google Classroom?')).toBeInTheDocument()
    })
    expect(screen.getByText('How do I create a study guide?')).toBeInTheDocument()
  })

  it('shows pinned and answered badges', async () => {
    renderFAQ()
    await waitFor(() => {
      expect(screen.getByText('Pinned')).toBeInTheDocument()
    })
    expect(screen.getByText('Answered')).toBeInTheDocument()
  })

  it('shows answer count and view count', async () => {
    renderFAQ()
    await waitFor(() => {
      expect(screen.getByText('1 answer')).toBeInTheDocument()
    })
    expect(screen.getByText('42 views')).toBeInTheDocument()
    expect(screen.getByText('0 answers')).toBeInTheDocument()
  })

  it('renders category filter pills', async () => {
    renderFAQ()
    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument()
    })
    expect(screen.getByText('Getting Started')).toBeInTheDocument()
    expect(screen.getByText('Google Classroom')).toBeInTheDocument()
    expect(screen.getByText('Study Tools')).toBeInTheDocument()
  })

  it('filters by category on pill click', async () => {
    const user = userEvent.setup()
    renderFAQ()

    await waitFor(() => {
      expect(screen.getByText('Google Classroom')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Google Classroom'))

    await waitFor(() => {
      expect(mockListQuestions).toHaveBeenCalledWith(
        expect.objectContaining({ category: 'google-classroom' })
      )
    })
  })

  it('searches questions on input', async () => {
    const user = userEvent.setup()
    renderFAQ()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search questions...')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('Search questions...'), 'google')

    await waitFor(() => {
      expect(mockListQuestions).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'google' })
      )
    })
  })

  it('opens and closes ask question modal', async () => {
    const user = userEvent.setup()
    renderFAQ()

    await waitFor(() => {
      expect(screen.getByText('Ask a Question')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Ask a Question'))

    expect(screen.getByPlaceholderText('What would you like to know?')).toBeInTheDocument()
    expect(screen.getByText('Cancel')).toBeInTheDocument()

    await user.click(screen.getByText('Cancel'))

    await waitFor(() => {
      expect(screen.queryByPlaceholderText('What would you like to know?')).not.toBeInTheDocument()
    })
  })

  it('submits a new question via modal', async () => {
    const user = userEvent.setup()
    renderFAQ()

    await waitFor(() => {
      expect(screen.getByText('Ask a Question')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Ask a Question'))

    await user.type(
      screen.getByPlaceholderText('What would you like to know?'),
      'How do I reset my password?'
    )

    await user.click(screen.getByText('Submit Question'))

    await waitFor(() => {
      expect(mockCreateQuestion).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'How do I reset my password?',
          category: 'other',
        })
      )
    })
  })

  it('shows empty state when no questions', async () => {
    mockListQuestions.mockResolvedValue([])
    renderFAQ()

    await waitFor(() => {
      expect(screen.getByText('No questions found. Be the first to ask!')).toBeInTheDocument()
    })
  })
})
