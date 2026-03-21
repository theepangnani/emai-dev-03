import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { eventsApi, type DetectedEvent } from '../api/events';
import './AssessmentCountdown.css';

function getUrgencyClass(days: number): string {
  if (days < 3) return 'ac-days-badge--red';
  if (days <= 7) return 'ac-days-badge--yellow';
  return 'ac-days-badge--green';
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function AssessmentCountdown() {
  const queryClient = useQueryClient();

  const { data: events, isLoading } = useQuery({
    queryKey: ['events-upcoming'],
    queryFn: eventsApi.getUpcoming,
  });

  const dismissMutation = useMutation({
    mutationFn: eventsApi.dismiss,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events-upcoming'] });
    },
  });

  if (isLoading) {
    return (
      <section className="ac-section" aria-busy="true" aria-label="Loading assessments">
        <div className="skeleton" style={{ height: 60, borderRadius: 12 }} />
      </section>
    );
  }

  if (!events || events.length === 0) return null;

  return (
    <section className="ac-section">
      <h2 className="ac-section-label">Upcoming Assessments</h2>
      <div className="ac-cards">
        {events.map((event: DetectedEvent) => {
          const days = event.days_remaining ?? 0;
          return (
            <div key={event.id} className="ac-card">
              <div className={`ac-days-badge ${getUrgencyClass(days)}`}>
                {days}
                <span className="ac-days-label">{days === 1 ? 'day' : 'days'}</span>
              </div>
              <div className="ac-card-body">
                <div className="ac-card-title">{event.event_title}</div>
                <div className="ac-card-meta">
                  <span className="ac-card-type">{event.event_type}</span>
                  {' \u00B7 '}
                  {formatDate(event.event_date)}
                </div>
              </div>
              <button
                className="ac-dismiss"
                onClick={() => dismissMutation.mutate(event.id)}
                aria-label={`Dismiss ${event.event_title}`}
                disabled={dismissMutation.isPending}
              >
                &times;
              </button>
            </div>
          );
        })}
      </div>
    </section>
  );
}
