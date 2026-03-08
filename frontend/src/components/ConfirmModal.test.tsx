import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { ConfirmModal, useConfirm } from './ConfirmModal'
import { renderWithProviders } from '../test/helpers'

// Stub unrelated APIs to prevent dashboard sidebar crashes in hook tests
vi.mock('../api/client', () => ({
  messagesApi: { getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }) },
  inspirationApi: { getRandom: vi.fn().mockRejectedValue(new Error('none')) },
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Test', role: 'student', roles: ['student'] },
    logout: vi.fn(),
    switchRole: vi.fn(),
  }),
}))

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

  // Regression tests for #1382 — Request More Credits when at limit
  it('renders extra action button when extraActionLabel is provided', () => {
    const onExtra = vi.fn()
    render(
      <ConfirmModal
        open={true}
        title="Generate Study Guide"
        message="You have 0 remaining."
        confirmLabel="Generate"
        extraActionLabel="Request More Credits"
        onExtraAction={onExtra}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.getByText('Request More Credits')).toBeInTheDocument()
  })

  it('does not render extra action button when not provided', () => {
    render(
      <ConfirmModal
        open={true}
        title="Generate Study Guide"
        message="You have 5 remaining."
        confirmLabel="Generate"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.queryByText('Request More Credits')).not.toBeInTheDocument()
  })

  it('disables confirm button when disableConfirm is true', () => {
    render(
      <ConfirmModal
        open={true}
        title="Generate Study Guide"
        message="You have 0 remaining."
        confirmLabel="Generate"
        disableConfirm={true}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.getByText('Generate')).toBeDisabled()
  })

  it('calls onExtraAction when extra action button is clicked', async () => {
    const onExtra = vi.fn()
    render(
      <ConfirmModal
        open={true}
        title="Generate Study Guide"
        message="You have 0 remaining."
        confirmLabel="Generate"
        extraActionLabel="Request More Credits"
        onExtraAction={onExtra}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    await userEvent.click(screen.getByText('Request More Credits'))
    expect(onExtra).toHaveBeenCalledOnce()
  })
})

// Test useConfirm hook with extra action (regression for #1382)
function UseConfirmHarness() {
  const { confirm, confirmModal } = useConfirm()
  const [result, setResult] = useState('')
  const [extraCalled, setExtraCalled] = useState(false)

  const handleClick = async () => {
    const ok = await confirm({
      title: 'Generate',
      message: 'You have 0 remaining.',
      confirmLabel: 'Generate',
      disableConfirm: true,
      extraActionLabel: 'Request More Credits',
      onExtraAction: () => setExtraCalled(true),
    })
    setResult(ok ? 'confirmed' : 'cancelled')
  }

  return (
    <div>
      <button onClick={handleClick}>Open</button>
      {result && <span data-testid="result">{result}</span>}
      {extraCalled && <span data-testid="extra-called">extra</span>}
      {confirmModal}
    </div>
  )
}

describe('useConfirm with extraAction (#1382)', () => {
  it('resolves as false and calls onExtraAction when extra action button is clicked', async () => {
    renderWithProviders(<UseConfirmHarness />)

    await userEvent.click(screen.getByText('Open'))

    await waitFor(() => {
      expect(screen.getByText('Request More Credits')).toBeInTheDocument()
    })

    const generateBtn = screen.getAllByRole('button').find(b => b.textContent === 'Generate')!
    expect(generateBtn).toBeDisabled()

    await userEvent.click(screen.getByText('Request More Credits'))

    await waitFor(() => {
      expect(screen.getByTestId('extra-called')).toBeInTheDocument()
      expect(screen.getByTestId('result')).toHaveTextContent('cancelled')
    })
  })
})
