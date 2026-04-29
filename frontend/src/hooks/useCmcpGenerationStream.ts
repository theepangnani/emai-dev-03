/**
 * CB-CMCP-001 M1-E 1E-3 (#4496) — Frontend SSE consumer for the
 * curriculum-mapped generation streaming endpoint
 * (`POST /api/cmcp/generate/stream`, shipped 1E-1 / #4488).
 *
 * Reuses the dev-03 streaming convention established by
 * `useFlashTutorStream` + `useStudyGuideStream` + `useTutorChat`:
 *   - `fetch` + `ReadableStream.getReader()` (POST means we can't use
 *     native `EventSource`).
 *   - `parseSSEBuffer` for the `event:` / `data:` framing.
 *   - `AbortController` for clean cancel + unmount.
 *
 * Wire format (matches `app/api/routes/cmcp_generate_stream.py`):
 *   - `data: <chunk-text>\n\n`              token chunk (literal `\n`
 *                                            inside chunk text is escaped
 *                                            as the 2-char sequence `\n`
 *                                            by the server — we unescape
 *                                            it here so the consumer sees
 *                                            real newlines).
 *   - `event: complete\ndata: <json>\n\n`   final payload carrying
 *                                            `voice_module_hash` +
 *                                            `voice_module_id` +
 *                                            `se_codes_targeted` +
 *                                            `persona` + `content_type`.
 *   - `event: error\ndata: <message>\n\n`   terminal error frame (data
 *                                            is plain string, not JSON).
 *
 * NOTE: 1E-1 does NOT yet emit `alignment_score` (1D-2 wire is pending),
 * so the hook surfaces it as `null` until the completion payload starts
 * carrying it. The hook reads `alignment_score` defensively if the
 * server later adds it without a hook change.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

/** Parsed SSE event — `event` defaults to `'message'` for token frames
 *  that omit the `event:` line. Unlike the shared `parseSSEBuffer`, the
 *  data string is NOT trimmed: token chunks carry meaningful leading /
 *  trailing whitespace ("Hello " + "world." must concatenate to
 *  "Hello world.", not "Helloworld."). The shared util's `.trim()` is
 *  fine for JSON-data events but eats whitespace on text streams. */
interface CmcpSSEEvent {
  event: string;
  data: string;
}

/** Parse an SSE text buffer into discrete events. Events are delimited
 *  by `\n\n`. Returns parsed events and any remaining incomplete text.
 *  Whitespace inside `data:` payloads is preserved exactly (only the
 *  single space immediately after `data:` is consumed, matching the
 *  SSE spec). */
function parseCmcpSSEBuffer(buffer: string): {
  events: CmcpSSEEvent[];
  remaining: string;
} {
  const events: CmcpSSEEvent[] = [];
  const blocks = buffer.split('\n\n');
  const remaining = blocks.pop() ?? '';

  for (const block of blocks) {
    if (!block) continue;

    let event = 'message';
    const dataLines: string[] = [];

    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) {
        // `event:` lines are control-plane metadata — trimming the
        // event name is safe and matches every other dev-03 SSE
        // consumer.
        event = line.slice(6).trim();
      } else if (line.startsWith('data: ')) {
        // Strip the single space after `data:` per spec but preserve
        // any further whitespace (token text fidelity).
        dataLines.push(line.slice(6));
      } else if (line.startsWith('data:')) {
        // No space after `data:` — preserve everything that follows.
        dataLines.push(line.slice(5));
      }
    }

    // Multi-line data payloads are joined with `\n` per the SSE spec.
    const data = dataLines.join('\n');
    if (data || event !== 'message') {
      events.push({ event, data });
    }
  }

  return { events, remaining };
}

/** HTTP-side content-type literal — mirrors `HTTPContentType` in
 *  `app/schemas/cmcp.py`. Long-form types (`STUDY_GUIDE`, `SAMPLE_TEST`,
 *  `ASSIGNMENT`) stream; short-form types are rejected with `400` from
 *  the server (the hook surfaces that as a terminal error). */
export type CmcpHTTPContentType =
  | 'STUDY_GUIDE'
  | 'WORKSHEET'
  | 'QUIZ'
  | 'SAMPLE_TEST'
  | 'ASSIGNMENT'
  | 'PARENT_COMPANION';

export type CmcpHTTPDifficulty = 'APPROACHING' | 'GRADE_LEVEL' | 'EXTENDING';
export type CmcpTargetPersona = 'student' | 'parent' | 'teacher';

export interface CmcpGenerateRequest {
  grade: number;
  subject_code: string;
  strand_code?: string | null;
  topic?: string | null;
  content_type: CmcpHTTPContentType;
  difficulty?: CmcpHTTPDifficulty;
  target_persona?: CmcpTargetPersona | null;
  course_id?: number | null;
}

export type CmcpStreamStatus =
  | 'idle'
  | 'connecting'
  | 'streaming'
  | 'done'
  | 'error';

/** Subset of the `event: complete` payload the hook surfaces verbatim
 *  for callers that want to display the curriculum-alignment metadata
 *  (SE codes, voice module, persona). */
