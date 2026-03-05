import { api } from './client';

export interface WaitlistEntry {
  id: number;
  full_name: string;
  email: string;
  roles: string[];
  status: 'pending' | 'approved' | 'registered' | 'declined';
  admin_notes: string | null;
  created_at: string;
  approved_at: string | null;
  registered_at: string | null;
}

export interface WaitlistStats {
  total: number;
  pending: number;
  approved: number;
  registered: number;
  declined: number;
}

export interface WaitlistListResponse {
  items: WaitlistEntry[];
  total: number;
}

export const adminWaitlistApi = {
  list: (params: { status?: string; search?: string; skip?: number; limit?: number }) =>
    api.get<WaitlistListResponse>('/api/admin/waitlist', { params }).then(r => r.data),

  stats: () =>
    api.get<WaitlistStats>('/api/admin/waitlist/stats').then(r => r.data),

  approve: (id: number) =>
    api.patch<WaitlistEntry>(`/api/admin/waitlist/${id}/approve`).then(r => r.data),

  decline: (id: number) =>
    api.patch<WaitlistEntry>(`/api/admin/waitlist/${id}/decline`).then(r => r.data),

  remind: (id: number) =>
    api.post<{ message: string }>(`/api/admin/waitlist/${id}/remind`).then(r => r.data),

  updateNotes: (id: number, notes: string) =>
    api.patch<WaitlistEntry>(`/api/admin/waitlist/${id}/notes`, { admin_notes: notes }).then(r => r.data),

  remove: (id: number) =>
    api.delete(`/api/admin/waitlist/${id}`).then(r => r.data),

  bulkApprove: (ids: number[]) =>
    api.post<{ approved: number }>('/api/admin/waitlist/bulk-approve', { ids }).then(r => r.data),
};
