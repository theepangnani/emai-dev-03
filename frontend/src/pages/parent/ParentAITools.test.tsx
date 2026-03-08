import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/helpers'
import { ParentAITools } from './ParentAITools'
import { createMockChild, createMockChildHighlight, createMockParentDashboard } from '../../test/mocks'

// Mock APIs
const mockGetDashboard = vi.fn()
const mockGetWeakSpots = vi.fn()
const mockCheckReadiness = vi.fn()
const mockGeneratePracticeProblems = vi.fn()

vi.mock('../../api/parent', () => ({
  parentApi: {
    getDashboard: (...args: unknown[]) => mockGetDashboard(...args),
  },
}))

vi.mock('../../api/parentAI', () => ({
  parentAIApi: {
    getWeakSpots: (...args: unknown[]) => mockGetWeakSpots(...args),
    checkReadiness: (...args: unknown[]) => mockCheckReadiness(...args),
    generatePracticeProblems: (...args: unknown[]) => mockGeneratePracticeProblems(...args),
  },
}))

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Test Parent', role: 'parent', roles: ['parent'] },
    logout: vi.fn(),
    switchRole: vi.fn(),
  }),
}))

vi.mock('../../api/client', () => ({
  messagesApi: { getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }) },
  inspirationApi: { getRandom: vi.fn().mockRejectedValue(new Error('none')) },
}))

const child = createMockChild({ student_id: 10, full_name: 'Alice' })
const highlight = createMockChildHighlight({
  student_id: 10,
  full_name: 'Alice',
  courses: [{ id: 100, name: 'Math 8' } as any],
})

beforeEach(() => {
  vi.clearAllMocks()
  mockGetDashboard.mockResolvedValue(
    createMockParentDashboard({
      children: [child],
      child_highlights: [highlight],
      all_assignments: [{ id: 200, title: 'Homework 1', course_id: 100 } as any],
    }),
  )
})

describe('ParentAITools', () => {
  it('renders all 3 tool cards after loading', async () => {
    renderWithProviders(<ParentAITools />)
    await waitFor(() => {
      expect(screen.getByText('Weak Spots Analysis')).toBeInTheDocument()
    })
    expect(screen.getByText('Readiness Check')).toBeInTheDocument()
    expect(screen.getByText('Practice Problems')).toBeInTheDocument()
  })

  it('shows empty state when no children linked', async () => {
    mockGetDashboard.mockResolvedValue(
      createMockParentDashboard({ children: [], child_highlights: [] }),
    )
    renderWithProviders(<ParentAITools />)
    await waitFor(() => {
      expect(screen.getByText('No children linked')).toBeInTheDocument()
    })
  })

  it('expands weak spots card and shows child selector', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ParentAITools />)
    await waitFor(() => {
      expect(screen.getByText('Weak Spots Analysis')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Weak Spots Analysis'))
    await waitFor(() => {
      expect(screen.getByText('Select child...')).toBeInTheDocument()
    })
  })

  it('shows loading state during weak spots analysis', async () => {
    mockGetWeakSpots.mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderWithProviders(<ParentAITools />)

    await waitFor(() => {
      expect(screen.getByText('Weak Spots Analysis')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Weak Spots Analysis'))

    const selects = screen.getAllByRole('combobox')
    await user.selectOptions(selects[0], '10')

    await user.click(screen.getByText('Analyze Weak Spots'))
    expect(screen.getByText('Analyzing...')).toBeInTheDocument()
  })

  it('displays error when weak spots API fails', async () => {
    mockGetWeakSpots.mockRejectedValue({
      response: { data: { detail: 'AI usage limit reached.' } },
    })
    const user = userEvent.setup()
    renderWithProviders(<ParentAITools />)

    await waitFor(() => {
      expect(screen.getByText('Weak Spots Analysis')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Weak Spots Analysis'))

    const selects = screen.getAllByRole('combobox')
    await user.selectOptions(selects[0], '10')
    await user.click(screen.getByText('Analyze Weak Spots'))

    await waitFor(() => {
      expect(screen.getByText('AI usage limit reached.')).toBeInTheDocument()
    })
  })

  it('displays weak spots results successfully', async () => {
    mockGetWeakSpots.mockResolvedValue({
      data: {
        student_name: 'Alice',
        course_name: null,
        weak_spots: [
          {
            topic: 'Fractions',
            severity: 'high',
            detail: 'Below 60%',
            quiz_score_summary: '2/3 below',
            suggested_action: 'Practice more',
          },
        ],
        summary: 'Needs work on fractions.',
        total_quizzes_analyzed: 3,
        total_assignments_analyzed: 2,
      },
    })
    const user = userEvent.setup()
    renderWithProviders(<ParentAITools />)

    await waitFor(() => {
      expect(screen.getByText('Weak Spots Analysis')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Weak Spots Analysis'))

    const selects = screen.getAllByRole('combobox')
    await user.selectOptions(selects[0], '10')
    await user.click(screen.getByText('Analyze Weak Spots'))

    await waitFor(() => {
      expect(screen.getByText('Fractions')).toBeInTheDocument()
    })
    expect(screen.getByText('Needs work on fractions.')).toBeInTheDocument()
    expect(screen.getByText('Practice more')).toBeInTheDocument()
  })

  it('expands readiness card and shows assignment selector after child selected', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ParentAITools />)

    await waitFor(() => {
      expect(screen.getByText('Readiness Check')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Readiness Check'))

    await waitFor(() => {
      expect(screen.getByText('Select child...')).toBeInTheDocument()
    })

    const selects = screen.getAllByRole('combobox')
    await user.selectOptions(selects[0], '10')

    await waitFor(() => {
      expect(screen.getByText('Select assignment...')).toBeInTheDocument()
    })
  })

  it('expands practice problems card and shows topic input', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ParentAITools />)

    await waitFor(() => {
      expect(screen.getByText('Practice Problems')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Practice Problems'))

    await waitFor(() => {
      expect(screen.getByText('Select child...')).toBeInTheDocument()
    })

    const selects = screen.getAllByRole('combobox')
    await user.selectOptions(selects[0], '10')

    await waitFor(() => {
      expect(screen.getByText('Select course...')).toBeInTheDocument()
    })

    const courseSelects = screen.getAllByRole('combobox')
    await user.selectOptions(courseSelects[1], '100')

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Fractions/)).toBeInTheDocument()
    })
  })
})
