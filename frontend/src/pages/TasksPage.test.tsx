import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────
const mockList = vi.fn()
const mockCreate = vi.fn()
const mockUpdate = vi.fn()
const mockDeleteTask = vi.fn()
const mockRestore = vi.fn()
const mockPermanentDelete = vi.fn()
const mockGetAssignableUsers = vi.fn()
const mockNavigate = vi.fn()
const mockSearchParams = new URLSearchParams()
const mockSetSearchParams = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearchParams: () => [mockSearchParams, mockSetSearchParams],
  }
})

vi.mock('../api/client', () => ({
  tasksApi: {
    list: (...args: any[]) => mockList(...args),
    create: (...args: any[]) => mockCreate(...args),
    update: (...args: any[]) => mockUpdate(...args),
    delete: (...args: any[]) => mockDeleteTask(...args),
    restore: (...args: any[]) => mockRestore(...args),
    permanentDelete: (...args: any[]) => mockPermanentDelete(...args),
    getAssignableUsers: (...args: any[]) => mockGetAssignableUsers(...args),
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

// ── Helpers ────────────────────────────────────────────────────
const makeMockTask = (overrides: Partial<import('../api/client').TaskItem> = {}): import('../api/client').TaskItem => ({
  id: 1,
  created_by_user_id: 1,
  assigned_to_user_id: null,
  title: 'Review Chapter 5',
  description: 'Read pages 100-120',
  due_date: '2025-12-01T10:00:00',
  is_completed: false,
  completed_at: null,
  archived_at: null,
  priority: 'medium',
  category: null,
  creator_name: 'Test User',
  assignee_name: null,
  course_id: null,
  course_content_id: null,
  study_guide_id: null,
  course_name: null,
  course_content_title: null,
  study_guide_title: null,
  study_guide_type: null,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: null,
  ...overrides,
})

const MOCK_TASKS = [
  makeMockTask({ id: 1, title: 'Review Chapter 5', priority: 'medium' }),
  makeMockTask({ id: 2, title: 'Complete homework', priority: 'high', due_date: '2025-12-15T10:00:00' }),
  makeMockTask({ id: 3, title: 'Optional reading', priority: 'low', due_date: null }),
]

function renderTasks(tasks = MOCK_TASKS) {
  mockList.mockResolvedValue(tasks)
  mockGetAssignableUsers.mockResolvedValue([])
  return renderWithProviders(<TasksPage />, { initialEntries: ['/tasks'] })
}

// ── Import after mocks ────────────────────────────────────────
import { TasksPage } from './TasksPage'

// ── Tests ──────────────────────────────────────────────────────
describe('TasksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading skeleton initially', () => {
    mockList.mockReturnValue(new Promise(() => {}))
    mockGetAssignableUsers.mockResolvedValue([])
    renderWithProviders(<TasksPage />, { initialEntries: ['/tasks'] })
    const skeletons = document.querySelectorAll('.skeleton')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('shows error state when fetch fails', async () => {
    mockList.mockRejectedValue(new Error('Server error'))
    mockGetAssignableUsers.mockResolvedValue([])
    renderWithProviders(<TasksPage />, { initialEntries: ['/tasks'] })
    await waitFor(() => {
      expect(screen.getByText(/Error loading tasks/)).toBeInTheDocument()
    })
  })

  it('renders task list after loading', async () => {
    renderTasks()
    await waitFor(() => {
      expect(screen.getByText('Review Chapter 5')).toBeInTheDocument()
    })
    expect(screen.getByText('Complete homework')).toBeInTheDocument()
    expect(screen.getByText('Optional reading')).toBeInTheDocument()
    expect(screen.getByText('3 tasks')).toBeInTheDocument()
  })

  it('shows empty state when no tasks', async () => {
    renderTasks([])
    await waitFor(() => {
      expect(screen.getByText('No tasks found.')).toBeInTheDocument()
    })
  })

  it('shows priority badges', async () => {
    renderTasks()
    await waitFor(() => {
      expect(screen.getByText('Review Chapter 5')).toBeInTheDocument()
    })
    expect(screen.getByText(/high/)).toBeInTheDocument()
    expect(screen.getByText(/medium/)).toBeInTheDocument()
    expect(screen.getByText(/low/)).toBeInTheDocument()
  })

  it('toggles task completion on checkbox click', async () => {
    const user = userEvent.setup()
    mockUpdate.mockResolvedValue({})
    renderTasks()
    await waitFor(() => {
      expect(screen.getByText('Review Chapter 5')).toBeInTheDocument()
    })

    const checkboxes = document.querySelectorAll('.task-row-checkbox')
    await user.click(checkboxes[0])

    expect(mockUpdate).toHaveBeenCalledWith(1, { is_completed: true })
  })

  it('opens create modal on "+ New Task" click', async () => {
    const user = userEvent.setup()
    renderTasks()
    await waitFor(() => {
      expect(screen.getByText('+ New Task')).toBeInTheDocument()
    })

    await user.click(screen.getByText('+ New Task'))
    expect(screen.getByRole('heading', { name: 'Create Task' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Task title')).toBeInTheDocument()
  })

  it('creates a task via the modal', async () => {
    const user = userEvent.setup()
    mockCreate.mockResolvedValue({})
    renderTasks()
    await waitFor(() => {
      expect(screen.getByText('+ New Task')).toBeInTheDocument()
    })

    await user.click(screen.getByText('+ New Task'))
    await user.type(screen.getByPlaceholderText('Task title'), 'New task title')
    await user.click(screen.getByRole('button', { name: 'Create Task' }))

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'New task title' }),
      )
    })
  })

  it('disables Create Task button when title is empty', async () => {
    const user = userEvent.setup()
    renderTasks()
    await waitFor(() => {
      expect(screen.getByText('+ New Task')).toBeInTheDocument()
    })

    await user.click(screen.getByText('+ New Task'))
    expect(screen.getByRole('button', { name: 'Create Task' })).toBeDisabled()
  })

  it('opens edit modal on edit button click', async () => {
    const user = userEvent.setup()
    renderTasks()
    await waitFor(() => {
      expect(screen.getByText('Review Chapter 5')).toBeInTheDocument()
    })

    const editBtns = screen.getAllByTitle('Edit')
    await user.click(editBtns[0])

    expect(screen.getByText('Edit Task')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Review Chapter 5')).toBeInTheDocument()
  })

  it('saves edited task', async () => {
    const user = userEvent.setup()
    mockUpdate.mockResolvedValue({})
    renderTasks()
    await waitFor(() => {
      expect(screen.getByText('Review Chapter 5')).toBeInTheDocument()
    })

    const editBtns = screen.getAllByTitle('Edit')
    await user.click(editBtns[0])

    const titleInput = screen.getByDisplayValue('Review Chapter 5')
    await user.clear(titleInput)
    await user.type(titleInput, 'Updated title')
    await user.click(screen.getByText('Save Changes'))

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ title: 'Updated title' }),
      )
    })
  })

  it('archives task with confirmation', async () => {
    const user = userEvent.setup()
    mockDeleteTask.mockResolvedValue({})
    renderTasks()
    await waitFor(() => {
      expect(screen.getByText('Review Chapter 5')).toBeInTheDocument()
    })

    const archiveBtns = screen.getAllByTitle('Archive')
    await user.click(archiveBtns[0])

    // Confirm modal
    await waitFor(() => {
      expect(screen.getByText('Archive Task')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Archive'))

    await waitFor(() => {
      expect(mockDeleteTask).toHaveBeenCalledWith(1)
    })
  })

  it('shows restore and permanent delete buttons for archived tasks', async () => {
    const archivedTask = makeMockTask({ id: 4, title: 'Archived task', archived_at: '2025-01-02T00:00:00Z' })
    renderTasks([archivedTask])
    await waitFor(() => {
      expect(screen.getByText('Archived task')).toBeInTheDocument()
    })

    expect(screen.getByTitle('Restore')).toBeInTheDocument()
    expect(screen.getByTitle('Delete Forever')).toBeInTheDocument()
  })

  it('restores an archived task', async () => {
    const user = userEvent.setup()
    mockRestore.mockResolvedValue({})
    const archivedTask = makeMockTask({ id: 4, title: 'Archived task', archived_at: '2025-01-02T00:00:00Z' })
    renderTasks([archivedTask])
    await waitFor(() => {
      expect(screen.getByText('Archived task')).toBeInTheDocument()
    })

    await user.click(screen.getByTitle('Restore'))

    await waitFor(() => {
      expect(mockRestore).toHaveBeenCalledWith(4)
    })
  })

  it('navigates to task detail on row click', async () => {
    const user = userEvent.setup()
    renderTasks()
    await waitFor(() => {
      expect(screen.getByText('Review Chapter 5')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Review Chapter 5'))
    expect(mockNavigate).toHaveBeenCalledWith('/tasks/1')
  })

  describe('filters', () => {
    it('filters by priority', async () => {
      const user = userEvent.setup()
      renderTasks()
      await waitFor(() => {
        expect(screen.getByText('3 tasks')).toBeInTheDocument()
      })

      const prioritySelect = screen.getAllByRole('combobox')[1] // Priority is second select
      await user.selectOptions(prioritySelect, 'high')

      // Only high priority task should be visible
      expect(screen.getByText('1 task')).toBeInTheDocument()
      expect(screen.getByText('Complete homework')).toBeInTheDocument()
      expect(screen.queryByText('Review Chapter 5')).not.toBeInTheDocument()
    })

    it('shows task count after filtering', async () => {
      const user = userEvent.setup()
      renderTasks()
      await waitFor(() => {
        expect(screen.getByText('3 tasks')).toBeInTheDocument()
      })

      const prioritySelect = screen.getAllByRole('combobox')[1]
      await user.selectOptions(prioritySelect, 'low')

      expect(screen.getByText('1 task')).toBeInTheDocument()
    })
  })

  it('shows linked study guide badge', async () => {
    const taskWithGuide = makeMockTask({
      id: 5,
      title: 'Review guide',
      study_guide_id: 42,
      study_guide_title: 'React Basics',
      study_guide_type: 'flashcards',
    })
    renderTasks([taskWithGuide])
    await waitFor(() => {
      expect(screen.getByText('Review guide')).toBeInTheDocument()
    })

    expect(screen.getByText('Flashcards: React Basics')).toBeInTheDocument()
  })

  it('shows assignee name for assigned tasks', async () => {
    const assignedTask = makeMockTask({
      id: 6,
      title: 'Assigned task',
      assigned_to_user_id: 2,
      assignee_name: 'Jane Doe',
    })
    renderTasks([assignedTask])
    await waitFor(() => {
      expect(screen.getByText('Assigned task')).toBeInTheDocument()
    })

    expect(screen.getByText('→ Jane Doe')).toBeInTheDocument()
  })

  it('shows Retry button on error and retries', async () => {
    const user = userEvent.setup()
    mockList.mockRejectedValueOnce(new Error('Server error'))
    mockGetAssignableUsers.mockResolvedValue([])
    renderWithProviders(<TasksPage />, { initialEntries: ['/tasks'] })

    await waitFor(() => {
      expect(screen.getByText('Retry')).toBeInTheDocument()
    })

    mockList.mockResolvedValue(MOCK_TASKS)
    await user.click(screen.getByText('Retry'))

    await waitFor(() => {
      expect(screen.getByText('Review Chapter 5')).toBeInTheDocument()
    })
  })
})
