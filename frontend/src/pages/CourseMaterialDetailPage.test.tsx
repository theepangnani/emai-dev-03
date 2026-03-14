import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ id: '1' }),
  }
})

vi.mock('../context/ThemeContext', () => ({
  useTheme: () => ({ theme: 'light', setTheme: vi.fn(), cycleTheme: vi.fn() }),
  ThemeProvider: ({ children }: { children: React.ReactNode }) => children,
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Teacher User', role: 'teacher', roles: ['teacher'] },
    logout: vi.fn(),
    switchRole: vi.fn(),
  }),
}))

const mockCourseContent = {
  id: 1,
  course_id: 10,
  course_name: 'Main Class',
  title: 't.math.set2.8',
  description: 'Test description',
  text_content: 'Some content',
  content_type: 'notes',
  has_file: false,
  original_filename: null,
  source_files_count: 0,
  created_at: '2026-03-01T00:00:00',
  updated_at: '2026-03-01T00:00:00',
}

const mockGet = vi.fn().mockResolvedValue(mockCourseContent)
const mockListGuides = vi.fn().mockResolvedValue([])
const mockTasksList = vi.fn().mockResolvedValue([])
const mockGetLinkedCourseIds = vi.fn().mockResolvedValue({ linked_course_ids: [10], children: [] })

vi.mock('../api/client', () => ({
  courseContentsApi: {
    get: (...args: any[]) => mockGet(...args),
    getLinkedCourseIds: (...args: any[]) => mockGetLinkedCourseIds(...args),
    delete: vi.fn().mockResolvedValue({}),
    download: vi.fn().mockResolvedValue({}),
  },
  studyApi: {
    listGuides: (...args: any[]) => mockListGuides(...args),
    resolveStudent: vi.fn().mockRejectedValue(new Error('not parent')),
  },
  parentApi: {
    assignCoursesToChild: vi.fn().mockResolvedValue({}),
  },
  messagesApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }),
  },
  inspirationApi: {
    getRandom: vi.fn().mockRejectedValue(new Error('none')),
  },
  faqApi: {
    getByErrorCode: vi.fn().mockRejectedValue(new Error('not found')),
  },
}))

vi.mock('../api/tasks', () => ({
  tasksApi: {
    list: (...args: any[]) => mockTasksList(...args),
  },
}))

vi.mock('../api/courses', () => ({
  coursesApi: {
    list: vi.fn().mockResolvedValue([]),
  },
}))

// Stub sub-components — EditMaterialModal renders with modal-overlay to test scroll lock
vi.mock('../components/EditMaterialModal', () => ({
  EditMaterialModal: ({ onClose }: { onClose: () => void }) => (
    <div className="modal-overlay" data-testid="edit-material-modal-overlay">
      <div className="modal edit-material-modal" data-testid="edit-material-modal">
        <button onClick={onClose}>Close</button>
      </div>
    </div>
  ),
}))

vi.mock('../components/CreateTaskModal', () => ({
  CreateTaskModal: () => null,
}))

vi.mock('../components/ConfirmModal', () => ({
  useConfirm: () => ({ confirm: vi.fn().mockResolvedValue(true), confirmModal: null }),
}))

vi.mock('../components/PageNav', () => ({
  PageNav: () => null,
}))

vi.mock('../components/DashboardLayout', () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => <div data-testid="dashboard-layout">{children}</div>,
}))

vi.mock('../context/FABContext', () => ({
  useRegisterNotesFAB: () => {},
  useFABContext: () => ({ notesFAB: null, registerNotesFAB: () => {}, unregisterNotesFAB: () => {} }),
  FABProvider: ({ children }: { children: React.ReactNode }) => children,
}))

vi.mock('../api/resourceLinks', () => ({
  resourceLinksApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({}),
  },
}))

vi.mock('../components/NotesPanel', () => ({
  NotesPanel: () => null,
}))

vi.mock('../components/SelectionTooltip', () => ({
  SelectionTooltip: () => null,
}))

vi.mock('../hooks/useTextSelection', () => ({
  useTextSelection: () => ({ selectedText: '', position: null, clearSelection: vi.fn() }),
}))

