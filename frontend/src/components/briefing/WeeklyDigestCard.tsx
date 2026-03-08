import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { weeklyDigestApi } from '../../api/weeklyDigest';
import type { WeeklyDigestResponse } from '../../api/weeklyDigest';
import './WeeklyDigestCard.css';

export function WeeklyDigestCard() {
  const [showPreview, setShowPreview] = useState(false);

  const {
    data: digest,
    isLoading,
    error,
    refetch,
  } = useQuery<WeeklyDigestResponse>({
    queryKey: ['weeklyDigest'],
    queryFn: weeklyDigestApi.preview,
    enabled: showPreview,
    staleTime: 60_000,
  });

  const sendMutation = useMutation({
    mutationFn: weeklyDigestApi.send,
  });

  const handleSend = () => {
    sendMutation.mutate(undefined, {
      onSuccess: () => {
        // auto-dismiss after 3s
        setTimeout(() => sendMutation.reset(), 3000);
      },
    });
  };

  if (!showPreview) {
    return (
      <button
        className="wd-trigger-btn"
        onClick={() => setShowPreview(true)}
        type="button"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>
        Preview Weekly Digest
      </button>
    );
  }

  return (
    <div className="wd-card">
      <div className="wd-card-header">
        <h3 className="wd-card-title">Weekly Progress Pulse</h3>
        <button
          className="wd-close-btn"
          onClick={() => { setShowPreview(false); sendMutation.reset(); }}
          aria-label="Close digest preview"
          type="button"
        >
          &times;
        </button>
      </div>

      {isLoading && (
        <div className="wd-loading">Loading digest...</div>
      )}

      {error && (
        <div className="wd-error">
          Failed to load digest.{' '}
          <button onClick={() => refetch()} type="button">Retry</button>
        </div>
      )}

      {digest && (
        <>
          <p className="wd-period">{digest.week_start} &mdash; {digest.week_end}</p>
          <p className="wd-greeting">{digest.greeting}</p>

          {digest.children.length === 0 ? (
            <p className="wd-empty">No children linked yet.</p>
          ) : (
            <div className="wd-children">
              {digest.children.map((child) => (
                <div key={child.student_id} className="wd-child">
                  <h4 className="wd-child-name">{child.full_name}</h4>
                  <p className="wd-child-highlight">{child.highlight}</p>

                  <div className="wd-child-stats">
                    <span className="wd-stat">
                      <strong>{child.tasks.completed}</strong>/{child.tasks.total} tasks
                    </span>
                    <span className="wd-stat">
                      <strong>{child.assignments.submitted}</strong>/{child.assignments.due} assignments
                    </span>
                    <span className="wd-stat">
                      <strong>{child.study_guides_created}</strong> guides
                    </span>
                    {child.quiz_scores.quiz_count > 0 && (
                      <span className="wd-stat">
                        <strong>{child.quiz_scores.average_percentage}%</strong> avg quiz
                      </span>
                    )}
                  </div>

                  {child.overdue_items.length > 0 && (
                    <div className="wd-overdue">
                      <span className="wd-overdue-label">Overdue ({child.overdue_items.length}):</span>
                      <ul className="wd-overdue-list">
                        {child.overdue_items.map((item) => (
                          <li key={`${item.item_type}-${item.id}`}>
                            {item.title} {item.due_date && <span className="wd-overdue-date">({item.due_date})</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          <p className="wd-summary">{digest.overall_summary}</p>

          <div className="wd-actions">
            <button
              className="wd-send-btn"
              onClick={handleSend}
              disabled={sendMutation.isPending}
              type="button"
            >
              {sendMutation.isPending ? 'Sending...' : 'Send to my email'}
            </button>
          </div>

          {sendMutation.isSuccess && (
            <p className="wd-success">{sendMutation.data?.message}</p>
          )}
          {sendMutation.isError && (
            <p className="wd-send-error">Failed to send. Please try again.</p>
          )}
        </>
      )}
    </div>
  );
}
