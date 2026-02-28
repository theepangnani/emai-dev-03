import { screen } from '@testing-library/react'
import { renderWithProviders } from '../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────
let mockRole: string | undefined = 'parent'

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: mockRole ? { id: 1, full_name: 'Test User', role: mockRole, roles: [mockRole] } : null,
    logout: vi.fn(),
    switchRole: vi.fn(),
  }),
}))

vi.mock('./ParentDashboard', () => ({
  ParentDashboard: () => <div data-testid="parent-dashboard">ParentDashboard</div>,
}))
vi.mock('./StudentDashboard', () => ({
  StudentDashboard: () => <div data-testid="student-dashboard">StudentDashboard</div>,
}))
vi.mock('./TeacherDashboard', () => ({
  TeacherDashboard: () => <div data-testid="teacher-dashboard">TeacherDashboard</div>,
}))
vi.mock('./AdminDashboard', () => ({
  AdminDashboard: () => <div data-testid="admin-dashboard">AdminDashboard</div>,
}))

import { Dashboard } from './Dashboard'

describe('Dashboard (dispatcher)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRole = 'parent'
  })

  it('renders ParentDashboard when user role is parent', () => {
    mockRole = 'parent'
    renderWithProviders(<Dashboard />)
    expect(screen.getByTestId('parent-dashboard')).toBeInTheDocument()
  })

  it('renders TeacherDashboard when user role is teacher', () => {
    mockRole = 'teacher'
    renderWithProviders(<Dashboard />)
    expect(screen.getByTestId('teacher-dashboard')).toBeInTheDocument()
  })

  it('renders AdminDashboard when user role is admin', () => {
    mockRole = 'admin'
    renderWithProviders(<Dashboard />)
    expect(screen.getByTestId('admin-dashboard')).toBeInTheDocument()
  })

  it('renders StudentDashboard when user role is student', () => {
    mockRole = 'student'
    renderWithProviders(<Dashboard />)
    expect(screen.getByTestId('student-dashboard')).toBeInTheDocument()
  })

})