vi.mock('../components/AICreditsDisplay', () => ({
  AIWarningBanner: () => null,
}))

vi.mock('../components/AILimitRequestModal', () => ({
  AILimitRequestModal: () => null,
}))

vi.mock('../components/Skeleton', () => ({
  DetailSkeleton: () => <div data-testid="skeleton">Loading...</div>,
}))

vi.mock('../components/FAQErrorHint', () => ({
  FAQErrorHint: () => null,
}))

vi.mock('./course-material/DocumentTab', () => ({
  DocumentTab: () => <div>Document Tab</div>,
}))

vi.mock('./course-material/StudyGuideTab', () => ({
  StudyGuideTab: () => <div>Study Guide Tab</div>,
}))

vi.mock('./course-material/QuizTab', () => ({
  QuizTab: () => <div>Quiz Tab</div>,
}))

vi.mock('./course-material/FlashcardsTab', () => ({
  FlashcardsTab: () => <div>Flashcards Tab</div>,
}))

vi.mock('./course-material/MindMapTab', () => ({
  MindMapTab: () => <div>Mind Map Tab</div>,
}))

vi.mock('./course-material/VideosLinksTab', () => ({
  VideosLinksTab: () => <div>Videos Tab</div>,
}))

vi.mock('./course-material/ReplaceDocumentModal', () => ({
  ReplaceDocumentModal: () => null,
}))

import { CourseMaterialDetailPage } from './CourseMaterialDetailPage'

describe('CourseMaterialDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('IntersectionObserver', vi.fn(() => ({
      observe: vi.fn(),
      disconnect: vi.fn(),
      unobserve: vi.fn(),
    })))
  })

  it('does NOT render course_name badge next to the title (no duplicate label)', async () => {
    renderWithProviders(<CourseMaterialDetailPage />)

    await waitFor(() => {
      expect(screen.getByText('t.math.set2.8')).toBeInTheDocument()
    })

    // The course name should appear only ONCE — in the meta row (cm-type-badge), NOT as cm-course-badge next to the title
    const badges = screen.getAllByText('Main Class')
    expect(badges).toHaveLength(1)
    expect(badges[0].className).toContain('cm-type-badge')
  })

  it('renders an edit icon button next to the title that opens EditMaterialModal', async () => {
    const user = userEvent.setup()
    renderWithProviders(<CourseMaterialDetailPage />)

    await waitFor(() => {
      expect(screen.getByText('t.math.set2.8')).toBeInTheDocument()
    })

    // The edit button next to the title should exist
    const editBtn = screen.getByLabelText('Edit material', { selector: '.cm-title-edit-btn' })
    expect(editBtn).toBeInTheDocument()

    // Clicking it should open the edit modal
    expect(screen.queryByTestId('edit-material-modal')).not.toBeInTheDocument()
    await user.click(editBtn)
    expect(screen.getByTestId('edit-material-modal')).toBeInTheDocument()
  })

  it('does NOT render welcome section on detail sub-page (#1098)', async () => {
    renderWithProviders(<CourseMaterialDetailPage />)

    await waitFor(() => {
      expect(screen.getByText('t.math.set2.8')).toBeInTheDocument()
    })

    // Welcome section should be suppressed on detail pages — headerSlot={() => null}
    expect(screen.queryByText(/Welcome back/)).not.toBeInTheDocument()
    expect(screen.queryByText("Here's your overview")).not.toBeInTheDocument()
  })

  it('renders modal-overlay class when edit modal is open (enables body scroll lock)', async () => {
    const user = userEvent.setup()
    renderWithProviders(<CourseMaterialDetailPage />)

    await waitFor(() => {
      expect(screen.getByText('t.math.set2.8')).toBeInTheDocument()
    })

    // No overlay initially
    expect(screen.queryByTestId('edit-material-modal-overlay')).not.toBeInTheDocument()

    // Open modal
    const editBtn = screen.getByLabelText('Edit material', { selector: '.cm-title-edit-btn' })
    await user.click(editBtn)

    // Overlay should have modal-overlay class (CSS rule body:has(.modal-overlay) locks scroll)
    const overlay = screen.getByTestId('edit-material-modal-overlay')
    expect(overlay).toHaveClass('modal-overlay')
  })
})