export interface CmcpCompletionMeta {
  se_codes_targeted: string[];
  voice_module_id: string | null;
  voice_module_hash: string | null;
  persona: CmcpTargetPersona;
  content_type: CmcpHTTPContentType;
}

export interface CmcpStreamState {
  status: CmcpStreamStatus;
  /** Aggregated text from `data:` token frames. */
  content: string;
  /** Populated from the `event: complete` payload. `null` until the
   *  completion frame arrives or until the server starts emitting an
   *  alignment score (1D-2). */
  alignment_score: number | null;
  voice_module_hash: string | null;
  /** Full completion-frame payload — surfaces SE codes, persona, etc.
   *  for callers that want to render the curriculum-alignment chip. */
  completion: CmcpCompletionMeta | null;
  error: string | null;
}

export interface StartStreamOptions {
  /** Override the default `/api/cmcp/generate/stream` endpoint (handy
   *  for tests or for piping through a future preview surface). */
  endpoint?: string;
}

export interface UseCmcpGenerationStreamReturn extends CmcpStreamState {
  /** True while connecting OR streaming. Drives skeleton visibility. */
  isStreaming: boolean;
  /** True when `prefers-reduced-motion: reduce` is set. The skeleton
   *  consumer should suppress shimmer animation in that case. */
  prefersReducedMotion: boolean;
  startStream: (
    request: CmcpGenerateRequest,
    options?: StartStreamOptions,
  ) => void;
  abort: () => void;
  reset: () => void;
}

const initialState: CmcpStreamState = {
  status: 'idle',
  content: '',
  alignment_score: null,
  voice_module_hash: null,
  completion: null,
  error: null,
};

/** Server-side `_sse_chunk` escapes literal `\n` to the 2-char sequence
 *  `\n` so the SSE framing isn't broken by mid-chunk newlines. Reverse
 *  that on the client so consumers see real line breaks. `\r` is dropped
 *  entirely on the server, so we only need to handle `\n`. */
function unescapeChunk(text: string): string {
  return text.replace(/\\n/g, '\n');
}

/** Detect the user's `prefers-reduced-motion` setting. Returns `false`
 *  when `matchMedia` is unavailable (e.g. older jsdom builds). */
function detectReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false;
  }
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return false;
  }
}

