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
  /** Tutor reply mode that produced this assistant message. */
  mode?: 'quick' | 'full';
  /** The user-prompt text that produced this assistant message. Stored on the
   *  assistant stub so a later "Get the full version" action can replay the
   *  same prompt with mode: 'full'. */
  userPrompt?: string;
}

export interface UseTutorChatResult {
  messages: TutorMessage[];
  sendMessage: (text: string, opts?: { mode?: 'quick' | 'full' }) => Promise<void>;
  /** Re-fire the user prompt that produced `assistantId` with mode:'full'. */
  requestFull: (assistantId: string) => void;
  isStreaming: boolean;
  cancel: () => void;
  error: string | null;
  clear: () => void;
}

/** Optional external state injection — lets callers hoist chat state above
 *  an unmount boundary (e.g. a mode toggle that would otherwise wipe the
 *  conversation on toggle). When both `externalMessages` and
 *  `externalSetMessages` are provided, the hook uses them directly; otherwise
 *  it falls back to its own internal useState. Same for conversationId. */
export interface UseTutorChatOptions {
  externalMessages?: TutorMessage[];
  externalSetMessages?: React.Dispatch<React.SetStateAction<TutorMessage[]>>;
  externalConversationId?: string | null;
  externalSetConversationId?: React.Dispatch<React.SetStateAction<string | null>>;
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

export function useTutorChat(options?: UseTutorChatOptions): UseTutorChatResult {
  const internal = useState<TutorMessage[]>([]);
  const internalConvId = useState<string | null>(null);

  const useExternalMessages =
    options?.externalMessages !== undefined && options?.externalSetMessages !== undefined;
  const messages = useExternalMessages ? options!.externalMessages! : internal[0];
  const setMessages = useExternalMessages ? options!.externalSetMessages! : internal[1];

  const useExternalConvId =
    options?.externalConversationId !== undefined &&
    options?.externalSetConversationId !== undefined;
  const conversationId = useExternalConvId
    ? options!.externalConversationId!
    : internalConvId[0];
  const setConversationId = useExternalConvId
    ? options!.externalSetConversationId!
    : internalConvId[1];

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

  const conversationIdRef = useRef<string | null>(conversationId);
  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  const setConversationIdRef = useRef(setConversationId);
  useEffect(() => {
    setConversationIdRef.current = setConversationId;
  }, [setConversationId]);

  const setMessagesRef = useRef(setMessages);
  useEffect(() => {
    setMessagesRef.current = setMessages;
  }, [setMessages]);

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
    setConversationIdRef.current(null);
    setMessagesRef.current([]);
    setError(null);
    setIsStreaming(false);
  }, []);

  const sendMessage = useCallback(
    async (text: string, opts?: { mode?: 'quick' | 'full' }) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      // Cancel any in-flight stream first so we don't interleave turns.
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const mode = opts?.mode;
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
        ...(mode ? { mode } : {}),
        userPrompt: trimmed,
      };

      // Snapshot history BEFORE appending the new user turn so the server
      // receives the prior conversation + the current message separately.
      // Read from the ref so sendMessage can remain a stable reference.
      const history = lastTurns(messagesRef.current);

      setMessagesRef.current((prev) => [...prev, userMessage, assistantStub]);
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
            ...(conversationIdRef.current
              ? { conversation_id: conversationIdRef.current }
              : {}),
            ...(mode ? { mode } : {}),
          }),
        });

        if (!response.ok || !response.body) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        // Race guard: once we've seen `done` for this stream, subsequent
        // frames (a late token straggler or a second chips payload) must
        // NOT mutate the bubble — otherwise we'd re-flash `streaming: true`
        // on the UI or append orphan text after the turn has settled.
        let streamDone = false;

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
                if (streamDone) {
                  console.warn('[useTutorChat] Token received after done; ignoring.');
                  continue;
                }
                setMessagesRef.current((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, content: m.content + (data.text ?? '') } : m,
                  ),
                );
              } else if (data.type === 'chips') {
                if (streamDone) {
                  console.warn('[useTutorChat] Chips received after done; ignoring.');
                  continue;
                }
                const suggestions: string[] = Array.isArray(data.suggestions)
                  ? data.suggestions.slice(0, 4)
                  : [];
                setMessagesRef.current((prev) =>
                  prev.map((m) => (m.id === assistantId ? { ...m, suggestions } : m)),
                );
              } else if (data.type === 'safety') {
                if (streamDone) {
                  console.warn('[useTutorChat] Safety received after done; ignoring.');
                  continue;
                }
                setMessagesRef.current((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: data.text ?? m.content, safety: true }
                      : m,
                  ),
                );
              } else if (data.type === 'done') {
                streamDone = true;
                if (typeof data.conversation_id === 'string') {
                  setConversationIdRef.current(data.conversation_id);
                }
                setMessagesRef.current((prev) =>
                  prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m)),
                );
              } else if (data.type === 'error') {
                setError(
                  typeof data.text === 'string'
                    ? data.text
                    : 'Something went wrong while streaming.',
                );
                setMessagesRef.current((prev) => prev.filter((m) => m.id !== assistantId));
              }
            } catch {
              /* malformed SSE line — skip */
            }
          }
        }
      } catch (err) {
        // Aborts are user-initiated — don't surface them as errors.
        if ((err as Error)?.name === 'AbortError') {
          setMessagesRef.current((prev) => prev.filter((m) => m.id !== assistantId));
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
          setMessagesRef.current((prev) => prev.filter((m) => m.id !== assistantId));
        }
      } finally {
        // Only clear streaming flag if this controller is still the active one
        // (a newer send would have replaced it).
        if (abortRef.current === controller) {
          abortRef.current = null;
          setIsStreaming(false);
          setMessagesRef.current((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m)),
          );
        }
      }
    },
    [],
  );

  const requestFull = useCallback(
    (assistantId: string) => {
      const target = messagesRef.current.find((m) => m.id === assistantId);
      if (!target || target.role !== 'assistant') return;
      if (target.mode === 'full') return;
      const prompt = target.userPrompt;
      if (!prompt) return;
      void sendMessage(prompt, { mode: 'full' });
    },
    [sendMessage],
  );

  return { messages, sendMessage, requestFull, isStreaming, cancel, error, clear };
}
