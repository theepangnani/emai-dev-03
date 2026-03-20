import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import DocumentTypeSelector, { DOCUMENT_TYPES } from '../components/DocumentTypeSelector'

describe('DocumentTypeSelector', () => {
  const mockOnChange = vi.fn()

  beforeEach(() => {
    mockOnChange.mockClear()
  })

  it('renders all 8 document type chips', () => {
    render(<DocumentTypeSelector onChange={mockOnChange} />)
    DOCUMENT_TYPES.forEach((type) => {
      expect(screen.getByText(type.label)).toBeInTheDocument()
    })
  })

  it('renders the title', () => {
    render(<DocumentTypeSelector onChange={mockOnChange} />)
    expect(screen.getByText('What type of document is this?')).toBeInTheDocument()
  })

  it('selects a chip on click', () => {
    render(<DocumentTypeSelector onChange={mockOnChange} />)
    fireEvent.click(screen.getByText('Teacher Notes / Handout'))
    expect(mockOnChange).toHaveBeenCalledWith('teacher_notes')
  })

  it('shows auto-detected badge when confidence is high', () => {
    render(
      <DocumentTypeSelector
        defaultType="past_exam"
        confidence={0.8}
        onChange={mockOnChange}
      />,
    )
    expect(screen.getByText('Auto-detected')).toBeInTheDocument()
  })

  it('does not show auto-detected badge when confidence is low', () => {
    render(
      <DocumentTypeSelector
        defaultType="past_exam"
        confidence={0.3}
        onChange={mockOnChange}
      />,
    )
    expect(screen.queryByText('Auto-detected')).not.toBeInTheDocument()
  })

  it('shows custom text input when Custom chip is selected', () => {
    render(<DocumentTypeSelector onChange={mockOnChange} />)
    fireEvent.click(screen.getByText('Custom'))
    expect(screen.getByPlaceholderText(/Unit 4 Vocabulary/)).toBeInTheDocument()
  })

  it('hides custom text input when non-custom chip is selected', () => {
    render(<DocumentTypeSelector onChange={mockOnChange} />)
    fireEvent.click(screen.getByText('Custom'))
    expect(screen.getByPlaceholderText(/Unit 4 Vocabulary/)).toBeInTheDocument()

    fireEvent.click(screen.getByText('Past Exam / Test'))
    expect(screen.queryByPlaceholderText(/Unit 4 Vocabulary/)).not.toBeInTheDocument()
  })

  it('pre-selects defaultType', () => {
    render(
      <DocumentTypeSelector defaultType="lab_experiment" onChange={mockOnChange} />,
    )
    const labButton = screen.getByText('Lab / Experiment').closest('button')
    expect(labButton).toHaveAttribute('aria-pressed', 'true')
  })

  it('disables chips when disabled prop is true', () => {
    render(<DocumentTypeSelector onChange={mockOnChange} disabled />)
    const firstChip = screen.getByText('Teacher Notes / Handout').closest('button')
    expect(firstChip).toBeDisabled()
  })

  it('does not fire onChange when disabled', () => {
    render(<DocumentTypeSelector onChange={mockOnChange} disabled />)
    fireEvent.click(screen.getByText('Teacher Notes / Handout'))
    expect(mockOnChange).not.toHaveBeenCalled()
  })
})
