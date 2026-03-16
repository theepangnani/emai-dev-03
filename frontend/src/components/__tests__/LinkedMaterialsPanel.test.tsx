import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { LinkedMaterialsPanel, type LinkedMaterialDisplay } from '../LinkedMaterialsPanel'

const mockMaterials: LinkedMaterialDisplay[] = [
  { id: 1, title: 'Math Notes', is_master: 'true', content_type: 'notes', has_file: false, original_filename: null, created_at: '2026-03-14T00:00:00Z' },
  { id: 2, title: 'Math Notes — Part 1', is_master: 'false', content_type: 'notes', has_file: true, original_filename: 'file1.pdf', created_at: '2026-03-14T00:00:00Z' },
  { id: 3, title: 'Math Notes — Part 2', is_master: 'false', content_type: 'notes', has_file: true, original_filename: 'file2.pdf', created_at: '2026-03-14T00:00:00Z' },
]

function renderPanel(props: Partial<React.ComponentProps<typeof LinkedMaterialsPanel>> = {}) {
  return render(
    <BrowserRouter>
      <LinkedMaterialsPanel
        materials={mockMaterials}
        currentMaterialId={1}
        isCurrentMaster={true}
        {...props}
      />
    </BrowserRouter>
  )
}

describe('LinkedMaterialsPanel', () => {
  it('renders nothing when no materials', () => {
    const { container } = renderPanel({ materials: [] })
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when loading', () => {
    const { container } = renderPanel({ loading: true })
    expect(container.firstChild).toBeNull()
  })

  it('renders collapsed by default with count', () => {
    renderPanel()
    expect(screen.getByText('Linked Materials (3)')).toBeInTheDocument()
    expect(screen.queryByText('Math Notes — Part 1')).not.toBeInTheDocument()
  })

  it('expands to show linked materials on click', () => {
    renderPanel()
    fireEvent.click(screen.getByText('Linked Materials (3)'))
    expect(screen.getByText('Math Notes — Part 1')).toBeInTheDocument()
    expect(screen.getByText('Math Notes — Part 2')).toBeInTheDocument()
  })

  it('shows Master badge for master materials', () => {
    renderPanel()
    fireEvent.click(screen.getByText('Linked Materials (3)'))
    expect(screen.getByText('Master')).toBeInTheDocument()
  })

  it('shows Sub badge for sub materials', () => {
    renderPanel()
    fireEvent.click(screen.getByText('Linked Materials (3)'))
    const subBadges = screen.getAllByText('Sub')
    expect(subBadges).toHaveLength(2)
  })

  it('renders links to material detail pages', () => {
    renderPanel()
    fireEvent.click(screen.getByText('Linked Materials (3)'))
    const links = screen.getAllByRole('link')
    expect(links[0]).toHaveAttribute('href', '/course-materials/1')
    expect(links[1]).toHaveAttribute('href', '/course-materials/2')
  })

  it('marks current material item', () => {
    renderPanel({ currentMaterialId: 2 })
    fireEvent.click(screen.getByText('Linked Materials (3)'))
    const currentItem = screen.getByText('Math Notes — Part 1').closest('a')
    expect(currentItem).toHaveClass('current')
  })

  it('collapses on second click', () => {
    renderPanel()
    const toggle = screen.getByText('Linked Materials (3)')
    fireEvent.click(toggle)
    expect(screen.getByText('Math Notes — Part 1')).toBeInTheDocument()
    fireEvent.click(toggle)
    expect(screen.queryByText('Math Notes — Part 1')).not.toBeInTheDocument()
  })

  it('shows reorder buttons when isCurrentMaster is true', () => {
    renderPanel({ isCurrentMaster: true })
    fireEvent.click(screen.getByText('Linked Materials (3)'))
    // Sub-materials should have up/down reorder buttons
    expect(screen.getByLabelText('Move Math Notes — Part 1 up')).toBeInTheDocument()
    expect(screen.getByLabelText('Move Math Notes — Part 1 down')).toBeInTheDocument()
    expect(screen.getByLabelText('Move Math Notes — Part 2 up')).toBeInTheDocument()
    expect(screen.getByLabelText('Move Math Notes — Part 2 down')).toBeInTheDocument()
  })

  it('hides reorder buttons when isCurrentMaster is false', () => {
    renderPanel({ isCurrentMaster: false })
    fireEvent.click(screen.getByText('Linked Materials (3)'))
    expect(screen.queryByLabelText('Move Math Notes — Part 1 up')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Move Math Notes — Part 1 down')).not.toBeInTheDocument()
  })

  it('calls onReorder when arrow button clicked', () => {
    const onReorder = vi.fn()
    renderPanel({ isCurrentMaster: true, onReorder })
    fireEvent.click(screen.getByText('Linked Materials (3)'))
    fireEvent.click(screen.getByLabelText('Move Math Notes — Part 2 up'))
    expect(onReorder).toHaveBeenCalledWith(3, 'up')
    fireEvent.click(screen.getByLabelText('Move Math Notes — Part 1 down'))
    expect(onReorder).toHaveBeenCalledWith(2, 'down')
  })

  it('shows delete button on sub-materials when isCurrentMaster', () => {
    renderPanel({ isCurrentMaster: true })
    fireEvent.click(screen.getByText('Linked Materials (3)'))
    expect(screen.getByLabelText('Delete Math Notes — Part 1')).toBeInTheDocument()
    expect(screen.getByLabelText('Delete Math Notes — Part 2')).toBeInTheDocument()
    // Master material should NOT have a delete button
    expect(screen.queryByLabelText('Delete Math Notes')).not.toBeInTheDocument()
  })

  it('calls onDeleteSub when delete confirmed', () => {
    const onDeleteSub = vi.fn()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderPanel({ isCurrentMaster: true, onDeleteSub })
    fireEvent.click(screen.getByText('Linked Materials (3)'))
    fireEvent.click(screen.getByLabelText('Delete Math Notes — Part 1'))
    expect(window.confirm).toHaveBeenCalled()
    expect(onDeleteSub).toHaveBeenCalledWith(2)
    vi.restoreAllMocks()
  })

  it('does not call onDeleteSub when delete cancelled', () => {
    const onDeleteSub = vi.fn()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderPanel({ isCurrentMaster: true, onDeleteSub })
    fireEvent.click(screen.getByText('Linked Materials (3)'))
    fireEvent.click(screen.getByLabelText('Delete Math Notes — Part 1'))
    expect(window.confirm).toHaveBeenCalled()
    expect(onDeleteSub).not.toHaveBeenCalled()
    vi.restoreAllMocks()
  })
})
