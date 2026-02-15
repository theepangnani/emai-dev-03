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

  it('renders all form fields', () => {
    renderWithProviders(<Register />)

    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByText(/select role\(s\)/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/parent \/ guardian/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/student/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/teacher/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument()
  })

  it('renders link to login page', () => {
    renderWithProviders(<Register />)

    expect(screen.getByRole('link', { name: /sign in/i })).toBeInTheDocument()
  })

  it('does not show teacher_type field by default (no roles selected)', () => {
    renderWithProviders(<Register />)

    expect(screen.queryByLabelText(/teacher type/i)).not.toBeInTheDocument()
  })

  it('shows teacher_type dropdown when teacher checkbox is checked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Register />)

    await user.click(screen.getByLabelText(/teacher/i))

    expect(screen.getByLabelText(/teacher type/i)).toBeInTheDocument()
    expect(screen.getByText(/school teacher/i)).toBeInTheDocument()
    expect(screen.getByText(/private tutor/i)).toBeInTheDocument()
  })

  it('hides teacher_type when teacher checkbox is unchecked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Register />)

    const teacherCheckbox = screen.getByRole('checkbox', { name: /teacher/i })
    await user.click(teacherCheckbox)
    expect(screen.getByLabelText(/teacher type/i)).toBeInTheDocument()

    await user.click(teacherCheckbox)
    expect(screen.queryByLabelText(/teacher type/i)).not.toBeInTheDocument()
  })

  it('validates password match', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Register />)

    await user.type(screen.getByLabelText(/full name/i), 'Test User')
    await user.type(screen.getByLabelText(/email/i), 'test@example.com')
    await user.click(screen.getByLabelText(/parent \/ guardian/i))
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'different456')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument()
    expect(mockRegister).not.toHaveBeenCalled()
  })

  it('submits form and calls register() on success', async () => {
    mockRegister.mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderWithProviders(<Register />)

    await user.type(screen.getByLabelText(/full name/i), 'New User')
    await user.type(screen.getByLabelText(/email/i), 'new@example.com')
    await user.click(screen.getByLabelText(/parent \/ guardian/i))
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(mockRegister).toHaveBeenCalledWith({
      email: 'new@example.com',
      password: 'password123',
      full_name: 'New User',
      roles: ['parent'],
    })
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
    })
  })

  it('submits with teacher_type when teacher checkbox is checked', async () => {
    mockRegister.mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderWithProviders(<Register />)

    await user.type(screen.getByLabelText(/full name/i), 'Teacher User')
    await user.type(screen.getByLabelText(/email/i), 'teacher@example.com')
    await user.click(screen.getByLabelText(/teacher/i))
    await user.selectOptions(screen.getByLabelText(/teacher type/i), 'school_teacher')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(mockRegister).toHaveBeenCalledWith({
      email: 'teacher@example.com',
      password: 'password123',
      full_name: 'Teacher User',
      roles: ['teacher'],
      teacher_type: 'school_teacher',
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
    await user.click(screen.getByLabelText(/parent \/ guardian/i))
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
    await user.click(screen.getByLabelText(/parent \/ guardian/i))
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
    await user.click(screen.getByLabelText(/parent \/ guardian/i))
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

    await user.click(screen.getByLabelText(/parent \/ guardian/i))
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(mockRegister).toHaveBeenCalledWith(
      expect.objectContaining({ google_id: 'google-123', roles: ['parent'] }),
    )
  })

  it('validates that at least one role is selected', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Register />)

    await user.type(screen.getByLabelText(/full name/i), 'Test User')
    await user.type(screen.getByLabelText(/email/i), 'test@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(screen.getByText(/please select at least one role/i)).toBeInTheDocument()
    expect(mockRegister).not.toHaveBeenCalled()
  })

  it('submits with multiple roles when multiple checkboxes are selected', async () => {
    mockRegister.mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderWithProviders(<Register />)

    await user.type(screen.getByLabelText(/full name/i), 'Multi Role User')
    await user.type(screen.getByLabelText(/email/i), 'multi@example.com')
    await user.click(screen.getByLabelText(/parent \/ guardian/i))
    await user.click(screen.getByLabelText(/student/i))
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(mockRegister).toHaveBeenCalledWith({
      email: 'multi@example.com',
      password: 'password123',
      full_name: 'Multi Role User',
      roles: ['parent', 'student'],
    })
  })
})
