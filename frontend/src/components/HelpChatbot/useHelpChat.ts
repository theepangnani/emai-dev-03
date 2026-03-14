import { useState, useCallback, useEffect } from 'react';
import { api } from '../../api/client';

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

interface HelpChatResponse {
  reply: string;
  videos?: VideoInfo[];
  sources?: string[];
  search_results?: SearchResult[];
  intent?: string;
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

    try {
      // Trim conversation to last 5 exchanges (10 messages) before sending
      const recentMessages = [...messages, userMessage]
        .slice(-10)
        .map(m => ({ role: m.role, content: m.content }));

      const { data } = await api.post<HelpChatResponse>('/api/help/chat', {
        message: text,
        conversation: recentMessages,
      });

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.reply,
        videos: data.videos,
        sources: data.sources,
        search_results: data.search_results,
        intent: data.intent,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 429) {
        setError('You\u2019ve reached the request limit. Please wait a few minutes and try again.');
      } else if (status === 401 || status === 403) {
        setError('Session expired. Please refresh the page and log in again.');
      } else {
        setError('Could not reach the help service. Please try again, or visit the Help page at /help.');
      }
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
