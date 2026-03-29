import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TextSelectionContextMenu } from '../TextSelectionContextMenu'
import { createRef } from 'react'

function renderContextMenu(props: Partial<React.ComponentProps<typeof TextSelectionContextMenu>> = {}) {
  const containerRef = createRef<HTMLDivElement>()
  const result = render(
    <div ref={containerRef} data-testid="container">
      <p>Some text content to select</p>
      <TextSelectionContextMenu
        containerRef={containerRef}
        onAddNote={vi.fn()}
        onAskChatBot={vi.fn()}
        {...props}
      />
    </div>
  )
  return { ...result, containerRef }
}

describe('TextSelectionContextMenu', () => {
  beforeEach(() => {
    // Non-touch by default
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    });
  })

  afterEach(() => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    });
  })

  it('is hidden by default', () => {
    renderContextMenu()
    expect(screen.queryByText('Add Note')).not.toBeInTheDocument()
  })

  it('shows menu on right-click with selected text', () => {
    renderContextMenu()

    // Mock text selection
    const mockSelection = {
      toString: () => 'selected text content',
      rangeCount: 1,
    }
    vi.spyOn(window, 'getSelection').mockReturnValue(mockSelection as unknown as Selection)

    const container = screen.getByTestId('container')
    fireEvent.contextMenu(container, { clientX: 100, clientY: 200 })

    expect(screen.getByText('Add Note')).toBeInTheDocument()
    expect(screen.getByText('Ask Chat Bot')).toBeInTheDocument()
  })

  it('does not show menu without text selection', () => {
    renderContextMenu()

    vi.spyOn(window, 'getSelection').mockReturnValue({
      toString: () => '',
      rangeCount: 0,
    } as unknown as Selection)

    const container = screen.getByTestId('container')
    fireEvent.contextMenu(container)

    expect(screen.queryByText('Add Note')).not.toBeInTheDocument()
  })

  it('calls onAddNote with selected text', () => {
    const onAddNote = vi.fn()
    renderContextMenu({ onAddNote })

    vi.spyOn(window, 'getSelection').mockReturnValue({
      toString: () => 'test text',
      rangeCount: 1,
    } as unknown as Selection)

    const container = screen.getByTestId('container')
    fireEvent.contextMenu(container, { clientX: 100, clientY: 200 })
    fireEvent.click(screen.getByText('Add Note'))

    expect(onAddNote).toHaveBeenCalledWith('test text')
  })

  it('calls onAskChatBot with selected text', () => {
    const onAskChatBot = vi.fn()
    renderContextMenu({ onAskChatBot })

    vi.spyOn(window, 'getSelection').mockReturnValue({
      toString: () => 'study text',
      rangeCount: 1,
    } as unknown as Selection)

    const container = screen.getByTestId('container')
    fireEvent.contextMenu(container, { clientX: 100, clientY: 200 })
    fireEvent.click(screen.getByText('Ask Chat Bot'))

    expect(onAskChatBot).toHaveBeenCalledWith('study text')
  })

  it('closes on Escape key', () => {
    renderContextMenu()

    vi.spyOn(window, 'getSelection').mockReturnValue({
      toString: () => 'test text',
      rangeCount: 1,
    } as unknown as Selection)

    const container = screen.getByTestId('container')
    fireEvent.contextMenu(container, { clientX: 100, clientY: 200 })
    expect(screen.getByText('Add Note')).toBeInTheDocument()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByText('Add Note')).not.toBeInTheDocument()
  })

  it('does not show menu on touch devices', () => {
    // Simulate touch device via pointer: coarse
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === '(pointer: coarse)',
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    });

    renderContextMenu()

    vi.spyOn(window, 'getSelection').mockReturnValue({
      toString: () => 'selected text content',
      rangeCount: 1,
    } as unknown as Selection)

    const container = screen.getByTestId('container')
    fireEvent.contextMenu(container, { clientX: 100, clientY: 200 })

    expect(screen.queryByText('Add Note')).not.toBeInTheDocument()
  })
})
