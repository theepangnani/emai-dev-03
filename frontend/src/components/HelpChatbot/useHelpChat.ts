import { useState, useCallback, useEffect } from 'react';

const CHAT_STORAGE_KEY = 'classbridge-help-messages';

export interface VideoInfo {
  title: string;
  url: string;
  provider: string;
}

export interface SearchAction {
  label: string;
  route: string;
}

export interface SearchResult {
  entity_type: string;
  id?: number;
  title: string;
  description?: string;
  actions: SearchAction[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  videos?: VideoInfo[];
  sources?: string[];
  search_results?: SearchResult[];
  intent?: string;
  timestamp: Date;
}

export function useHelpChat() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      const stored = sessionStorage.getItem(CHAT_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        return parsed.map((m: ChatMessage) => ({ ...m, timestamp: new Date(m.timestamp) }));
      }
    } catch { /* ignore */ }
    return [];
  });
  useEffect(() => {
    try {
      sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
    } catch { /* ignore */ }
  }, [messages]);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(async (text: string) => {
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    const assistantId = `assistant-${Date.now()}`;
    // Add empty assistant placeholder immediately
    setMessages(prev => [...prev, {
      id: assistantId,
      role: 'assistant' as const,
      content: '',
      timestamp: new Date(),
    }]);

    try {
      const recentMessages = [...messages, userMessage]
        .slice(-10)
        .map(m => ({ role: m.role, content: m.content }));

      const token = localStorage.getItem('token') || '';

      const apiBase = import.meta.env.VITE_API_URL ?? '';
      const response = await fetch(`${apiBase}/api/help/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message: text,
          conversation: recentMessages,
          page_context: '',
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

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));

            if (data.type === 'token') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: m.content + data.text } : m
              ));
            } else if (data.type === 'search') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: data.reply, search_results: data.search_results, intent: data.intent }
                  : m
              ));
            } else if (data.type === 'done') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, sources: data.sources, videos: data.videos }
                  : m
              ));
            } else if (data.type === 'error') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: data.text } : m
              ));
            }
          } catch { /* malformed SSE line, skip */ }
        }
      }
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      const message = (err as Error)?.message ?? '';
      const httpStatus = status ?? (message.startsWith('HTTP ') ? parseInt(message.slice(5), 10) : undefined);
      if (httpStatus === 429) {
        setError('You\u2019ve reached the request limit. Please wait a few minutes and try again.');
      } else if (httpStatus === 401 || httpStatus === 403) {
        setError('Session expired. Please refresh the page and log in again.');
      } else {
        setError('Could not reach the help service. Please try again, or visit the Help page at /help.');
      }
      // Remove the empty assistant placeholder on error
      setMessages(prev => prev.filter(m => m.id !== assistantId));
    } finally {
      setIsLoading(false);
    }
  }, [messages]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    try { sessionStorage.removeItem(CHAT_STORAGE_KEY); } catch { /* ignore */ }
  }, []);

  return { messages, sendMessage, isLoading, error, clearMessages };
}
