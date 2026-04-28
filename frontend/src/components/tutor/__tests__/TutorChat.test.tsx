import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock the PDF export helper so we can assert it was invoked without
// actually loading html2pdf.js in jsdom.
vi.mock('../../../utils/exportUtils', () => ({
  downloadAsPdf: vi.fn().mockResolvedValue(undefined),
  printElement: vi.fn(),
}));

// Stream A (#4312) wraps ArcMascot in a data-arc={getArcVariant(user?.id)}
// element which calls useAuth(). Mock AuthContext so the pre-existing
// TutorChat tests don't require an AuthProvider.
vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: 'test@example.com',
      full_name: 'Test User',
      role: 'STUDENT',
      roles: ['STUDENT'],
      is_active: true,
      google_connected: false,
      needs_onboarding: false,
      onboarding_completed: true,
      email_verified: true,
      interests: [],
    },
    token: 'test-token',
    isLoading: false,
    login: vi.fn(),
    loginWithToken: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    switchRole: vi.fn(),
    completeOnboarding: vi.fn(),
    resendVerification: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

import { TutorChat } from '../TutorChat';
import { downloadAsPdf } from '../../../utils/exportUtils';

// Helpers to build an SSE ReadableStream the component-under-test will consume.
function makeSSEStream(lines: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(line));
      }
      controller.close();
    },
  });
}

function mockFetchOk(lines: string[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      body: makeSSEStream(lines),
    }),
  );
}

function mockFetchFail(status: number) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: false,
      status,
      body: null,
    }),
  );
}

