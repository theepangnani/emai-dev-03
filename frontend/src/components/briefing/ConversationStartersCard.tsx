import { useState, useCallback } from 'react';
import { conversationStartersApi } from '../../api/conversationStarters';
import type { ConversationStartersResponse } from '../../api/conversationStarters';
import './ConversationStartersCard.css';

interface Props {
  studentId: number;
}

export function ConversationStartersCard({ studentId }: Props) {
  const [data, setData] = useState<ConversationStartersResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const handleGenerate = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await conversationStartersApi.generate(studentId);
      setData(result);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setError(
        status === 429
          ? 'AI credit limit reached. Request more credits from settings.'
          : 'Could not generate conversation starters.'
      );
    } finally {
      setIsLoading(false);
    }
  }, [studentId]);

  const handleCopy = useCallback((text: string, idx: number) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 2000);
    });
  }, []);

  // Initial state — show generate button
  if (!data && !isLoading && !error) {
    return (
      <div className="conv-starters-card">
        <div className="conv-starters-header">
          <h4 className="conv-starters-title">
            <span className="conv-starters-title-icon" aria-hidden="true">&#128172;</span>
            Dinner Table Talk
          </h4>
        </div>
        <p className="conv-starters-subtitle">
          Get conversation starters to chat about school at dinner. Uses 1 AI credit.
        </p>
        <button className="conv-starters-generate" onClick={handleGenerate}>
          Generate Conversation Ideas
        </button>
      </div>
    );
  }

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
    return (
      <div className="conv-starters-card">
        <div className="conv-starters-error">{error}</div>
        <button className="conv-starters-generate" onClick={handleGenerate}>
          Try Again
        </button>
      </div>
    );
  }

  if (!data || data.starters.length === 0) {
    return (
      <div className="conv-starters-card">
        <div className="conv-starters-empty">No conversation starters generated.</div>
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
        <button
          className="conv-starters-refresh"
          onClick={handleGenerate}
          disabled={isLoading}
          title="Generate new conversation starters (uses 1 AI credit)"
        >
          {isLoading ? 'Generating...' : 'Refresh'}
        </button>
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
