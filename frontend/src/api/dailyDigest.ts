import { api } from './client';

export interface DigestSettings {
  daily_digest_enabled: boolean;
  email_consent_date: string | null;
}

export interface DailyDigestPreview {
  date: string;
  greeting: string;
  children: Array<{
    student_id: number;
    full_name: string;
    grade_level: number | null;
    overdue_tasks: Array<{ id: number; title: string; due_date: string | null; course_name: string | null; is_overdue: boolean }>;
    due_today_tasks: Array<{ id: number; title: string; due_date: string | null; course_name: string | null }>;
    upcoming_assignments: Array<{ id: number; title: string; due_date: string | null; course_name: string; status: string }>;
    recent_study_count: number;
    needs_attention: boolean;
  }>;
  total_overdue: number;
  total_due_today: number;
  total_upcoming: number;
  attention_needed: boolean;
}

export interface DigestSendResponse {
  success: boolean;
  message: string;
}

export const dailyDigestApi = {
  getSettings: async () => {
    const response = await api.get('/api/digest/settings');
    return response.data as DigestSettings;
  },
  updateSettings: async (settings: Partial<DigestSettings>) => {
    const response = await api.patch('/api/digest/settings', settings);
    return response.data as DigestSettings;
  },
  preview: async () => {
    const response = await api.get('/api/digest/daily/preview');
    return response.data as DailyDigestPreview;
  },
  send: async () => {
    const response = await api.post('/api/digest/daily/send');
    return response.data as DigestSendResponse;
  },
};
