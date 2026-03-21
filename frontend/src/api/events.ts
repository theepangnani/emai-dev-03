import { api } from './client';

export interface DetectedEvent {
  id: number;
  student_id: number;
  course_id: number | null;
  course_content_id: number | null;
  event_type: string;
  event_title: string;
  event_date: string;
  source: string;
  dismissed: boolean;
  created_at: string | null;
  days_remaining: number | null;
}

export interface CreateEventPayload {
  event_type: string;
  event_title: string;
  event_date: string;
  course_id?: number | null;
  source?: string;
}

export const eventsApi = {
  getUpcoming: async (): Promise<DetectedEvent[]> => {
    const resp = await api.get('/api/events/upcoming');
    return resp.data;
  },
  create: async (data: CreateEventPayload): Promise<DetectedEvent> => {
    const resp = await api.post('/api/events', data);
    return resp.data;
  },
  dismiss: async (eventId: number): Promise<void> => {
    await api.delete(`/api/events/${eventId}`);
  },
};
