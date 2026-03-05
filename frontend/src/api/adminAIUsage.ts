import { api } from './client';

export interface AIUsageUser {
  id: number;
  full_name: string;
  email: string;
  role: string;
  ai_usage_count: number;
  ai_usage_limit: number;
}

export interface AIUsageUserList {
  items: AIUsageUser[];
  total: number;
}

export interface AILimitRequest {
  id: number;
  user_id: number;
  user_name: string;
  user_email: string;
  requested_amount: number;
  reason: string;
  status: 'pending' | 'approved' | 'declined';
  created_at: string;
}

export interface AILimitRequestList {
  items: AILimitRequest[];
  total: number;
}

export interface AIUsageSummary {
  total_ai_calls: number;
  top_users: Array<{ id: number; full_name: string; ai_usage_count: number }>;
}

export const adminAIUsageApi = {
  listUsers: (params?: { search?: string; sort_by?: string; sort_dir?: string; skip?: number; limit?: number }) =>
    api.get<AIUsageUserList>('/api/admin/ai-usage', { params }).then((r) => r.data),

  getSummary: () =>
    api.get<AIUsageSummary>('/api/admin/ai-usage/summary').then((r) => r.data),

  listRequests: (params?: { status?: string; skip?: number; limit?: number }) =>
    api.get<AILimitRequestList>('/api/admin/ai-usage/requests', { params }).then((r) => r.data),

  approveRequest: (id: number, amount: number) =>
    api.patch(`/api/admin/ai-usage/requests/${id}/approve`, { approved_amount: amount }).then((r) => r.data),

  declineRequest: (id: number) =>
    api.patch(`/api/admin/ai-usage/requests/${id}/decline`).then((r) => r.data),

  setUserLimit: (userId: number, limit: number) =>
    api.patch(`/api/admin/ai-usage/users/${userId}/limit`, { ai_usage_limit: limit }).then((r) => r.data),

  resetUserCount: (userId: number) =>
    api.post(`/api/admin/ai-usage/users/${userId}/reset`).then((r) => r.data),
};
