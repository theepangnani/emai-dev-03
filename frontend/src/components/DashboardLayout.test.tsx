import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// Mutable mock state
let mockUser: any = null

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    logout: vi.fn(),
    switchRole: vi.fn(),
  }),
}))

vi.mock('../context/ThemeContext', () => ({
  useTheme: () => ({ theme: 'light', setTheme: vi.fn(), cycleTheme: vi.fn() }),
}))

vi.mock('../api/client', () => ({
  messagesApi: { getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }) },
  inspirationApi: { getRandom: vi.fn().mockResolvedValue(null) },
}))

vi.mock('./NotificationBell', () => ({
  NotificationBell: () => <div data-testid="notification-bell" />,
}))

import { DashboardLayout } from './DashboardLayout'

function renderLayout(role: string) {
  mockUser = { id: 1, full_name: 'Test User', role, roles: [role] }

  return render(
    <MemoryRouter>
      <DashboardLayout welcomeSubtitle="Test subtitle">
        <div data-testid="child-content">Content</div>
      </DashboardLayout>
    </MemoryRouter>,
  )
}

describe('DashboardLayout', () => {
  beforeEach(() => {
    mockUser = null
  })

  it('renders child content', () => {
    renderLayout('parent')
    expect(screen.getByTestId('child-content')).toBeInTheDocument()
  })

  it('shows parent nav items for parent role', () => {
    renderLayout('parent')
    expect(screen.getByText('Home')).toBeInTheDocument()
    expect(screen.getByText('My Kids')).toBeInTheDocument()
    expect(screen.queryByText('Courses')).not.toBeInTheDocument()
  })

  it('shows standard nav items for student role', () => {
    renderLayout('student')
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Courses')).toBeInTheDocument()
    expect(screen.getByText('Course Materials')).toBeInTheDocument()
  })

  it('shows teacher comms for teacher role', () => {
    renderLayout('teacher')
    expect(screen.getByText('Teacher Comms')).toBeInTheDocument()
  })
})
