import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api/client';

export interface JourneyHint {
  id: number;
  hint_key: string;
  message: string;
  cta_label?: string;
  cta_route?: string;
  priority?: number;
}

interface UseJourneyHintResult {
  hint: JourneyHint | null;
  loading: boolean;
  dismiss: () => void;
  snooze: () => void;
  suppressAll: () => void;
}

const SESSION_KEY = 'journey_hint_shown_count';
const MAX_PER_SESSION = 1;

function getSessionCount(): number {
  const val = sessionStorage.getItem(SESSION_KEY);
  return val ? parseInt(val, 10) : 0;
}

function incrementSessionCount(): void {
  sessionStorage.setItem(SESSION_KEY, String(getSessionCount() + 1));
}

export function useJourneyHint(pageName: string): UseJourneyHintResult {
  const [hint, setHint] = useState<JourneyHint | null>(null);
  const [loading, setLoading] = useState(true);
  const hintIdRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchHint() {
      // Enforce 1-hint-per-session cap
      if (getSessionCount() >= MAX_PER_SESSION) {
        setHint(null);
        setLoading(false);
        return;
      }

      try {
        const res = await api.get('/api/journey/hints/next', {
          params: { page_context: pageName },
        });
        if (!cancelled && res.data) {
          setHint(res.data);
          hintIdRef.current = res.data.id;
        }
      } catch {
        // API not available yet or no hint — render nothing
        if (!cancelled) setHint(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchHint();
    return () => { cancelled = true; };
  }, [pageName]);

  const dismiss = useCallback(() => {
    const id = hintIdRef.current;
    setHint(null);
    incrementSessionCount();
    if (id) {
      api.post(`/api/journey/hints/${id}/dismiss`).catch(() => {});
    }
  }, []);

  const snooze = useCallback(() => {
    const id = hintIdRef.current;
    setHint(null);
    incrementSessionCount();
    if (id) {
      api.post(`/api/journey/hints/${id}/snooze`).catch(() => {});
    }
  }, []);

  const suppressAll = useCallback(() => {
    setHint(null);
    incrementSessionCount();
    api.post('/api/journey/hints/suppress-all').catch(() => {});
  }, []);

  return { hint, loading, dismiss, snooze, suppressAll };
}
