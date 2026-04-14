/**
 * CareerConnectCard — CB-ILE-001 M3
 *
 * Dismissable card shown on session results page that connects
 * the session topic to a real-world career.
 *
 * Fully self-contained: any API or rendering failure returns null
 * so the parent results page is never affected.
 */
import { Component, useState } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ileApi } from '../../api/ile';

/* ---------- local error boundary ---------- */

interface BoundaryProps {
  children: ReactNode;
}

class CareerConnectBoundary extends Component<BoundaryProps, { hasError: boolean }> {
  state = { hasError: false };

  static getDerivedStateFromError(): { hasError: boolean } {
    return { hasError: true };
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  componentDidCatch(_error: Error, _info: ErrorInfo): void {
    // Swallow — the card is non-critical
  }

  render() {
    if (this.state.hasError) return null;
    return this.props.children;
  }
}

/* ---------- inner card ---------- */

interface CareerConnectCardProps {
  sessionId: number;
  topic: string;
}

function CareerConnectCardInner({ sessionId, topic }: CareerConnectCardProps) {
  const [dismissed, setDismissed] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['ile-career-connect', sessionId],
    queryFn: () => ileApi.getCareerConnect(sessionId),
    retry: false,
    staleTime: Infinity,
  });

  if (dismissed || isError || (!isLoading && !data)) return null;

  // Guard against null, undefined, empty, or whitespace-only career/connection
  if (!isLoading && data && (!data.career?.trim() || !data.connection?.trim())) return null;

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

/* ---------- public export ---------- */

export function CareerConnectCard(props: CareerConnectCardProps) {
  return (
    <CareerConnectBoundary>
      <CareerConnectCardInner {...props} />
    </CareerConnectBoundary>
  );
}
