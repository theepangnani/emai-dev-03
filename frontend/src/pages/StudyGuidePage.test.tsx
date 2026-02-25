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

vi.mock('../components/ContentCard', () => ({
  ContentCard: ({ children }: { children: React.ReactNode }) => <div data-testid="content-card">{children}</div>,
  MarkdownBody: ({ content }: { content: string }) => <div data-testid="markdown-content">{content}</div>,
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
      expect(screen.getByText('Failed to load study guide. Please try again.')).toBeInTheDocument()
    })
  })

  it('shows specific message when guide not found (404)', async () => {
    mockGetGuide.mockRejectedValue({ response: { status: 404 } })
    renderWithProviders(<StudyGuidePage />, { initialEntries: ['/study/guide/7'] })
    await waitFor(() => {
      expect(screen.getByText('This study guide no longer exists. It may have been deleted or archived.')).toBeInTheDocument()
    })
  })

  it('renders guide title and content after loading', async () => {
    renderStudyGuide()
    await waitFor(() => {
      // Title appears in both breadcrumb and heading
      const matches = screen.getAllByText('Study Guide: Photosynthesis')
      expect(matches.length).toBeGreaterThanOrEqual(1)
    })
    // Markdown renderer loads via dynamic import — wait for it
    await waitFor(() => {
      expect(screen.getByTestId('markdown-content')).toBeInTheDocument()
    })
  })

  it('shows creation date', async () => {
    renderStudyGuide()
    // The date is rendered as a formatted date string without "Created:" prefix
    const expectedDate = new Date('2025-06-15T10:00:00Z').toLocaleDateString()
    await waitFor(() => {
      expect(screen.getByText(expectedDate)).toBeInTheDocument()
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
      const matches = screen.getAllByText('Study Guide: Photosynthesis')
      expect(matches.length).toBeGreaterThanOrEqual(1)
    })
    expect(screen.queryByText('v1')).not.toBeInTheDocument()
  })

  it('renders action buttons (Print, Regenerate, Delete)', async () => {
    renderStudyGuide()
    // Action buttons are icon-only with title attributes
    await waitFor(() => {
      expect(screen.getByTitle('Print')).toBeInTheDocument()
    })
    expect(screen.getByTitle('Regenerate')).toBeInTheDocument()
    expect(screen.getByTitle('Delete')).toBeInTheDocument()
  })

  it('deletes guide after confirmation', async () => {
    const user = userEvent.setup()
    mockDeleteGuide.mockResolvedValue(undefined)
    renderStudyGuide()
    await waitFor(() => {
      expect(screen.getByTitle('Delete')).toBeInTheDocument()
    })

    await user.click(screen.getByTitle('Delete'))

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
      expect(screen.getByTitle('Delete')).toBeInTheDocument()
    })

    await user.click(screen.getByTitle('Delete'))

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
      expect(screen.getByTitle('Regenerate')).toBeInTheDocument()
    })

    await user.click(screen.getByTitle('Regenerate'))

    await waitFor(() => {
      expect(mockGenerateGuide).toHaveBeenCalledWith(
        expect.objectContaining({ regenerate_from_id: 7 }),
      )
    })
    expect(mockNavigate).toHaveBeenCalledWith('/study/guide/99', { state: { newGuide: true } })
  })

  it('shows error when regenerate fails', async () => {
    const user = userEvent.setup()
    mockGenerateGuide.mockRejectedValue(new Error('AI failed'))
    renderStudyGuide()
    await waitFor(() => {
      expect(screen.getByTitle('Regenerate')).toBeInTheDocument()
    })

    await user.click(screen.getByTitle('Regenerate'))

    await waitFor(() => {
      expect(screen.getByText('Failed to regenerate')).toBeInTheDocument()
    })
  })

  it('opens task modal on "+ Task" button click', async () => {
    const user = userEvent.setup()
    renderStudyGuide()
    await waitFor(() => {
      expect(screen.getByTitle('Create Task')).toBeInTheDocument()
    })

    await user.click(screen.getByTitle('Create Task'))
    expect(screen.getByTestId('create-task-modal')).toBeInTheDocument()
  })

  it('has page navigation with back button', async () => {
    renderStudyGuide()
    await waitFor(() => {
      // PageNav provides deterministic back link to Materials
      const navLinks = screen.getAllByText('Materials')
      expect(navLinks.length).toBeGreaterThanOrEqual(1)
    })
  })
})
