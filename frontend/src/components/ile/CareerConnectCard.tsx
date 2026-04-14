/**
 * CareerConnectCard — CB-ILE-001 M3
 *
 * Dismissable card shown on session results page that connects
 * the session topic to a real-world career.
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ileApi } from '../../api/ile';

interface CareerConnectCardProps {
  sessionId: number;
  topic: string;
}

export function CareerConnectCard({ sessionId, topic }: CareerConnectCardProps) {
  const [dismissed, setDismissed] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['ile-career-connect', sessionId],
    queryFn: () => ileApi.getCareerConnect(sessionId),
    retry: false,
    staleTime: Infinity,
  });

  if (dismissed || isError || (!isLoading && !data)) return null;

  return (
    <div className="fts-career-connect">
      <button
        className="fts-career-dismiss"
        onClick={() => setDismissed(true)}
        aria-label="Dismiss career connection"
      >
        &times;
      </button>
      {isLoading ? (
        <p className="fts-career-loading">Finding a career connection...</p>
      ) : data ? (
        <>
          <p className="fts-career-label">Did you know?</p>
          <p className="fts-career-text">
            Students interested in <strong>{data.career}</strong> use{' '}
            <strong>{topic}</strong> to {data.connection}
          </p>
        </>
      ) : null}
    </div>
  );
}
