import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SelectionTooltip } from './SelectionTooltip'

const mockRect = {
  top: 100,
  left: 200,
  width: 80,
  height: 20,
  bottom: 120,
  right: 280,
  x: 200,
  y: 100,
  toJSON: () => {},
} as DOMRect

describe('SelectionTooltip', () => {
  it('renders nothing when not visible', () => {
    const { container } = render(
      <SelectionTooltip rect={mockRect} visible={false} onAddToNotes={vi.fn()} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders Add to Notes button when visible', () => {
    render(
      <SelectionTooltip rect={mockRect} visible onAddToNotes={vi.fn()} />
    )
    expect(screen.getByText('Add to Notes')).toBeInTheDocument()
  })

  it('calls onAddToNotes when Add to Notes is clicked', async () => {
    const user = userEvent.setup()
    const onAddToNotes = vi.fn()
    render(
      <SelectionTooltip rect={mockRect} visible onAddToNotes={onAddToNotes} />
    )
    await user.click(screen.getByText('Add to Notes'))
    expect(onAddToNotes).toHaveBeenCalledOnce()
  })

  it('does not render Generate Study Material button when callback not provided', () => {
    render(
      <SelectionTooltip rect={mockRect} visible onAddToNotes={vi.fn()} />
    )
    expect(screen.queryByText('Generate Study Material')).not.toBeInTheDocument()
  })

  it('renders Generate Study Material button when callback is provided', () => {
    render(
      <SelectionTooltip
        rect={mockRect}
        visible
        onAddToNotes={vi.fn()}
        onGenerateStudyMaterial={vi.fn()}
      />
    )
    expect(screen.getByText('Generate Study Material')).toBeInTheDocument()
  })

  it('calls onGenerateStudyMaterial when Generate Study Material is clicked', async () => {
    const user = userEvent.setup()
    const onGenerate = vi.fn()
    render(
      <SelectionTooltip
        rect={mockRect}
        visible
        onAddToNotes={vi.fn()}
        onGenerateStudyMaterial={onGenerate}
      />
    )
    await user.click(screen.getByText('Generate Study Material'))
    expect(onGenerate).toHaveBeenCalledOnce()
  })

  it('renders both buttons side by side', () => {
    render(
      <SelectionTooltip
        rect={mockRect}
        visible
        onAddToNotes={vi.fn()}
        onGenerateStudyMaterial={vi.fn()}
      />
    )
    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(2)
    expect(screen.getByText('Add to Notes')).toBeInTheDocument()
    expect(screen.getByText('Generate Study Material')).toBeInTheDocument()
  })
})
