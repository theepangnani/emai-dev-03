import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────
const mockGetGuide = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ id: '42' }),
  }
})

vi.mock('../api/client', () => ({
  studyApi: {
    getGuide: (...args: any[]) => mockGetGuide(...args),
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

// ── Helpers ────────────────────────────────────────────────────
const MOCK_CARDS = [
  { front: 'What is React?', back: 'A JavaScript library for building UIs' },
  { front: 'What is JSX?', back: 'A syntax extension for JavaScript' },
  { front: 'What is a hook?', back: 'A function to use React features' },
]

const MOCK_GUIDE = {
  id: 42,
  user_id: 1,
  assignment_id: null,
  course_id: 10,
  course_content_id: null,
  title: 'React Basics',
  content: JSON.stringify(MOCK_CARDS),
  guide_type: 'flashcards',
  version: 1,
  parent_guide_id: null,
  created_at: '2025-01-01T00:00:00Z',
  archived_at: null,
}

function renderFlashcards() {
  mockGetGuide.mockResolvedValue(MOCK_GUIDE)
  return renderWithProviders(
    <FlashcardsPage />,
    { initialEntries: ['/flashcards/42'] },
  )
}

// ── Import after mocks ────────────────────────────────────────
import { FlashcardsPage } from './FlashcardsPage'

// ── Tests ──────────────────────────────────────────────────────
describe('FlashcardsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading skeleton initially', () => {
    mockGetGuide.mockReturnValue(new Promise(() => {})) // never resolves
    renderWithProviders(<FlashcardsPage />, { initialEntries: ['/flashcards/42'] })
    // Skeleton elements rendered
    const skeletons = document.querySelectorAll('.skeleton')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('shows error state when fetch fails', async () => {
    mockGetGuide.mockRejectedValue(new Error('Network error'))
    renderWithProviders(<FlashcardsPage />, { initialEntries: ['/flashcards/42'] })
    await waitFor(() => {
      expect(screen.getByText('Failed to load flashcards')).toBeInTheDocument()
    })
  })

  it('renders the first card after loading', async () => {
    renderFlashcards()
    await waitFor(() => {
      expect(screen.getByText('What is React?')).toBeInTheDocument()
    })
    expect(screen.getByText('Card 1 of 3')).toBeInTheDocument()
    expect(screen.getByText('React Basics')).toBeInTheDocument()
  })

  it('flips card on click', async () => {
    const user = userEvent.setup()
    renderFlashcards()
    await waitFor(() => {
      expect(screen.getByText('What is React?')).toBeInTheDocument()
    })

    const card = document.querySelector('.flashcard')!
    await user.click(card)

    expect(card.classList.contains('flipped')).toBe(true)
  })

  it('shows mastery buttons after flip', async () => {
    const user = userEvent.setup()
    renderFlashcards()
    await waitFor(() => {
      expect(screen.getByText('What is React?')).toBeInTheDocument()
    })

    await user.click(document.querySelector('.flashcard')!)

    expect(screen.getByText('Got it')).toBeInTheDocument()
    expect(screen.getByText('Still Learning')).toBeInTheDocument()
  })

  it('hides navigation buttons when flipped', async () => {
    const user = userEvent.setup()
    renderFlashcards()
    await waitFor(() => {
      expect(screen.getByText(/Previous/)).toBeInTheDocument()
    })

    await user.click(document.querySelector('.flashcard')!)

    expect(screen.queryByText(/Previous/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Next/)).not.toBeInTheDocument()
  })

  it('advances to next card on "Got it" click', async () => {
    const user = userEvent.setup()
    renderFlashcards()
    await waitFor(() => {
      expect(screen.getByText('What is React?')).toBeInTheDocument()
    })

    // Flip + Got it
    await user.click(document.querySelector('.flashcard')!)
    await user.click(screen.getByText('Got it'))

    expect(screen.getByText('What is JSX?')).toBeInTheDocument()
    expect(screen.getByText('Card 2 of 3')).toBeInTheDocument()
  })

  it('advances to next card on "Still Learning" click', async () => {
    const user = userEvent.setup()
    renderFlashcards()
    await waitFor(() => {
      expect(screen.getByText('What is React?')).toBeInTheDocument()
    })

    await user.click(document.querySelector('.flashcard')!)
    await user.click(screen.getByText('Still Learning'))

    expect(screen.getByText('What is JSX?')).toBeInTheDocument()
  })

  it('navigates forward/backward with Next/Previous buttons', async () => {
    const user = userEvent.setup()
    renderFlashcards()
    await waitFor(() => {
      expect(screen.getByText('What is React?')).toBeInTheDocument()
    })

    await user.click(screen.getByText(/Next/))
    expect(screen.getByText('What is JSX?')).toBeInTheDocument()
    expect(screen.getByText('Card 2 of 3')).toBeInTheDocument()

    await user.click(screen.getByText(/Previous/))
    expect(screen.getByText('What is React?')).toBeInTheDocument()
    expect(screen.getByText('Card 1 of 3')).toBeInTheDocument()
  })

  it('disables Previous on first card and Next on last card', async () => {
    const user = userEvent.setup()
    renderFlashcards()
    await waitFor(() => {
      expect(screen.getByText('What is React?')).toBeInTheDocument()
    })

    // Previous disabled on first card
    expect(screen.getByText(/Previous/).closest('button')).toBeDisabled()

    // Navigate to last card
    await user.click(screen.getByText(/Next/))
    await user.click(screen.getByText(/Next/))
    expect(screen.getByText('Card 3 of 3')).toBeInTheDocument()
    expect(screen.getByText(/Next/).closest('button')).toBeDisabled()
  })

  it('shows session summary after marking all cards', async () => {
    const user = userEvent.setup()
    renderFlashcards()
    await waitFor(() => {
      expect(screen.getByText('What is React?')).toBeInTheDocument()
    })

    // Mark all 3 cards
    for (let i = 0; i < 3; i++) {
      await user.click(document.querySelector('.flashcard')!)
      await user.click(screen.getByText('Got it'))
    }

    expect(screen.getByText('Session Complete!')).toBeInTheDocument()
    expect(screen.getByText('100% mastered')).toBeInTheDocument()
    expect(screen.getByText('You nailed every card!')).toBeInTheDocument()
  })

  it('shows review button in summary when cards marked as learning', async () => {
    const user = userEvent.setup()
    renderFlashcards()
    await waitFor(() => {
      expect(screen.getByText('What is React?')).toBeInTheDocument()
    })

    // 2 mastered, 1 learning
    await user.click(document.querySelector('.flashcard')!)
    await user.click(screen.getByText('Got it'))

    await user.click(document.querySelector('.flashcard')!)
    await user.click(screen.getByText('Still Learning'))

    await user.click(document.querySelector('.flashcard')!)
    await user.click(screen.getByText('Got it'))

    expect(screen.getByText('Session Complete!')).toBeInTheDocument()
    expect(screen.getByText('Review Difficult (1)')).toBeInTheDocument()
  })

  it('enters review mode with only difficult cards', async () => {
    const user = userEvent.setup()
    renderFlashcards()
    await waitFor(() => {
      expect(screen.getByText('What is React?')).toBeInTheDocument()
    })

    // Mark first as mastered, second as learning, third as mastered
    await user.click(document.querySelector('.flashcard')!)
    await user.click(screen.getByText('Got it'))

    await user.click(document.querySelector('.flashcard')!)
    await user.click(screen.getByText('Still Learning'))

    await user.click(document.querySelector('.flashcard')!)
    await user.click(screen.getByText('Got it'))

    // Enter review mode
    await user.click(screen.getByText('Review Difficult (1)'))

    // Should show only the difficult card
    expect(screen.getByText('Card 1 of 1')).toBeInTheDocument()
    expect(screen.getByText('What is JSX?')).toBeInTheDocument()
    expect(screen.getByText('Review Mode')).toBeInTheDocument()
  })

  it('restarts all cards on Start Over', async () => {
    const user = userEvent.setup()
    renderFlashcards()
    await waitFor(() => {
      expect(screen.getByText('What is React?')).toBeInTheDocument()
    })

    // Mark all cards
    for (let i = 0; i < 3; i++) {
      await user.click(document.querySelector('.flashcard')!)
      await user.click(screen.getByText('Got it'))
    }

    await user.click(screen.getByText('Start Over'))

    // Back to first card with all 3 cards
    expect(screen.getByText('What is React?')).toBeInTheDocument()
    expect(screen.getByText('Card 1 of 3')).toBeInTheDocument()
  })

  it('shows version badge when version > 1', async () => {
    mockGetGuide.mockResolvedValue({ ...MOCK_GUIDE, version: 2 })
    renderWithProviders(<FlashcardsPage />, { initialEntries: ['/flashcards/42'] })
    await waitFor(() => {
      expect(screen.getByText('v2')).toBeInTheDocument()
    })
  })

  it('opens task modal on "+ Task" button click', async () => {
    const user = userEvent.setup()
    renderFlashcards()
    await waitFor(() => {
      expect(screen.getByText('What is React?')).toBeInTheDocument()
    })

    await user.click(screen.getByTitle('Create task'))
    expect(screen.getByTestId('create-task-modal')).toBeInTheDocument()
  })

  // ── Keyboard shortcut tests ───────────────────────────────────
  describe('keyboard shortcuts', () => {
    it('flips card on Space key', async () => {
      const user = userEvent.setup()
      renderFlashcards()
      await waitFor(() => {
        expect(screen.getByText('What is React?')).toBeInTheDocument()
      })

      await user.keyboard(' ')
      expect(document.querySelector('.flashcard.flipped')).toBeInTheDocument()
    })

    it('flips card on Enter key', async () => {
      const user = userEvent.setup()
      renderFlashcards()
      await waitFor(() => {
        expect(screen.getByText('What is React?')).toBeInTheDocument()
      })

      await user.keyboard('{Enter}')
      expect(document.querySelector('.flashcard.flipped')).toBeInTheDocument()
    })

    it('navigates with ArrowRight/ArrowLeft keys', async () => {
      const user = userEvent.setup()
      renderFlashcards()
      await waitFor(() => {
        expect(screen.getByText('What is React?')).toBeInTheDocument()
      })

      await user.keyboard('{ArrowRight}')
      expect(screen.getByText('What is JSX?')).toBeInTheDocument()

      await user.keyboard('{ArrowLeft}')
      expect(screen.getByText('What is React?')).toBeInTheDocument()
    })

    it('ArrowRight marks as mastered when flipped', async () => {
      const user = userEvent.setup()
      renderFlashcards()
      await waitFor(() => {
        expect(screen.getByText('What is React?')).toBeInTheDocument()
      })

      // Flip, then ArrowRight should mark mastered + advance
      await user.keyboard(' ')
      await user.keyboard('{ArrowRight}')

      expect(screen.getByText('What is JSX?')).toBeInTheDocument()
    })

    it('1 key marks as mastered when flipped', async () => {
      const user = userEvent.setup()
      renderFlashcards()
      await waitFor(() => {
        expect(screen.getByText('What is React?')).toBeInTheDocument()
      })

      await user.keyboard(' ')
      await user.keyboard('1')

      expect(screen.getByText('What is JSX?')).toBeInTheDocument()
    })

    it('2 key marks as still learning when flipped', async () => {
      const user = userEvent.setup()
      renderFlashcards()
      await waitFor(() => {
        expect(screen.getByText('What is React?')).toBeInTheDocument()
      })

      await user.keyboard(' ')
      await user.keyboard('2')

      expect(screen.getByText('What is JSX?')).toBeInTheDocument()
    })

    it('keyboard works correctly through all cards to summary', async () => {
      const user = userEvent.setup()
      renderFlashcards()
      await waitFor(() => {
        expect(screen.getByText('What is React?')).toBeInTheDocument()
      })

      // Card 1: flip + mastered
      await user.keyboard(' ')
      await user.keyboard('1')
      // Card 2: flip + learning
      await user.keyboard(' ')
      await user.keyboard('2')
      // Card 3: flip + mastered
      await user.keyboard(' ')
      await user.keyboard('1')

      expect(screen.getByText('Session Complete!')).toBeInTheDocument()
      expect(screen.getByText('Review Difficult (1)')).toBeInTheDocument()
    })

    it('does not navigate past first card with ArrowLeft', async () => {
      const user = userEvent.setup()
      renderFlashcards()
      await waitFor(() => {
        expect(screen.getByText('What is React?')).toBeInTheDocument()
      })

      await user.keyboard('{ArrowLeft}')
      expect(screen.getByText('What is React?')).toBeInTheDocument()
      expect(screen.getByText('Card 1 of 3')).toBeInTheDocument()
    })

    it('does not navigate past last card with ArrowRight', async () => {
      const user = userEvent.setup()
      renderFlashcards()
      await waitFor(() => {
        expect(screen.getByText('What is React?')).toBeInTheDocument()
      })

      await user.keyboard('{ArrowRight}')
      await user.keyboard('{ArrowRight}')
      await user.keyboard('{ArrowRight}') // should not go past card 3

      expect(screen.getByText('Card 3 of 3')).toBeInTheDocument()
    })

    it('shows correct keyboard hints based on flip state', async () => {
      const user = userEvent.setup()
      renderFlashcards()
      await waitFor(() => {
        expect(screen.getByText('Arrow Keys: Navigate')).toBeInTheDocument()
      })

      await user.keyboard(' ') // flip
      expect(screen.getByText('1: Got it')).toBeInTheDocument()
      expect(screen.getByText('2: Still Learning')).toBeInTheDocument()
      expect(screen.queryByText('Arrow Keys: Navigate')).not.toBeInTheDocument()
    })
  })

  describe('shuffle', () => {
    it('resets to first card on shuffle', async () => {
      const user = userEvent.setup()
      renderFlashcards()
      await waitFor(() => {
        expect(screen.getByText('What is React?')).toBeInTheDocument()
      })

      // Go to card 2
      await user.click(screen.getByText(/Next/))
      expect(screen.getByText('Card 2 of 3')).toBeInTheDocument()

      // Shuffle resets to card 1 of 3
      await user.click(screen.getByText('Shuffle'))
      expect(screen.getByText('Card 1 of 3')).toBeInTheDocument()
    })
  })
})
