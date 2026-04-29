/**
 * CB-CMCP-001 M1-E 1E-3 (#4496) — tests for the SSE consumer hook
 * `useCmcpGenerationStream`.
 *
 * Coverage:
 *  - loading: status flips connecting → streaming and `isStreaming` is
 *    true while tokens are flowing.
 *  - streaming: token frames append to `content`; multi-line chunks
 *    that the server escaped as `\n` are unescaped.
 *  - complete: `event: complete` payload populates `voice_module_hash`,
 *    `alignment_score`, and `completion` metadata; `status` → `done`.
 *  - error: `event: error` data populates `error` and `status` → `error`.
 *  - prefers-reduced-motion: when the media query matches, the hook
 *    surfaces `prefersReducedMotion: true` so the skeleton consumer can
 *    suppress shimmer animation.
 *  - 400 short-form redirect: server-side gate surfaces a useful error
 *    message instead of a silent stuck-loading state.
 *  - reset: clears content + status back to idle.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useCmcpGenerationStream } from '../useCmcpGenerationStream';

// ── Helpers ──────────────────────────────────────────────────────────

/** Build a `ReadableStream<Uint8Array>` from a list of pre-encoded SSE
 *  lines. Each entry should already include the trailing `\n\n`. */
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
      status: 200,
      body: makeSSEStream(lines),
      headers: new Headers({ 'content-type': 'text/event-stream' }),
    }),
  );
}

function mockFetchError(status: number, body?: { detail?: string }) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: false,
      status,
      body: null,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => body ?? {},
    }),
  );
}

const REQUEST = {
  grade: 5,
  subject_code: 'MATH',
  strand_code: 'B',
  content_type: 'STUDY_GUIDE',
} as const;

// ── Tests ────────────────────────────────────────────────────────────

// Snapshot the default `matchMedia` mock from `setup.ts` so tests that
// override it (e.g. the prefers-reduced-motion: reduce case) can be
// restored cleanly without leaking the override into the next test.
const ORIGINAL_MATCH_MEDIA = window.matchMedia;

