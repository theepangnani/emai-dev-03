import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock the PDF export helper so we can assert it was invoked without
// actually loading html2pdf.js in jsdom. Use importActual + spread so we
// only override `downloadAsPdf` — any other export the SUT happens to
// pick up (printElement, future helpers) keeps its real implementation
// (SUGG-8 mock-shadow hardening).
vi.mock('../../../utils/exportUtils', async () => {
  const actual = await vi.importActual<typeof import('../../../utils/exportUtils')>('../../../utils/exportUtils');
  return {
    ...actual,
    downloadAsPdf: vi.fn().mockResolvedValue(undefined),
  };
});

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

  it('clicking a practice-style chip routes through mode:"worksheet" — #4382', async () => {
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
        'data: {"type":"token","text":"1. Factor x^2-9."}\n\n',
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

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
    const secondBody = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(secondBody.mode).toBe('worksheet');
  });

  it('routes a chip with the bare word "problems" through worksheet mode (regex limitation, documented) — #4382', async () => {
    const fetchMock = vi.fn();
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"Here you go."}\n\n',
        'data: {"type":"chips","suggestions":["Walk me through inverse problem-solving steps"]}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"1. ..."}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const user = userEvent.setup();
    render(<TutorChat firstName="Sam" />);
    await user.type(screen.getByRole('textbox', { name: /message arc/i }), 'topic{Enter}');
    const chipList = await screen.findByRole('list', { name: /suggested follow-up/i });
    await user.click(within(chipList).getByText('Walk me through inverse problem-solving steps'));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
    // Documents that the boundary regex still matches the bare word "problem".
    // This is a known limitation — true intent detection would need an action verb.
    const secondBody = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(secondBody.mode).toBe('worksheet');
  });

  it('clicking a non-practice chip does NOT include a mode field — #4382', async () => {
    const fetchMock = vi.fn();
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"Here you go."}\n\n',
        'data: {"type":"chips","suggestions":["What are the historical origins?"]}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"Real-life uses include..."}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const user = userEvent.setup();
    render(<TutorChat firstName="Sam" />);

    const input = screen.getByRole('textbox', { name: /message arc/i });
    await user.type(input, 'Tell me about photosynthesis{Enter}');

    const chipList = await screen.findByRole('list', {
      name: /suggested follow-up/i,
    });
    const chip = within(chipList).getByText(
      'What are the historical origins?',
    );
    await user.click(chip);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
    const secondBody = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(secondBody).not.toHaveProperty('mode');
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

  it('clicking "Get the full version" twice quickly only fires ONE additional fetch (#4395 debounce)', async () => {
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
    // Double-click in quick succession before React re-renders.
    await user.click(fullBtn);
    await user.click(fullBtn);

    await waitFor(() => {
      expect(screen.getByText(/long structured/i)).toBeInTheDocument();
    });

    // 1 initial sendMessage + 1 requestFull = 2 total. Two clicks must NOT
    // fire 3 fetches.
    expect(fetchMock).toHaveBeenCalledTimes(2);
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

  it('attaches the PDF wrapper just below the viewport (NOT off-screen at -99999px, NOT opacity:0) — #4431/#4438', async () => {
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

    // Wrapper must be positioned just BELOW the viewport (top: 100vh) so the
    // browser performs full layout/paint and html2canvas can capture it, but
    // the user never sees it.
    const wrapper = vi.mocked(downloadAsPdf).mock.calls[0][0] as HTMLElement;
    expect(wrapper.style.top).toBe('100vh');
    expect(wrapper.style.left).toBe('0px');
    expect(wrapper.style.pointerEvents).toBe('none');
    // SUGG-2 — accessibility hygiene
    expect(wrapper.getAttribute('aria-hidden')).toBe('true');
    // Anti-regression — broken values must NOT be present.
    expect(wrapper.style.left).not.toBe('-99999px');
    expect(wrapper.style.opacity).not.toBe('0');  // opacity-inherit risk
  });

  it('invokes requestAnimationFrame BEFORE downloadAsPdf in the download flow — #4431/#4438', async () => {
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame');
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

    // Snapshot rAF call count BEFORE the download click — any prior calls
    // (auto-scroll, React internals) shouldn't influence the assertion.
    const rafCallsBeforeClick = rafSpy.mock.calls.length;

    const dl = await screen.findByRole('button', { name: /download pdf/i });
    await user.click(dl);

    await waitFor(() => {
      expect(downloadAsPdf).toHaveBeenCalledTimes(1);
    });

    // At least one NEW rAF call after the click (our explicit settle await).
    // Acknowledged limitation: React 19 batching / userEvent may also call
    // rAF post-click — this is a directional guard, not absolute proof. Pair
    // with the positioning test for full mutation coverage.
    expect(rafSpy.mock.calls.length).toBeGreaterThan(rafCallsBeforeClick);

    // Stronger ordering check: the FIRST downloadAsPdf invocation must come
    // AFTER at least one post-click rAF.
    const dlOrder = vi.mocked(downloadAsPdf).mock.invocationCallOrder[0];
    const postClickRafs = rafSpy.mock.invocationCallOrder.slice(rafCallsBeforeClick);
    expect(postClickRafs.some((order) => order < dlOrder)).toBe(true);

    rafSpy.mockRestore();
  });

  it('sanitizes HTML in assistant content before passing to PDF (IMPORTANT-3 XSS guard)', async () => {
    // Stream an assistant reply with a payload that would execute via inline HTML.
    mockFetchOk([
      'data: {"type":"token","text":"Some content <img src=x onerror=\\"window.__pwn=true\\"> end."}\n\n',
      'data: {"type":"done"}\n\n',
    ]);

    // Make sure the global is clean before the test.
    // @ts-expect-error -- test-only marker
    delete window.__pwn;

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

    // The wrapper element passed to downloadAsPdf MUST NOT contain the
    // dangerous attributes — DOMPurify strips onerror + drops the img,
    // or rewrites it. Either way, no event handler survives.
    const wrapper = vi.mocked(downloadAsPdf).mock.calls[0][0] as HTMLElement;
    expect(wrapper.innerHTML).not.toContain('onerror');
    expect(wrapper.innerHTML).not.toContain('window.__pwn');

    // Confirm sanitization didn't have a side effect (i.e. the inline
    // handler was never executed during DOM attach).
    // @ts-expect-error -- test-only marker
    expect(window.__pwn).toBeUndefined();
  });

  it('logs and swallows when downloadAsPdf rejects (IMPORTANT-1 catch path)', async () => {
    vi.mocked(downloadAsPdf).mockRejectedValueOnce(new Error('boom'));
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    mockFetchOk([
      'data: {"type":"token","text":"Some content."}\n\n',
      'data: {"type":"done"}\n\n',
    ]);

    const user = userEvent.setup();
    render(<TutorChat firstName="Maya" />);
    await user.type(screen.getByRole('textbox', { name: /message arc/i }), 'hello{Enter}');

    const dl = await screen.findByRole('button', { name: /download pdf/i });
    await user.click(dl);

    await waitFor(() => {
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining('PDF download failed'),
        expect.any(Error),
      );
    });

    warnSpy.mockRestore();
  });

  it('logs and swallows when marked.parse throws (IMPORTANT-5 catch path)', async () => {
    // Spy on marked.parse and force it to throw — exercises the new outer try/catch.
    const markedModule = await import('marked');
    const parseSpy = vi.spyOn(markedModule.marked, 'parse').mockImplementation(() => {
      throw new Error('marked-boom');
    });
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    mockFetchOk([
      'data: {"type":"token","text":"some content"}\n\n',
      'data: {"type":"done"}\n\n',
    ]);

    const user = userEvent.setup();
    render(<TutorChat firstName="Maya" />);
    await user.type(screen.getByRole('textbox', { name: /message arc/i }), 'hi{Enter}');

    const dl = await screen.findByRole('button', { name: /download pdf/i });
    await user.click(dl);

    await waitFor(() => {
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining('PDF download failed'),
        expect.any(Error),
      );
    });

    parseSpy.mockRestore();
    warnSpy.mockRestore();
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
