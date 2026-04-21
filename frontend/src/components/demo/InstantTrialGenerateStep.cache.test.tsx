import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { InstantTrialGenerateStep } from './InstantTrialGenerateStep';

const mockStreamGenerate = vi.fn();

vi.mock('../../api/demo', async () => {
  const actual = await vi.importActual<typeof import('../../api/demo')>('../../api/demo');
  return {
    ...actual,
    streamGenerate: (...args: unknown[]) => mockStreamGenerate(...args),
  };
});

function setupStreamMock(script: Array<{ event: 'token' | 'done' | 'error'; data: unknown }>) {
  mockStreamGenerate.mockImplementation((_jwt: string, _payload: unknown, cb: {
    onToken: (c: string) => void;
    onDone: (d: unknown) => void;
    onError: (m: string) => void;
  }) => {
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

beforeEach(() => {
  mockStreamGenerate.mockReset();
});

describe('InstantTrialGenerateStep — per-tab cache (#3762)', () => {
  it('preserves Ask thread when switching to Study Guide and back', async () => {
    const user = userEvent.setup();
    setupStreamMock([
      { event: 'token', data: 'Ask answer here.' },
      { event: 'done', data: { demo_type: 'ask', latency_ms: 1, input_tokens: 1, output_tokens: 1, cost_cents: 0 } },
    ]);

    render(
      <InstantTrialGenerateStep
        sessionJwt="jwt"
        waitlistPreviewPosition={10}
        onVerify={() => {}}
      />,
    );

    // Ask is a multi-turn chatbox — type then send.
    await user.type(screen.getByLabelText(/type your question/i), 'What is a cell?');
    await user.click(screen.getByRole('button', { name: /send question/i }));
    await waitFor(() => {
      expect(screen.getByText(/Ask answer here\./)).toBeInTheDocument();
    });

    // Switch to Study Guide — idle (no output), Generate button visible.
    // The Ask thread stays mounted-but-hidden so its state survives
    // tab switches (#3762 per-tab cache contract).
    await user.click(screen.getByRole('tab', { name: /study guide/i }));
    expect(screen.getByRole('button', { name: /generate study guide/i })).toBeInTheDocument();

    // Switch back to Ask — cached thread should still render.
    await user.click(screen.getByRole('tab', { name: /^ask/i }));
    await waitFor(() => {
      expect(screen.getByText(/Ask answer here\./)).toBeInTheDocument();
    });
  });

  it('clears all caches when the source changes', async () => {
    const user = userEvent.setup();
    setupStreamMock([
      { event: 'token', data: 'Ask answer here.' },
      { event: 'done', data: { demo_type: 'ask', latency_ms: 1, input_tokens: 1, output_tokens: 1, cost_cents: 0 } },
    ]);

    render(
      <InstantTrialGenerateStep
        sessionJwt="jwt"
        waitlistPreviewPosition={10}
        onVerify={() => {}}
      />,
    );

    await user.type(screen.getByLabelText(/type your question/i), 'What is a cell?');
    await user.click(screen.getByRole('button', { name: /send question/i }));
    await waitFor(() => {
      expect(screen.getByText(/Ask answer here\./)).toBeInTheDocument();
    });

    // Switch source from sample to paste — Ask thread must reset.
    const pasteLabel = screen.getByText(/paste your own text/i).closest('label')!;
    await user.click(pasteLabel);
    expect(screen.queryByText(/Ask answer here\./)).not.toBeInTheDocument();
    // Empty state starter chips return.
    expect(
      screen.getByRole('button', { name: /explain photosynthesis simply/i }),
    ).toBeInTheDocument();
  });

  it('renders the Flash Tutor short learning cycle when flash_tutor is done (#3786)', async () => {
    const user = userEvent.setup();
    const cards = JSON.stringify([
      { front: 'Q1', back: 'A1' },
      { front: 'Q2', back: 'A2' },
      { front: 'Q3', back: 'A3' },
    ]);
    setupStreamMock([
      { event: 'token', data: cards },
      { event: 'done', data: { demo_type: 'flash_tutor', latency_ms: 1, input_tokens: 1, output_tokens: 1, cost_cents: 0 } },
    ]);

    render(
      <InstantTrialGenerateStep
        sessionJwt="jwt"
        waitlistPreviewPosition={10}
        onVerify={() => {}}
      />,
    );

    await user.click(screen.getByRole('tab', { name: /flash tutor/i }));
    await user.click(screen.getByRole('button', { name: /generate flash tutor/i }));

    // Short learning cycle: mastery ring + first card front.
    expect(await screen.findByRole('progressbar', { name: /mastery/i })).toBeInTheDocument();
    expect(screen.getByText('Q1')).toBeInTheDocument();
  });

  it('renders GatedActionBar with download+save+more_flashcards actions on flash_tutor done', async () => {
    const user = userEvent.setup();
    const cards = JSON.stringify([{ front: 'Q', back: 'A' }]);
    setupStreamMock([
      { event: 'token', data: cards },
      { event: 'done', data: { demo_type: 'flash_tutor', latency_ms: 1, input_tokens: 1, output_tokens: 1, cost_cents: 0 } },
    ]);

    render(
      <InstantTrialGenerateStep
        sessionJwt="jwt"
        waitlistPreviewPosition={10}
        onVerify={() => {}}
      />,
    );

    await user.click(screen.getByRole('tab', { name: /flash tutor/i }));
    await user.click(screen.getByRole('button', { name: /generate flash tutor/i }));

    expect(await screen.findByRole('button', { name: /download pdf/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save to library/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /more flashcards/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /ask a follow-up/i })).toBeNull();
  });

  it('renders GatedActionBar with save+follow_up on ask done', async () => {
    const user = userEvent.setup();
    setupStreamMock([
      { event: 'token', data: 'An answer.' },
      { event: 'done', data: { demo_type: 'ask', latency_ms: 1, input_tokens: 1, output_tokens: 1, cost_cents: 0 } },
    ]);

    render(
      <InstantTrialGenerateStep
        sessionJwt="jwt"
        waitlistPreviewPosition={10}
        onVerify={() => {}}
      />,
    );

    await user.type(screen.getByLabelText(/type your question/i), 'What is a cell?');
    await user.click(screen.getByRole('button', { name: /send question/i }));
    expect(await screen.findByRole('button', { name: /save to library/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /ask a follow-up/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /download pdf/i })).toBeNull();
  });
});
