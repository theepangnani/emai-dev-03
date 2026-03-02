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
    // Nav items appear in both slide-out menu and persistent sidebar
    expect(screen.getAllByText('Home').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('My Kids').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Tasks').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Messages').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Help').length).toBeGreaterThanOrEqual(1)
  })

  it('shows standard nav items for student role', () => {
    renderLayout('student')
    expect(screen.getAllByText('Home').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Study').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Tasks').length).toBeGreaterThanOrEqual(1)
  })

  it('shows teacher comms for teacher role', () => {
    renderLayout('teacher')
    expect(screen.getAllByText('Teacher Comms').length).toBeGreaterThanOrEqual(1)
  })
})
