/**
 * useTutorChat — SSE streaming chat hook for the Tutor Explain mode.
 *
 * Wraps the /api/tutor/chat/stream endpoint. Event contract (server-sent):
 *   • token   — { type: "token", text: string }            → append to current bubble
 *   • chips   — { type: "chips", suggestions: string[] }   → follow-up suggestion chips
 *   • safety  — { type: "safety", text: string }           → flagged/guardrail message
 *   • done    — { type: "done", credits_used?: number }    → close the turn
 *   • error   — { type: "error", text?: string }           → inline error state
 *
 * Memory: callers send the last 3 (user, assistant) pairs + current message.
 * The backend persists its own copy, so we don't round-trip full history.
 *
 * Parallels `HelpChatbot/useHelpChat.ts` but with cancel support (AbortController)
 * and a tutor-specific message shape (suggestions, safety flag).
 */
import { useState, useCallback, useRef, useEffect } from 'react';

export interface TutorMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  /** Follow-up suggestions emitted after an assistant turn. */
  suggestions?: string[];
  /** True when the model/guardrail returned a safety notice. */
  safety?: boolean;
  /** True while tokens are still streaming into this bubble. */
  streaming?: boolean;
  timestamp: Date;
}

export interface UseTutorChatResult {
  messages: TutorMessage[];
  sendMessage: (text: string) => Promise<void>;
  isStreaming: boolean;
  cancel: () => void;
  error: string | null;
  clear: () => void;
}

/** Last 3 (user, assistant) pairs = 6 messages. */
const HISTORY_TURNS = 3;

function lastTurns(messages: TutorMessage[], limit = HISTORY_TURNS) {
  // Walk backwards collecting complete pairs.
  const pairs: TutorMessage[][] = [];
  let pending: TutorMessage | null = null;
  for (let i = messages.length - 1; i >= 0 && pairs.length < limit; i--) {
    const m = messages[i];
    if (m.role === 'assistant' && !pending) {
      pending = m;
    } else if (m.role === 'user' && pending) {
      pairs.unshift([m, pending]);
      pending = null;
    }
  }
  return pairs.flat().map((m) => ({ role: m.role, content: m.content }));
}

export function useTutorChat(): UseTutorChatResult {
  const [messages, setMessages] = useState<TutorMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Snapshot-only refs so `sendMessage` can stay stable across re-renders.
  // Consumers can then safely depend on `sendMessage` in useEffect/useMemo
  // without triggering churn on every `messages` update.
  const messagesRef = useRef<TutorMessage[]>(messages);
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  }, []);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages([]);
    setError(null);
    setIsStreaming(false);
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      // Cancel any in-flight stream first so we don't interleave turns.
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const userMessage: TutorMessage = {
        id: `u-${Date.now()}`,
        role: 'user',
        content: trimmed,
        timestamp: new Date(),
      };
      const assistantId = `a-${Date.now()}`;
      const assistantStub: TutorMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        streaming: true,
        timestamp: new Date(),
      };

      // Snapshot history BEFORE appending the new user turn so the server
      // receives the prior conversation + the current message separately.
      // Read from the ref so sendMessage can remain a stable reference.
      const history = lastTurns(messagesRef.current);

      setMessages((prev) => [...prev, userMessage, assistantStub]);
      setIsStreaming(true);
      setError(null);

      try {
        const token = localStorage.getItem('token') || '';
        const apiBase = import.meta.env.VITE_API_URL ?? '';
        const response = await fetch(`${apiBase}/api/tutor/chat/stream`, {
          method: 'POST',
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            message: trimmed,
            history,
          }),
        });

        if (!response.ok || !response.body) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          if (controller.signal.aborted) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'token') {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, content: m.content + (data.text ?? '') } : m,
                  ),
                );
              } else if (data.type === 'chips') {
                const suggestions: string[] = Array.isArray(data.suggestions)
                  ? data.suggestions.slice(0, 4)
                  : [];
                setMessages((prev) =>
                  prev.map((m) => (m.id === assistantId ? { ...m, suggestions } : m)),
                );
              } else if (data.type === 'safety') {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: data.text ?? m.content, safety: true }
                      : m,
                  ),
                );
              } else if (data.type === 'done') {
                setMessages((prev) =>
                  prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m)),
                );
              } else if (data.type === 'error') {
                setError(
                  typeof data.text === 'string'
                    ? data.text
                    : 'Something went wrong while streaming.',
                );
                setMessages((prev) => prev.filter((m) => m.id !== assistantId));
              }
            } catch {
              /* malformed SSE line — skip */
            }
          }
        }
      } catch (err) {
        // Aborts are user-initiated — don't surface them as errors.
        if ((err as Error)?.name === 'AbortError') {
          setMessages((prev) => prev.filter((m) => m.id !== assistantId));
        } else {
          const message = (err as Error)?.message ?? '';
          const httpStatus = message.startsWith('HTTP ')
            ? parseInt(message.slice(5), 10)
            : undefined;
          if (httpStatus === 429) {
            setError("You've hit the request limit. Give it a minute and try again.");
          } else if (httpStatus === 401 || httpStatus === 403) {
            setError('Session expired. Refresh the page and log in again.');
          } else {
            setError("Arc couldn't reach the tutor service. Try again in a moment.");
          }
          setMessages((prev) => prev.filter((m) => m.id !== assistantId));
        }
      } finally {
        // Only clear streaming flag if this controller is still the active one
        // (a newer send would have replaced it).
        if (abortRef.current === controller) {
          abortRef.current = null;
          setIsStreaming(false);
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m)),
          );
        }
      }
    },
    [],
  );

  return { messages, sendMessage, isStreaming, cancel, error, clear };
}
