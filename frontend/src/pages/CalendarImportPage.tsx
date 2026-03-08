import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { calendarImportApi } from '../api/calendarImport';
import type { CalendarFeed } from '../api/calendarImport';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import './CalendarImportPage.css';

export function CalendarImportPage() {
  const queryClient = useQueryClient();
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');

  const feedsQuery = useQuery({
    queryKey: ['calendarFeeds'],
    queryFn: calendarImportApi.listFeeds,
  });

  const addMutation = useMutation({
    mutationFn: (feedUrl: string) => calendarImportApi.addFeed(feedUrl),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendarFeeds'] });
      setUrl('');
      setError('');
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail || 'Failed to import calendar');
    },
  });

  const syncMutation = useMutation({
    mutationFn: (feedId: number) => calendarImportApi.syncFeed(feedId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendarFeeds'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (feedId: number) => calendarImportApi.deleteFeed(feedId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendarFeeds'] });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setError('');
    addMutation.mutate(url.trim());
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleString();
  };

  return (
    <DashboardLayout>
      <div className="calendar-import">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Calendar Import' },
        ]} />

        <h1 className="calendar-import-title">Calendar Import</h1>
        <p className="calendar-import-subtitle">
          Paste a school calendar ICS URL to automatically sync events.
        </p>

        <form className="calendar-import-form" onSubmit={handleSubmit}>
          <input
            type="url"
            className="calendar-import-input"
            placeholder="Paste ICS calendar URL (e.g., https://school.edu/calendar.ics)"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={addMutation.isPending}
          />
          <button
            type="submit"
            className="calendar-import-btn"
            disabled={addMutation.isPending || !url.trim()}
          >
            {addMutation.isPending ? 'Importing...' : 'Import'}
          </button>
        </form>

        {error && <div className="calendar-import-error">{error}</div>}

        <section className="calendar-feeds-section">
          <h2>Imported Calendars</h2>

          {feedsQuery.isLoading && <p>Loading...</p>}

          {feedsQuery.data?.length === 0 && (
            <p className="calendar-feeds-empty">No calendars imported yet.</p>
          )}

          {feedsQuery.data?.map((feed: CalendarFeed) => (
            <div key={feed.id} className="calendar-feed-card">
              <div className="calendar-feed-info">
                <h3 className="calendar-feed-name">
                  {feed.name || 'Unnamed Calendar'}
                </h3>
                <p className="calendar-feed-url">{feed.url}</p>
                <div className="calendar-feed-meta">
                  <span>{feed.event_count} events</span>
                  <span>Last synced: {formatDate(feed.last_synced)}</span>
                </div>
              </div>
              <div className="calendar-feed-actions">
                <button
                  className="calendar-feed-sync-btn"
                  onClick={() => syncMutation.mutate(feed.id)}
                  disabled={syncMutation.isPending}
                >
                  {syncMutation.isPending ? 'Syncing...' : 'Sync Now'}
                </button>
                <button
                  className="calendar-feed-delete-btn"
                  onClick={() => {
                    if (confirm('Remove this calendar and all its events?')) {
                      deleteMutation.mutate(feed.id);
                    }
                  }}
                  disabled={deleteMutation.isPending}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </section>
      </div>
    </DashboardLayout>
  );
}
