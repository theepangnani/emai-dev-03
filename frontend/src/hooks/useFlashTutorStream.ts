import { useState, useRef, useCallback, useEffect } from 'react';
import { parseSSEBuffer } from '../utils/sseParser';
import type { ILESessionCreate } from '../api/ile';

type StreamStatus = 'idle' | 'connecting' | 'streaming' | 'done' | 'error';

interface FlashTutorStreamState {
  status: StreamStatus;
  sessionId: number | null;
  questionsReady: number;
  totalQuestions: number;
  error: string | null;
}

export function useFlashTutorStream() {
  const [state, setState] = useState<FlashTutorStreamState>({
    status: 'idle',
    sessionId: null,
    questionsReady: 0,
    totalQuestions: 0,
    error: null,
  });
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  const startStream = useCallback(async (params: ILESessionCreate) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ status: 'connecting', sessionId: null, questionsReady: 0, totalQuestions: 0, error: null });

    try {
      const token = localStorage.getItem('token');
      const apiBase = import.meta.env.VITE_API_URL ?? '';
      const res = await fetch(`${apiBase}/api/ile/sessions?stream=true`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(params),
        signal: controller.signal,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: `Request failed with status ${res.status}` }));
        setState(s => ({ ...s, status: 'error', error: errData.detail || errData.message || `Error ${res.status}` }));
        return;
      }

      // Check if response is JSON (non-streaming fallback) vs SSE
      const contentType = res.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const data = await res.json();
        setState({ status: 'done', sessionId: data.id, questionsReady: data.question_count, totalQuestions: data.question_count, error: null });
        return;
      }

      // SSE streaming
      setState(s => ({ ...s, status: 'streaming' }));
      const reader = res.body!.getReader();
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

            if (event.event === 'start') {
              setState(s => ({ ...s, sessionId: data.session_id, totalQuestions: data.question_count }));
            } else if (event.event === 'question') {
              setState(s => ({ ...s, questionsReady: data.index + 1 }));
            } else if (event.event === 'done') {
              setState(s => ({ ...s, status: 'done', sessionId: data.session_id }));
            } else if (event.event === 'error') {
              setState(s => ({ ...s, status: 'error', error: data.message }));
            }
          } catch {
            // Malformed SSE data, skip
          }
        }
      }

      // Stream ended without a 'done' event
      setState(s => {
        if (s.status === 'done' || s.status === 'error') return s;
        return { ...s, status: 'done' };
      });
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') return;
      setState(s => ({ ...s, status: 'error', error: err instanceof Error ? err.message : 'Stream failed' }));
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState({ status: 'idle', sessionId: null, questionsReady: 0, totalQuestions: 0, error: null });
  }, []);

  return { ...state, startStream, reset };
}
