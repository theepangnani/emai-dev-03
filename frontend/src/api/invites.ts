import { api } from './client';

// Invite Types
export interface InviteResponse {
  id: number;
  email: string;
  invite_type: string;
  token: string;
  expires_at: string;
  invited_by_user_id: number;
  metadata_json: Record<string, any> | null;
  accepted_at: string | null;
  last_resent_at: string | null;
  created_at: string;
  status: 'pending' | 'accepted' | 'expired';
}

// Invites API
export const invitesApi = {
  create: async (data: { email: string; invite_type: string; metadata?: Record<string, any> }) => {
    const response = await api.post('/api/invites/', data);
    return response.data as InviteResponse;
  },

  inviteParent: async (parentEmail: string, studentId?: number) => {
    const response = await api.post('/api/invites/invite-parent', {
      parent_email: parentEmail,
      student_id: studentId,
    });
    return response.data;
  },

  inviteTeacher: async (teacherEmail: string) => {
    const response = await api.post('/api/invites/invite-teacher', {
      teacher_email: teacherEmail,
    });
    return response.data;
  },

  listSent: async () => {
    const response = await api.get('/api/invites/sent');
    return response.data as InviteResponse[];
  },

  resend: async (inviteId: number) => {
    const response = await api.post(`/api/invites/${inviteId}/resend`);
    return response.data as InviteResponse;
  },
};