export function useCmcpGenerationStream(): UseCmcpGenerationStreamReturn {
  const [state, setState] = useState<CmcpStreamState>(initialState);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState<boolean>(
    () => detectReducedMotion(),
  );

  const abortRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);

  // Subscribe to `prefers-reduced-motion` changes so a user toggling
  // their OS-level setting mid-session sees the skeleton update without
  // a page reload. Falls back gracefully on browsers that don't support
  // `addEventListener` on a MediaQueryList (Safari < 14).
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return;
    }
    let mql: MediaQueryList;
    try {
      mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    } catch {
      return;
    }
    const handler = (e: MediaQueryListEvent) => {
      setPrefersReducedMotion(e.matches);
    };
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', handler);
      return () => mql.removeEventListener('change', handler);
    }
    // Safari < 14 fallback
    if (typeof (mql as MediaQueryList).addListener === 'function') {
      (mql as MediaQueryList).addListener(handler);
      return () => (mql as MediaQueryList).removeListener(handler);
    }
    return;
  }, []);

  // Track mounted state so async stream callbacks don't setState after
  // unmount (React 18+ warns; React 19 silently drops, but a stale
  // closure that fires `setState` post-unmount is still a bug).
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, []);

  const abort = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    // Transition out of `connecting` / `streaming` so the skeleton
    // stops showing immediately. Without this the AbortError thrown
    // by `fetch` is swallowed by the catch (intentional cancel) and
    // the hook would stay `streaming: true` indefinitely. Matches the
    // pattern in `useStudyGuideStream`.
    setState((prev) =>
      prev.status === 'connecting' || prev.status === 'streaming'
        ? { ...prev, status: 'idle' }
        : prev,
    );
  }, []);

  const reset = useCallback(() => {
    abort();
    if (isMountedRef.current) {
      setState(initialState);
    }
  }, [abort]);

  const startStream = useCallback(
    (request: CmcpGenerateRequest, opts?: StartStreamOptions) => {
      // Cancel any in-flight stream before starting a new one.
      if (abortRef.current) {
        abortRef.current.abort();
      }
      const controller = new AbortController();
      abortRef.current = controller;

      setState({
        status: 'connecting',
        content: '',
        alignment_score: null,
        voice_module_hash: null,
        completion: null,
        error: null,
      });

      const token = (typeof localStorage !== 'undefined'
        ? localStorage.getItem('token')
        : null) || '';
      const apiBase = import.meta.env.VITE_API_URL ?? '';
      const endpoint = opts?.endpoint ?? '/api/cmcp/generate/stream';

      (async () => {
        try {
          const response = await fetch(`${apiBase}${endpoint}`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify(request),
            signal: controller.signal,
          });

          if (!response.ok || !response.body) {
            // Map the common HTTP error shapes to user-facing copy.
            // 400 → short-form redirect (caller should hit sync route).
            // 401/403 → session/permission. 422 → no CEG match. Else
            // generic.
            const status = response.status;
            let errorMessage: string;
            if (status === 400) {
              const body = await response.json().catch(() => null);
              errorMessage =
                (body && typeof body.detail === 'string' && body.detail) ||
                'This content type does not support streaming.';
            } else if (status === 401 || status === 403) {
              errorMessage =
                'Session expired. Please refresh the page and log in again.';
            } else if (status === 422) {
              const body = await response.json().catch(() => null);
              errorMessage =
                (body && typeof body.detail === 'string' && body.detail) ||
                'No matching curriculum expectations for this request.';
            } else if (status === 429) {
              errorMessage =
                "You've reached the request limit. Please wait a few minutes and try again.";
            } else {
              errorMessage = `Server error (${status}). Please try again.`;
            }
            if (isMountedRef.current) {
              setState((prev) => ({
                ...prev,
                status: 'error',
                error: errorMessage,
              }));
            }
            return;
          }

          if (isMountedRef.current) {
            setState((prev) => ({ ...prev, status: 'streaming' }));
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';
          // Race guard: once we've seen the terminal `complete` or
          // `error` frame, ignore subsequent stragglers (a buffered
          // flush from the proxy can deliver one extra token after the
          // server has already written the terminal frame).
          let terminal = false;

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            if (controller.signal.aborted) break;

            buffer += decoder.decode(value, { stream: true });
            const { events, remaining } = parseCmcpSSEBuffer(buffer);
            buffer = remaining;

            for (const sseEvent of events) {
              if (terminal) continue;

              if (sseEvent.event === 'complete') {
                let payload: Partial<CmcpCompletionMeta> & {
                  alignment_score?: number;
                } = {};
                try {
                  payload = JSON.parse(sseEvent.data);
                } catch {
                  // Malformed completion payload — surface as error.
                  terminal = true;
                  if (isMountedRef.current) {
                    setState((prev) => ({
                      ...prev,
                      status: 'error',
                      error: 'Malformed completion payload.',
                    }));
                  }
                  break;
                }
                terminal = true;
                if (isMountedRef.current) {
                  setState((prev) => ({
                    ...prev,
                    status: 'done',
                    voice_module_hash: payload.voice_module_hash ?? null,
                    alignment_score:
                      typeof payload.alignment_score === 'number'
                        ? payload.alignment_score
                        : null,
                    completion: {
                      se_codes_targeted: Array.isArray(payload.se_codes_targeted)
                        ? payload.se_codes_targeted
                        : [],
                      voice_module_id: payload.voice_module_id ?? null,
                      voice_module_hash: payload.voice_module_hash ?? null,
                      persona: (payload.persona ?? 'student') as CmcpTargetPersona,
                      content_type: (payload.content_type ??
                        request.content_type) as CmcpHTTPContentType,
                    },
                    error: null,
                  }));
                }
              } else if (sseEvent.event === 'error') {
                // Server emits the error message as a plain string,
                // not JSON. Use the data verbatim and unescape any
                // newlines the server escaped on the wire.
                terminal = true;
                if (isMountedRef.current) {
                  setState((prev) => ({
                    ...prev,
                    status: 'error',
                    error: unescapeChunk(sseEvent.data) || 'Generation failed.',
                  }));
                }
              } else {
                // Default `message` event = token chunk. The server
                // emits chunks as `data: <text>\n\n` with no `event:`
                // line, so `parseSSEBuffer` labels them `'message'`.
                const chunk = unescapeChunk(sseEvent.data);
                if (isMountedRef.current) {
                  setState((prev) => ({
                    ...prev,
                    content: prev.content + chunk,
                  }));
                }
              }
            }
          }

          // Stream ended without a terminal frame (network close, server
          // EOF). Mark done if we received any content; otherwise error
          // so the UI doesn't render an empty success state.
          if (!terminal && isMountedRef.current) {
            setState((prev) => {
              if (prev.status === 'done' || prev.status === 'error') {
                return prev;
              }
              if (prev.content.length > 0) {
                return { ...prev, status: 'done' };
              }
              return {
                ...prev,
                status: 'error',
                error: 'Stream closed before any content arrived.',
              };
            });
          }
        } catch (err: unknown) {
          if ((err as Error)?.name === 'AbortError') {
            // Intentional cancel — don't surface as error. Leave the
            // partial content in place; caller can `reset()` to clear.
            return;
          }
          if (isMountedRef.current) {
            setState((prev) => ({
              ...prev,
              status: 'error',
              error: 'Could not connect to the server. Please try again.',
            }));
          }
        } finally {
          if (abortRef.current === controller) {
            abortRef.current = null;
          }
        }
      })();
    },
    [],
  );

  return {
    ...state,
    isStreaming: state.status === 'connecting' || state.status === 'streaming',
    prefersReducedMotion,
    startStream,
    abort,
    reset,
  };
}
