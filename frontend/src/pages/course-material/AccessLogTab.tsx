import { useState, useEffect, useReducer } from 'react';
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

interface FetchState {
  entries: AccessLogEntry[];
  totalViews: number;
  totalDownloads: number;
  uniqueViewers: number;
  loading: boolean;
  error: string | null;
  endpointMissing: boolean;
}

type FetchAction =
  | { type: 'FETCH_START' }
  | { type: 'FETCH_SUCCESS'; data: { access_log: AccessLogEntry[]; total_views: number; total_downloads: number; unique_viewers: number } }
  | { type: 'FETCH_404' }
  | { type: 'FETCH_ERROR' };

function fetchReducer(state: FetchState, action: FetchAction): FetchState {
  switch (action.type) {
    case 'FETCH_START':
      return { ...state, loading: true, error: null, endpointMissing: false };
    case 'FETCH_SUCCESS':
      return { ...state, loading: false, entries: action.data.access_log, totalViews: action.data.total_views, totalDownloads: action.data.total_downloads, uniqueViewers: action.data.unique_viewers };
    case 'FETCH_404':
      return { ...state, loading: false, endpointMissing: true };
    case 'FETCH_ERROR':
      return { ...state, loading: false, error: 'Failed to load access log' };
  }
}

const initialState: FetchState = {
  entries: [], totalViews: 0, totalDownloads: 0, uniqueViewers: 0,
  loading: true, error: null, endpointMissing: false,
};

export function AccessLogTab({ courseContentId }: AccessLogTabProps) {
  const [state, dispatch] = useReducer(fetchReducer, initialState);
  const { entries, totalViews, totalDownloads, uniqueViewers, loading, error, endpointMissing } = state;
  const [days, setDays] = useState(30);

  useEffect(() => {
    let cancelled = false;
    dispatch({ type: 'FETCH_START' });

    courseContentsApi.getAccessLog(courseContentId, days ? { days } : undefined)
      .then(data => {
        if (!cancelled) dispatch({ type: 'FETCH_SUCCESS', data });
      })
      .catch(err => {
        if (cancelled) return;
        if (err?.response?.status === 404) {
          dispatch({ type: 'FETCH_404' });
        } else {
          dispatch({ type: 'FETCH_ERROR' });
        }
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
