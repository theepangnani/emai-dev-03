import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { InstantTrialModal } from './InstantTrialModal';

/** Click a role card (label wrapping a pointer-events:none radio). */
function selectRole(roleLabel: RegExp) {
  const el = screen.getByText(roleLabel).closest('label');
  if (!el) throw new Error(`No role label found for ${roleLabel}`);
  fireEvent.click(el);
}

// --- Mocks ---------------------------------------------------------------

const mockCreateSession = vi.fn();
const mockStreamGenerate = vi.fn();

vi.mock('../../api/demo', async () => {
  const actual = await vi.importActual<typeof import('../../api/demo')>('../../api/demo');
  return {
    ...actual,
    createSession: (...args: unknown[]) => mockCreateSession(...args),
    streamGenerate: (...args: unknown[]) => mockStreamGenerate(...args),
  };
});

function setupStreamMock(script: Array<{ event: 'token' | 'done' | 'error'; data: unknown }>) {
  mockStreamGenerate.mockImplementation((_jwt: string, _payload: unknown, cb: {
    onToken: (c: string) => void;
    onDone: (d: unknown) => void;
    onError: (m: string) => void;
  }) => {
    // Synchronous-ish delivery — use microtasks so React can flush.
    Promise.resolve().then(() => {
      for (const ev of script) {
        if (ev.event === 'token') cb.onToken(ev.data as string);
        else if (ev.event === 'done') cb.onDone(ev.data as never);
        else cb.onError(ev.data as string);
      }
    });
    return new AbortController();
  });
}

async function fillAndSubmitStep1(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/full name/i), 'Ada Lovelace');
  await user.type(screen.getByLabelText(/^email$/i), 'ada@example.com');
  selectRole(/^Parent$/);
  await user.click(screen.getByRole('checkbox'));
  await user.click(screen.getByRole('button', { name: /start demo/i }));
}

beforeEach(() => {
  mockCreateSession.mockReset();
  mockStreamGenerate.mockReset();
});

// --- Tests --------------------------------------------------------------

describe('InstantTrialModal — aria and close', () => {
  it('renders with aria-modal and aria-labelledby', () => {
    render(<InstantTrialModal onClose={() => {}} />);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    const labelledBy = dialog.getAttribute('aria-labelledby');
    expect(labelledBy).toBeTruthy();
    expect(document.getElementById(labelledBy!)).toHaveTextContent(/try classbridge now/i);
  });

  it('has a hidden honeypot field named _hp', () => {
    const { container } = render(<InstantTrialModal onClose={() => {}} />);
    const hp = container.querySelector('input[name="_hp"]');
    expect(hp).not.toBeNull();
    expect(hp).toHaveClass('demo-honeypot');
    expect(hp).toHaveAttribute('aria-hidden', 'true');
  });

  it('calls onClose when the X button is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<InstantTrialModal onClose={onClose} />);
    await user.click(screen.getByRole('button', { name: /close demo/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it('closes on Escape key', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<InstantTrialModal onClose={onClose} />);
    await user.keyboard('{Escape}');
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});

describe('InstantTrialModal — step 1 validation', () => {
  it('blocks submit with inline errors when required fields are empty', async () => {
    const user = userEvent.setup();
    render(<InstantTrialModal onClose={() => {}} />);
    await user.click(screen.getByRole('button', { name: /start demo/i }));
    expect(await screen.findByText(/please enter your full name/i)).toBeInTheDocument();
    // New gentler copy (#3701)
    expect(screen.getByText(/looks off/i)).toBeInTheDocument();
    expect(screen.getByText(/please pick the role/i)).toBeInTheDocument();
    expect(screen.getByText(/please accept the consent/i)).toBeInTheDocument();
    expect(mockCreateSession).not.toHaveBeenCalled();
  });

  it('shows the under-13 notice when role=student', async () => {
    render(<InstantTrialModal onClose={() => {}} />);
    selectRole(/^Student$/);
    expect(screen.getByRole('note')).toHaveTextContent(/under 13/i);
  });
});

describe('InstantTrialModal — step 1 → step 2', () => {
  it('posts without the honeypot and advances to step 2', async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      session_jwt: 'jwt-123',
      verification_required: true,
      waitlist_preview_position: 347,
    });
    render(<InstantTrialModal onClose={() => {}} />);
    await fillAndSubmitStep1(user);

    await waitFor(() => {
      expect(mockCreateSession).toHaveBeenCalledTimes(1);
    });
    const payload = mockCreateSession.mock.calls[0][0];
    expect(payload).toMatchObject({
      full_name: 'Ada Lovelace',
      email: 'ada@example.com',
      role: 'parent',
      consent: true,
    });
    // Honeypot was untouched — wrapper must strip/exclude it.
    expect(payload._hp).toBeFalsy();

    // Step 2 surfaces the tablist
    expect(await screen.findByRole('tablist')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /ask/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /study guide/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /flash tutor/i })).toBeInTheDocument();
  });
});