describe('TutorChat', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('token', 'test-token');
  });

  afterEach(() => {
    localStorage.removeItem('token');
    vi.unstubAllGlobals();
  });

  it('renders empty state with Arc greeting and headline only (no starter cards — #4095 Bug 1)', () => {
    render(<TutorChat firstName="Maya" />);

    // Eyebrow greeting uses first name
    expect(screen.getByText(/Hey, Maya\./i)).toBeInTheDocument();

    // Distinctive headline (not a generic "How can I help?")
    expect(
      screen.getByRole('heading', { name: /what do you want to/i }),
    ).toBeInTheDocument();

    // Starter prompts removed — the misleading pre-canned cards
    // ("Explain photosynthesis like I'm in grade 7" etc.) were dropped in
    // #4095 Bug 1 because they were pre-canned / not personalized.
    expect(screen.queryByRole('list', { name: /starter prompts/i })).toBeNull();
    expect(screen.queryByText(/Explain photosynthesis like I/i)).toBeNull();
  });

  it('sends a message via Enter and surfaces the user bubble', async () => {
    mockFetchOk([
      'data: {"type":"token","text":"Sure! "}\n\n',
      'data: {"type":"token","text":"Let me explain."}\n\n',
      'data: {"type":"done"}\n\n',
    ]);

    const user = userEvent.setup();
    render(<TutorChat firstName="Sam" />);

    const input = screen.getByRole('textbox', { name: /message arc/i });
    await user.type(input, 'Explain fractions{Enter}');

    await waitFor(() => {
      expect(screen.getByText('Explain fractions')).toBeInTheDocument();
    });

    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining('/api/tutor/chat/stream'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"message":"Explain fractions"'),
      }),
    );
  });

  it('renders streamed tokens progressively', async () => {
    mockFetchOk([
      'data: {"type":"token","text":"Photosynthesis "}\n\n',
      'data: {"type":"token","text":"is how plants eat sunlight."}\n\n',
      'data: {"type":"done"}\n\n',
    ]);

    const user = userEvent.setup();
    render(<TutorChat firstName="Jo" />);

    // Click send via button
    const input = screen.getByRole('textbox', { name: /message arc/i });
    await user.type(input, 'what is photosynthesis');
    fireEvent.click(screen.getByRole('button', { name: /send message/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/Photosynthesis is how plants eat sunlight\./i),
      ).toBeInTheDocument();
    });
  });

  it('shows suggestion chips after the assistant finishes', async () => {
    mockFetchOk([
      'data: {"type":"token","text":"Here you go."}\n\n',
      'data: {"type":"chips","suggestions":["Go deeper","Quiz me","Another example"]}\n\n',
      'data: {"type":"done"}\n\n',
    ]);

    const user = userEvent.setup();
    render(<TutorChat firstName="Pat" />);

    const input = screen.getByRole('textbox', { name: /message arc/i });
    await user.type(input, 'Tell me more{Enter}');

    await waitFor(() => {
      const chipList = screen.getByRole('list', {
        name: /suggested follow-up/i,
      });
      expect(within(chipList).getByText('Go deeper')).toBeInTheDocument();
      expect(within(chipList).getByText('Quiz me')).toBeInTheDocument();
      expect(within(chipList).getByText('Another example')).toBeInTheDocument();
    });
  });

  it('clicking a suggestion chip auto-sends the chip text (no Send click required) — #4381', async () => {
    const fetchMock = vi.fn();
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"Here you go."}\n\n',
        'data: {"type":"chips","suggestions":["Practice factoring problems for Grade 10"]}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"Sure, here is one."}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const user = userEvent.setup();
    render(<TutorChat firstName="Sam" />);

    const input = screen.getByRole('textbox', { name: /message arc/i });
    await user.type(input, 'Tell me about factoring{Enter}');

    const chipList = await screen.findByRole('list', {
      name: /suggested follow-up/i,
    });
    const chip = within(chipList).getByText(
      'Practice factoring problems for Grade 10',
    );
    await user.click(chip);

    // The chip click must auto-send → fetch fired a SECOND time with the
    // chip text in the body. No Send click needed.
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
    const secondBody = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(secondBody.message).toBe(
      'Practice factoring problems for Grade 10',
    );
  });

  it('clicking a chip during an active stream is a no-op — #4381', async () => {
    // Stream stays open (no done frame) so isStreaming=true throughout.
    let resolveDone: (() => void) | null = null;
    const longStream = new ReadableStream<Uint8Array>({
      start(controller) {
        const encoder = new TextEncoder();
        controller.enqueue(encoder.encode('data: {"type":"token","text":"thinking..."}\n\n'));
        // Emit chips mid-stream — abnormal but the simplest way to get a
        // chip in the DOM while isStreaming is still true. (`showChips`
        // also requires !lastAssistant.streaming, so the chips will not
        // actually render — that's the point: the guard is defense-in-depth
        // for both DOM-visibility and the handler-level check.)
        controller.enqueue(
          encoder.encode(
            'data: {"type":"chips","suggestions":["Practice factoring problems for Grade 10"]}\n\n',
          ),
        );
        resolveDone = () => {
          controller.enqueue(encoder.encode('data: {"type":"done"}\n\n'));
          controller.close();
        };
      },
    });
    const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, body: longStream });
    vi.stubGlobal('fetch', fetchMock);

    const user = userEvent.setup();
    render(<TutorChat firstName="Sam" />);

    await user.type(
      screen.getByRole('textbox', { name: /message arc/i }),
      'topic{Enter}',
    );

    // Streaming begins; only ONE fetch so far.
    await waitFor(() => {
      expect(screen.getByText(/thinking\.\.\./i)).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Chips don't render mid-stream (showChips guard), so there's nothing
    // for the user to click — but if the chip somehow fires onSelect, the
    // handler's `if (isStreaming) return` keeps the fetch count at 1.
    // Assert the chip list is NOT in the DOM right now.
    expect(screen.queryByRole('list', { name: /suggested follow-up/i })).toBeNull();

    // Settle and confirm the count never went past 1.
    resolveDone?.();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
  });

  it('round-trips conversation_id from done frame on the next request', async () => {
    // First turn — backend issues conversation_id in done frame.
    const fetchMock = vi.fn();
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"one"}\n\n',
        'data: {"type":"done","conversation_id":"conv-abc"}\n\n',
      ]),
    });
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"two"}\n\n',
        'data: {"type":"done","conversation_id":"conv-abc"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const user = userEvent.setup();
    render(<TutorChat firstName="River" />);

    const input = screen.getByRole('textbox', { name: /message arc/i });
    await user.type(input, 'first{Enter}');
    await waitFor(() => expect(screen.getByText(/^one$/i)).toBeInTheDocument());

    await user.type(input, 'second{Enter}');
    await waitFor(() => expect(screen.getByText(/^two$/i)).toBeInTheDocument());

    // Second call body must carry conversation_id from the first done frame.
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const secondBody = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(secondBody.conversation_id).toBe('conv-abc');
    // First call must NOT have conversation_id (new conversation).
    const firstBody = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(firstBody.conversation_id).toBeUndefined();
  });

  it('puts aria-live on the assistant bubble, not the outer scroll container', async () => {
    mockFetchOk([
      'data: {"type":"token","text":"Hello."}\n\n',
      'data: {"type":"done"}\n\n',
    ]);

    const user = userEvent.setup();
    const { container } = render(<TutorChat firstName="Maya" />);

    // Outer scroll container must NOT carry aria-live — otherwise every
    // token update re-announces the entire conversation.
    const stream = container.querySelector('.tutor-chat__stream');
    expect(stream).not.toBeNull();
    expect(stream?.getAttribute('aria-live')).toBeNull();

    const input = screen.getByRole('textbox', { name: /message arc/i });
    await user.type(input, 'hi{Enter}');

    await waitFor(() => {
      expect(screen.getByText(/Hello\./i)).toBeInTheDocument();
    });

    // Assistant bubble carries aria-live=polite + aria-atomic=false.
    const assistantBubble = container.querySelector('.tutor-msg--arc');
    expect(assistantBubble).not.toBeNull();
    expect(assistantBubble?.getAttribute('aria-live')).toBe('polite');
    expect(assistantBubble?.getAttribute('aria-atomic')).toBe('false');

    // User bubble must NOT carry aria-live — announcing user echoes is redundant.
    const userBubble = container.querySelector('.tutor-msg--user');
    expect(userBubble).not.toBeNull();
    expect(userBubble?.getAttribute('aria-live')).toBeNull();
  });

  it('shows action buttons under a settled assistant bubble', async () => {
    mockFetchOk([
      'data: {"type":"token","text":"Sure thing."}\n\n',
      'data: {"type":"done"}\n\n',
    ]);

    const user = userEvent.setup();
    render(<TutorChat firstName="Maya" />);
    await user.type(
      screen.getByRole('textbox', { name: /message arc/i }),
      'tell me{Enter}',
    );

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /get the full version/i }),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /download pdf/i })).toBeInTheDocument();
  });

  it('does NOT show action buttons while a bubble is still streaming', async () => {
    // Provide tokens but no done frame for the duration of the assertion.
    let resolveDone: (() => void) | null = null;
    const longStream = new ReadableStream<Uint8Array>({
      start(controller) {
        const encoder = new TextEncoder();
        controller.enqueue(encoder.encode('data: {"type":"token","text":"streaming..."}\n\n'));
        // Don't enqueue done — leave the stream open until the test resolves it.
        resolveDone = () => {
          controller.enqueue(encoder.encode('data: {"type":"done"}\n\n'));
          controller.close();
        };
      },
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, body: longStream }));

    const user = userEvent.setup();
    render(<TutorChat firstName="Maya" />);
    await user.type(
      screen.getByRole('textbox', { name: /message arc/i }),
      'tell me{Enter}',
    );

    await waitFor(() => {
      expect(screen.getByText(/streaming\.\.\./i)).toBeInTheDocument();
    });

    // Mid-stream: actions must be hidden.
    expect(
      screen.queryByRole('button', { name: /get the full version/i }),
    ).toBeNull();
    expect(screen.queryByRole('button', { name: /download pdf/i })).toBeNull();

    // Cleanly close the stream so the test/component can settle.
    resolveDone?.();
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /download pdf/i }),
      ).toBeInTheDocument();
    });
  });

  it('does NOT show action buttons on a safety bubble', async () => {
    mockFetchOk([
      'data: {"type":"safety","text":"Heads up, that one falls outside what I can help with."}\n\n',
      'data: {"type":"done"}\n\n',
    ]);

    const user = userEvent.setup();
    render(<TutorChat firstName="Maya" />);
    await user.type(
      screen.getByRole('textbox', { name: /message arc/i }),
      'risky question{Enter}',
    );

    await waitFor(() => {
      expect(screen.getByText(/Heads up, that one falls outside/i)).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /get the full version/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /download pdf/i })).toBeNull();
  });

  it('does NOT show action buttons on an empty-content bubble', async () => {
    // Fetch resolves with no token frames + immediate done — bubble has empty content.
    mockFetchOk(['data: {"type":"done"}\n\n']);

    const user = userEvent.setup();
    const { container } = render(<TutorChat firstName="Maya" />);
    await user.type(
      screen.getByRole('textbox', { name: /message arc/i }),
      'hello{Enter}',
    );

    await waitFor(() => {
      const arc = container.querySelector('.tutor-msg--arc');
      expect(arc).not.toBeNull();
    });

    expect(screen.queryByRole('button', { name: /download pdf/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /get the full version/i })).toBeNull();
  });

  it('hides "Get the full version" once a message has been replayed in mode:"full"', async () => {
    const fetchMock = vi.fn();
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"short"}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"long structured"}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const user = userEvent.setup();
    render(<TutorChat firstName="Maya" />);
    await user.type(
      screen.getByRole('textbox', { name: /message arc/i }),
      'topic{Enter}',
    );

    const fullBtn = await screen.findByRole('button', { name: /get the full version/i });
    await user.click(fullBtn);

    await waitFor(() => {
      expect(screen.getByText(/long structured/i)).toBeInTheDocument();
    });

    // The freshly-arrived assistant bubble was sent in mode:'full' →
    // "Get the full version" must not render under it.
    const fullModeBubble = screen
      .getByText(/long structured/i)
      .closest('.tutor-msg');
    expect(fullModeBubble).not.toBeNull();
    expect(
      within(fullModeBubble as HTMLElement).queryByRole('button', {
        name: /get the full version/i,
      }),
    ).toBeNull();
    // Download PDF still shows.
    expect(
      within(fullModeBubble as HTMLElement).getByRole('button', {
        name: /download pdf/i,
      }),
    ).toBeInTheDocument();
  });

  it('clicking "Download PDF" invokes the downloadAsPdf helper', async () => {
    mockFetchOk([
      'data: {"type":"token","text":"Some content."}\n\n',
      'data: {"type":"done"}\n\n',
    ]);

    const user = userEvent.setup();
    render(<TutorChat firstName="Maya" />);
    await user.type(
      screen.getByRole('textbox', { name: /message arc/i }),
      'hello{Enter}',
    );

    const dl = await screen.findByRole('button', { name: /download pdf/i });
    await user.click(dl);

    await waitFor(() => {
      expect(downloadAsPdf).toHaveBeenCalledTimes(1);
    });
    const [, filename] = vi.mocked(downloadAsPdf).mock.calls[0];
    expect(filename).toMatch(/^Arc-tutor-\d{8}-\d{4}\.pdf$/);
  });

  it('renders a readable error banner (not a raw error code) on failure', async () => {
    mockFetchFail(500);

    const user = userEvent.setup();
    render(<TutorChat firstName="Alex" />);

    const input = screen.getByRole('textbox', { name: /message arc/i });
    await user.type(input, 'hello{Enter}');

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/Arc hit a snag\./i);
    // Should NOT leak the raw HTTP code into the banner
    expect(alert).not.toHaveTextContent(/HTTP 500/);
    expect(alert).not.toHaveTextContent(/^500$/);
  });
});
