import { useState, useRef, useCallback, useEffect } from 'react';
import { parseSSEBuffer } from '../utils/sseParser';

export interface StudyGuideCreateParams {
  course_content_id?: number;
  course_id?: number;
  assignment_id?: number;
  title?: string;
  content?: string;
  focus_prompt?: string;
  document_type?: string;
  study_goal?: string;
  study_goal_text?: string;
}

interface StreamState {
  status: 'idle' | 'connecting' | 'streaming' | 'done' | 'error';
  content: string;
  guideId: number | null;
  guide: unknown | null;
  error: string | null;
}

export interface UseStudyGuideStreamReturn extends StreamState {
  isStreaming: boolean;
  startStream: (params: StudyGuideCreateParams) => void;
  abort: () => void;
  reset: () => void;
}

const FLUSH_INTERVAL = 80; // ms — render throttling

export function useStudyGuideStream(): UseStudyGuideStreamReturn {
  const [state, setState] = useState<StreamState>({
    status: 'idle',
    content: '',
    guideId: null,
    guide: null,
    error: null,
  });

  const abortRef = useRef<AbortController | null>(null);
  const bufferRef = useRef(''); // accumulated but not yet flushed content
  const flushedRef = useRef(''); // content already pushed to state
  const flushTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Flush accumulated content to state at throttled interval
  const startFlushing = useCallback(() => {
    if (flushTimerRef.current) return;
    flushTimerRef.current = setInterval(() => {
      if (bufferRef.current !== flushedRef.current) {
        const snapshot = bufferRef.current;
        flushedRef.current = snapshot;
        setState(prev => ({ ...prev, content: snapshot }));
      }
    }, FLUSH_INTERVAL);
  }, []);

  const stopFlushing = useCallback(() => {
    if (flushTimerRef.current) {
      clearInterval(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    // Final flush
    if (bufferRef.current !== flushedRef.current) {
      const snapshot = bufferRef.current;
      flushedRef.current = snapshot;
      setState(prev => ({ ...prev, content: snapshot }));
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (flushTimerRef.current) clearInterval(flushTimerRef.current);
      abortRef.current?.abort();
    };
  }, []);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    stopFlushing();
    setState(prev => {
      if (prev.status === 'streaming' || prev.status === 'connecting') {
        return { ...prev, status: 'error', error: 'Generation cancelled' };
      }
      return prev;
    });
  }, [stopFlushing]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    stopFlushing();
    bufferRef.current = '';
    flushedRef.current = '';
    setState({ status: 'idle', content: '', guideId: null, guide: null, error: null });
  }, [stopFlushing]);

  const startStream = useCallback((params: StudyGuideCreateParams) => {
    // Abort any existing stream
    abortRef.current?.abort();
    stopFlushing();

    const controller = new AbortController();
    abortRef.current = controller;
    bufferRef.current = '';
    flushedRef.current = '';

    setState({ status: 'connecting', content: '', guideId: null, guide: null, error: null });

    const token = localStorage.getItem('token') || '';
    const apiBase = import.meta.env.VITE_API_URL ?? (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000');

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
          const errText = await response.text().catch(() => '');
          let errMsg = `HTTP ${response.status}`;
          try {
            const parsed = JSON.parse(errText);
            errMsg = parsed.detail || errMsg;
          } catch { /* use default */ }
          setState(prev => ({ ...prev, status: 'error', error: errMsg }));
          return;
        }

        setState(prev => ({ ...prev, status: 'streaming' }));
        startFlushing();

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let sseBuffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          sseBuffer += decoder.decode(value, { stream: true });
          const { events, remaining } = parseSSEBuffer(sseBuffer);
          sseBuffer = remaining;

          for (const evt of events) {
            try {
              const data = JSON.parse(evt.data);

              if (evt.event === 'token' || data.type === 'token') {
                bufferRef.current += data.text ?? data.token ?? '';
              } else if (evt.event === 'done' || data.type === 'done') {
                stopFlushing();
                // If the done event includes final content, use it
                const finalContent = data.content || bufferRef.current;
                bufferRef.current = finalContent;
                flushedRef.current = finalContent;
                setState(prev => ({
                  ...prev,
                  status: 'done',
                  content: finalContent,
                  guideId: data.guide_id ?? data.id ?? prev.guideId,
                  guide: data.guide ?? data,
                }));
              } else if (evt.event === 'error' || data.type === 'error') {
                stopFlushing();
                setState(prev => ({
                  ...prev,
                  status: 'error',
                  error: data.message || data.text || 'Stream error',
                }));
              } else if (evt.event === 'guide_id' || data.type === 'guide_id') {
                setState(prev => ({ ...prev, guideId: data.guide_id ?? data.id }));
              }
            } catch { /* malformed SSE data, skip */ }
          }
        }

        // If we finished reading without a done event, mark as done
        stopFlushing();
        setState(prev => {
          if (prev.status === 'streaming') {
            return { ...prev, status: 'done', content: bufferRef.current };
          }
          return prev;
        });
      } catch (err: unknown) {
        stopFlushing();
        if ((err as Error)?.name === 'AbortError') return; // user cancelled
        setState(prev => ({
          ...prev,
          status: 'error',
          error: (err as Error)?.message || 'Connection failed',
        }));
      }
    })();
  }, [startFlushing, stopFlushing]);

  return {
    ...state,
    isStreaming: state.status === 'connecting' || state.status === 'streaming',
    startStream,
    abort,
    reset,
  };
}
