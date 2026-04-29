import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// Spy on Navigate's props so we can assert state.from without rendering a
// second route. Using vi.importActual + spread keeps every other react-router
// export real (avoids mock-shadow shadowing useNavigate, useLocation, etc.).
const navigateSpy = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    Navigate: (props: Record<string, unknown>) => {
      navigateSpy(props)
      return null
    },
  }
})

// Mock AuthContext
const mockUseAuth = vi.fn()
vi.mock('../context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}))

import { ProtectedRoute } from './ProtectedRoute'

function renderProtected(allowedRoles?: string[], initialEntry: string = '/') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <ProtectedRoute allowedRoles={allowedRoles}>
        <div data-testid="protected-content">Secret Content</div>
      </ProtectedRoute>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    navigateSpy.mockClear()
  })

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
    expect(navigateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ to: '/login' }),
    )
  })

  it('preserves the originating path in Navigate state when redirecting to /login (#4486)', () => {
    mockUseAuth.mockReturnValue({ user: null, isLoading: false })
    renderProtected(undefined, '/email-digest')
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
    expect(navigateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        to: '/login',
        state: expect.objectContaining({
          from: expect.objectContaining({ pathname: '/email-digest' }),
        }),
      }),
    )
  })

  it('renders children when authenticated and no role restriction', () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: 'parent', roles: ['parent'], needs_onboarding: false, onboarding_completed: true },
      isLoading: false,
    })
    renderProtected()
    expect(screen.getByTestId('protected-content')).toBeInTheDocument()
  })

  it('renders children when user has matching role', () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: 'teacher', roles: ['teacher', 'parent'], needs_onboarding: false, onboarding_completed: true },
      isLoading: false,
    })
    renderProtected(['teacher', 'admin'])
    expect(screen.getByTestId('protected-content')).toBeInTheDocument()
  })

  it('blocks access when user lacks required role', () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: 'student', roles: ['student'], needs_onboarding: false, onboarding_completed: true },
      isLoading: false,
    })
    renderProtected(['admin'])
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
  })

  it('redirects to onboarding when onboarding_completed is false', () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: null, roles: [], needs_onboarding: true, onboarding_completed: false },
      isLoading: false,
    })
    renderProtected()
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
  })

  it('redirects to onboarding when needs_onboarding is true', () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: null, roles: [], needs_onboarding: true, onboarding_completed: false },
      isLoading: false,
    })
    renderProtected()
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
  })
})
