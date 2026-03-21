import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ParentSummaryCard from '../components/ParentSummaryCard'

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '../context/AuthContext'
const mockUseAuth = vi.mocked(useAuth)

describe('ParentSummaryCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders for parent role', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'PARENT', roles: ['PARENT'] } } as ReturnType<typeof useAuth>)
    render(<ParentSummaryCard summary="Test summary with action items" />)
    expect(screen.getByText('Parent Summary')).toBeInTheDocument()
    expect(screen.getByText('Test summary with action items')).toBeInTheDocument()
  })

  it('does not render for student role', () => {
    mockUseAuth.mockReturnValue({
      user: { role: 'STUDENT', roles: ['STUDENT'] },
    } as ReturnType<typeof useAuth>)
    const { container } = render(<ParentSummaryCard summary="Test summary" />)
    expect(container.firstChild).toBeNull()
  })

  it('does not render when summary is null', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'PARENT', roles: ['PARENT'] } } as ReturnType<typeof useAuth>)
    const { container } = render(<ParentSummaryCard summary={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('does not render when summary is empty', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'PARENT', roles: ['PARENT'] } } as ReturnType<typeof useAuth>)
    const { container } = render(<ParentSummaryCard summary="" />)
    expect(container.firstChild).toBeNull()
  })

  it('shows student name in title', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'PARENT', roles: ['PARENT'] } } as ReturnType<typeof useAuth>)
    render(<ParentSummaryCard summary="Test" studentName="Haashini" />)
    expect(screen.getByText(/Haashini/)).toBeInTheDocument()
  })

  it('toggles collapse on header click', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'PARENT', roles: ['PARENT'] } } as ReturnType<typeof useAuth>)
    render(<ParentSummaryCard summary="My summary text" />)

    expect(screen.getByText('My summary text')).toBeInTheDocument()

    // Click to collapse
    fireEvent.click(screen.getByText('Parent Summary'))
    expect(screen.queryByText('My summary text')).not.toBeInTheDocument()

    // Click to expand
    fireEvent.click(screen.getByText('Parent Summary'))
    expect(screen.getByText('My summary text')).toBeInTheDocument()
  })

  it('starts collapsed when collapsed prop is true', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'PARENT', roles: ['PARENT'] } } as ReturnType<typeof useAuth>)
    render(<ParentSummaryCard summary="Hidden text" collapsed />)
    expect(screen.queryByText('Hidden text')).not.toBeInTheDocument()
  })

  it('renders for multi-role user with PARENT in roles array', () => {
    mockUseAuth.mockReturnValue({
      user: { role: 'TEACHER', roles: ['TEACHER', 'PARENT'] },
    } as ReturnType<typeof useAuth>)
    render(<ParentSummaryCard summary="Multi-role test" />)
    expect(screen.getByText('Multi-role test')).toBeInTheDocument()
  })
})
