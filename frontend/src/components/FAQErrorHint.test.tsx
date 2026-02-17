import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────

const mockGetByErrorCode = vi.fn()
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../api/client', () => ({
  faqApi: {
    getByErrorCode: (...args: any[]) => mockGetByErrorCode(...args),
  },
}))

// ── Import after mocks ────────────────────────────────────────
import { FAQErrorHint, extractFaqCode } from './FAQErrorHint'

// ── Tests ──────────────────────────────────────────────────────
describe('FAQErrorHint', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders nothing when faqCode is null', () => {
    const { container } = renderWithProviders(<FAQErrorHint faqCode={null} />)
    expect(container.querySelector('.faq-error-hint')).toBeNull()
  })

  it('renders nothing when faqCode is undefined', () => {
    const { container } = renderWithProviders(<FAQErrorHint />)
    expect(container.querySelector('.faq-error-hint')).toBeNull()
  })

  it('renders hint when FAQ entry is found', async () => {
    mockGetByErrorCode.mockResolvedValue({
      id: 5,
      title: 'How to fix Google sync',
      url: '/faq/5',
    })
    renderWithProviders(<FAQErrorHint faqCode="GOOGLE_SYNC_FAILED" />)
    await waitFor(() => {
      expect(screen.getByText('How to fix Google sync')).toBeInTheDocument()
    })
    expect(screen.getByText('Need help? See:')).toBeInTheDocument()
    expect(mockGetByErrorCode).toHaveBeenCalledWith('GOOGLE_SYNC_FAILED')
  })

  it('navigates to FAQ detail on link click', async () => {
    mockGetByErrorCode.mockResolvedValue({
      id: 5,
      title: 'How to fix Google sync',
      url: '/faq/5',
    })
    const user = userEvent.setup()
    renderWithProviders(<FAQErrorHint faqCode="GOOGLE_SYNC_FAILED" />)
    await waitFor(() => {
      expect(screen.getByText('How to fix Google sync')).toBeInTheDocument()
    })
    await user.click(screen.getByText('How to fix Google sync'))
    expect(mockNavigate).toHaveBeenCalledWith('/faq/5')
  })

  it('renders nothing when API returns 404', async () => {
    mockGetByErrorCode.mockRejectedValue(new Error('Not found'))
    const { container } = renderWithProviders(<FAQErrorHint faqCode="UNKNOWN_CODE" />)
    // Wait for the effect to resolve
    await waitFor(() => {
      expect(mockGetByErrorCode).toHaveBeenCalledWith('UNKNOWN_CODE')
    })
    expect(container.querySelector('.faq-error-hint')).toBeNull()
  })
})

describe('extractFaqCode', () => {
  it('extracts faq_code from Axios error response', () => {
    const error = {
      response: {
        data: { detail: 'Sync failed', faq_code: 'GOOGLE_SYNC_FAILED' },
      },
    }
    expect(extractFaqCode(error)).toBe('GOOGLE_SYNC_FAILED')
  })

  it('returns null for regular errors', () => {
    expect(extractFaqCode(new Error('plain error'))).toBeNull()
  })

  it('returns null for null input', () => {
    expect(extractFaqCode(null)).toBeNull()
  })

  it('returns null when response has no faq_code', () => {
    const error = {
      response: {
        data: { detail: 'Some error' },
      },
    }
    expect(extractFaqCode(error)).toBeNull()
  })
})
