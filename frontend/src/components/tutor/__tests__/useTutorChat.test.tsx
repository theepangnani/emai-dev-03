import { renderHook, act } from '@testing-library/react';
import { useTutorChat } from '../useTutorChat';

// Helper to build a ReadableStream from SSE lines.
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

describe('useTutorChat', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('token', 'test-token');
  });

  afterEach(() => {
    localStorage.removeItem('token');
    vi.unstubAllGlobals();
  });

  it('exposes a stable `sendMessage` reference across re-renders', () => {
    const { result, rerender } = renderHook(() => useTutorChat());

    const first = result.current.sendMessage;
    rerender();
    const second = result.current.sendMessage;
    rerender();
    const third = result.current.sendMessage;
    rerender();
    const fourth = result.current.sendMessage;

    // All four references must point to the SAME function. If any rerender
    // spawned a new closure, consumers that put sendMessage in a
    // useEffect/useMemo dep list would churn.
    expect(first).toBe(second);
    expect(second).toBe(third);
    expect(third).toBe(fourth);
  });

  it('ignores token (and chips/safety) frames that arrive after done', async () => {
    // A misbehaving backend / network-buffered flush can deliver a token
    // AFTER the terminal `done` frame. The hook must drop those frames
    // instead of re-appending text or flipping `streaming` back to true.
    mockFetchOk([
      'data: {"type":"token","text":"real "}\n\n',
      'data: {"type":"token","text":"content"}\n\n',
      'data: {"type":"done"}\n\n',
      // Stragglers after the terminal frame — must all be ignored.
      'data: {"type":"token","text":" LATE"}\n\n',
      'data: {"type":"chips","suggestions":["late chip"]}\n\n',
    ]);

    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { result } = renderHook(() => useTutorChat());

    await act(async () => {
      await result.current.sendMessage('test');
    });

    const assistant = result.current.messages.find((m) => m.role === 'assistant');
    expect(assistant).toBeDefined();
    // Late token must NOT have been appended.
    expect(assistant?.content).toBe('real content');
    // Late chips must NOT have overwritten the bubble's suggestions.
    expect(assistant?.suggestions ?? []).toEqual([]);
    // Stream should be settled — late tokens must not re-flip streaming.
    expect(assistant?.streaming).toBe(false);
    expect(result.current.isStreaming).toBe(false);

    // At least one warn was logged for the dropped late frames.
    expect(warnSpy).toHaveBeenCalled();
    warnSpy.mockRestore();
  });

  it('still sees the latest messages snapshot even though sendMessage is stable', async () => {
    mockFetchOk([
      'data: {"type":"token","text":"hi"}\n\n',
      'data: {"type":"done"}\n\n',
    ]);

    const { result } = renderHook(() => useTutorChat());
    const originalSend = result.current.sendMessage;

    await act(async () => {
      await result.current.sendMessage('first');
    });

    // sendMessage should still be the very first reference we grabbed —
    // messages changed but the callback identity did not.
    expect(result.current.sendMessage).toBe(originalSend);
    expect(result.current.messages.some((m) => m.content === 'first')).toBe(true);
  });

  it('includes mode:"full" in POST body when sendMessage is called with { mode: "full" }', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"ok"}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useTutorChat());
    await act(async () => {
      await result.current.sendMessage('explain', { mode: 'full' });
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.mode).toBe('full');
  });

  it('includes mode:"worksheet" in POST body when sendMessage is called with { mode: "worksheet" } — #4382', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"ok"}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useTutorChat());
    await act(async () => {
      await result.current.sendMessage('practice problems please', { mode: 'worksheet' });
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.mode).toBe('worksheet');
  });

  it('omits mode field entirely when sendMessage is called without opts', async () => {
    // Server defaults to "quick" when mode is absent — don't bother sending it.
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"ok"}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useTutorChat());
    await act(async () => {
      await result.current.sendMessage('explain');
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body).not.toHaveProperty('mode');
  });

  it('requestFull replays the original userPrompt with mode:"full"', async () => {
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
        'data: {"type":"token","text":"long"}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useTutorChat());
    await act(async () => {
      await result.current.sendMessage('Explain photosynthesis');
    });

    const assistant = result.current.messages.find((m) => m.role === 'assistant');
    expect(assistant).toBeDefined();
    expect(assistant?.userPrompt).toBe('Explain photosynthesis');

    await act(async () => {
      result.current.requestFull(assistant!.id);
      // Allow the inner sendMessage to flush.
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const secondBody = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(secondBody.mode).toBe('full');
    expect(secondBody.message).toBe('Explain photosynthesis');
  });

  it('requestFull no-ops when message is already mode:"full"', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce({
      ok: true,
      body: makeSSEStream([
        'data: {"type":"token","text":"deep dive"}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useTutorChat());
    await act(async () => {
      await result.current.sendMessage('deep topic', { mode: 'full' });
    });

    const assistant = result.current.messages.find((m) => m.role === 'assistant');
    expect(assistant?.mode).toBe('full');

    await act(async () => {
      result.current.requestFull(assistant!.id);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    // No second fetch — the assistant message already satisfies mode:'full'.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('requestFull no-ops when assistantId does not match any message', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useTutorChat());
    await act(async () => {
      result.current.requestFull('does-not-exist');
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('requestFull marks the source message fullRequested:true (debounce guard)', async () => {
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
        'data: {"type":"token","text":"long"}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useTutorChat());
    await act(async () => {
      await result.current.sendMessage('Explain photosynthesis');
    });

    const assistant = result.current.messages.find((m) => m.role === 'assistant');
    expect(assistant).toBeDefined();
    expect(assistant?.fullRequested).toBeFalsy();

    await act(async () => {
      result.current.requestFull(assistant!.id);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    // The original quick-mode source message must now be marked fullRequested:true
    // so a second click on "Get the full version" is suppressed.
    const sourceAfter = result.current.messages.find((m) => m.id === assistant!.id);
    expect(sourceAfter?.fullRequested).toBe(true);
  });

  it('requestFull called twice in quick succession only fires ONE additional fetch', async () => {
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
        'data: {"type":"token","text":"long"}\n\n',
        'data: {"type":"done"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useTutorChat());
    await act(async () => {
      await result.current.sendMessage('Explain photosynthesis');
    });

    const assistant = result.current.messages.find((m) => m.role === 'assistant');
    expect(assistant).toBeDefined();

    // Two back-to-back calls — second must be debounced by fullRequested guard.
    await act(async () => {
      result.current.requestFull(assistant!.id);
      result.current.requestFull(assistant!.id);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    // 1 initial sendMessage + 1 requestFull = 2 fetches total (NOT 3).
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
