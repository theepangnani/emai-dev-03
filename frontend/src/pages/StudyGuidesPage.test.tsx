import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────
const mockListAll = vi.fn()
const mockListGuides = vi.fn()
const mockCoursesList = vi.fn()
const mockGetLinkedCourseIds = vi.fn()
const mockGetChildren = vi.fn()
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
  studyApi: {
    listGuides: (...args: unknown[]) => mockListGuides(...args),
    generateGuide: vi.fn(),
    generateQuiz: vi.fn(),
    generateFlashcards: vi.fn(),
  },
  courseContentsApi: {
    listAll: (...args: unknown[]) => mockListAll(...args),
    list: vi.fn().mockResolvedValue([]),
    getLinkedCourseIds: (...args: unknown[]) => mockGetLinkedCourseIds(...args),
  },
  coursesApi: {
    list: (...args: unknown[]) => mockCoursesList(...args),
  },
  parentApi: {
    getChildren: (...args: unknown[]) => mockGetChildren(...args),
  },
  tasksApi: {
    list: vi.fn().mockResolvedValue([]),
  },
  messagesApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }),
  },
  notificationsApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ count: 0 }),
    list: vi.fn().mockResolvedValue([]),
    markAsRead: vi.fn(),
    markAllAsRead: vi.fn(),
  },
  inspirationApi: {
    getRandom: vi.fn().mockRejectedValue(new Error('none')),
  },
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Test Parent', role: 'parent', roles: ['parent'] },
    logout: vi.fn(),
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

vi.mock('../utils/logger', () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}))

vi.mock('../components/LottieLoader', () => ({
  LottieLoader: () => <div data-testid="lottie-loader" />,
}))

import { StudyGuidesPage } from './StudyGuidesPage'

const sampleContent = [
  {
    id: 1,
    course_id: 10,
    course_name: 'Math',
    title: 'Unit B Notes',
    description: null,
    text_content: null,
    content_type: 'notes',
    reference_url: null,
    google_classroom_url: null,
    created_by_user_id: 1,
    google_classroom_material_id: null,
    has_file: false,
    original_filename: null,
    file_size: null,
    mime_type: null,
    created_at: '2026-03-02T10:00:00Z',
    updated_at: null,
    archived_at: null,
    last_viewed_at: null,
  },
]

describe('StudyGuidesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListAll.mockResolvedValue(sampleContent)
    mockListGuides.mockResolvedValue([])
    mockCoursesList.mockResolvedValue([{ id: 10, name: 'Math' }])
    mockGetChildren.mockResolvedValue([
      { user_id: 2, student_id: 1, full_name: 'Child One', grade_level: 5 },
    ])
    mockGetLinkedCourseIds.mockResolvedValue({
      linked_course_ids: [10],
      course_student_map: { 10: [1] },
      children: [{ student_id: 1, user_id: 2, full_name: 'Child One' }],
    })
  })

  it('renders Create Class Material button with proper styling (#1103)', async () => {
    renderWithProviders(<StudyGuidesPage />, {
      initialEntries: ['/course-materials'],
    })

    await waitFor(() => {
      expect(screen.getByText('Unit B Notes')).toBeInTheDocument()
    })

    const btn = screen.getByRole('button', { name: 'Create Class Material' })
    expect(btn).toBeInTheDocument()
    expect(btn.className).toContain('title-add-btn')

    // Verify the button has an SVG icon inside it (not empty/unstyled)
    const svg = btn.querySelector('svg')
    expect(svg).not.toBeNull()
  })

  it('renders material card content (title, course badge, date)', async () => {
    renderWithProviders(<StudyGuidesPage />, {
      initialEntries: ['/course-materials'],
    })

    await waitFor(() => {
      expect(screen.getByText('Unit B Notes')).toBeInTheDocument()
    })

    expect(screen.getByText('Math')).toBeInTheDocument()
    // Date format varies by locale; just verify a date element exists
    const dateEl = screen.getByText(new Date('2026-03-02T10:00:00Z').toLocaleDateString())
    expect(dateEl).toBeInTheDocument()
  })
})
