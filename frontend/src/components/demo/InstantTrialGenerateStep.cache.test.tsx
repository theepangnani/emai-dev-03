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
  it('preserves Ask output when switching to Study Guide and back', async () => {
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

    await user.click(screen.getByRole('button', { name: /generate ask/i }));
    await waitFor(() => {
      expect(screen.getByText(/Ask answer here\./)).toBeInTheDocument();
    });

    // Switch to Study Guide — idle (no output), Generate button visible.
    await user.click(screen.getByRole('tab', { name: /study guide/i }));
    expect(screen.queryByText(/Ask answer here\./)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /generate study guide/i })).toBeInTheDocument();

    // Switch back to Ask — cached output should still render.
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

    await user.click(screen.getByRole('button', { name: /generate ask/i }));
    await waitFor(() => {
      expect(screen.getByText(/Ask answer here\./)).toBeInTheDocument();
    });

    // Switch source from sample to paste — cache must clear.
    const pasteLabel = screen.getByText(/paste your own text/i).closest('label')!;
    await user.click(pasteLabel);
    expect(screen.queryByText(/Ask answer here\./)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /generate ask/i })).toBeInTheDocument();
  });

  it('preserves the Ask question when source changes', async () => {
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

    const questionInput = screen.getByLabelText(/your question/i) as HTMLInputElement;
    await user.clear(questionInput);
    await user.type(questionInput, 'What is photosynthesis?');
    expect(questionInput.value).toBe('What is photosynthesis?');

    // Switch source from sample to paste — cache clears but question must persist.
    const pasteLabel = screen.getByText(/paste your own text/i).closest('label')!;
    await user.click(pasteLabel);

    expect((screen.getByLabelText(/your question/i) as HTMLInputElement).value).toBe(
      'What is photosynthesis?',
    );
  });

  it('renders FlashcardDeck when flash_tutor is done', async () => {
    const user = userEvent.setup();
    const cards = JSON.stringify([
      { front: 'Q1', back: 'A1' },
      { front: 'Q2', back: 'A2' },
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

    const region = await screen.findByRole('region', { name: /flashcards/i });
    expect(region).toBeInTheDocument();
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

    await user.click(screen.getByRole('button', { name: /generate ask/i }));
    expect(await screen.findByRole('button', { name: /save to library/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /ask a follow-up/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /download pdf/i })).toBeNull();
  });
});
