import { useState, useCallback, useEffect, useRef } from 'react';
import type { StudyGuideContext } from '../../context/FABContext';

const HELP_STORAGE_KEY = 'classbridge-help-messages';

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
  mode?: 'help' | 'study_qa';
  credits_used?: number;
  timestamp: Date;
}

function getStorageKey(ctx?: StudyGuideContext | null): string {
  return ctx ? `classbridge-study-qa-${ctx.id}` : HELP_STORAGE_KEY;
}

export function useHelpChat(studyGuideContext?: StudyGuideContext | null) {
  const storageKey = getStorageKey(studyGuideContext);
  const prevKeyRef = useRef(storageKey);

  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      const stored = sessionStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        return parsed.map((m: ChatMessage) => ({ ...m, timestamp: new Date(m.timestamp) }));
      }
    } catch { /* ignore */ }
    return [];
  });

  // When storage key changes (different guide or switching modes), reload messages
  useEffect(() => {
    if (prevKeyRef.current !== storageKey) {
      prevKeyRef.current = storageKey;
      try {
        const stored = sessionStorage.getItem(storageKey);
        if (stored) {
          const parsed = JSON.parse(stored);
          setMessages(parsed.map((m: ChatMessage) => ({ ...m, timestamp: new Date(m.timestamp) })));
        } else {
          setMessages([]);
        }
      } catch {
        setMessages([]);
      }
    }
  }, [storageKey]);

  useEffect(() => {
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(messages));
    } catch { /* ignore */ }
  }, [messages, storageKey]);

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
          study_guide_id: studyGuideContext?.id ?? null,
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
                  ? {
                      ...m,
                      sources: data.sources,
                      videos: data.videos,
                      mode: data.mode || 'help',
                      credits_used: data.credits_used,
                    }
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
      const errMessage = (err as Error)?.message ?? '';
      const httpStatus = status ?? (errMessage.startsWith('HTTP ') ? parseInt(errMessage.slice(5), 10) : undefined);
      const isStudy = !!studyGuideContext?.id;
      if (httpStatus === 429) {
        setError('You\u2019ve reached the request limit. Please wait a few minutes and try again.');
      } else if (httpStatus === 401) {
        setError('Session expired. Please refresh the page and log in again.');
      } else if (httpStatus === 403) {
        setError(isStudy
          ? 'You don\u2019t have access to this study guide\u2019s Q&A. The guide may belong to another user.'
          : 'Session expired. Please refresh the page and log in again.');
      } else if (httpStatus === 404) {
        setError(isStudy
          ? 'This study guide was not found. It may have been deleted or regenerated.'
          : 'Could not reach the help service. Please try again, or visit the Help page at /help.');
      } else {
        setError(isStudy
          ? 'Could not reach the study assistant. Please try again later.'
          : 'Could not reach the help service. Please try again, or visit the Help page at /help.');
      }
      setMessages(prev => prev.filter(m => m.id !== assistantId));
    } finally {
      setIsLoading(false);
    }
  }, [messages, studyGuideContext?.id]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    try { sessionStorage.removeItem(storageKey); } catch { /* ignore */ }
  }, [storageKey]);

  const saveAsGuide = useCallback(async (content: string, title?: string) => {
    if (!studyGuideContext) return null;
    const token = localStorage.getItem('token') || '';
    const apiBase = import.meta.env.VITE_API_URL ?? '';
    const res = await fetch(`${apiBase}/api/study/guides/${studyGuideContext.id}/qa/save-as-guide`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content, title: title || '' }),
    });
    if (!res.ok) throw new Error(`Save failed: ${res.status}`);
    return res.json();
  }, [studyGuideContext]);

  const saveAsMaterial = useCallback(async (content: string, title?: string) => {
    if (!studyGuideContext) return null;
    const token = localStorage.getItem('token') || '';
    const apiBase = import.meta.env.VITE_API_URL ?? '';
    const res = await fetch(`${apiBase}/api/study/guides/${studyGuideContext.id}/qa/save-as-material`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content, title: title || '' }),
    });
    if (!res.ok) throw new Error(`Save failed: ${res.status}`);
    return res.json();
  }, [studyGuideContext]);

  return {
    messages, sendMessage, isLoading, error, clearMessages,
    saveAsGuide, saveAsMaterial,
    isStudyMode: !!studyGuideContext,
  };
}
