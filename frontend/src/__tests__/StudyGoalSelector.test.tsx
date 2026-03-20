import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import StudyGoalSelector, { STUDY_GOALS } from '../components/StudyGoalSelector'

describe('StudyGoalSelector', () => {
  const mockOnChange = vi.fn()

  beforeEach(() => {
    mockOnChange.mockClear()
  })

  it('renders the dropdown with all goals', () => {
    render(<StudyGoalSelector onChange={mockOnChange} />)
    const dropdown = screen.getByRole('combobox')
    expect(dropdown).toBeInTheDocument()

    STUDY_GOALS.forEach((goal) => {
      expect(screen.getByText(goal.label)).toBeInTheDocument()
    })
  })

  it('renders the label', () => {
    render(<StudyGoalSelector onChange={mockOnChange} />)
    expect(screen.getByText('What are you preparing for?')).toBeInTheDocument()
  })

  it('fires onChange on dropdown selection', () => {
    render(<StudyGoalSelector onChange={mockOnChange} />)
    const dropdown = screen.getByRole('combobox')
    fireEvent.change(dropdown, { target: { value: 'upcoming_test' } })
    expect(mockOnChange).toHaveBeenCalledWith('upcoming_test', undefined)
  })

  it('renders focus field', () => {
    render(<StudyGoalSelector onChange={mockOnChange} />)
    expect(screen.getByPlaceholderText(/Chapter 4 only/)).toBeInTheDocument()
  })

  it('fires onChange with focus text', () => {
    render(<StudyGoalSelector onChange={mockOnChange} />)
    const input = screen.getByPlaceholderText(/Chapter 4 only/)
    fireEvent.change(input, { target: { value: 'quadratic equations' } })
    expect(mockOnChange).toHaveBeenCalledWith('', 'quadratic equations')
  })

  it('shows character count', () => {
    render(<StudyGoalSelector onChange={mockOnChange} />)
    expect(screen.getByText('0/200')).toBeInTheDocument()
  })

  it('updates character count on input', () => {
    render(<StudyGoalSelector onChange={mockOnChange} />)
    const input = screen.getByPlaceholderText(/Chapter 4 only/)
    fireEvent.change(input, { target: { value: 'hello' } })
    expect(screen.getByText('5/200')).toBeInTheDocument()
  })

  it('respects defaultGoal', () => {
    render(<StudyGoalSelector defaultGoal="final_exam" onChange={mockOnChange} />)
    const dropdown = screen.getByRole('combobox') as HTMLSelectElement
    expect(dropdown.value).toBe('final_exam')
  })

  it('disables inputs when disabled', () => {
    render(<StudyGoalSelector onChange={mockOnChange} disabled />)
    expect(screen.getByRole('combobox')).toBeDisabled()
    expect(screen.getByPlaceholderText(/Chapter 4 only/)).toBeDisabled()
  })
})
