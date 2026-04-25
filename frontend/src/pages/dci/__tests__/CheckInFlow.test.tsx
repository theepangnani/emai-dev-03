/**
 * CB-DCI-001 M0-9 — happy-path tests for the kid /checkin flow.
 *
 * Three tests, one per input type. The backend (M0-4 + M0-8) may not be
 * merged yet, so we mock `../../../api/dci` directly. Each test exercises
 * the same arc: page renders → user provides input → "Send to ClassBridge"
 * → AI chip surfaces → "All good — finish" → done screen renders.
 */
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { renderWithProviders } from '../../../test/helpers'

// ── Mocks ──────────────────────────────────────────────────────
const mockSubmit = vi.fn()
const mockGetStatus = vi.fn()
const mockCorrect = vi.fn()
const mockGetStreak = vi.fn()

vi.mock('../../../api/dci', () => ({
  dciApi: {
    submitCheckin: (...args: unknown[]) => mockSubmit(...args),
    getStatus: (...args: unknown[]) => mockGetStatus(...args),
    correct: (...args: unknown[]) => mockCorrect(...args),
    getStreak: (...args: unknown[]) => mockGetStreak(...args),
  },
}))

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 42,
      full_name: 'Haashini Sharma',
      role: 'student',
      roles: ['student'],
    },
    logout: vi.fn(),
  }),
}))

// Lazy import after mocks so the mocks are in place when the page modules
// pull `dciApi` / useAuth.
import { CheckInIntroPage } from '../CheckInIntroPage'
import { CheckInCapturePage } from '../CheckInCapturePage'
import { CheckInDonePage } from '../CheckInDonePage'

beforeEach(() => {
  vi.clearAllMocks()
  mockGetStreak.mockResolvedValue({
    kid_id: 42,
    current_streak: 3,
    longest_streak: 7,
    last_checkin_date: '2026-04-24',
    last_voice_sentiment: 0.4,
  })
  mockSubmit.mockResolvedValue({
    checkin_id: 100,
    status: 'classified',
    classifications: [
      {
        artifact_type: 'text',
        subject: 'Math',
        topic: 'Fractions',
        deadline_iso: '2026-05-01',
        confidence: 0.91,
        corrected_by_kid: false,
      },
    ],
  })
})

describe('CheckInIntroPage (Screen 1)', () => {
  it('greets the kid by first name + shows three input CTAs', async () => {
    renderWithProviders(<CheckInIntroPage />)
    await waitFor(() => {
      expect(screen.getByText(/Hi Haashini/)).toBeInTheDocument()
    })
    expect(screen.getByText('Snap a photo')).toBeInTheDocument()
    expect(screen.getByText('Record voice')).toBeInTheDocument()
    expect(screen.getByText('Type a line')).toBeInTheDocument()
  })
})

describe('CheckInCapturePage — text happy path', () => {
  it('lets the kid type a line, send it, see AI chip, and finish', async () => {
    // delay:null ⇒ no per-keystroke wait, keeps the test fast under
    // full-suite contention (textarea triggers a parent re-render per char).
    const user = userEvent.setup({ delay: null })
    renderWithProviders(<CheckInCapturePage />, {
      initialEntries: ['/checkin/capture?mode=text'],
    })

    const textarea = await screen.findByLabelText(
      /tell classbridge about your day/i,
    )
    // Use paste rather than type — bulk insert avoids N re-renders.
    await user.click(textarea)
    await user.paste('We learned about fractions today')

    const sendBtn = screen.getByRole('button', { name: /send to classbridge/i })
    expect(sendBtn).toBeEnabled()
    await user.click(sendBtn)

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledTimes(1)
    })

    // AIDetectedChip appears with the classifier output
    await waitFor(() => {
      expect(
        screen.getByText(/Math · Fractions · due 2026-05-01/),
      ).toBeInTheDocument()
    })

    // "All good — finish" CTA appears once submission lands
    expect(
      screen.getByRole('button', { name: /all good — finish/i }),
    ).toBeInTheDocument()
  })
})

