import { api } from './client';

// Google Account Types
export interface GoogleAccount {
  id: number;
  google_email: string;
  display_name: string | null;
  account_label: string | null;
  is_primary: boolean;
  connected_at: string | null;
  last_sync_at: string | null;
}

// Google Classroom API
export const googleApi = {
  getAuthUrl: async () => {
    const response = await api.get('/api/google/auth');
    return response.data;
  },

  getConnectUrl: async (addAccount = false) => {
    const response = await api.get('/api/google/connect', { params: addAccount ? { add_account: true } : {} });
    return response.data;
  },

  getStatus: async () => {
    const response = await api.get('/api/google/status');
    return response.data;
  },

  disconnect: async () => {
    const response = await api.delete('/api/google/disconnect');
    return response.data;
  },

  getCourses: async () => {
    const response = await api.get('/api/google/courses');
    return response.data;
  },

  syncCourses: async (classroomType?: 'school' | 'private', accountId?: number) => {
    const params: Record<string, string | number> = {};
    if (classroomType) params.classroom_type = classroomType;
    if (accountId !== undefined) params.account_id = accountId;
    const response = await api.post('/api/google/courses/sync', null, { params });
    return response.data;
  },

  getAssignments: async (courseId: string) => {
    const response = await api.get(`/api/google/courses/${courseId}/assignments`);
    return response.data;
  },

  syncAssignments: async (courseId: string) => {
    const response = await api.post(`/api/google/courses/${courseId}/assignments/sync`);
    return response.data;
  },

  // Teacher multi-account management
  getTeacherAccounts: async () => {
    const response = await api.get('/api/google/teacher/accounts');
    return response.data as GoogleAccount[];
  },

  updateTeacherAccount: async (accountId: number, label?: string, setPrimary?: boolean) => {
    const params: Record<string, string | boolean> = {};
    if (label !== undefined) params.label = label;
    if (setPrimary) params.set_primary = true;
    const response = await api.patch(`/api/google/teacher/accounts/${accountId}`, null, { params });
    return response.data;
  },

  removeTeacherAccount: async (accountId: number) => {
    const response = await api.delete(`/api/google/teacher/accounts/${accountId}`);
    return response.data;
  },
};
