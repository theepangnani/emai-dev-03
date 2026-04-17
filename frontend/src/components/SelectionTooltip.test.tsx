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

  it('does not render Ask Chat Bot button when callback not provided', () => {
    render(
      <SelectionTooltip rect={mockRect} visible onAddToNotes={vi.fn()} />
    )
    expect(screen.queryByText('Ask Chat Bot')).not.toBeInTheDocument()
  })

  it('renders Ask Chat Bot button when callback is provided', () => {
    render(
      <SelectionTooltip
        rect={mockRect}
        visible
        onAddToNotes={vi.fn()}
        onAskChatBot={vi.fn()}
      />
    )
    expect(screen.getByText('Ask Chat Bot')).toBeInTheDocument()
  })

  it('calls onAskChatBot when Ask Chat Bot is clicked', async () => {
    const user = userEvent.setup()
    const onAskChatBot = vi.fn()
    render(
      <SelectionTooltip
        rect={mockRect}
        visible
        onAddToNotes={vi.fn()}
        onAskChatBot={onAskChatBot}
      />
    )
    await user.click(screen.getByText('Ask Chat Bot'))
    expect(onAskChatBot).toHaveBeenCalledOnce()
  })

  it('renders both buttons side by side', () => {
    render(
      <SelectionTooltip
        rect={mockRect}
        visible
        onAddToNotes={vi.fn()}
        onAskChatBot={vi.fn()}
      />
    )
    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(2)
    expect(screen.getByText('Add to Notes')).toBeInTheDocument()
    expect(screen.getByText('Ask Chat Bot')).toBeInTheDocument()
  })

  it('does not render Start Session button when callback not provided', () => {
    render(
      <SelectionTooltip rect={mockRect} visible onAddToNotes={vi.fn()} />
    )
    expect(screen.queryByText('Start Session')).not.toBeInTheDocument()
  })

  it('renders Start Session button when callback is provided', () => {
    render(
      <SelectionTooltip
        rect={mockRect}
        visible
        onAddToNotes={vi.fn()}
        onStartSession={vi.fn()}
      />
    )
    expect(screen.getByText('Start Session')).toBeInTheDocument()
  })

  it('calls onStartSession when Start Session is clicked', async () => {
    const user = userEvent.setup()
    const onStartSession = vi.fn()
    render(
      <SelectionTooltip
        rect={mockRect}
        visible
        onAddToNotes={vi.fn()}
        onStartSession={onStartSession}
      />
    )
    await user.click(screen.getByText('Start Session'))
    expect(onStartSession).toHaveBeenCalledOnce()
  })

  it('renders all three buttons when all callbacks provided', () => {
    render(
      <SelectionTooltip
        rect={mockRect}
        visible
        onAddToNotes={vi.fn()}
        onAskChatBot={vi.fn()}
        onStartSession={vi.fn()}
      />
    )
    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(3)
    expect(screen.getByText('Add to Notes')).toBeInTheDocument()
    expect(screen.getByText('Ask Chat Bot')).toBeInTheDocument()
    expect(screen.getByText('Start Session')).toBeInTheDocument()
  })
})