describe('CheckInCapturePage — photo happy path', () => {
  beforeEach(() => {
    mockSubmit.mockResolvedValueOnce({
      checkin_id: 101,
      status: 'classified',
      classifications: [
        {
          artifact_type: 'photo',
          subject: 'Science',
          topic: 'Plants',
          deadline_iso: null,
          confidence: 0.88,
          corrected_by_kid: false,
        },
      ],
    })
  })

  it('captures a webcam frame, sends it, and surfaces the AI chip', async () => {
    const user = userEvent.setup()

    // Stub navigator.mediaDevices.getUserMedia for jsdom.
    const fakeStream = {
      getTracks: () => [{ stop: vi.fn() }],
    } as unknown as MediaStream
    Object.defineProperty(navigator, 'mediaDevices', {
      value: { getUserMedia: vi.fn().mockResolvedValue(fakeStream) },
      configurable: true,
    })

    // canvas.toBlob isn't implemented in jsdom — fake it.
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
      drawImage: vi.fn(),
    })) as unknown as typeof HTMLCanvasElement.prototype.getContext
    HTMLCanvasElement.prototype.toBlob = function (cb: BlobCallback) {
      cb(new Blob(['fake'], { type: 'image/jpeg' }))
    }

    renderWithProviders(<CheckInCapturePage />, {
      initialEntries: ['/checkin/capture?mode=photo'],
    })

    // Wait for the picker (camera permission resolves async)
    const snap = await screen.findByRole('button', { name: /snap photo/i })
    await user.click(snap)

    const sendBtn = await screen.findByRole('button', {
      name: /send to classbridge/i,
    })
    await user.click(sendBtn)

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledTimes(1)
    })
    await waitFor(() => {
      expect(screen.getByText(/Science · Plants/)).toBeInTheDocument()
    })
  })
})

describe('CheckInCapturePage — voice happy path', () => {
  beforeEach(() => {
    mockSubmit.mockResolvedValueOnce({
      checkin_id: 102,
      status: 'classified',
      classifications: [
        {
          artifact_type: 'voice',
          subject: 'English',
          topic: 'Poetry',
          deadline_iso: null,
          confidence: 0.7,
          corrected_by_kid: false,
        },
      ],
    })
  })

  it('records voice, sends it, and surfaces the AI chip', async () => {
    const user = userEvent.setup()

    // Mock MediaRecorder + getUserMedia for jsdom.
    const fakeStream = {
      getTracks: () => [{ stop: vi.fn() }],
    } as unknown as MediaStream
    Object.defineProperty(navigator, 'mediaDevices', {
      value: { getUserMedia: vi.fn().mockResolvedValue(fakeStream) },
      configurable: true,
    })

    class FakeRecorder {
      static isTypeSupported() {
        return true
      }
      state = 'inactive'
      ondataavailable: ((e: { data: Blob }) => void) | null = null
      onstop: (() => void) | null = null
      start() {
        this.state = 'recording'
      }
      stop() {
        this.state = 'inactive'
        this.ondataavailable?.({ data: new Blob(['voice'], { type: 'audio/webm' }) })
        this.onstop?.()
      }
    }
    ;(window as unknown as { MediaRecorder: typeof FakeRecorder }).MediaRecorder =
      FakeRecorder

    renderWithProviders(<CheckInCapturePage />, {
      initialEntries: ['/checkin/capture?mode=voice'],
    })

    const recordBtn = await screen.findByRole('button', { name: /record voice/i })
    await user.click(recordBtn)
    const stopBtn = await screen.findByRole('button', { name: /stop/i })
    await user.click(stopBtn)

    const sendBtn = await screen.findByRole('button', {
      name: /send to classbridge/i,
    })
    await user.click(sendBtn)

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledTimes(1)
    })
    await waitFor(() => {
      expect(screen.getByText(/English · Poetry/)).toBeInTheDocument()
    })
  })
})

describe('CheckInDonePage', () => {
  it('renders success ring, parents-preview list, and explicit close copy', async () => {
    // Render Done page directly with a state-shaped fake (router replays state)
    const { container } = renderWithProviders(<CheckInDonePage />, {
      initialEntries: [
        {
          pathname: '/checkin/done',
          state: {
            classifications: [
              {
                artifact_type: 'text',
                subject: 'Math',
                topic: 'Fractions',
                deadline_iso: '2026-05-01',
                confidence: 0.9,
                corrected_by_kid: false,
              },
            ],
            completed_seconds: 47,
          },
        } as unknown as string,
      ],
    })

    await waitFor(() => {
      expect(
        screen.getByText(/close the app\. have a snack\. you're good\./i),
      ).toBeInTheDocument()
    })

    expect(
      screen.getByText(/Tonight your parents will see:/i),
    ).toBeInTheDocument()
    const list = within(container).getByRole('list')
    expect(within(list).getByText(/Math — Fractions/)).toBeInTheDocument()
  })
})
