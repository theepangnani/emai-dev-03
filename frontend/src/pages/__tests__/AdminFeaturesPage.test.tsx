import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────
const mockGetFeatures = vi.fn()
const mockUpdateFeatureVariant = vi.fn()

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Admin User', role: 'admin', roles: ['admin'] },
    logout: vi.fn(),
    switchRole: vi.fn(),
  }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

vi.mock('../../api/admin', () => ({
  adminApi: {
    getFeatures: (...args: unknown[]) => mockGetFeatures(...args),
    updateFeatureToggle: vi.fn().mockResolvedValue({ enabled: false }),
    updateFeatureVariant: (...args: unknown[]) => mockUpdateFeatureVariant(...args),
  },
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../api/client')
  return {
    ...actual,
    messagesApi: {
      getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }),
    },
    inspirationApi: {
      getRandom: vi.fn().mockRejectedValue(new Error('none')),
    },
  }
})

vi.mock('../../components/NotificationBell', () => ({
  NotificationBell: () => <div data-testid="notification-bell" />,
}))

vi.mock('../../components/ThemeToggle', () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}))

vi.mock('../../components/Toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

// ── Import after mocks ────────────────────────────────────────
import { AdminFeaturesPage } from '../AdminFeaturesPage'

describe('AdminFeaturesPage — kill-switch mismatch warning (#3933)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders warning chip when enabled=false but variant is non-off', async () => {
    mockGetFeatures.mockResolvedValue([
      {
        key: 'landing_v2',
        name: 'Landing V2',
        description: null,
        enabled: false,
        variant: 'on_for_all',
        updated_at: '2026-04-20T00:00:00Z',
      },
    ])

    renderWithProviders(<AdminFeaturesPage />)

    const alert = await screen.findByTestId('feature-mismatch-landing_v2')
    expect(alert).toBeInTheDocument()
    expect(alert).toHaveTextContent(/Enabled is off/i)
    expect(alert).toHaveTextContent(/on_for_all/)
    expect(alert).toHaveTextContent(/Kill-switch is active/i)
  })

  it('does NOT render warning when enabled=false and variant=off', async () => {
    mockGetFeatures.mockResolvedValue([
      {
        key: 'landing_v2',
        name: 'Landing V2',
        description: null,
        enabled: false,
        variant: 'off',
        updated_at: '2026-04-20T00:00:00Z',
      },
    ])

    renderWithProviders(<AdminFeaturesPage />)

    await waitFor(() => {
      expect(screen.getByText('Landing V2')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('feature-mismatch-landing_v2')).not.toBeInTheDocument()
  })

  it('does NOT render warning when enabled=true and variant=on_for_all', async () => {
    mockGetFeatures.mockResolvedValue([
      {
        key: 'landing_v2',
        name: 'Landing V2',
        description: null,
        enabled: true,
        variant: 'on_for_all',
        updated_at: '2026-04-20T00:00:00Z',
      },
    ])

    renderWithProviders(<AdminFeaturesPage />)

    await waitFor(() => {
      expect(screen.getByText('Landing V2')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('feature-mismatch-landing_v2')).not.toBeInTheDocument()
  })

  it('Auto-fix button calls updateFeatureVariant with off', async () => {
    mockGetFeatures.mockResolvedValue([
      {
        key: 'landing_v2',
        name: 'Landing V2',
        description: null,
        enabled: false,
        variant: 'on_for_all',
        updated_at: '2026-04-20T00:00:00Z',
      },
    ])
    mockUpdateFeatureVariant.mockResolvedValue({ feature: 'landing_v2', variant: 'off' })

    const user = userEvent.setup()
    renderWithProviders(<AdminFeaturesPage />)

    const fixBtn = await screen.findByRole('button', { name: /auto-fix/i })
    await user.click(fixBtn)

    await waitFor(() => {
      expect(mockUpdateFeatureVariant).toHaveBeenCalledWith('landing_v2', 'off')
    })
  })
})
