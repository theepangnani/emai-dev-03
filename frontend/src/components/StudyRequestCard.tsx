import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { studyRequestsApi, type StudyRequestData } from '../api/studyRequests';

interface StudyRequestCardProps {
  requests: StudyRequestData[];
  onUpdate?: () => void;
}

const urgencyLabels: Record<string, string> = {
  low: 'when you have time',
  normal: 'this week',
  high: 'before your next class',
};

export function StudyRequestCard({ requests, onUpdate }: StudyRequestCardProps) {
  const navigate = useNavigate();
  const [responding, setResponding] = useState<number | null>(null);

  if (requests.length === 0) return null;

  const handleRespond = async (
    id: number,
    status: 'accepted' | 'deferred' | 'completed',
  ) => {
    setResponding(id);
    try {
      await studyRequestsApi.respond(id, { status });
      onUpdate?.();
      if (status === 'accepted') {
        navigate('/course-materials');
      }
    } catch {
      // Silently fail — notification will remain
    } finally {
      setResponding(null);
    }
  };

  return (
    <section className="sd-alerts">
      <h2 className="sd-section-label">Study Requests from Parent</h2>
      <div className="sd-alerts-list">
        {requests.map((sr) => (
          <div key={sr.id} className="sd-alert-card parent_request">
            <span className="sd-alert-icon">{'\u{1F4E9}'}</span>
            <div className="sd-alert-body">
              <span className="sd-alert-label">
                {sr.parent_name || 'Your parent'} suggested
              </span>
              <span className="sd-alert-title">
                {sr.subject}
                {sr.topic ? ` — ${sr.topic}` : ''}
                {' '}({urgencyLabels[sr.urgency] || sr.urgency})
              </span>
              {sr.message && (
                <span className="sd-alert-title" style={{ fontSize: 13, opacity: 0.8, marginTop: 2 }}>
                  &quot;{sr.message}&quot;
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
              <button
                className="generate-btn"
                style={{ fontSize: 12, padding: '4px 10px' }}
                onClick={() => handleRespond(sr.id, 'accepted')}
                disabled={responding === sr.id}
              >
                Accept
              </button>
              <button
                className="cancel-btn"
                style={{ fontSize: 12, padding: '4px 10px' }}
                onClick={() => handleRespond(sr.id, 'deferred')}
                disabled={responding === sr.id}
              >
                Defer
              </button>
              <button
                className="cancel-btn"
                style={{ fontSize: 12, padding: '4px 10px' }}
                onClick={() => handleRespond(sr.id, 'completed')}
                disabled={responding === sr.id}
              >
                Done
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
