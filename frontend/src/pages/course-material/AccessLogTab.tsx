import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { courseContentsApi, type AccessLogResponse } from '../../api/client';

interface AccessLogTabProps {
  contentId: number;
}

const DAY_OPTIONS = [
  { value: 7, label: 'Last 7 days' },
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
];

export function AccessLogTab({ contentId }: AccessLogTabProps) {
  const [days, setDays] = useState(30);

  const { data, isLoading, error } = useQuery<AccessLogResponse>({
    queryKey: ['access-log', contentId, days],
    queryFn: () => courseContentsApi.getAccessLog(contentId, { days }),
    enabled: contentId > 0,
  });

  if (isLoading) {
    return <div className="access-log-loading">Loading access log...</div>;
  }

  if (error) {
    return <div className="access-log-error">Unable to load access log.</div>;
  }

  const events = data?.events ?? [];
  const summary = data?.summary ?? { total_views: 0, total_downloads: 0, unique_viewers: 0 };

  return (
    <div className="access-log-tab">
      {/* Summary stats */}
      <div className="access-log-summary">
        <div className="access-log-stat">
          <span className="access-log-stat-value">{summary.total_views}</span>
          <span className="access-log-stat-label">Views</span>
        </div>
        <div className="access-log-stat">
          <span className="access-log-stat-value">{summary.total_downloads}</span>
          <span className="access-log-stat-label">Downloads</span>
        </div>
        <div className="access-log-stat">
          <span className="access-log-stat-value">{summary.unique_viewers}</span>
          <span className="access-log-stat-label">Unique Viewers</span>
        </div>
      </div>

      {/* Date range filter */}
      <div className="access-log-filters">
        <select
          className="access-log-select"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
        >
          {DAY_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* Events table */}
      {events.length === 0 ? (
        <p className="access-log-empty">No access events in this time period.</p>
      ) : (
        <div className="access-log-table-wrap">
          <table className="access-log-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Action</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event, idx) => (
                <tr key={idx}>
                  <td>{event.user_name}</td>
                  <td><span className={`access-log-role ${event.role}`}>{event.role}</span></td>
                  <td>{event.action}</td>
                  <td>{event.timestamp ? new Date(event.timestamp).toLocaleString() : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
