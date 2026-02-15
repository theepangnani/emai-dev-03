import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'

// Mocks — must be before component import
const mockRegister = vi.fn()
const mockNavigate = vi.fn()
const mockSearchParams = new URLSearchParams()
const mockSetSearchParams = vi.fn()

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    register: mockRegister,
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

import { Register } from './Register'

describe('Register', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams.delete('google_email')
    mockSearchParams.delete('google_name')
    mockSearchParams.delete('google_id')
  })

  it('renders simplified form fields (no role selection)', () => {
    renderWithProviders(<Register />)

    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument()

    // Role checkboxes and teacher type should NOT be present
    expect(screen.queryByText(/select role/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/teacher type/i)).not.toBeInTheDocument()
  })

  it('renders link to login page', () => {
    renderWithProviders(<Register />)

    expect(screen.getByRole('link', { name: /sign in/i })).toBeInTheDocument()
  })

  it('validates password match', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Register />)

    await user.type(screen.getByLabelText(/full name/i), 'Test User')
    await user.type(screen.getByLabelText(/email/i), 'test@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'different456')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument()
    expect(mockRegister).not.toHaveBeenCalled()
  })

  it('submits form with empty roles and navigates to /onboarding', async () => {
    mockRegister.mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderWithProviders(<Register />)

    await user.type(screen.getByLabelText(/full name/i), 'New User')
    await user.type(screen.getByLabelText(/email/i), 'new@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(mockRegister).toHaveBeenCalledWith({
      email: 'new@example.com',
      password: 'password123',
      full_name: 'New User',
      roles: [],
    })
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/onboarding')
    })
  })

  it('shows error message on registration failure', async () => {
    mockRegister.mockRejectedValue({
      response: { data: { detail: 'Email already registered' } },
    })
    const user = userEvent.setup()

    renderWithProviders(<Register />)

    await user.type(screen.getByLabelText(/full name/i), 'Test')
    await user.type(screen.getByLabelText(/email/i), 'dup@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(screen.getByText(/email already registered/i)).toBeInTheDocument()
    })
  })

  it('shows generic error when no detail in response', async () => {
    mockRegister.mockRejectedValue(new Error('Network'))
    const user = userEvent.setup()

    renderWithProviders(<Register />)

    await user.type(screen.getByLabelText(/full name/i), 'Test')
    await user.type(screen.getByLabelText(/email/i), 'test@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(screen.getByText(/registration failed/i)).toBeInTheDocument()
    })
  })

  it('disables submit button while loading', async () => {
    mockRegister.mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()

    renderWithProviders(<Register />)

    await user.type(screen.getByLabelText(/full name/i), 'Test')
    await user.type(screen.getByLabelText(/email/i), 'test@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(screen.getByRole('button', { name: /creating account/i })).toBeDisabled()
  })

  it('pre-fills from Google OAuth params', () => {
    mockSearchParams.set('google_email', 'google@example.com')
    mockSearchParams.set('google_name', 'Google User')
    mockSearchParams.set('google_id', 'google-123')

    renderWithProviders(<Register />)

    expect(screen.getByLabelText(/email/i)).toHaveValue('google@example.com')
    expect(screen.getByLabelText(/email/i)).toBeDisabled()
    expect(screen.getByLabelText(/full name/i)).toHaveValue('Google User')
    expect(screen.getByText(/complete your google account setup/i)).toBeInTheDocument()
  })

  it('includes google_id in register call for Google signup', async () => {
    mockSearchParams.set('google_email', 'google@example.com')
    mockSearchParams.set('google_name', 'Google User')
    mockSearchParams.set('google_id', 'google-123')
    mockRegister.mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderWithProviders(<Register />)

    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(mockRegister).toHaveBeenCalledWith(
      expect.objectContaining({ google_id: 'google-123', roles: [] }),
    )
  })
})
