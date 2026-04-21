import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'
import { createMockNotification } from '../test/mocks'

// Mocks
const mockGetUnreadCount = vi.fn()
const mockList = vi.fn()
const mockMarkAsRead = vi.fn()
const mockMarkAllAsRead = vi.fn()
const mockNavigate = vi.fn()

vi.mock('../api/client', () => ({
  notificationsApi: {
    getUnreadCount: () => mockGetUnreadCount(),
    list: (...args: unknown[]) => mockList(...args),
    markAsRead: (...args: unknown[]) => mockMarkAsRead(...args),
    markAllAsRead: () => mockMarkAllAsRead(),
  },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

import { NotificationBell } from './NotificationBell'

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetUnreadCount.mockResolvedValue({ count: 0 })
    mockList.mockResolvedValue([])
    mockMarkAsRead.mockResolvedValue(undefined)
    mockMarkAllAsRead.mockResolvedValue(undefined)
  })

  it('renders bell button', async () => {
    renderWithProviders(<NotificationBell />)

    expect(screen.getByRole('button', { name: /notifications/i })).toBeInTheDocument()
  })

  it('shows unread count badge when count > 0', async () => {
    mockGetUnreadCount.mockResolvedValue({ count: 5 })

    renderWithProviders(<NotificationBell />)

    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument()
    })
  })

  it('caps badge at 99+', async () => {
    mockGetUnreadCount.mockResolvedValue({ count: 150 })

    renderWithProviders(<NotificationBell />)

    await waitFor(() => {
      expect(screen.getByText('99+')).toBeInTheDocument()
    })
  })

  it('hides badge when count is 0', async () => {
    mockGetUnreadCount.mockResolvedValue({ count: 0 })

    renderWithProviders(<NotificationBell />)

    // Wait for the API call to resolve
    await waitFor(() => {
      expect(mockGetUnreadCount).toHaveBeenCalled()
    })
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('opens dropdown and loads notifications on click', async () => {
    const notifications = [
      createMockNotification({ id: 1, title: 'Assignment Due', type: 'assignment_due' }),
      createMockNotification({ id: 2, title: 'New Message', type: 'message' }),
    ]
    mockList.mockResolvedValue(notifications)
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)

    await user.click(screen.getByRole('button', { name: /notifications/i }))

    await waitFor(() => {
      expect(screen.getByText('Assignment Due')).toBeInTheDocument()
    })
    expect(screen.getByText('New Message')).toBeInTheDocument()
    expect(mockList).toHaveBeenCalledWith(0, 10, true)
  })

  it('shows loading state while fetching notifications', async () => {
    // List never resolves to keep loading state
    mockList.mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)

    await user.click(screen.getByRole('button', { name: /notifications/i }))

    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('shows empty state when no notifications', async () => {
    mockList.mockResolvedValue([])
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)

    await user.click(screen.getByRole('button', { name: /notifications/i }))

    await waitFor(() => {
      expect(screen.getByText(/no notifications/i)).toBeInTheDocument()
    })
  })

  it('closes dropdown on second click', async () => {
    mockList.mockResolvedValue([])
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)

    const bell = screen.getByRole('button', { name: /notifications/i })

    // Open
    await user.click(bell)
    await waitFor(() => {
      expect(screen.getByText(/no notifications/i)).toBeInTheDocument()
    })

    // Close
    await user.click(bell)
    expect(screen.queryByText(/no notifications/i)).not.toBeInTheDocument()
  })

  it('clicking notification marks as read and opens modal', async () => {
    const notification = createMockNotification({
      id: 10,
      title: 'Test Alert',
      content: 'Alert body text',
      read: false,
    })
    mockGetUnreadCount.mockResolvedValue({ count: 1 })
    mockList.mockResolvedValue([notification])
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)

    await user.click(screen.getByRole('button', { name: /notifications/i }))
    await waitFor(() => {
      expect(screen.getByText('Test Alert')).toBeInTheDocument()
    })

    // Click the notification item in the dropdown
    await user.click(screen.getByText('Test Alert'))

    expect(mockMarkAsRead).toHaveBeenCalledWith(10)

    // Modal should appear (portaled to body)
    await waitFor(() => {
      expect(screen.getByText('Alert body text')).toBeInTheDocument()
    })
  })

  it('does not call markAsRead for already-read notifications', async () => {
    const notification = createMockNotification({
      id: 20,
      title: 'Read Alert',
      read: true,
    })
    mockList.mockResolvedValue([notification])
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)

    await user.click(screen.getByRole('button', { name: /notifications/i }))
    await waitFor(() => {
      expect(screen.getByText('Read Alert')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Read Alert'))

    expect(mockMarkAsRead).not.toHaveBeenCalled()
  })

  it('modal action button navigates to link', async () => {
    const notification = createMockNotification({
      id: 30,
      title: 'Go Somewhere',
      content: 'Click to navigate',
      link: '/dashboard',
    })
    mockList.mockResolvedValue([notification])
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)

    // Open dropdown, click notification to open modal
    await user.click(screen.getByRole('button', { name: /notifications/i }))
    await waitFor(() => {
      expect(screen.getByText('Go Somewhere')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Go Somewhere'))

    // Modal should have action button
    await waitFor(() => {
      expect(screen.getByText(/go to/i)).toBeInTheDocument()
    })

    await user.click(screen.getByText(/go to/i))

    expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
  })

  it('modal has no action button when notification has no link', async () => {
    const notification = createMockNotification({
      id: 40,
      title: 'No Link',
      content: 'Just info',
      link: null,
    })
    mockList.mockResolvedValue([notification])
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)

    await user.click(screen.getByRole('button', { name: /notifications/i }))
    await waitFor(() => {
      expect(screen.getByText('No Link')).toBeInTheDocument()
    })
    await user.click(screen.getByText('No Link'))

    await waitFor(() => {
      expect(screen.getByText('Just info')).toBeInTheDocument()
    })
    expect(screen.queryByText(/go to/i)).not.toBeInTheDocument()
  })

  it('modal closes when close button is clicked', async () => {
    const notification = createMockNotification({
      id: 50,
      title: 'Closeable',
      content: 'Close me',
    })
    mockList.mockResolvedValue([notification])
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)

    await user.click(screen.getByRole('button', { name: /notifications/i }))
    await waitFor(() => {
      expect(screen.getByText('Closeable')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Closeable'))

    // Modal is open
    await waitFor(() => {
      expect(screen.getByText('Close me')).toBeInTheDocument()
    })

    // Click close button (×)
    await user.click(screen.getByText('×'))

    await waitFor(() => {
      expect(screen.queryByText('Close me')).not.toBeInTheDocument()
    })
  })

  it('mark all read button calls markAllAsRead and clears list', async () => {
    mockGetUnreadCount.mockResolvedValue({ count: 3 })
    const notifications = [
      createMockNotification({ id: 1, title: 'N1', read: false }),
      createMockNotification({ id: 2, title: 'N2', read: false }),
    ]
    mockList.mockResolvedValue(notifications)
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)

    // Wait for unread count
    await waitFor(() => {
      expect(screen.getByText('3')).toBeInTheDocument()
    })

    // Open dropdown
    await user.click(screen.getByRole('button', { name: /notifications/i }))
    await waitFor(() => {
      expect(screen.getByText('N1')).toBeInTheDocument()
    })

    // Click "Mark all read"
    await user.click(screen.getByText(/mark all read/i))

    expect(mockMarkAllAsRead).toHaveBeenCalledOnce()
    await waitFor(() => {
      expect(screen.getByText(/no notifications/i)).toBeInTheDocument()
    })
  })

  it('mark all read button hidden when no unread notifications', async () => {
    mockGetUnreadCount.mockResolvedValue({ count: 0 })
    mockList.mockResolvedValue([])
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)

    await user.click(screen.getByRole('button', { name: /notifications/i }))

    await waitFor(() => {
      expect(screen.getByText(/no notifications/i)).toBeInTheDocument()
    })
    expect(screen.queryByText(/mark all read/i)).not.toBeInTheDocument()
  })

  // #3884: HTML content in the notification modal must render as real
  // DOM elements (not literal text), and unsafe tags must be stripped.
  describe('HTML content rendering (#3884)', () => {
    it('renders sanitised HTML tags as real DOM elements, not literal text', async () => {
      const notification = createMockNotification({
        id: 100,
        title: 'Email Digest for Alex',
        content: '<h3>Hello</h3><p>Body</p>',
      })
      mockList.mockResolvedValue([notification])
      const user = userEvent.setup()

      renderWithProviders(<NotificationBell />)

      await user.click(screen.getByRole('button', { name: /notifications/i }))
      await waitFor(() => {
        expect(screen.getByText('Email Digest for Alex')).toBeInTheDocument()
      })
      await user.click(screen.getByText('Email Digest for Alex'))

      // Real heading element with text "Hello"
      const heading = await screen.findByRole('heading', { level: 3, name: 'Hello' })
      expect(heading.tagName).toBe('H3')

      // Real paragraph with text "Body"
      const body = screen.getByText('Body')
      expect(body.tagName).toBe('P')

      // Literal tag text must NOT appear anywhere
      expect(screen.queryByText(/<h3>Hello<\/h3>/)).not.toBeInTheDocument()
      expect(screen.queryByText(/<p>Body<\/p>/)).not.toBeInTheDocument()
    })

    it('strips <script> tags from notification content', async () => {
      const notification = createMockNotification({
        id: 101,
        title: 'Malicious Notification',
        content: '<p>Safe text</p><script>alert(1)</script>',
      })
      mockList.mockResolvedValue([notification])
      const user = userEvent.setup()

      renderWithProviders(<NotificationBell />)

      await user.click(screen.getByRole('button', { name: /notifications/i }))
      await waitFor(() => {
        expect(screen.getByText('Malicious Notification')).toBeInTheDocument()
      })
      await user.click(screen.getByText('Malicious Notification'))

      // Safe content still renders
      await waitFor(() => {
        expect(screen.getByText('Safe text')).toBeInTheDocument()
      })

      // No <script> element anywhere in the DOM
      expect(document.querySelector('script[data-notif]')).toBeNull()
      // More thorough: ensure no script tag with the payload text survives in the modal
      const allScripts = document.body.querySelectorAll('script')
      allScripts.forEach((s) => {
        expect(s.textContent).not.toContain('alert(1)')
      })
      // Literal "alert(1)" text from the payload must not be visible either
      expect(screen.queryByText(/alert\(1\)/)).not.toBeInTheDocument()
    })

    it('renders plain-text notification content unchanged', async () => {
      const notification = createMockNotification({
        id: 102,
        title: 'Plain Alert',
        content: 'You have a new message',
      })
      mockList.mockResolvedValue([notification])
      const user = userEvent.setup()

      renderWithProviders(<NotificationBell />)

      await user.click(screen.getByRole('button', { name: /notifications/i }))
      await waitFor(() => {
        expect(screen.getByText('Plain Alert')).toBeInTheDocument()
      })
      await user.click(screen.getByText('Plain Alert'))

      await waitFor(() => {
        expect(screen.getByText('You have a new message')).toBeInTheDocument()
      })
    })
  })

  it('polls unread count every 60 seconds', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    mockGetUnreadCount.mockResolvedValue({ count: 0 })

    renderWithProviders(<NotificationBell />)

    // Flush initial useEffect microtask
    await vi.advanceTimersByTimeAsync(0)
    expect(mockGetUnreadCount).toHaveBeenCalledTimes(1)

    // Advance 60 seconds — second poll
    await vi.advanceTimersByTimeAsync(60_000)
    expect(mockGetUnreadCount).toHaveBeenCalledTimes(2)

    // Advance another 60 seconds — third poll
    await vi.advanceTimersByTimeAsync(60_000)
    expect(mockGetUnreadCount).toHaveBeenCalledTimes(3)

    vi.useRealTimers()
  })
})
