import { api } from './client';

export interface StudyRequestData {
  id: number;
  parent_id: number;
  student_id: number;
  subject: string;
  topic: string | null;
  urgency: 'low' | 'normal' | 'high';
  message: string | null;
  status: 'pending' | 'accepted' | 'deferred' | 'completed';
  student_response: string | null;
  responded_at: string | null;
  created_at: string;
  parent_name: string | null;
}

export interface StudyRequestCreatePayload {
  student_id: number;
  subject: string;
  topic?: string;
  urgency?: 'low' | 'normal' | 'high';
  message?: string;
}

export interface StudyRequestRespondPayload {
  status: 'accepted' | 'deferred' | 'completed';
  response?: string;
}

export const studyRequestsApi = {
  create: async (data: StudyRequestCreatePayload): Promise<StudyRequestData> => {
    const resp = await api.post('/api/study-requests', data);
    return resp.data;
  },

  list: async (): Promise<StudyRequestData[]> => {
    const resp = await api.get('/api/study-requests');
    return resp.data;
  },

  get: async (id: number): Promise<StudyRequestData> => {
    const resp = await api.get(`/api/study-requests/${id}`);
    return resp.data;
  },

  respond: async (id: number, data: StudyRequestRespondPayload): Promise<StudyRequestData> => {
    const resp = await api.patch(`/api/study-requests/${id}/respond`, data);
    return resp.data;
  },

  pendingCount: async (): Promise<number> => {
    const resp = await api.get('/api/study-requests/pending');
    return resp.data.count;
  },
};
