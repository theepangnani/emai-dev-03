import { useState, useEffect } from 'react';
import { courseContentsApi } from '../../api/client';
import type { AccessLogEntry } from '../../api/client';

interface AccessLogTabProps {
  courseContentId: number;
}

const DATE_RANGE_OPTIONS = [
  { value: 7, label: 'Last 7 days' },
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
  { value: 0, label: 'All time' },
];

export function AccessLogTab({ courseContentId }: AccessLogTabProps) {
  const [entries, setEntries] = useState<AccessLogEntry[]>([]);
  const [totalViews, setTotalViews] = useState(0);
  const [totalDownloads, setTotalDownloads] = useState(0);
  const [uniqueViewers, setUniqueViewers] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [endpointMissing, setEndpointMissing] = useState(false);
  const [days, setDays] = useState(30);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setEndpointMissing(false);

    courseContentsApi.getAccessLog(courseContentId, days ? { days } : undefined)
      .then(data => {
        if (cancelled) return;
        setEntries(data.entries);
        setTotalViews(data.total_views);
        setTotalDownloads(data.total_downloads);
        setUniqueViewers(data.unique_viewers);
      })
      .catch(err => {
        if (cancelled) return;
        if (err?.response?.status === 404) {
          setEndpointMissing(true);
        } else {
          setError('Failed to load access log');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [courseContentId, days]);

  if (loading) {
    return (
      <div className="access-log-tab">
        <div className="access-log-loading">Loading access log...</div>
      </div>
    );
  }

  if (endpointMissing) {
    return (
      <div className="access-log-tab">
        <div className="access-log-coming-soon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M12 7v5l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <h3>Access Log — Coming Soon</h3>
          <p>The access log feature is being developed. You will be able to see who viewed or downloaded this material and when.</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="access-log-tab">
        <div className="access-log-error">{error}</div>
      </div>
    );
  }

  return (
    <div className="access-log-tab">
      <div className="access-log-stats">
        <div className="access-log-stat">
          <span className="access-log-stat-value">{totalViews}</span>
          <span className="access-log-stat-label">Total Views</span>
        </div>
        <div className="access-log-stat">
          <span className="access-log-stat-value">{totalDownloads}</span>
          <span className="access-log-stat-label">Total Downloads</span>
        </div>
        <div className="access-log-stat">
          <span className="access-log-stat-value">{uniqueViewers}</span>
          <span className="access-log-stat-label">Unique Viewers</span>
        </div>
      </div>

      <div className="access-log-filter">
        <label htmlFor="access-log-range">Date range:</label>
        <select
          id="access-log-range"
          value={days}
          onChange={e => setDays(Number(e.target.value))}
        >
          {DATE_RANGE_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {entries.length === 0 ? (
        <p className="access-log-empty">No access log entries for this period.</p>
      ) : (
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
            {entries.map(entry => (
              <tr key={entry.id}>
                <td>{entry.user_name}</td>
                <td><span className={`access-log-role ${entry.user_role}`}>{entry.user_role}</span></td>
                <td>{entry.action}</td>
                <td>{new Date(entry.timestamp).toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
