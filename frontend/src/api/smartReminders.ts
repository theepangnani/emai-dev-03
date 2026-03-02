import { api } from './client';

export type ReminderUrgency = 'low' | 'medium' | 'high' | 'critical';

export interface ReminderPreferences {
  user_id: number;
  remind_3_days: boolean;
  remind_1_day: boolean;
  remind_3_hours: boolean;
  remind_overdue: boolean;
  ai_personalized_messages: boolean;
  parent_escalation_hours: number;
  updated_at: string | null;
}

export interface ReminderPreferenceUpdate {
  remind_3_days?: boolean;
  remind_1_day?: boolean;
  remind_3_hours?: boolean;
  remind_overdue?: boolean;
  ai_personalized_messages?: boolean;
  parent_escalation_hours?: number;
}

export interface ReminderLog {
  id: number;
  user_id: number;
  assignment_id: number | null;
  urgency: ReminderUrgency;
  message: string;
  sent_at: string;
  channel: string;
  priority_score: number | null;
}

export interface ReminderStats {
  sent_today: number;
  by_urgency: Record<ReminderUrgency, number>;
  total_all_time: number;
}

export interface TriggerResult {
  sent: number;
  skipped: number;
  errors: number;
  message: string;
}

export const smartRemindersApi = {
  getPreferences: async (): Promise<ReminderPreferences> => {
    const res = await api.get<ReminderPreferences>('/api/reminders/preferences');
    return res.data;
  },

  updatePreferences: async (payload: ReminderPreferenceUpdate): Promise<ReminderPreferences> => {
    const res = await api.put<ReminderPreferences>('/api/reminders/preferences', payload);
    return res.data;
  },

  getLogs: async (limit = 50): Promise<ReminderLog[]> => {
    const res = await api.get<ReminderLog[]>('/api/reminders/logs', { params: { limit } });
    return res.data;
  },

  triggerRun: async (): Promise<TriggerResult> => {
    const res = await api.post<TriggerResult>('/api/reminders/test');
    return res.data;
  },

  getStats: async (): Promise<ReminderStats> => {
    const res = await api.get<ReminderStats>('/api/reminders/stats');
    return res.data;
  },
};
