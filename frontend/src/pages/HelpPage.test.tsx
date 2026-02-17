import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────
vi.mock('../api/client', () => ({
  messagesApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }),
  },
  inspirationApi: {
    getRandom: vi.fn().mockRejectedValue(new Error('none')),
  },
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Test User', role: 'parent', roles: ['parent'] },
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
import { HelpPage } from './HelpPage'

// ── Tests ──────────────────────────────────────────────────────
describe('HelpPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  function renderHelp() {
    return renderWithProviders(<HelpPage />, { initialEntries: ['/help'] })
  }

  it('renders all FAQ section titles', () => {
    renderHelp()
    expect(screen.getByText('Getting Started')).toBeInTheDocument()
    expect(screen.getByText('Study Tools')).toBeInTheDocument()
    expect(screen.getByText('Communication')).toBeInTheDocument()
    expect(screen.getByText('Account & Settings')).toBeInTheDocument()
    expect(screen.getByText('Troubleshooting')).toBeInTheDocument()
  })

  it('renders all FAQ questions', () => {
    renderHelp()
    expect(screen.getByText('How do I connect my Google Classroom account?')).toBeInTheDocument()
    expect(screen.getByText('How do I sync my courses and assignments?')).toBeInTheDocument()
    expect(screen.getByText("How do I link my child's account (for parents)?")).toBeInTheDocument()
    expect(screen.getByText('How do I create a study guide from course materials?')).toBeInTheDocument()
    expect(screen.getByText('How do I take a quiz or use flashcards?')).toBeInTheDocument()
    expect(screen.getByText('How do I send a message to a teacher or parent?')).toBeInTheDocument()
    expect(screen.getByText('How do I create and track tasks?')).toBeInTheDocument()
    expect(screen.getByText('What should I do if my Google sync fails?')).toBeInTheDocument()
    expect(screen.getByText('Where can I report a bug or request a feature?')).toBeInTheDocument()
  })

  it('does not show any answers initially', () => {
    renderHelp()
    const answers = document.querySelectorAll('.help-answer')
    expect(answers.length).toBe(0)
  })

  it('expands an answer when a question is clicked', async () => {
    const user = userEvent.setup()
    renderHelp()

    const question = screen.getByText('How do I connect my Google Classroom account?')
    await user.click(question)

    expect(screen.getByText(/Go to your Dashboard and click/)).toBeInTheDocument()
  })

  it('collapses an answer when the same question is clicked again', async () => {
    const user = userEvent.setup()
    renderHelp()

    const question = screen.getByText('How do I connect my Google Classroom account?')
    await user.click(question)
    expect(screen.getByText(/Go to your Dashboard and click/)).toBeInTheDocument()

    await user.click(question)
    expect(screen.queryByText(/Go to your Dashboard and click/)).not.toBeInTheDocument()
  })

  it('closes previously open item when a different one is clicked', async () => {
    const user = userEvent.setup()
    renderHelp()

    // Open first question
    await user.click(screen.getByText('How do I connect my Google Classroom account?'))
    expect(screen.getByText(/Go to your Dashboard and click/)).toBeInTheDocument()

    // Open a different question
    await user.click(screen.getByText('What should I do if my Google sync fails?'))
    expect(screen.getByText(/try clicking the sync button again/)).toBeInTheDocument()

    // First answer should be closed
    expect(screen.queryByText(/Go to your Dashboard and click/)).not.toBeInTheDocument()
  })

  it('sets aria-expanded correctly on question buttons', async () => {
    const user = userEvent.setup()
    renderHelp()

    const questionBtn = screen.getByText('How do I connect my Google Classroom account?').closest('button')!
    expect(questionBtn).toHaveAttribute('aria-expanded', 'false')

    await user.click(questionBtn)
    expect(questionBtn).toHaveAttribute('aria-expanded', 'true')

    await user.click(questionBtn)
    expect(questionBtn).toHaveAttribute('aria-expanded', 'false')
  })

  it('renders chevron with expanded class when item is open', async () => {
    const user = userEvent.setup()
    renderHelp()

    const questionBtn = screen.getByText('How do I connect my Google Classroom account?').closest('button')!
    const chevron = questionBtn.querySelector('.help-chevron')!

    expect(chevron).not.toHaveClass('expanded')

    await user.click(questionBtn)
    expect(chevron).toHaveClass('expanded')
  })

  it('renders inside DashboardLayout with subtitle', () => {
    renderHelp()
    expect(screen.getByText('Find answers to common questions')).toBeInTheDocument()
  })
})
