import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'
import {
  createMockConversation,
  createMockConversationDetail,
  createMockMessage,
  createMockRecipient,
  createMockUser,
} from '../test/mocks'

// Mocks
const mockListConversations = vi.fn()
const mockGetConversation = vi.fn()
const mockGetRecipients = vi.fn()
const mockSendMessage = vi.fn()
const mockCreateConversation = vi.fn()
const mockMarkAsRead = vi.fn()
const mockGetUnreadCount = vi.fn()
let mockUser: any = null
const mockLogout = vi.fn()
const mockNavigate = vi.fn()

vi.mock('../api/client', () => ({
  messagesApi: {
    listConversations: (...args: unknown[]) => mockListConversations(...args),
    getConversation: (...args: unknown[]) => mockGetConversation(...args),
    getRecipients: () => mockGetRecipients(),
    sendMessage: (...args: unknown[]) => mockSendMessage(...args),
    createConversation: (...args: unknown[]) => mockCreateConversation(...args),
    markAsRead: (...args: unknown[]) => mockMarkAsRead(...args),
    getUnreadCount: () => mockGetUnreadCount(),
  },
  notificationsApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ count: 0 }),
    list: vi.fn().mockResolvedValue([]),
    markAsRead: vi.fn().mockResolvedValue(undefined),
    markAllAsRead: vi.fn().mockResolvedValue(undefined),
  },
  inspirationApi: {
    getRandom: vi.fn().mockRejectedValue(new Error('none')),
  },
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    logout: mockLogout,
    switchRole: vi.fn(),
    resendVerification: vi.fn(),
  }),
}))

vi.mock('../components/GlobalSearch', () => ({
  GlobalSearch: () => <div data-testid="global-search" />,
}))

