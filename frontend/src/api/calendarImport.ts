import { api } from './client';

export interface CalendarFeed {
  id: number;
  url: string;
  name: string | null;
  last_synced: string | null;
  event_count: number;
  is_active: boolean;
  created_at: string;
}

export interface CalendarEvent {
  id: number;
  feed_id: number;
  uid: string;
  title: string;
  description: string | null;
  start_date: string;
  end_date: string | null;
  all_day: boolean;
  location: string | null;
  created_at: string;
}

export const calendarImportApi = {
  async addFeed(url: string): Promise<CalendarFeed> {
    const { data } = await api.post<CalendarFeed>('/api/import/calendar', { url });
    return data;
  },

  async listFeeds(): Promise<CalendarFeed[]> {
    const { data } = await api.get<CalendarFeed[]>('/api/import/calendar');
    return data;
  },

  async syncFeed(feedId: number): Promise<CalendarFeed> {
    const { data } = await api.post<CalendarFeed>(`/api/import/calendar/${feedId}/sync`);
    return data;
  },

  async deleteFeed(feedId: number): Promise<void> {
    await api.delete(`/api/import/calendar/${feedId}`);
  },

  async listEvents(params?: { start?: string; end?: string; feed_id?: number }): Promise<CalendarEvent[]> {
    const { data } = await api.get<CalendarEvent[]>('/api/calendar-events', { params });
    return data;
  },
};