describe('InstantTrialModal — step 2 SSE rendering', () => {
  it('renders streamed tokens and terminates on done', async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      session_jwt: 'jwt-abc',
      verification_required: true,
      waitlist_preview_position: 10,
    });
    setupStreamMock([
      { event: 'token', data: 'Hello ' },
      { event: 'token', data: 'world.' },
      { event: 'done', data: { demo_type: 'ask', latency_ms: 12, input_tokens: 1, output_tokens: 2, cost_cents: 0 } },
    ]);

    render(<InstantTrialModal onClose={() => {}} />);
    await fillAndSubmitStep1(user);
    await screen.findByRole('tablist');

    // Ask tab is now a multi-turn chatbox (§6.135.5, #3785) — type + send.
    await user.type(screen.getByLabelText(/type your question/i), 'What is a cell?');
    await user.click(screen.getByRole('button', { name: /send question/i }));

    await waitFor(() => {
      expect(screen.getByText(/Hello world\./)).toBeInTheDocument();
    });
    // Conversion card appears after done
    expect(await screen.findByRole('button', { name: /verify my email/i })).toBeInTheDocument();
  });

  it('shows an error when the SSE stream emits error', async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      session_jwt: 'jwt-err',
      verification_required: true,
      waitlist_preview_position: 5,
    });
    setupStreamMock([{ event: 'error', data: 'AI generation failed.' }]);

    render(<InstantTrialModal onClose={() => {}} />);
    await fillAndSubmitStep1(user);
    await screen.findByRole('tablist');
    await user.type(screen.getByLabelText(/type your question/i), 'What is a cell?');
    await user.click(screen.getByRole('button', { name: /send question/i }));

    const alert = await screen.findByRole('alert');
    expect(within(alert).getByText(/ai generation failed/i)).toBeInTheDocument();
  });
});

// --- Fast-follow tests (#3700) -----------------------------------------

describe('InstantTrialModal — SSE abort on unmount (#3700)', () => {
  it('aborts the in-flight SSE stream when the modal unmounts mid-stream', async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      session_jwt: 'jwt-unmount',
      verification_required: true,
      waitlist_preview_position: 1,
    });

    const aborted = { value: false };
    mockStreamGenerate.mockImplementation(() => {
      const controller = new AbortController();
      controller.signal.addEventListener('abort', () => {
        aborted.value = true;
      });
      return controller;
    });

    const { unmount } = render(<InstantTrialModal onClose={() => {}} />);
    await fillAndSubmitStep1(user);
    await screen.findByRole('tablist');
    await user.type(screen.getByLabelText(/type your question/i), 'Hi?');
    await user.click(screen.getByRole('button', { name: /send question/i }));

    expect(mockStreamGenerate).toHaveBeenCalled();
    unmount();
    expect(aborted.value).toBe(true);
  });
});