vi.mock('../components/ThemeToggle', () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../utils/logger', () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}))

import { MessagesPage } from './MessagesPage'

describe('MessagesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUser = createMockUser({ id: 1, full_name: 'Test Parent' })
    mockListConversations.mockResolvedValue([])
    mockGetRecipients.mockResolvedValue([])
    mockGetUnreadCount.mockResolvedValue({ total_unread: 0 })
    // jsdom doesn't implement scrollIntoView
    Element.prototype.scrollIntoView = vi.fn()
  })

  // ── Loading & Empty States ──────────────────────────────────

  it('shows loading skeleton initially', () => {
    // Never resolve to keep loading state
    mockListConversations.mockReturnValue(new Promise(() => {}))

    renderWithProviders(<MessagesPage />)

    // Skeleton is visible via CSS class
    expect(document.querySelector('.loading-grid')).toBeInTheDocument()
  })

  it('shows empty state when no conversations', async () => {
    mockListConversations.mockResolvedValue([])

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText(/no messages yet/i)).toBeInTheDocument()
    })
  })

  it('shows "select a conversation" when loaded with no selection', async () => {
    mockListConversations.mockResolvedValue([
      createMockConversation({ id: 1, other_participant_name: 'Teacher Jane' }),
    ])

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText(/select a conversation to view messages/i)).toBeInTheDocument()
    })
  })

  // ── Conversation List ───────────────────────────────────────

  it('renders conversation list from API', async () => {
    mockListConversations.mockResolvedValue([
      createMockConversation({ id: 1, other_participant_name: 'Teacher Jane' }),
      createMockConversation({ id: 2, other_participant_name: 'Admin Bob' }),
    ])

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText('Teacher Jane')).toBeInTheDocument()
    })
    expect(screen.getByText('Admin Bob')).toBeInTheDocument()
  })

  it('shows unread badge on conversations', async () => {
    mockListConversations.mockResolvedValue([
      createMockConversation({ id: 1, other_participant_name: 'Jane', unread_count: 3 }),
    ])

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText('3')).toBeInTheDocument()
    })
  })

  it('shows admin badge for admin conversations', async () => {
    mockListConversations.mockResolvedValue([
      createMockConversation({ id: 1, other_participant_name: 'Admin User', other_participant_role: 'admin' }),
    ])

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText('Admin')).toBeInTheDocument()
    })
  })

  // ── Selecting Conversation ──────────────────────────────────

  it('loads conversation detail when clicking a conversation', async () => {
    const detail = createMockConversationDetail({
      id: 1,
      participant_1_id: 1,
      participant_1_name: 'Test Parent',
      participant_2_id: 2,
      participant_2_name: 'Teacher Jane',
      messages: [
        createMockMessage({ id: 10, sender_id: 2, sender_name: 'Teacher Jane', content: 'Hello parent!' }),
      ],
      messages_total: 1,
    })
    mockListConversations.mockResolvedValue([
      createMockConversation({ id: 1, other_participant_name: 'Teacher Jane' }),
    ])
    mockGetConversation.mockResolvedValue(detail)
    const user = userEvent.setup()

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText('Teacher Jane')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Teacher Jane'))

    await waitFor(() => {
      expect(screen.getByText('Hello parent!')).toBeInTheDocument()
    })
    expect(mockGetConversation).toHaveBeenCalledWith(1, { offset: 0, limit: 30 })
    expect(mockMarkAsRead).toHaveBeenCalledWith(1)
  })

  // ── Send Message ────────────────────────────────────────────

  it('sends message via textarea and send button', async () => {
    const detail = createMockConversationDetail({
      id: 1,
      participant_2_name: 'Teacher Jane',
      messages: [createMockMessage({ id: 10, content: 'Hi' })],
      messages_total: 1,
    })
    mockListConversations.mockResolvedValue([
      createMockConversation({ id: 1, other_participant_name: 'Teacher Jane' }),
    ])
    mockGetConversation.mockResolvedValue(detail)
    mockSendMessage.mockResolvedValue(createMockMessage({ id: 11, content: 'My reply' }))
    const user = userEvent.setup()

    renderWithProviders(<MessagesPage />)

    // Select conversation
    await waitFor(() => {
      expect(screen.getByText('Teacher Jane')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Teacher Jane'))

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/type your message/i)).toBeInTheDocument()
    })

    // Type and send
    await user.type(screen.getByPlaceholderText(/type your message/i), 'My reply')
    await user.click(screen.getByRole('button', { name: /^send$/i }))

    expect(mockSendMessage).toHaveBeenCalledWith(1, 'My reply')
  })

  it('send button is disabled when textarea is empty', async () => {
    const detail = createMockConversationDetail({
      id: 1,
      participant_2_name: 'Jane',
      messages: [],
      messages_total: 0,
    })
    mockListConversations.mockResolvedValue([
      createMockConversation({ id: 1, other_participant_name: 'Jane' }),
    ])
    mockGetConversation.mockResolvedValue(detail)
    const user = userEvent.setup()

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText('Jane')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Jane'))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^send$/i })).toBeDisabled()
    })
  })

  it('Enter key sends message (without Shift)', async () => {
    const detail = createMockConversationDetail({
      id: 1,
      participant_2_name: 'Jane',
      messages: [],
      messages_total: 0,
    })
    mockListConversations.mockResolvedValue([
      createMockConversation({ id: 1, other_participant_name: 'Jane' }),
    ])
    mockGetConversation.mockResolvedValue(detail)
    mockSendMessage.mockResolvedValue(createMockMessage({ id: 20, content: 'Enter msg' }))
    const user = userEvent.setup()

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText('Jane')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Jane'))

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/type your message/i)).toBeInTheDocument()
    })

    const textarea = screen.getByPlaceholderText(/type your message/i)
    await user.type(textarea, 'Enter msg')
    await user.keyboard('{Enter}')

    expect(mockSendMessage).toHaveBeenCalledWith(1, 'Enter msg')
  })

  // ── New Conversation Modal ──────────────────────────────────

  it('opens new conversation modal', async () => {
    const recipients = [
      createMockRecipient({ user_id: 10, full_name: 'Mrs. Smith', role: 'teacher' }),
    ]
    mockGetRecipients.mockResolvedValue(recipients)
    mockListConversations.mockResolvedValue([])
    const user = userEvent.setup()

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText(/no messages yet/i)).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /\+ new message/i }))

    // Modal header and form
    expect(screen.getByRole('heading', { name: /new message/i })).toBeInTheDocument()
    expect(screen.getByText('To:')).toBeInTheDocument()
    expect(screen.getByText(/select a recipient/i)).toBeInTheDocument()
  })

  it('loads recipients in new conversation modal', async () => {
    const recipients = [
      createMockRecipient({ user_id: 10, full_name: 'Mrs. Smith', role: 'teacher' }),
      createMockRecipient({ user_id: 11, full_name: 'Admin Jane', role: 'admin' }),
    ]
    mockGetRecipients.mockResolvedValue(recipients)
    mockListConversations.mockResolvedValue([])
    const user = userEvent.setup()

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText(/no messages yet/i)).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /\+ new message/i }))

    expect(screen.getByText(/mrs\. smith/i)).toBeInTheDocument()
    expect(screen.getByText(/admin jane/i)).toBeInTheDocument()
  })

  it('creates conversation via modal', async () => {
    const recipients = [
      createMockRecipient({ user_id: 10, full_name: 'Mrs. Smith', role: 'teacher' }),
    ]
    mockGetRecipients.mockResolvedValue(recipients)
    mockListConversations.mockResolvedValue([])
    const newConv = createMockConversationDetail({
      id: 99,
      participant_2_name: 'Mrs. Smith',
      messages: [createMockMessage({ id: 50, content: 'Hello teacher' })],
      messages_total: 1,
    })
    mockCreateConversation.mockResolvedValue(newConv)
    const user = userEvent.setup()

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText(/no messages yet/i)).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /\+ new message/i }))

    // Fill form — labels aren't linked via for/id, so query by role
    const selects = screen.getAllByRole('combobox')
    const recipientSelect = selects.find(s => s.querySelector('option[value="10"]'))!
    await user.selectOptions(recipientSelect, '10')
    await user.type(screen.getByPlaceholderText(/homework question/i), 'Quick question')
    await user.type(screen.getByPlaceholderText(/write your message/i), 'Hello teacher')
    await user.click(screen.getByRole('button', { name: /send message/i }))

    expect(mockCreateConversation).toHaveBeenCalledWith({
      recipient_id: 10,
      subject: 'Quick question',
      initial_message: 'Hello teacher',
    })
  })

  it('shows no recipients message when none available', async () => {
    mockGetRecipients.mockResolvedValue([])
    mockListConversations.mockResolvedValue([])
    const user = userEvent.setup()

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText(/no messages yet/i)).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /\+ new message/i }))

    expect(screen.getByText(/no recipients available/i)).toBeInTheDocument()
  })

  it('closes modal via cancel button', async () => {
    mockListConversations.mockResolvedValue([])
    const user = userEvent.setup()

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText(/no messages yet/i)).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /\+ new message/i }))
    expect(screen.getByRole('heading', { name: /new message/i })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(screen.queryByRole('heading', { name: /new message/i })).not.toBeInTheDocument()
  })

  // ── Navigation & Auth ───────────────────────────────────────

  it('renders inside DashboardLayout with nav and header', async () => {
    mockListConversations.mockResolvedValue([])

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      // DashboardLayout provides the header with user name and sign out
      expect(screen.getByText('Test Parent')).toBeInTheDocument()
      expect(screen.getByText(/sign out/i)).toBeInTheDocument()
    })
  })

  // ── Error Handling ──────────────────────────────────────────

  it('shows error banner when conversation load fails', async () => {
    mockListConversations.mockRejectedValue(new Error('Network'))

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText(/failed to load conversations/i)).toBeInTheDocument()
    })
  })

  it('error banner can be dismissed', async () => {
    mockListConversations.mockRejectedValue(new Error('Network'))
    const user = userEvent.setup()

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText(/failed to load conversations/i)).toBeInTheDocument()
    })

    // Click the × dismiss button within the error banner
    const errorBanner = screen.getByText(/failed to load conversations/i).closest('.error-banner')!
    const dismissBtn = errorBanner.querySelector('button')!
    await user.click(dismissBtn)

    expect(screen.queryByText(/failed to load conversations/i)).not.toBeInTheDocument()
  })

  // ── Load More ───────────────────────────────────────────────

  it('shows load more button when there are more conversations', async () => {
    // Return exactly conversationLimit (20) items to indicate more exist
    const conversations = Array.from({ length: 20 }, (_, i) =>
      createMockConversation({ id: i + 1, other_participant_name: `User ${i + 1}` }),
    )
    mockListConversations.mockResolvedValue(conversations)

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText(/load more/i)).toBeInTheDocument()
    })
  })

  it('hides load more when fewer than limit returned', async () => {
    mockListConversations.mockResolvedValue([
      createMockConversation({ id: 1, other_participant_name: 'Only One' }),
    ])

    renderWithProviders(<MessagesPage />)

    await waitFor(() => {
      expect(screen.getByText('Only One')).toBeInTheDocument()
    })
    expect(screen.queryByText(/load more/i)).not.toBeInTheDocument()
  })
})
