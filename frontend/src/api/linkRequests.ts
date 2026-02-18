import { api } from './client';

export interface LinkRequestUser {
  id: number;
  full_name: string;
  email: string | null;
}

export interface LinkRequestItem {
  id: number;
  request_type: string;
  status: string;
  requester: LinkRequestUser;
  target: LinkRequestUser;
  student_id: number | null;
  relationship_type: string | null;
  message: string | null;
  created_at: string;
  expires_at: string;
  responded_at: string | null;
}

export const linkRequestsApi = {
  getPending: async () => {
    const response = await api.get<LinkRequestItem[]>('/api/link-requests');
    return response.data;
  },

  getSent: async () => {
    const response = await api.get<LinkRequestItem[]>('/api/link-requests/sent');
    return response.data;
  },

  respond: async (id: number, action: 'approve' | 'reject') => {
    const response = await api.post<{ message: string; status: string }>(
      `/api/link-requests/${id}/respond`,
      { action },
    );
    return response.data;
  },
};
