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
});
