import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────
const mockGetGuide = vi.fn()
const mockDeleteGuide = vi.fn()
const mockGenerateGuide = vi.fn()
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ id: '7' }),
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../api/client', () => ({
  studyApi: {
    getGuide: (...args: any[]) => mockGetGuide(...args),
    deleteGuide: (...args: any[]) => mockDeleteGuide(...args),
    generateGuide: (...args: any[]) => mockGenerateGuide(...args),
    updateGuide: vi.fn(),
  },
  coursesApi: { list: vi.fn().mockResolvedValue([]) },
  tasksApi: { create: vi.fn() },
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Test User', role: 'student', roles: ['student'] },
    logout: vi.fn(),
    switchRole: vi.fn(),
  }),
}))

vi.mock('../components/CourseAssignSelect', () => ({
  CourseAssignSelect: () => <div data-testid="course-assign-select" />,
}))

vi.mock('../components/CreateTaskModal', () => ({
  CreateTaskModal: ({ open }: { open: boolean }) =>
    open ? <div data-testid="create-task-modal">Task Modal</div> : null,
}))

// Mock react-markdown to avoid lazy-loading complexity in tests
vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => <div data-testid="markdown-content">{children}</div>,
}))

vi.mock('remark-gfm', () => ({
  default: () => {},
}))

// ── Helpers ────────────────────────────────────────────────────
const MOCK_GUIDE = {
  id: 7,
  user_id: 1,
  assignment_id: null,
  course_id: 5,
  course_content_id: null,
  title: 'Study Guide: Photosynthesis',
  content: '# Photosynthesis\n\nThe process by which plants convert sunlight into energy.',
  guide_type: 'study_guide',
  version: 1,
  parent_guide_id: null,
  created_at: '2025-06-15T10:00:00Z',
  archived_at: null,
}

function renderStudyGuide() {
  mockGetGuide.mockResolvedValue(MOCK_GUIDE)
  return renderWithProviders(<StudyGuidePage />, { initialEntries: ['/study/guide/7'] })
}

// ── Import after mocks ────────────────────────────────────────
import { StudyGuidePage } from './StudyGuidePage'

// ── Tests ──────────────────────────────────────────────────────
describe('StudyGuidePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state initially', () => {
    mockGetGuide.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<StudyGuidePage />, { initialEntries: ['/study/guide/7'] })
    expect(screen.getByText('Loading study guide...')).toBeInTheDocument()
  })

  it('shows error state when fetch fails', async () => {
    mockGetGuide.mockRejectedValue(new Error('Network error'))
    renderWithProviders(<StudyGuidePage />, { initialEntries: ['/study/guide/7'] })
    await waitFor(() => {
      expect(screen.getByText('Failed to load study guide')).toBeInTheDocument()
    })
  })

  it('renders guide title and content after loading', async () => {
    renderStudyGuide()
    await waitFor(() => {
      expect(screen.getByText('Study Guide: Photosynthesis')).toBeInTheDocument()
    })
    // Markdown renderer loads via dynamic import — wait for it
    await waitFor(() => {
      expect(screen.getByTestId('markdown-content')).toBeInTheDocument()
    })
  })

  it('shows creation date', async () => {
    renderStudyGuide()
    await waitFor(() => {
      expect(screen.getByText(/Created:/)).toBeInTheDocument()
    })
  })

  it('shows version badge when version > 1', async () => {
    mockGetGuide.mockResolvedValue({ ...MOCK_GUIDE, version: 2 })
    renderWithProviders(<StudyGuidePage />, { initialEntries: ['/study/guide/7'] })
    await waitFor(() => {
      expect(screen.getByText('v2')).toBeInTheDocument()
    })
  })

  it('does not show version badge for version 1', async () => {
    renderStudyGuide()
    await waitFor(() => {
      expect(screen.getByText('Study Guide: Photosynthesis')).toBeInTheDocument()
    })
    expect(screen.queryByText('v1')).not.toBeInTheDocument()
  })

  it('renders action buttons (Print, Regenerate, Delete)', async () => {
    renderStudyGuide()
    await waitFor(() => {
      expect(screen.getByText('Print')).toBeInTheDocument()
    })
    expect(screen.getByText('Regenerate')).toBeInTheDocument()
    expect(screen.getByText('Delete')).toBeInTheDocument()
  })

  it('deletes guide after confirmation', async () => {
    const user = userEvent.setup()
    mockDeleteGuide.mockResolvedValue(undefined)
    renderStudyGuide()
    await waitFor(() => {
      expect(screen.getByText('Delete')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Delete'))

    // Confirm modal should appear
    await waitFor(() => {
      expect(screen.getByText('Delete Study Guide')).toBeInTheDocument()
    })

    // Click the danger-styled Delete button inside the confirm modal
    const confirmBtn = document.querySelector('.danger-btn') as HTMLButtonElement
    await user.click(confirmBtn)

    await waitFor(() => {
      expect(mockDeleteGuide).toHaveBeenCalledWith(7)
    })
    expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
  })

  it('does not delete when cancelling confirmation', async () => {
    const user = userEvent.setup()
    renderStudyGuide()
    await waitFor(() => {
      expect(screen.getByText('Delete')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Delete'))

    await waitFor(() => {
      expect(screen.getByText('Delete Study Guide')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Cancel'))
    expect(mockDeleteGuide).not.toHaveBeenCalled()
  })

  it('navigates to new guide on Regenerate', async () => {
    const user = userEvent.setup()
    mockGenerateGuide.mockResolvedValue({ id: 99 })
    renderStudyGuide()
    await waitFor(() => {
      expect(screen.getByText('Regenerate')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Regenerate'))

    await waitFor(() => {
      expect(mockGenerateGuide).toHaveBeenCalledWith(
        expect.objectContaining({ regenerate_from_id: 7 }),
      )
    })
    expect(mockNavigate).toHaveBeenCalledWith('/study/guide/99')
  })

  it('shows error when regenerate fails', async () => {
    const user = userEvent.setup()
    mockGenerateGuide.mockRejectedValue(new Error('AI failed'))
    renderStudyGuide()
    await waitFor(() => {
      expect(screen.getByText('Regenerate')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Regenerate'))

    await waitFor(() => {
      expect(screen.getByText('Failed to regenerate')).toBeInTheDocument()
    })
  })

  it('opens task modal on "+ Task" button click', async () => {
    const user = userEvent.setup()
    renderStudyGuide()
    await waitFor(() => {
      expect(screen.getByTitle('Create task')).toBeInTheDocument()
    })

    await user.click(screen.getByTitle('Create task'))
    expect(screen.getByTestId('create-task-modal')).toBeInTheDocument()
  })

  it('has back link to dashboard', async () => {
    renderStudyGuide()
    await waitFor(() => {
      expect(screen.getByText(/Back to Dashboard/)).toBeInTheDocument()
    })
  })
})
