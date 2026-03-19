import { renderHook, act, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'

// Mock authApi before importing AuthProvider
const mockLogin = vi.fn()
const mockRegister = vi.fn()
const mockGetMe = vi.fn()
const mockLogout = vi.fn()
const mockSwitchRole = vi.fn()

vi.mock('../api/client', () => ({
  authApi: {
    login: (...args: unknown[]) => mockLogin(...args),
    register: (...args: unknown[]) => mockRegister(...args),
    getMe: () => mockGetMe(),
    logout: () => mockLogout(),
    switchRole: (...args: unknown[]) => mockSwitchRole(...args),
  },
}))

import { AuthProvider, useAuth } from './AuthContext'

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>
}

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    // Default: no token → getMe not called → isLoading settles to false
    mockGetMe.mockRejectedValue(new Error('no token'))
  })

  it('settles to not loading with no user when no token exists', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })
    expect(result.current.user).toBeNull()
    expect(result.current.token).toBeNull()
  })

  it('loads user from existing token in localStorage', async () => {
    localStorage.setItem('token', 'existing-jwt')
    const mockUser = { id: 1, email: 'test@example.com', full_name: 'Test', role: 'parent', roles: ['parent'], is_active: true, google_connected: false }
    mockGetMe.mockResolvedValue(mockUser)

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })
    expect(result.current.user).toEqual(mockUser)
    expect(mockGetMe).toHaveBeenCalledOnce()
  })

  it('clears stale token when getMe fails', async () => {
    localStorage.setItem('token', 'stale-jwt')
    mockGetMe.mockRejectedValue(new Error('401'))

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })
    expect(result.current.user).toBeNull()
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('login() stores token, fetches user', async () => {
    mockLogin.mockResolvedValue({ access_token: 'new-jwt', refresh_token: 'refresh-jwt' })
    const mockUser = { id: 1, email: 'test@example.com', full_name: 'Test', role: 'parent', roles: ['parent'], is_active: true, google_connected: false }
    mockGetMe.mockResolvedValue(mockUser)

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    await act(async () => {
      await result.current.login('test@example.com', 'password123')
    })

    expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123', undefined)
    expect(localStorage.getItem('token')).toBe('new-jwt')
    expect(localStorage.getItem('refresh_token')).toBe('refresh-jwt')
    expect(result.current.user).toEqual(mockUser)
  })

  it('register() calls register then auto-logs in', async () => {
    mockRegister.mockResolvedValue({})
    mockLogin.mockResolvedValue({ access_token: 'reg-jwt' })
    const mockUser = { id: 2, email: 'new@example.com', full_name: 'New User', role: 'student', roles: ['student'], is_active: true, google_connected: false }
    mockGetMe.mockResolvedValue(mockUser)

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    const regData = { email: 'new@example.com', password: 'pass1234', full_name: 'New User', role: 'student' }
    await act(async () => {
      await result.current.register(regData)
    })

    expect(mockRegister).toHaveBeenCalledWith(regData)
    expect(mockLogin).toHaveBeenCalledWith('new@example.com', 'pass1234', undefined)
    expect(result.current.user).toEqual(mockUser)
  })

  it('logout() clears token and user', async () => {
    localStorage.setItem('token', 'existing-jwt')
    const mockUser = { id: 1, email: 'test@example.com', full_name: 'Test', role: 'parent', roles: ['parent'], is_active: true, google_connected: false }
    mockGetMe.mockResolvedValue(mockUser)
    mockLogout.mockResolvedValue({})

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.user).toEqual(mockUser)
    })

    act(() => {
      result.current.logout()
    })

    expect(result.current.user).toBeNull()
    expect(result.current.token).toBeNull()
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })

  it('switchRole() updates user data', async () => {
    localStorage.setItem('token', 'existing-jwt')
    const parentUser = { id: 1, email: 'test@example.com', full_name: 'Test', role: 'parent', roles: ['parent', 'teacher'], is_active: true, google_connected: false }
    const teacherUser = { ...parentUser, role: 'teacher' }
    mockGetMe.mockResolvedValue(parentUser)
    mockSwitchRole.mockResolvedValue(teacherUser)

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.user?.role).toBe('parent')
    })

    await act(async () => {
      await result.current.switchRole('teacher')
    })

    expect(mockSwitchRole).toHaveBeenCalledWith('teacher')
    expect(result.current.user?.role).toBe('teacher')
  })

  it('loginWithToken() stores token and triggers user load', async () => {
    const mockUser = { id: 1, email: 'test@example.com', full_name: 'Test', role: 'parent', roles: ['parent'], is_active: true, google_connected: false }
    mockGetMe.mockResolvedValue(mockUser)

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    act(() => {
      result.current.loginWithToken('oauth-jwt', 'oauth-refresh')
    })

    await waitFor(() => {
      expect(result.current.user).toEqual(mockUser)
    })
    expect(localStorage.getItem('token')).toBe('oauth-jwt')
    expect(localStorage.getItem('refresh_token')).toBe('oauth-refresh')
  })
})
