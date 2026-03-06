import { api } from './client';

export interface DeletionStatus {
  deletion_requested: boolean;
  deletion_confirmed: boolean;
  deletion_requested_at: string | null;
  deletion_confirmed_at: string | null;
  is_deleted: boolean;
  message: string;
}

export interface DeletionRequestItem {
  user_id: number;
  email: string | null;
  full_name: string;
  role: string | null;
  deletion_requested_at: string | null;
  deletion_confirmed_at: string | null;
  is_deleted: boolean;
}

export interface DeletionRequestList {
  items: DeletionRequestItem[];
  total: number;
}

export const accountDeletionApi = {
  getStatus: async (): Promise<DeletionStatus> => {
    const response = await api.get('/api/users/me/deletion-status');
    return response.data;
  },

  requestDeletion: async (): Promise<DeletionStatus> => {
    const response = await api.delete('/api/users/me/account');
    return response.data;
  },

  confirmDeletion: async (token: string): Promise<DeletionStatus> => {
    const response = await api.post('/api/users/me/confirm-deletion', { token });
    return response.data;
  },

  cancelDeletion: async (): Promise<DeletionStatus> => {
    const response = await api.post('/api/users/me/cancel-deletion');
    return response.data;
  },

  // Admin endpoints
  listDeletionRequests: async (params?: {
    status?: string;
    skip?: number;
    limit?: number;
  }): Promise<DeletionRequestList> => {
    const response = await api.get('/api/admin/deletion-requests', { params });
    return response.data;
  },

  processDeletion: async (userId: number): Promise<{ message: string }> => {
    const response = await api.post(`/api/admin/deletion-requests/${userId}/process`);
    return response.data;
  },
};
