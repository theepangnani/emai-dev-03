import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────
const mockGetGuide = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ id: '10' }),
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
const MOCK_QUESTIONS = [
  {
    question: 'What does HTML stand for?',
    options: {
      A: 'Hyper Text Markup Language',
      B: 'Hot Mail',
      C: 'How To Make Lasagna',
      D: 'None of the above',
    },
    correct_answer: 'A',
    explanation: 'HTML stands for Hyper Text Markup Language.',
  },
  {
    question: 'What does CSS stand for?',
    options: {
      A: 'Computer Style Sheets',
      B: 'Cascading Style Sheets',
      C: 'Creative Style System',
      D: 'Colorful Style Sheets',
    },
    correct_answer: 'B',
    explanation: 'CSS stands for Cascading Style Sheets.',
  },
  {
    question: 'What is JavaScript?',
    options: {
      A: 'A markup language',
      B: 'A database',
      C: 'A programming language',
      D: 'An operating system',
    },
    correct_answer: 'C',
    explanation: 'JavaScript is a programming language.',
  },
]

const MOCK_GUIDE = {
  id: 10,
  user_id: 1,
  assignment_id: null,
  course_id: 5,
  course_content_id: null,
  title: 'Web Basics Quiz',
  content: JSON.stringify(MOCK_QUESTIONS),
  guide_type: 'quiz',
  version: 1,
  parent_guide_id: null,
  created_at: '2025-01-01T00:00:00Z',
  archived_at: null,
}

function renderQuiz() {
  mockGetGuide.mockResolvedValue(MOCK_GUIDE)
  return renderWithProviders(<QuizPage />, { initialEntries: ['/quiz/10'] })
}

// ── Import after mocks ────────────────────────────────────────
import { QuizPage } from './QuizPage'

