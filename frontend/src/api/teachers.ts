import { api } from './client';

// Teacher Communication Types
export interface TeacherCommunication {
  id: number;
  user_id: number;
  type: 'email' | 'announcement' | 'comment';
  source_id: string;
  sender_name: string | null;
  sender_email: string | null;
  subject: string | null;
  body: string | null;
  snippet: string | null;
  ai_summary: string | null;
  course_name: string | null;
  is_read: boolean;
  received_at: string | null;
  created_at: string;
}

export interface TeacherCommunicationList {
  items: TeacherCommunication[];
  total: number;
  page: number;
  page_size: number;
}

export interface EmailMonitoringStatus {
  gmail_enabled: boolean;
  classroom_enabled: boolean;
  gmail_scope_granted: boolean;
  last_gmail_sync: string | null;
  last_classroom_sync: string | null;
  total_communications: number;
  unread_count: number;
}

// Teacher Communications API
export const teacherCommsApi = {
  list: async (params?: {
    page?: number;
    page_size?: number;
    type?: string;
    search?: string;
    unread_only?: boolean;
  }) => {
    const response = await api.get('/api/teacher-communications/', { params });
    return response.data as TeacherCommunicationList;
  },

  get: async (id: number) => {
    const response = await api.get(`/api/teacher-communications/${id}`);
    return response.data as TeacherCommunication;
  },

  getStatus: async () => {
    const response = await api.get('/api/teacher-communications/status');
    return response.data as EmailMonitoringStatus;
  },

  markAsRead: async (id: number) => {
    await api.put(`/api/teacher-communications/${id}/read`);
  },

  triggerSync: async () => {
    const response = await api.post('/api/teacher-communications/sync');
    return response.data as { synced: number };
  },

  getEmailMonitoringAuthUrl: async () => {
    const response = await api.get('/api/teacher-communications/auth/email-monitoring');
    return response.data as { authorization_url: string };
  },

  reply: async (id: number, body: string) => {
    const response = await api.post(`/api/teacher-communications/${id}/reply`, { body });
    return response.data as { status: string; to: string };
  },
};

// Teacher Thanks Types (#2226)
export interface TeacherThanksCount {
  teacher_id: number;
  total_count: number;
  week_count: number;
}

export interface TeacherThanksStatus {
  thanked_today: boolean;
}

export interface TeacherThanksResponse {
  id: number;
  from_user_id: number;
  teacher_id: number;
  course_id: number | null;
  message: string | null;
  created_at: string;
}

// Teacher Thanks API
export const teacherThanksApi = {
  sendThanks: async (teacherId: number, data: { course_id?: number; message?: string }) => {
    const response = await api.post(`/api/teachers/${teacherId}/thank`, data);
    return response.data as TeacherThanksResponse;
  },

  getThanksCount: async (teacherId: number) => {
    const response = await api.get(`/api/teachers/${teacherId}/thanks-count`);
    return response.data as TeacherThanksCount;
  },

  getThanksStatus: async (teacherId: number) => {
    const response = await api.get(`/api/teachers/${teacherId}/thanks-status`);
    return response.data as TeacherThanksStatus;
  },

  getMyThanksCount: async () => {
    const response = await api.get('/api/teachers/me/thanks-count');
    return response.data as TeacherThanksCount;
  },
};