describe('InstantTrialModal — 10s timeout fallback (#3700)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('surfaces "Join the waitlist instead" link when createSession hangs > 10s', async () => {
    vi.useFakeTimers();
    try {
      mockCreateSession.mockImplementation(() => new Promise(() => {}));
      render(<InstantTrialModal onClose={() => {}} />);
      fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Ada' } });
      fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'a@b.com' } });
      fireEvent.click(screen.getByText('Parent').closest('label')!);
      fireEvent.click(screen.getByRole('checkbox'));
      fireEvent.click(screen.getByRole('button', { name: /start demo/i }));

      await act(async () => {
        vi.advanceTimersByTime(10_100);
      });

      expect(
        screen.getByRole('link', { name: /join the waitlist instead/i }),
      ).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('InstantTrialModal — per-tab cache (#3762)', () => {
  it('preserves Ask output when switching to Study Guide and back', async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      session_jwt: 'jwt-tabs',
      verification_required: true,
      waitlist_preview_position: 1,
    });
    setupStreamMock([
      { event: 'token', data: 'First output.' },
      { event: 'done', data: { demo_type: 'ask', latency_ms: 5, input_tokens: 1, output_tokens: 1, cost_cents: 0 } },
    ]);

    render(<InstantTrialModal onClose={() => {}} />);
    await fillAndSubmitStep1(user);
    await screen.findByRole('tablist');
    await user.type(screen.getByLabelText(/type your question/i), 'What is a cell?');
    await user.click(screen.getByRole('button', { name: /send question/i }));

    await waitFor(() => {
      expect(screen.getByText(/First output\./)).toBeInTheDocument();
    });

    // Switch to Study Guide tab — Study Guide is idle, Ask output is
    // kept mounted but hidden (preserves thread across tab switches).
    await user.click(screen.getByRole('tab', { name: /study guide/i }));
    expect(
      screen.getByRole('button', { name: /generate study guide/i }),
    ).toBeInTheDocument();

    // Switch back to Ask — cached thread still renders.
    await user.click(screen.getByRole('tab', { name: /^ask/i }));
    await waitFor(() => {
      expect(screen.getByText(/First output\./)).toBeInTheDocument();
    });
  });
});

describe('InstantTrialModal — maximize toggle (#3755)', () => {
  it('renders maximize button and toggles aria-label on click', async () => {
    const user = userEvent.setup();
    render(<InstantTrialModal onClose={() => {}} />);
    const btn = screen.getByRole('button', { name: /maximize/i });
    expect(btn).toHaveAttribute('aria-label', 'Maximize');
    await user.click(btn);
    expect(screen.getByRole('button', { name: /restore size/i })).toHaveAttribute(
      'aria-label',
      'Restore size',
    );
    await user.click(screen.getByRole('button', { name: /restore size/i }));
    expect(screen.getByRole('button', { name: /maximize/i })).toHaveAttribute(
      'aria-label',
      'Maximize',
    );
  });

  it('applies demo-modal--maximized class when toggled on', async () => {
    const user = userEvent.setup();
    render(<InstantTrialModal onClose={() => {}} />);
    const dialog = screen.getByRole('dialog');
    expect(dialog.classList.contains('demo-modal--maximized')).toBe(false);
    await user.click(screen.getByRole('button', { name: /maximize/i }));
    expect(dialog.classList.contains('demo-modal--maximized')).toBe(true);
    await user.click(screen.getByRole('button', { name: /restore size/i }));
    expect(dialog.classList.contains('demo-modal--maximized')).toBe(false);
  });
});

describe('InstantTrialModal — handleVerify renders notice (#3700)', () => {
  it('renders the verify-notice banner after the CTA is clicked', async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      session_jwt: 'jwt-verify',
      verification_required: true,
      waitlist_preview_position: 1,
    });
    setupStreamMock([
      { event: 'token', data: 'done' },
      { event: 'done', data: { demo_type: 'ask', latency_ms: 1, input_tokens: 1, output_tokens: 1, cost_cents: 0 } },
    ]);

    render(<InstantTrialModal onClose={() => {}} />);
    await fillAndSubmitStep1(user);
    await screen.findByRole('tablist');
    await user.type(screen.getByLabelText(/type your question/i), 'What is a cell?');
    await user.click(screen.getByRole('button', { name: /send question/i }));

    const verifyBtn = await screen.findByRole('button', { name: /verify my email/i });
    await user.click(verifyBtn);

    const status = await screen.findByRole('status');
    expect(status).toHaveTextContent(/verification link/i);
    expect(status).toHaveTextContent(/ada@example.com/);
  });
});