// ── Tests ──────────────────────────────────────────────────────
describe('QuizPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading skeleton initially', () => {
    mockGetGuide.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<QuizPage />, { initialEntries: ['/quiz/10'] })
    const skeletons = document.querySelectorAll('.skeleton')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('shows error state when fetch fails', async () => {
    mockGetGuide.mockRejectedValue(new Error('Network error'))
    renderWithProviders(<QuizPage />, { initialEntries: ['/quiz/10'] })
    await waitFor(() => {
      expect(screen.getByText('Failed to load quiz')).toBeInTheDocument()
    })
  })

  it('renders the first question after loading', async () => {
    renderQuiz()
    await waitFor(() => {
      expect(screen.getByText('What does HTML stand for?')).toBeInTheDocument()
    })
    expect(screen.getByText('Question 1 of 3')).toBeInTheDocument()
    expect(screen.getByText('Web Basics Quiz')).toBeInTheDocument()
    // All four options visible
    expect(screen.getByText('Hyper Text Markup Language')).toBeInTheDocument()
    expect(screen.getByText('Hot Mail')).toBeInTheDocument()
  })

  it('selects an answer option on click', async () => {
    const user = userEvent.setup()
    renderQuiz()
    await waitFor(() => {
      expect(screen.getByText('What does HTML stand for?')).toBeInTheDocument()
    })

    const optionBtn = screen.getByText('Hyper Text Markup Language').closest('button')!
    await user.click(optionBtn)
    expect(optionBtn.classList.contains('selected')).toBe(true)
  })

  it('disables Submit Answer when no option selected', async () => {
    renderQuiz()
    await waitFor(() => {
      expect(screen.getByText('Submit Answer')).toBeInTheDocument()
    })
    expect(screen.getByText('Submit Answer').closest('button')).toBeDisabled()
  })

  it('shows correct result after submitting correct answer', async () => {
    const user = userEvent.setup()
    renderQuiz()
    await waitFor(() => {
      expect(screen.getByText('What does HTML stand for?')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Hyper Text Markup Language').closest('button')!)
    await user.click(screen.getByText('Submit Answer'))

    expect(screen.getByText('Correct!')).toBeInTheDocument()
    expect(screen.getByText('HTML stands for Hyper Text Markup Language.')).toBeInTheDocument()
  })

  it('shows incorrect result after submitting wrong answer', async () => {
    const user = userEvent.setup()
    renderQuiz()
    await waitFor(() => {
      expect(screen.getByText('What does HTML stand for?')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Hot Mail').closest('button')!)
    await user.click(screen.getByText('Submit Answer'))

    expect(screen.getByText('Incorrect')).toBeInTheDocument()
    expect(screen.getByText('HTML stands for Hyper Text Markup Language.')).toBeInTheDocument()
  })

  it('disables option buttons after submit', async () => {
    const user = userEvent.setup()
    renderQuiz()
    await waitFor(() => {
      expect(screen.getByText('What does HTML stand for?')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Hyper Text Markup Language').closest('button')!)
    await user.click(screen.getByText('Submit Answer'))

    // All options should be disabled
    const optionButtons = document.querySelectorAll('.option')
    optionButtons.forEach(btn => {
      expect(btn).toBeDisabled()
    })
  })

  it('advances to next question on "Next Question" click', async () => {
    const user = userEvent.setup()
    renderQuiz()
    await waitFor(() => {
      expect(screen.getByText('What does HTML stand for?')).toBeInTheDocument()
    })

    // Answer + submit + next
    await user.click(screen.getByText('Hyper Text Markup Language').closest('button')!)
    await user.click(screen.getByText('Submit Answer'))
    await user.click(screen.getByText('Next Question'))

    expect(screen.getByText('What does CSS stand for?')).toBeInTheDocument()
    expect(screen.getByText('Question 2 of 3')).toBeInTheDocument()
  })

  it('shows quiz results after answering all questions', async () => {
    const user = userEvent.setup()
    renderQuiz()
    await waitFor(() => {
      expect(screen.getByText('What does HTML stand for?')).toBeInTheDocument()
    })

    // Q1: correct
    await user.click(screen.getByText('Hyper Text Markup Language').closest('button')!)
    await user.click(screen.getByText('Submit Answer'))
    await user.click(screen.getByText('Next Question'))

    // Q2: correct
    await user.click(screen.getByText('Cascading Style Sheets').closest('button')!)
    await user.click(screen.getByText('Submit Answer'))
    await user.click(screen.getByText('Next Question'))

    // Q3: correct (last question — button says "See Results")
    await user.click(screen.getByText('A programming language').closest('button')!)
    await user.click(screen.getByText('Submit Answer'))

    // Results displayed
    expect(screen.getByText('Quiz Complete!')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument() // score
    expect(screen.getByText('/ 3')).toBeInTheDocument()
    expect(screen.getByText('100% correct')).toBeInTheDocument()
    expect(screen.getByText('Perfect score! Outstanding work!')).toBeInTheDocument()
  })

  it('shows partial score with correct encouragement messages', async () => {
    const user = userEvent.setup()
    renderQuiz()
    await waitFor(() => {
      expect(screen.getByText('What does HTML stand for?')).toBeInTheDocument()
    })

    // Q1: wrong
    await user.click(screen.getByText('Hot Mail').closest('button')!)
    await user.click(screen.getByText('Submit Answer'))
    await user.click(screen.getByText('Next Question'))

    // Q2: wrong
    await user.click(screen.getByText('Computer Style Sheets').closest('button')!)
    await user.click(screen.getByText('Submit Answer'))
    await user.click(screen.getByText('Next Question'))

    // Q3: wrong
    await user.click(screen.getByText('A markup language').closest('button')!)
    await user.click(screen.getByText('Submit Answer'))

    expect(screen.getByText('Quiz Complete!')).toBeInTheDocument()
    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.getByText('0% correct')).toBeInTheDocument()
    expect(screen.getByText('Keep studying — every attempt makes you stronger!')).toBeInTheDocument()
  })

  it('resets quiz on Try Again', async () => {
    const user = userEvent.setup()
    renderQuiz()
    await waitFor(() => {
      expect(screen.getByText('What does HTML stand for?')).toBeInTheDocument()
    })

    // Complete the quiz quickly (all wrong)
    for (let i = 0; i < 3; i++) {
      const opts = document.querySelectorAll('.option')
      await user.click(opts[3]) // always pick D (wrong for all)
      await user.click(screen.getByText('Submit Answer'))
      if (i < 2) await user.click(screen.getByText('Next Question'))
    }

    expect(screen.getByText('Quiz Complete!')).toBeInTheDocument()
    await user.click(screen.getByText('Try Again'))

    // Back to question 1
    expect(screen.getByText('What does HTML stand for?')).toBeInTheDocument()
    expect(screen.getByText('Question 1 of 3')).toBeInTheDocument()
  })

  it('shows last question button as "See Results"', async () => {
    const user = userEvent.setup()
    renderQuiz()
    await waitFor(() => {
      expect(screen.getByText('What does HTML stand for?')).toBeInTheDocument()
    })

    // Navigate to last question
    for (let i = 0; i < 2; i++) {
      const opts = document.querySelectorAll('.option')
      await user.click(opts[0])
      await user.click(screen.getByText('Submit Answer'))
      await user.click(screen.getByText('Next Question'))
    }

    // On last question, answer + submit
    const opts = document.querySelectorAll('.option')
    await user.click(opts[0])
    await user.click(screen.getByText('Submit Answer'))

    // No more "Next Question" — quiz is complete, results shown
    expect(screen.queryByText('Next Question')).not.toBeInTheDocument()
    expect(screen.getByText('Quiz Complete!')).toBeInTheDocument()
  })

  it('shows version badge when version > 1', async () => {
    mockGetGuide.mockResolvedValue({ ...MOCK_GUIDE, version: 3 })
    renderWithProviders(<QuizPage />, { initialEntries: ['/quiz/10'] })
    await waitFor(() => {
      expect(screen.getByText('v3')).toBeInTheDocument()
    })
  })

  it('opens task modal on "+ Task" button click', async () => {
    const user = userEvent.setup()
    renderQuiz()
    await waitFor(() => {
      expect(screen.getByText('What does HTML stand for?')).toBeInTheDocument()
    })

    await user.click(screen.getByTitle('Create task'))
    expect(screen.getByTestId('create-task-modal')).toBeInTheDocument()
  })
})
