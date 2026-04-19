import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { InstantTrialModal } from './InstantTrialModal';

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
  await user.click(screen.getByRole('radio', { name: /parent/i }));
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
    expect(screen.getByText(/please enter a valid email/i)).toBeInTheDocument();
    expect(screen.getByText(/please pick the role/i)).toBeInTheDocument();
    expect(screen.getByText(/please accept the consent/i)).toBeInTheDocument();
    expect(mockCreateSession).not.toHaveBeenCalled();
  });

  it('shows the under-13 notice when role=student', async () => {
    const user = userEvent.setup();
    render(<InstantTrialModal onClose={() => {}} />);
    await user.click(screen.getByRole('radio', { name: /student/i }));
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

    await user.click(screen.getByRole('button', { name: /generate ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/Hello world\./)).toBeInTheDocument();
    });
    // Watermark present
    expect(screen.getByText('Demo sample')).toBeInTheDocument();
    // Conversion card appears after done
    expect(await screen.findByRole('button', { name: /verify my email/i })).toBeInTheDocument();
    // Copy button is shown (aria-label covers full intent)
    expect(screen.getByRole('button', { name: /copy demo output/i })).toBeInTheDocument();
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
    await user.click(screen.getByRole('button', { name: /generate ask/i }));

    const alert = await screen.findByRole('alert');
    expect(within(alert).getByText(/ai generation failed/i)).toBeInTheDocument();
  });
});