describe('useCmcpGenerationStream', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('token', 'test-token');
  });

  afterEach(() => {
    localStorage.removeItem('token');
    vi.unstubAllGlobals();
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: ORIGINAL_MATCH_MEDIA,
    });
  });

  it('starts in idle state with empty fields', () => {
    const { result } = renderHook(() => useCmcpGenerationStream());
    expect(result.current.status).toBe('idle');
    expect(result.current.content).toBe('');
    expect(result.current.alignment_score).toBeNull();
    expect(result.current.voice_module_hash).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.isStreaming).toBe(false);
  });

  it('appends token chunks and resolves with completion metadata', async () => {
    mockFetchOk([
      'data: Hello \n\n',
      'data: world.\n\n',
      'event: complete\ndata: {"se_codes_targeted":["B1.1","B1.2"],"voice_module_id":"voice.parent.v1","voice_module_hash":"abc123","persona":"parent","content_type":"STUDY_GUIDE"}\n\n',
    ]);

    const { result } = renderHook(() => useCmcpGenerationStream());

    act(() => {
      result.current.startStream(REQUEST);
    });

    await waitFor(() => expect(result.current.status).toBe('done'));

    expect(result.current.content).toBe('Hello world.');
    expect(result.current.voice_module_hash).toBe('abc123');
    expect(result.current.completion?.se_codes_targeted).toEqual([
      'B1.1',
      'B1.2',
    ]);
    expect(result.current.completion?.persona).toBe('parent');
    expect(result.current.completion?.voice_module_id).toBe('voice.parent.v1');
    expect(result.current.error).toBeNull();
    expect(result.current.isStreaming).toBe(false);
  });

  it('unescapes \\n inside token chunks (server escapes literal newlines)', async () => {
    // Server-side `_sse_chunk` replaces literal `\n` with the 2-char
    // sequence `\n` so SSE framing isn't broken mid-chunk. The hook
    // must reverse that on the client.
    //
    // WIRE BYTES: `data: line1\nline2\n\n` where the `\n` between
    // line1 and line2 is the literal 2-char escape sequence (backslash
    // + 'n'), and the trailing `\n\n` is two real newlines (SSE block
    // terminator). The TS source string `'data: line1\\nline2\n\n'`
    // encodes exactly that — `\\n` is the 2-char escape, `\n` is the
    // newline. After SSE parsing the data field is `line1\nline2`
    // (still the 2-char escape); `unescapeChunk` converts it to
    // `line1` + real newline + `line2`.
    //
    // MUTATION-VERIFIED: removing `unescapeChunk(sseEvent.data)` from
    // the production code makes this assertion fail (received
    // `line1\nline2` 2-char escape, expected real newline).
    mockFetchOk([
      'data: line1\\nline2\n\n',
      'event: complete\ndata: {"se_codes_targeted":[],"voice_module_id":null,"voice_module_hash":null,"persona":"student","content_type":"STUDY_GUIDE"}\n\n',
    ]);

    const { result } = renderHook(() => useCmcpGenerationStream());
    act(() => {
      result.current.startStream(REQUEST);
    });
    await waitFor(() => expect(result.current.status).toBe('done'));
    expect(result.current.content).toBe('line1\nline2');
    // Belt-and-suspenders: explicitly verify the result contains a
    // real newline character (not the 2-char escape sequence). If
    // `unescapeChunk` is removed and someone "fixes" the toBe()
    // assertion above by escaping the expected value, this guard
    // still catches the regression.
    expect(result.current.content).toContain('\n');
    expect(result.current.content).not.toContain('\\n');
    expect(result.current.content.length).toBe('line1'.length + 1 + 'line2'.length);
  });

  it('unescapes multiple \\n occurrences across multi-chunk token frames', async () => {
    // Stronger mutation-test for `unescapeChunk` — multiple chunks
    // each carrying multiple escapes. If unescape regex is replaced
    // with `replace('\\n', '\n')` (no /g flag, would only fix the
    // first occurrence per chunk), this test still catches it.
    mockFetchOk([
      'data: a\\nb\\nc\n\n',
      'data: \\nd\\n\n\n',
      'event: complete\ndata: {"se_codes_targeted":[],"voice_module_id":null,"voice_module_hash":null,"persona":"student","content_type":"STUDY_GUIDE"}\n\n',
    ]);

    const { result } = renderHook(() => useCmcpGenerationStream());
    act(() => {
      result.current.startStream(REQUEST);
    });
    await waitFor(() => expect(result.current.status).toBe('done'));
    expect(result.current.content).toBe('a\nb\nc\nd\n');
  });

  it('flips status to streaming and reports isStreaming=true mid-stream', async () => {
    // Build a stream we can drive frame-by-frame so we can observe the
    // intermediate `streaming` state — a bulk-loaded stream resolves
    // too fast for the assertion to land before `done`.
    const encoder = new TextEncoder();
    let enqueueChunk: ((s: string) => void) | null = null;
    let closeStream: (() => void) | null = null;
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        enqueueChunk = (s: string) => controller.enqueue(encoder.encode(s));
        closeStream = () => controller.close();
      },
    });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body,
        headers: new Headers({ 'content-type': 'text/event-stream' }),
      }),
    );

    const { result } = renderHook(() => useCmcpGenerationStream());

    act(() => {
      result.current.startStream(REQUEST);
    });

    // First chunk arrives — hook transitions to streaming.
    await act(async () => {
      enqueueChunk!('data: token1\n\n');
      // Yield to the microtask queue so the reader can pick it up.
      await new Promise((r) => setTimeout(r, 0));
    });
    await waitFor(() => expect(result.current.status).toBe('streaming'));
    expect(result.current.isStreaming).toBe(true);
    expect(result.current.content).toBe('token1');

    // Terminal frame arrives — flips to done.
    await act(async () => {
      enqueueChunk!(
        'event: complete\ndata: {"se_codes_targeted":[],"voice_module_id":null,"voice_module_hash":"final","persona":"student","content_type":"STUDY_GUIDE"}\n\n',
      );
      closeStream!();
      await new Promise((r) => setTimeout(r, 0));
    });
    await waitFor(() => expect(result.current.status).toBe('done'));
    expect(result.current.voice_module_hash).toBe('final');
    expect(result.current.isStreaming).toBe(false);
  });

  it('surfaces event: error frames as terminal error state', async () => {
    mockFetchOk([
      'data: partial\n\n',
      'event: error\ndata: Generation failed mid-stream\n\n',
    ]);

    const { result } = renderHook(() => useCmcpGenerationStream());
    act(() => {
      result.current.startStream(REQUEST);
    });
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.error).toBe('Generation failed mid-stream');
    // Partial content received before the error frame remains visible
    // so the consumer can decide whether to render it.
    expect(result.current.content).toBe('partial');
  });

  it('maps a 400 short-form redirect into a user-readable error', async () => {
    mockFetchError(400, {
      detail: 'Use /api/cmcp/generate (sync) for short-form content types',
    });

    const { result } = renderHook(() => useCmcpGenerationStream());
    act(() => {
      result.current.startStream({ ...REQUEST, content_type: 'QUIZ' });
    });
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.error).toContain('Use /api/cmcp/generate');
  });

  it('maps 401/403 to a session-expired message', async () => {
    mockFetchError(401);
    const { result } = renderHook(() => useCmcpGenerationStream());
    act(() => {
      result.current.startStream(REQUEST);
    });
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.error).toMatch(/session expired/i);
  });

  it('respects prefers-reduced-motion: reduce', () => {
    // Override the default `setup.ts` matchMedia mock for this test
    // only — make `(prefers-reduced-motion: reduce)` match.
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn((query: string) => ({
        matches: query.includes('prefers-reduced-motion: reduce'),
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      })),
    });

    const { result } = renderHook(() => useCmcpGenerationStream());
    expect(result.current.prefersReducedMotion).toBe(true);
  });

  it('reports prefersReducedMotion=false when the media query does not match', () => {
    // Default setup.ts mock returns `matches: false` for everything.
    const { result } = renderHook(() => useCmcpGenerationStream());
    expect(result.current.prefersReducedMotion).toBe(false);
  });

  it('reset() returns the hook to idle state', async () => {
    mockFetchOk([
      'data: some content\n\n',
      'event: complete\ndata: {"se_codes_targeted":[],"voice_module_id":null,"voice_module_hash":"h","persona":"student","content_type":"STUDY_GUIDE"}\n\n',
    ]);

    const { result } = renderHook(() => useCmcpGenerationStream());
    act(() => {
      result.current.startStream(REQUEST);
    });
    await waitFor(() => expect(result.current.status).toBe('done'));
    expect(result.current.content).toBe('some content');

    act(() => {
      result.current.reset();
    });
    expect(result.current.status).toBe('idle');
    expect(result.current.content).toBe('');
    expect(result.current.voice_module_hash).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('abort() transitions out of streaming and clears isStreaming', async () => {
    // Regression guard for the IMP-4 finding: previously `abort()`
    // would AbortController.abort() but leave `state.status` stuck
    // at 'streaming', so the skeleton kept rendering after the user
    // canceled. Verify abort() returns the hook to a non-streaming
    // state immediately.
    const encoder = new TextEncoder();
    let enqueueChunk: ((s: string) => void) | null = null;
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        enqueueChunk = (s: string) => controller.enqueue(encoder.encode(s));
        // Intentionally never close — caller must abort.
      },
    });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body,
        headers: new Headers({ 'content-type': 'text/event-stream' }),
      }),
    );

    const { result } = renderHook(() => useCmcpGenerationStream());
    act(() => {
      result.current.startStream(REQUEST);
    });

    // Drive through to streaming state.
    await act(async () => {
      enqueueChunk!('data: partial\n\n');
      await new Promise((r) => setTimeout(r, 0));
    });
    await waitFor(() => expect(result.current.status).toBe('streaming'));
    expect(result.current.isStreaming).toBe(true);

    // Caller cancels.
    act(() => {
      result.current.abort();
    });

    // Hook must immediately reflect the cancel — skeleton stops.
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.status).toBe('idle');
    // Partial content stays in place; reset() is the explicit clear.
    expect(result.current.content).toBe('partial');
  });

  it('reads alignment_score from the completion payload when present', async () => {
    // 1E-1 does NOT yet emit alignment_score (1D-2 wire is pending),
    // but the hook must surface it defensively the moment the server
    // starts including it — without requiring a frontend release.
    mockFetchOk([
      'data: content\n\n',
      'event: complete\ndata: {"se_codes_targeted":[],"voice_module_id":null,"voice_module_hash":"h","persona":"student","content_type":"STUDY_GUIDE","alignment_score":0.92}\n\n',
    ]);

    const { result } = renderHook(() => useCmcpGenerationStream());
    act(() => {
      result.current.startStream(REQUEST);
    });
    await waitFor(() => expect(result.current.status).toBe('done'));
    expect(result.current.alignment_score).toBe(0.92);
  });
});
