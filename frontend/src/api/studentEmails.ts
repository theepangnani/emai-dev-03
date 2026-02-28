import { api } from './client';

export type EmailType = 'personal' | 'school';

export interface StudentEmailItem {
  id: number;
  student_id: number;
  email: string;
  email_type: EmailType;
  is_primary: boolean;
  verified_at: string | null;
  created_at: string;
}

export interface StudentEmailCreatePayload {
  email: string;
  email_type: EmailType;
}

export const studentEmailsApi = {
  list: async () => {
    const response = await api.get<StudentEmailItem[]>('/api/users/me/emails');
    return response.data;
  },

  add: async (payload: StudentEmailCreatePayload) => {
    const response = await api.post<StudentEmailItem>('/api/users/me/emails', payload);
    return response.data;
  },

  setPrimary: async (emailId: number) => {
    const response = await api.put<StudentEmailItem>('/api/users/me/emails/primary', {
      email_id: emailId,
    });
    return response.data;
  },

  remove: async (emailId: number) => {
    await api.delete(`/api/users/me/emails/${emailId}`);
  },

  verify: async (emailId: number) => {
    const response = await api.put<StudentEmailItem>(`/api/users/me/emails/${emailId}/verify`);
    return response.data;
  },
};
