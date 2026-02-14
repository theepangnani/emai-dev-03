import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// Mock AuthContext
const mockUseAuth = vi.fn()
vi.mock('../context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}))

import { ProtectedRoute } from './ProtectedRoute'

function renderProtected(allowedRoles?: string[]) {
  return render(
    <MemoryRouter>
      <ProtectedRoute allowedRoles={allowedRoles}>
        <div data-testid="protected-content">Secret Content</div>
      </ProtectedRoute>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  it('shows loading while auth is loading', () => {
    mockUseAuth.mockReturnValue({ user: null, isLoading: true })
    renderProtected()
    expect(screen.getByText('Loading...')).toBeInTheDocument()
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
  })

  it('redirects to login when not authenticated', () => {
    mockUseAuth.mockReturnValue({ user: null, isLoading: false })
    renderProtected()
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
  })

  it('renders children when authenticated and no role restriction', () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: 'parent', roles: ['parent'] },
      isLoading: false,
    })
    renderProtected()
    expect(screen.getByTestId('protected-content')).toBeInTheDocument()
  })

  it('renders children when user has matching role', () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: 'teacher', roles: ['teacher', 'parent'] },
      isLoading: false,
    })
    renderProtected(['teacher', 'admin'])
    expect(screen.getByTestId('protected-content')).toBeInTheDocument()
  })

  it('blocks access when user lacks required role', () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: 'student', roles: ['student'] },
      isLoading: false,
    })
    renderProtected(['admin'])
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
  })
})
