import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

export interface JourneyHint {
  hint_key: string;
  title: string;
  description: string;
  journey_id: string;
  journey_url: string;
  diagram_url: string;
}

export interface UseJourneyHintResult {
  hint: JourneyHint | null;
  loading: boolean;
  dismiss: () => Promise<void>;
  snooze: () => Promise<void>;
  suppressAll: () => Promise<void>;
}

const SESSION_KEY = 'journey_hint_session_count';
const MAX_PER_SESSION = 3;

export function useJourneyHint(pageName: string): UseJourneyHintResult {
  const [hint, setHint] = useState<JourneyHint | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const fetchHint = async () => {
      // Session frequency cap
      const count = parseInt(sessionStorage.getItem(SESSION_KEY) || '0', 10);
      if (count >= MAX_PER_SESSION) {
        setLoading(false);
        return;
      }

      try {
        const res = await api.get<{ hint: JourneyHint | null }>('/api/journey/hints', {
          params: { page: pageName },
        });
        if (!cancelled && res.data?.hint) {
          setHint(res.data.hint);
          // Increment session counter
          sessionStorage.setItem(SESSION_KEY, String(count + 1));
        }
      } catch {
        // API may not exist yet (parallel stream) — gracefully return null
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchHint();
    return () => { cancelled = true; };
  }, [pageName]);

  const dismiss = useCallback(async () => {
    if (!hint) return;
    setHint(null);
    try {
      await api.post(`/api/journey/hints/${hint.hint_key}/dismiss`);
    } catch {
      // Silently fail — API may not exist yet
    }
  }, [hint]);

  const snooze = useCallback(async () => {
    if (!hint) return;
    setHint(null);
    try {
      await api.post(`/api/journey/hints/${hint.hint_key}/snooze`);
    } catch {
      // Silently fail
    }
  }, [hint]);

  const suppressAll = useCallback(async () => {
    setHint(null);
    try {
      await api.post('/api/journey/hints/suppress-all');
    } catch {
      // Silently fail
    }
  }, []);

  return { hint, loading, dismiss, snooze, suppressAll };
}
