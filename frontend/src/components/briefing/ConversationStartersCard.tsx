import { useState, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { conversationStartersApi } from '../../api/conversationStarters';
import type { ConversationStartersResponse } from '../../api/conversationStarters';
import './ConversationStartersCard.css';

interface Props {
  /** If provided, generate for a specific child. Otherwise uses daily endpoint. */
  studentId?: number;
}

export function ConversationStartersCard({ studentId }: Props) {
  const queryClient = useQueryClient();
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const { data, isLoading, error } = useQuery<ConversationStartersResponse>({
    queryKey: ['conversation-starters', studentId ?? 'daily'],
    queryFn: () =>
      studentId
        ? conversationStartersApi.generate(studentId)
        : conversationStartersApi.getDaily(),
    staleTime: 5 * 60 * 1000, // 5 min
    retry: 1,
  });

  const handleRefresh = useCallback(async () => {
    if (!studentId || isRefreshing) return;
    setIsRefreshing(true);
    try {
      const fresh = await conversationStartersApi.generate(studentId);
      queryClient.setQueryData(['conversation-starters', studentId], fresh);
    } catch {
      // silently fail — stale data still visible
    } finally {
      setIsRefreshing(false);
    }
  }, [studentId, isRefreshing, queryClient]);

  const handleCopy = useCallback((text: string, idx: number) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 2000);
    });
  }, []);

  if (isLoading) {
    return (
      <div className="conv-starters-card">
        <div className="conv-starters-loading">
          <div className="conv-starters-spinner" />
          Generating conversation ideas...
        </div>
      </div>
    );
  }

  if (error) {
    const msg = (error as { response?: { status?: number } })?.response?.status === 429
      ? 'AI credit limit reached. Request more credits from settings.'
      : 'Could not load conversation starters.';
    return (
      <div className="conv-starters-card">
        <div className="conv-starters-error">{msg}</div>
      </div>
    );
  }

  if (!data || data.starters.length === 0) {
    return (
      <div className="conv-starters-card">
        <div className="conv-starters-empty">No conversation starters yet. Link a child to get started.</div>
      </div>
    );
  }

  return (
    <div className="conv-starters-card">
      <div className="conv-starters-header">
        <h4 className="conv-starters-title">
          <span className="conv-starters-title-icon" aria-hidden="true">&#128172;</span>
          Dinner Table Talk
        </h4>
        {studentId && (
          <button
            className="conv-starters-refresh"
            onClick={handleRefresh}
            disabled={isRefreshing}
            title="Generate new conversation starters"
          >
            {isRefreshing ? 'Generating...' : 'Refresh'}
          </button>
        )}
      </div>
      <p className="conv-starters-subtitle">
        Natural ways to chat with {data.student_name} about school
      </p>
      <ul className="conv-starters-list">
        {data.starters.map((s, i) => (
          <li key={i} className="conv-starter-item">
            <span className="conv-starter-quote" aria-hidden="true">&#8220;</span>
            <div className="conv-starter-body">
              <p className="conv-starter-prompt">{s.prompt}</p>
              {s.context && <p className="conv-starter-context">{s.context}</p>}
            </div>
            <button
              className={`conv-starter-copy ${copiedIdx === i ? 'conv-starter-copy--copied' : ''}`}
              onClick={() => handleCopy(s.prompt, i)}
              title="Copy to clipboard"
            >
              {copiedIdx === i ? 'Copied!' : 'Copy'}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
