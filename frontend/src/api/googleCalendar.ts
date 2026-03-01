import { api } from './client';

export interface CalendarStatus {
  connected: boolean;
  scope_granted: boolean;
}

export interface CalendarSyncResult {
  synced: number;
  message: string;
}

export interface CalendarConnectResult {
  authorization_url: string;
}

export const googleCalendarApi = {
  /** GET /api/google/calendar/status — check if user has calendar scope */
  getStatus: async (): Promise<CalendarStatus> => {
    const response = await api.get('/api/google/calendar/status');
    return response.data as CalendarStatus;
  },

  /** POST /api/google/calendar/connect — get OAuth URL to grant calendar.events scope */
  connect: async (): Promise<CalendarConnectResult> => {
    const response = await api.post('/api/google/calendar/connect');
    return response.data as CalendarConnectResult;
  },

  /** POST /api/google/calendar/sync — bulk-sync tasks with due dates to Google Calendar */
  sync: async (): Promise<CalendarSyncResult> => {
    const response = await api.post('/api/google/calendar/sync');
    return response.data as CalendarSyncResult;
  },

  /** DELETE /api/google/calendar/disconnect — stop calendar sync (removes scope preference) */
  disconnect: async (): Promise<{ message: string }> => {
    const response = await api.delete('/api/google/calendar/disconnect');
    return response.data as { message: string };
  },
};
