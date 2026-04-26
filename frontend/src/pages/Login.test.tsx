import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'

// Mocks — must be before component import
const mockLogin = vi.fn()
const mockLoginWithToken = vi.fn()
let mockUser: any = null
const mockNavigate = vi.fn()
const mockSearchParams = new URLSearchParams()
const mockSetSearchParams = vi.fn()
const mockGetAuthUrl = vi.fn()
let mockWaitlistEnabled = false

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    login: mockLogin,
    loginWithToken: mockLoginWithToken,
  }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearchParams: () => [mockSearchParams, mockSetSearchParams],
  }
})

vi.mock('../api/client', () => ({
  googleApi: {
    getAuthUrl: () => mockGetAuthUrl(),
  },
}))

// Mock useFeature so tests aren't gated on the async /api/features query.
// Without this, `waitlist_enabled` falls back to its DEFAULT_DURING_LOAD=true,
// hiding the "Sign up" link and breaking the auth-footer test (#4251).
vi.mock('../hooks/useFeatureToggle', () => ({
  useFeature: (key: string) => {
    if (key === 'waitlist_enabled') return mockWaitlistEnabled
    return false
  },
}))

import { Login } from './Login'

describe('Login', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUser = null
    mockWaitlistEnabled = false
    // Reset search params to empty
    mockSearchParams.delete('token')
    mockSearchParams.delete('error')
  })

  it('renders email and password inputs and submit button', () => {
    renderWithProviders(<Login />)

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('renders Google sign-in button', () => {
    renderWithProviders(<Login />)

    expect(screen.getByRole('button', { name: /continue with google/i })).toBeInTheDocument()
  })

  it('renders links to sign up and forgot password', () => {
    renderWithProviders(<Login />)

    // waitlist_enabled defaults to false, so "Sign up" link is shown
    expect(screen.getByRole('link', { name: /sign up/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /forgot password/i })).toBeInTheDocument()
  })

  it('renders waitlist link when waitlist_enabled is true', () => {
    mockWaitlistEnabled = true

    renderWithProviders(<Login />)

    expect(screen.getByRole('link', { name: /join the waitlist/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /sign up/i })).not.toBeInTheDocument()
  })

  it('submits credentials and calls login()', async () => {
    mockLogin.mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderWithProviders(<Login />)

    await user.type(screen.getByLabelText(/email/i), 'test@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123', { started_at: expect.any(Number), website: '' })
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
    })
  })

  it('shows error message on login failure', async () => {
    mockLogin.mockRejectedValue({
      response: { data: { detail: 'Invalid credentials' } },
    })
    const user = userEvent.setup()

    renderWithProviders(<Login />)

    await user.type(screen.getByLabelText(/email/i), 'bad@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'wrong')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument()
    })
  })

  it('shows generic error when no detail in response', async () => {
    mockLogin.mockRejectedValue(new Error('Network error'))
    const user = userEvent.setup()

    renderWithProviders(<Login />)

    await user.type(screen.getByLabelText(/email/i), 'test@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'pass')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByText(/login failed/i)).toBeInTheDocument()
    })
  })

  it('disables submit button while loading', async () => {
    // login never resolves to keep loading state
    mockLogin.mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()

    renderWithProviders(<Login />)

    await user.type(screen.getByLabelText(/email/i), 'test@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'pass')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled()
  })

  it('redirects to dashboard when user is already logged in', async () => {
    mockUser = { id: 1, role: 'parent' }

    renderWithProviders(<Login />)

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard', { replace: true })
    })
  })

  it('handles OAuth callback with token param', () => {
    mockSearchParams.set('token', 'oauth-jwt-token')

    renderWithProviders(<Login />)

    expect(mockLoginWithToken).toHaveBeenCalledWith('oauth-jwt-token')
    expect(mockSetSearchParams).toHaveBeenCalledWith({}, { replace: true })
  })

  it('handles OAuth callback with error param', async () => {
    mockSearchParams.set('error', 'access_denied')

    renderWithProviders(<Login />)

    await waitFor(() => {
      expect(screen.getByText(/google sign-in failed: access_denied/i)).toBeInTheDocument()
    })
    expect(mockSetSearchParams).toHaveBeenCalledWith({}, { replace: true })
  })

  it('Google button calls getAuthUrl', async () => {
    mockGetAuthUrl.mockResolvedValue({ authorization_url: 'https://accounts.google.com/auth' })
    const user = userEvent.setup()

    // Mock window.location.href
    const hrefSetter = vi.fn()
    Object.defineProperty(window, 'location', {
      value: { ...window.location, href: '' },
      writable: true,
    })
    Object.defineProperty(window.location, 'href', {
      set: hrefSetter,
      get: () => '',
    })

    renderWithProviders(<Login />)

    await user.click(screen.getByRole('button', { name: /continue with google/i }))

    await waitFor(() => {
      expect(mockGetAuthUrl).toHaveBeenCalledOnce()
    })
  })

  it('shows error when Google sign-in fails', async () => {
    mockGetAuthUrl.mockRejectedValue(new Error('Network'))
    const user = userEvent.setup()

    renderWithProviders(<Login />)

    await user.click(screen.getByRole('button', { name: /continue with google/i }))

    await waitFor(() => {
      expect(screen.getByText(/failed to initiate google sign-in/i)).toBeInTheDocument()
    })
  })
})
