import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConfirmModal } from './ConfirmModal'

describe('ConfirmModal', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <ConfirmModal
        open={false}
        title="Test"
        message="Are you sure?"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders title and message when open', () => {
    render(
      <ConfirmModal
        open={true}
        title="Delete Item"
        message="This cannot be undone."
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    )
    expect(screen.getByText('Delete Item')).toBeInTheDocument()
    expect(screen.getByText('This cannot be undone.')).toBeInTheDocument()
  })

  it('calls onConfirm when confirm button clicked', async () => {
    const onConfirm = vi.fn()
    render(
      <ConfirmModal
        open={true}
        title="Confirm"
        message="Proceed?"
        confirmLabel="Yes"
        onConfirm={onConfirm}
        onCancel={() => {}}
      />,
    )
    await userEvent.click(screen.getByText('Yes'))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('calls onCancel when cancel button clicked', async () => {
    const onCancel = vi.fn()
    render(
      <ConfirmModal
        open={true}
        title="Confirm"
        message="Proceed?"
        cancelLabel="No"
        onConfirm={() => {}}
        onCancel={onCancel}
      />,
    )
    await userEvent.click(screen.getByText('No'))
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('uses danger variant styling', () => {
    render(
      <ConfirmModal
        open={true}
        title="Remove Item"
        message="This is permanent."
        variant="danger"
        confirmLabel="Delete"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    )
    const confirmBtn = screen.getByRole('button', { name: 'Delete' })
    expect(confirmBtn).toHaveClass('danger-btn')
  })
})
