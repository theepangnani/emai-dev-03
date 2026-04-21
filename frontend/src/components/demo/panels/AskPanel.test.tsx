import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AskPanel } from './AskPanel';
import type { DemoGameActions } from '../gamification/useDemoGameState';

const mockStreamGenerate = vi.fn();

vi.mock('../../../api/demo', async () => {
  const actual = await vi.importActual<typeof import('../../../api/demo')>(
    '../../../api/demo',
  );
  return {
    ...actual,
    streamGenerate: (...args: unknown[]) => mockStreamGenerate(...args),
  };
});

interface StreamCallbacks {
  onToken: (c: string) => void;
  onDone: (d: unknown) => void;
  onError: (m: string) => void;
}

function setupStreamMock(
  script: Array<{ event: 'token' | 'done' | 'error'; data: unknown }>,
) {
  mockStreamGenerate.mockImplementation(
    (_jwt: string, _payload: unknown, cb: StreamCallbacks) => {
      Promise.resolve().then(() => {
        for (const ev of script) {
          if (ev.event === 'token') cb.onToken(ev.data as string);
          else if (ev.event === 'done') cb.onDone(ev.data as never);
          else cb.onError(ev.data as string);
        }
      });
      return new AbortController();
    },
  );
}

function stubGameActions(): DemoGameActions {
  return {
    awardXP: vi.fn(),
    markQuest: vi.fn(),
    incrementStreak: vi.fn(),
    resetStreak: vi.fn(),
    earnAchievement: vi.fn(),
    resetAll: vi.fn(),
  };
}

beforeEach(() => {
  mockStreamGenerate.mockReset();
});

describe('AskPanel — empty state + starter chips', () => {
  it('renders the empty state with 3 starter chips', () => {
    render(<AskPanel sessionJwt="jwt" />);
    expect(screen.getByText(/ask me anything/i)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /explain photosynthesis simply/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /what caused world war i/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /how does gravity work/i }),
    ).toBeInTheDocument();
  });

  it('starter-chip click triggers a generation with the chip text as the question', async () => {
    const user = userEvent.setup();
    setupStreamMock([
      { event: 'token', data: 'Photosynthesis is…' },
      {
        event: 'done',
        data: {
          demo_type: 'ask',
          latency_ms: 1,
          input_tokens: 1,
          output_tokens: 1,
          cost_cents: 0,
        },
      },
    ]);

    render(<AskPanel sessionJwt="jwt" />);
    await user.click(
      screen.getByRole('button', { name: /explain photosynthesis simply/i }),
    );

    expect(mockStreamGenerate).toHaveBeenCalledTimes(1);
    const call = mockStreamGenerate.mock.calls[0];
    expect(call[0]).toBe('jwt');
    expect(call[1]).toMatchObject({
      demo_type: 'ask',
      question: 'Explain photosynthesis simply',
    });
    expect(call[1].history).toBeUndefined();

    await waitFor(() => {
      expect(screen.getByText(/photosynthesis is/i)).toBeInTheDocument();
    });
  });
});

describe('AskPanel — multi-turn', () => {
  it('sends prior turns as history on subsequent sends', async () => {
    const user = userEvent.setup();
    setupStreamMock([
      { event: 'token', data: 'First answer.' },
      {
        event: 'done',
        data: {
          demo_type: 'ask',
          latency_ms: 1,
          input_tokens: 1,
          output_tokens: 1,
          cost_cents: 0,
        },
      },
    ]);
    render(<AskPanel sessionJwt="jwt" />);

    const input = screen.getByLabelText(/type your question/i);
    await user.type(input, 'Q1');
    await user.click(screen.getByRole('button', { name: /send question/i }));
    await waitFor(() => {
      expect(screen.getByText(/first answer/i)).toBeInTheDocument();
    });

    // Second turn — history should contain both prior turns.
    setupStreamMock([
      { event: 'token', data: 'Second answer.' },
      {
        event: 'done',
        data: {
          demo_type: 'ask',
          latency_ms: 1,
          input_tokens: 1,
          output_tokens: 1,
          cost_cents: 0,
        },
      },
    ]);
    await user.type(input, 'Q2');
    await user.click(screen.getByRole('button', { name: /send question/i }));

    await waitFor(() => {
      expect(screen.getByText(/second answer/i)).toBeInTheDocument();
    });
    const lastCall = mockStreamGenerate.mock.calls.at(-1)!;
    expect(lastCall[1].history).toEqual([
      { role: 'user', content: 'Q1' },
      { role: 'assistant', content: 'First answer.' },
    ]);
    expect(lastCall[1].question).toBe('Q2');
  });

  it('caps at 3 assistant turns and shows the waitlist upsell', async () => {
    const user = userEvent.setup();

    function queueOnce(text: string) {
      setupStreamMock([
        { event: 'token', data: text },
        {
          event: 'done',
          data: {
            demo_type: 'ask',
            latency_ms: 1,
            input_tokens: 1,
            output_tokens: 1,
            cost_cents: 0,
          },
        },
      ]);
    }

    render(<AskPanel sessionJwt="jwt" />);
    const input = screen.getByLabelText(/type your question/i);
    const send = () =>
      screen.getByRole('button', { name: /send question/i });

    queueOnce('Turn 1 answer.');
    await user.type(input, 'q1');
    await user.click(send());
    await waitFor(() => {
      expect(screen.getByText(/turn 1 answer/i)).toBeInTheDocument();
    });

    queueOnce('Turn 2 answer.');
    await user.type(input, 'q2');
    await user.click(send());
    await waitFor(() => {
      expect(screen.getByText(/turn 2 answer/i)).toBeInTheDocument();
    });

    queueOnce('Turn 3 answer.');
    await user.type(input, 'q3');
    await user.click(send());
    await waitFor(() => {
      expect(screen.getByText(/turn 3 answer/i)).toBeInTheDocument();
    });

    // Cap reached: input + send disabled; upsell visible.
    expect(input).toBeDisabled();
    expect(send()).toBeDisabled();
    expect(input).toHaveAttribute(
      'placeholder',
      'Demo limit reached — continue on the waitlist',
    );
    expect(
      screen.getByText(/keep the conversation going — join the waitlist/i),
    ).toBeInTheDocument();
  });

  it('turn meter advances with each completed turn', async () => {
    const user = userEvent.setup();
    setupStreamMock([
      { event: 'token', data: 'done' },
      {
        event: 'done',
        data: {
          demo_type: 'ask',
          latency_ms: 1,
          input_tokens: 1,
          output_tokens: 1,
          cost_cents: 0,
        },
      },
    ]);
    render(<AskPanel sessionJwt="jwt" />);

    expect(
      screen.getByRole('group', { name: /0 of 3 free turns used/i }),
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText(/type your question/i), 'Hi?');
    await user.click(screen.getByRole('button', { name: /send question/i }));

    await waitFor(() => {
      expect(
        screen.getByRole('group', { name: /1 of 3 free turns used/i }),
      ).toBeInTheDocument();
    });
  });
});

