import { api } from './client';
import { parseSSEBuffer } from '../utils/sseParser';

export type DemoRole = 'parent' | 'student' | 'teacher' | 'other';
export type DemoType = 'ask' | 'study_guide' | 'flash_tutor';

export interface CreateDemoSessionPayload {
  email: string;
  full_name?: string;
  role: DemoRole;
  consent: boolean;
  _hp?: string;
}

export interface CreateDemoSessionResponse {
  session_jwt: string;
  verification_required: boolean;
  waitlist_preview_position: number;
}

export interface DemoHistoryTurn {
  role: 'user' | 'assistant';
  content: string;
}

export interface GeneratePayload {
  demo_type: DemoType;
  source_text?: string;
  question?: string;
  /**
   * Optional prior turns for the Ask multi-turn chatbox (§6.135.5, #3785).
   * Capped at 2 prior turns by the backend (`DemoGenerateRequest.history`).
   */
  history?: DemoHistoryTurn[];
}

export interface GenerateDoneData {
  demo_type: DemoType;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  cost_cents: number;
}

export interface VerifyCodeResponse {
  verified: boolean;
  waitlist_position: number;
  anomaly_flagged: boolean;
}

/** Create a demo session. Honeypot field (`_hp`) is silently dropped if empty. */
export async function createSession(
  payload: CreateDemoSessionPayload,
): Promise<CreateDemoSessionResponse> {
  const body: Record<string, unknown> = {
    email: payload.email,
    role: payload.role,
    consent: payload.consent,
  };
  if (payload.full_name) body.full_name = payload.full_name;
  // Only forward the honeypot if non-empty — matches backend expectation.
  if (payload._hp && payload._hp.trim()) body._hp = payload._hp;
  const res = await api.post<CreateDemoSessionResponse>(
    '/api/v1/demo/sessions',
    body,
  );
  return res.data;
}

/** Verify a demo session with the 6-digit fallback code. */
export async function verifyWithCode(
  email: string,
  code: string,
): Promise<VerifyCodeResponse> {
  const res = await api.post<VerifyCodeResponse>(
    '/api/v1/demo/verify/code',
    { email, code },
  );
  return res.data;
}

interface StreamCallbacks {
  onToken: (chunk: string) => void;
  onDone: (data: GenerateDoneData) => void;
  onError: (message: string) => void;
}

/**
 * Consume the SSE stream from POST /api/v1/demo/generate.
 * Uses fetch + ReadableStream (POST can't use EventSource). Returns an abort
 * controller the caller can use to cancel the stream.
 */
export function streamGenerate(
  sessionJwt: string,
  payload: GeneratePayload,
  { onToken, onDone, onError }: StreamCallbacks,
): AbortController {
  const controller = new AbortController();
  const apiBase =
    import.meta.env.VITE_API_URL ??
    (typeof window !== 'undefined' ? window.location.origin : '');

  (async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/demo/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Demo-Session': sessionJwt,
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!res.ok) {
        let message = `Request failed with status ${res.status}`;
        try {
          const errData = await res.json();
          const detail = errData?.detail;
          if (typeof detail === 'string') message = detail;
          else if (detail?.message) message = detail.message;
        } catch {
          // ignore parse error
        }
        onError(message);
        return;
      }

      if (!res.body) {
        onError('Streaming not supported by this browser.');
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const { events, remaining } = parseSSEBuffer(buffer);
        buffer = remaining;

        for (const event of events) {
          try {
            const data = JSON.parse(event.data);
            if (event.event === 'token') {
              const chunk = typeof data.chunk === 'string' ? data.chunk : '';
              if (chunk) onToken(chunk);
            } else if (event.event === 'done') {
              onDone(data as GenerateDoneData);
              return;
            } else if (event.event === 'error') {
              onError(data?.message ?? 'Generation failed.');
              return;
            }
          } catch {
            // malformed SSE payload — skip
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error)?.name === 'AbortError') return;
      onError(err instanceof Error ? err.message : 'Stream failed.');
    }
  })();

  return controller;
}

export const demoApi = { createSession, streamGenerate, verifyWithCode };
