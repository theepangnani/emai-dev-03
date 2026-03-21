import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../test/helpers'
import { OnTrackBadge } from './OnTrackBadge'

const mockGetChildOnTrack = vi.fn()

vi.mock('../api/client', () => ({
  parentApi: {
    getChildOnTrack: (...args: unknown[]) => mockGetChildOnTrack(...args),
  },
}))

beforeEach(() => {
  mockGetChildOnTrack.mockReset()
})

describe('OnTrackBadge', () => {
  it('renders green badge when signal is green', async () => {
    mockGetChildOnTrack.mockResolvedValue({
      signal: 'green',
      reason: 'Studied 1 day ago. Keep it up!',
      last_activity_days: 1,
      upcoming_count: 0,
    })

    renderWithProviders(<OnTrackBadge studentId={1} />)

    await waitFor(() => {
      expect(screen.getByText('On Track')).toBeInTheDocument()
    })
    const badge = screen.getByText('On Track').closest('.on-track-badge')
    expect(badge).toHaveClass('on-track-badge--green')
  })

  it('renders yellow badge when signal is yellow', async () => {
    mockGetChildOnTrack.mockResolvedValue({
      signal: 'yellow',
      reason: 'Last studied 5 days ago. A gentle check-in might help.',
      last_activity_days: 5,
      upcoming_count: 0,
    })

    renderWithProviders(<OnTrackBadge studentId={2} />)

    await waitFor(() => {
      expect(screen.getByText('Needs Attention')).toBeInTheDocument()
    })
    const badge = screen.getByText('Needs Attention').closest('.on-track-badge')
    expect(badge).toHaveClass('on-track-badge--yellow')
  })

  it('renders red badge when signal is red', async () => {
    mockGetChildOnTrack.mockResolvedValue({
      signal: 'red',
      reason: 'No study activity in 10 days. Consider reaching out to encourage studying.',
      last_activity_days: 10,
      upcoming_count: 2,
    })

    renderWithProviders(<OnTrackBadge studentId={3} />)

    await waitFor(() => {
      expect(screen.getByText('At Risk')).toBeInTheDocument()
    })
    const badge = screen.getByText('At Risk').closest('.on-track-badge')
    expect(badge).toHaveClass('on-track-badge--red')
  })

  it('renders nothing while loading', () => {
    mockGetChildOnTrack.mockReturnValue(new Promise(() => {})) // never resolves

    const { container } = renderWithProviders(<OnTrackBadge studentId={4} />)
    expect(container.querySelector('.on-track-badge')).toBeNull()
  })

  it('includes reason in tooltip', async () => {
    const reason = 'Studied 0 days ago. Keep it up!'
    mockGetChildOnTrack.mockResolvedValue({
      signal: 'green',
      reason,
      last_activity_days: 0,
      upcoming_count: 1,
    })

    renderWithProviders(<OnTrackBadge studentId={5} />)

    await waitFor(() => {
      expect(screen.getByText(reason)).toBeInTheDocument()
    })
  })
})