describe('AskPanel — markdown streaming', () => {
  it('preserves bold markdown during streaming', async () => {
    const user = userEvent.setup();
    setupStreamMock([
      { event: 'token', data: 'Gravity is **really strong**.' },
      {
        event: 'done',
        data: {
          demo_type: 'ask',
          latency_ms: 1,
          input_tokens: 1,
          output_tokens: 1,
          cost_cents: 0,
        },
      },
    ]);
    render(<AskPanel sessionJwt="jwt" />);

    await user.type(screen.getByLabelText(/type your question/i), 'Gravity?');
    await user.click(screen.getByRole('button', { name: /send question/i }));

    // <strong> rendered from markdown **...**
    await waitFor(() => {
      expect(screen.getByText(/really strong/i).tagName.toLowerCase()).toBe(
        'strong',
      );
    });
  });
});

describe('AskPanel — gamification hooks', () => {
  it('awards 15 XP + marks ask quest + first-spark on turn 1', async () => {
    const user = userEvent.setup();
    const actions = stubGameActions();
    setupStreamMock([
      { event: 'token', data: 'ok' },
      {
        event: 'done',
        data: {
          demo_type: 'ask',
          latency_ms: 1,
          input_tokens: 1,
          output_tokens: 1,
          cost_cents: 0,
        },
      },
    ]);

    render(
      <AskPanel
        sessionJwt="jwt"
        gameActions={actions}
        isFirstXpOfSession
      />,
    );
    await user.type(screen.getByLabelText(/type your question/i), 'Hi?');
    await user.click(screen.getByRole('button', { name: /send question/i }));

    await waitFor(() => {
      expect(actions.awardXP).toHaveBeenCalledWith(15);
    });
    expect(actions.markQuest).toHaveBeenCalledWith('ask');
    expect(actions.earnAchievement).toHaveBeenCalledWith('first-spark');
  });

  it('awards 10 XP on subsequent turns and does not re-award first-spark', async () => {
    const user = userEvent.setup();
    const actions = stubGameActions();
    setupStreamMock([
      { event: 'token', data: 'ok1' },
      {
        event: 'done',
        data: {
          demo_type: 'ask',
          latency_ms: 1,
          input_tokens: 1,
          output_tokens: 1,
          cost_cents: 0,
        },
      },
    ]);

    const { rerender } = render(
      <AskPanel
        sessionJwt="jwt"
        gameActions={actions}
        isFirstXpOfSession
      />,
    );
    await user.type(screen.getByLabelText(/type your question/i), 'q1');
    await user.click(screen.getByRole('button', { name: /send question/i }));
    await waitFor(() => {
      expect(actions.awardXP).toHaveBeenCalledWith(15);
    });

    // Second turn — XP is no longer "first of session".
    setupStreamMock([
      { event: 'token', data: 'ok2' },
      {
        event: 'done',
        data: {
          demo_type: 'ask',
          latency_ms: 1,
          input_tokens: 1,
          output_tokens: 1,
          cost_cents: 0,
        },
      },
    ]);
    rerender(
      <AskPanel
        sessionJwt="jwt"
        gameActions={actions}
        isFirstXpOfSession={false}
      />,
    );
    await user.type(screen.getByLabelText(/type your question/i), 'q2');
    await user.click(screen.getByRole('button', { name: /send question/i }));

    await waitFor(() => {
      expect(actions.awardXP).toHaveBeenCalledWith(10);
    });
    expect(actions.earnAchievement).toHaveBeenCalledTimes(1);
  });
});

describe('AskPanel — resetKey', () => {
  it('clears the thread when resetKey changes', async () => {
    const user = userEvent.setup();
    setupStreamMock([
      { event: 'token', data: 'stale answer' },
      {
        event: 'done',
        data: {
          demo_type: 'ask',
          latency_ms: 1,
          input_tokens: 1,
          output_tokens: 1,
          cost_cents: 0,
        },
      },
    ]);
    const { rerender } = render(<AskPanel sessionJwt="jwt" resetKey={0} />);

    await user.type(screen.getByLabelText(/type your question/i), 'q');
    await user.click(screen.getByRole('button', { name: /send question/i }));
    await waitFor(() => {
      expect(screen.getByText(/stale answer/i)).toBeInTheDocument();
    });

    rerender(<AskPanel sessionJwt="jwt" resetKey={1} />);
    expect(screen.queryByText(/stale answer/i)).not.toBeInTheDocument();
    expect(screen.getByText(/ask me anything/i)).toBeInTheDocument();
  });
});
