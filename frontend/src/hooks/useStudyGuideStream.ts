import { useState, useCallback, useRef, useEffect } from 'react';
import { parseSSEBuffer } from '../utils/sseParser';
import type { StudyGuide } from '../api/study';

/** Parameters accepted by the streaming study guide endpoint. */
export interface StudyGuideCreateParams {
  assignment_id?: number;
  course_id?: number;
  course_content_id?: number;
  title?: string;
  content?: string;
  regenerate_from_id?: number;
  custom_prompt?: string;
  focus_prompt?: string;
  document_type?: string;
  study_goal?: string;
  study_goal_text?: string;
}

export interface StreamState {
  status: 'idle' | 'connecting' | 'streaming' | 'done' | 'error';
  content: string;
  guideId: number | null;
  guide: StudyGuide | null;
  error: string | null;
}

export interface UseStudyGuideStreamReturn extends StreamState {
  isStreaming: boolean;
  startStream: (params: StudyGuideCreateParams) => void;
  abort: () => void;
  reset: () => void;
}

const FLUSH_INTERVAL_MS = 80;

const initialState: StreamState = {
  status: 'idle',
  content: '',
  guideId: null,
  guide: null,
  error: null,
};

export function useStudyGuideStream(): UseStudyGuideStreamReturn {
  const [state, setState] = useState<StreamState>(initialState);

  const abortControllerRef = useRef<AbortController | null>(null);
  const flushIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const contentBufferRef = useRef<string>('');
  const isMountedRef = useRef(true);

  // Track mounted state for safe state updates
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      if (flushIntervalRef.current) {
        clearInterval(flushIntervalRef.current);
        flushIntervalRef.current = null;
      }
    };
  }, []);

  const stopFlushInterval = useCallback(() => {
    if (flushIntervalRef.current) {
      clearInterval(flushIntervalRef.current);
      flushIntervalRef.current = null;
    }
  }, []);

  const startFlushInterval = useCallback(() => {
    stopFlushInterval();
    flushIntervalRef.current = setInterval(() => {
      if (!isMountedRef.current) return;
      const buffered = contentBufferRef.current;
      setState(prev => {
        if (prev.content === buffered) return prev;
        return { ...prev, content: buffered };
      });
    }, FLUSH_INTERVAL_MS);
  }, [stopFlushInterval]);

  const abort = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    stopFlushInterval();
    if (isMountedRef.current) {
      // Flush any remaining buffered content
      const buffered = contentBufferRef.current;
      setState(prev => ({
        ...prev,
        content: buffered || prev.content,
        status: prev.status === 'done' ? 'done' : 'error',
        error: prev.status === 'done' ? null : 'Stream aborted',
      }));
    }
  }, [stopFlushInterval]);

  const reset = useCallback(() => {
    abort();
    contentBufferRef.current = '';
    if (isMountedRef.current) {
      setState(initialState);
    }
  }, [abort]);

  const startStream = useCallback((params: StudyGuideCreateParams) => {
    // Abort any existing stream
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    stopFlushInterval();

    const controller = new AbortController();
    abortControllerRef.current = controller;
    contentBufferRef.current = '';

    setState({
      status: 'connecting',
      content: '',
      guideId: null,
      guide: null,
      error: null,
    });

    const token = localStorage.getItem('token') || '';
    const apiBase = import.meta.env.VITE_API_URL ?? '';

    (async () => {
      try {
        const response = await fetch(`${apiBase}/api/study/generate/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(params),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          const status = response.status;
          let errorMessage: string;
          if (status === 429) {
            errorMessage = 'You\u2019ve reached the request limit. Please wait a few minutes and try again.';
          } else if (status === 401 || status === 403) {
            errorMessage = 'Session expired. Please refresh the page and log in again.';
          } else {
            errorMessage = `Server error (${status}). Please try again.`;
          }
          if (isMountedRef.current) {
            setState(prev => ({ ...prev, status: 'error', error: errorMessage }));
          }
          return;
        }

        if (isMountedRef.current) {
          setState(prev => ({ ...prev, status: 'streaming' }));
        }
        startFlushInterval();

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let sseBuffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          sseBuffer += decoder.decode(value, { stream: true });
          const { events, remaining } = parseSSEBuffer(sseBuffer);
          sseBuffer = remaining;

          for (const sseEvent of events) {
            try {
              const data = JSON.parse(sseEvent.data);

              switch (sseEvent.event) {
                case 'start':
                  if (isMountedRef.current) {
                    setState(prev => ({ ...prev, guideId: data.guide_id ?? null }));
                  }
                  break;

                case 'chunk':
                  contentBufferRef.current += data.text ?? '';
                  break;

                case 'done': {
                  // Final flush of buffered content
                  stopFlushInterval();
                  const finalContent = contentBufferRef.current;
                  if (isMountedRef.current) {
                    setState(prev => ({
                      ...prev,
                      status: 'done',
                      content: finalContent,
                      guide: data.guide ?? null,
                    }));
                  }
                  break;
                }

                case 'error':
                  stopFlushInterval();
                  if (isMountedRef.current) {
                    setState(prev => ({
                      ...prev,
                      status: 'error',
                      content: contentBufferRef.current,
                      error: data.message ?? 'An error occurred during generation.',
                    }));
                  }
                  break;
              }
            } catch {
              // Malformed SSE data, skip
            }
          }
        }

        // Stream ended without a 'done' event — flush remaining content
        if (isMountedRef.current) {
          stopFlushInterval();
          setState(prev => {
            if (prev.status === 'done' || prev.status === 'error') return prev;
            return { ...prev, status: 'done', content: contentBufferRef.current };
          });
        }
      } catch (err: unknown) {
        if ((err as Error)?.name === 'AbortError') {
          // Intentional abort — already handled
          return;
        }
        stopFlushInterval();
        if (isMountedRef.current) {
          setState(prev => ({
            ...prev,
            status: 'error',
            content: contentBufferRef.current,
            error: 'Could not connect to the server. Please try again.',
          }));
        }
      }
    })();
  }, [startFlushInterval, stopFlushInterval]);

  return {
    ...state,
    isStreaming: state.status === 'connecting' || state.status === 'streaming',
    startStream,
    abort,
    reset,
  };
}
