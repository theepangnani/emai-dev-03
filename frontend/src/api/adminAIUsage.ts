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
  approved_amount: number | null;
  created_at: string;
  resolved_at: string | null;
}

export interface AILimitRequestList {
  items: AILimitRequest[];
  total: number;
}

export interface AIUsageSummary {
  total_ai_calls: number;
  top_users: Array<{ id: number; full_name: string; ai_usage_count: number }>;
}

export interface AIUsageHistoryEntry {
  id: number;
  user_id: number;
  generation_type: string;
  course_material_id: number | null;
  credits_used: number;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  estimated_cost_usd: number | null;
  model_name: string | null;
  is_regeneration: boolean;
  parent_generation_id: number | null;
  created_at: string;
  user_name: string | null;
  user_email: string | null;
  course_material_title: string | null;
}

export interface AICostSummary {
  total_cost_usd: number;
  total_tokens: number;
  by_type: Array<{ type: string; count: number; cost_usd: number; tokens: number }>;
  by_user: Array<{ user_id: number; name: string; count: number; cost_usd: number }>;
}

export interface AIUsageHistoryList {
  items: AIUsageHistoryEntry[];
  total: number;
}

export const adminAIUsageApi = {
  listUsers: (params?: { search?: string; sort_by?: string; sort_dir?: string; skip?: number; limit?: number }) =>
    api.get<AIUsageUserList>('/api/admin/ai-usage', { params }).then((r) => r.data),

  getSummary: () =>
    api.get<AIUsageSummary>('/api/admin/ai-usage/summary').then((r) => r.data),

  getCostSummary: (params?: { date_from?: string; date_to?: string }) =>
    api.get<AICostSummary>('/api/admin/ai-usage/cost-summary', { params }).then((r) => r.data),

  listRequests: (params?: { status?: string; skip?: number; limit?: number }) =>
    api.get<AILimitRequestList>('/api/admin/ai-usage/requests', { params }).then((r) => r.data),

  listHistory: (params?: {
    user_id?: number;
    generation_type?: string;
    type?: string;
    date_from?: string;
    date_to?: string;
    search?: string;
    skip?: number;
    limit?: number;
  }) =>
    api.get<AIUsageHistoryList>('/api/admin/ai-usage/history', { params }).then((r) => r.data),

  approveRequest: (id: number, amount: number) =>
    api.patch(`/api/admin/ai-usage/requests/${id}/approve`, { approved_amount: amount }).then((r) => r.data),

  declineRequest: (id: number) =>
    api.patch(`/api/admin/ai-usage/requests/${id}/decline`).then((r) => r.data),

  setUserLimit: (userId: number, limit: number) =>
    api.patch(`/api/admin/ai-usage/users/${userId}/limit`, { ai_usage_limit: limit }).then((r) => r.data),

  resetUserCount: (userId: number) =>
    api.post(`/api/admin/ai-usage/users/${userId}/reset`).then((r) => r.data),

  bulkSetLimit: (limit: number, resetCounts: boolean = false) =>
    api.post<{ updated_count: number; new_limit: number }>('/api/admin/ai-usage/bulk-set-limit', {
      ai_usage_limit: limit,
      reset_counts: resetCounts,
    }).then((r) => r.data),

  listAuditLog: async (params: { skip?: number; limit?: number }) => {
    const { data } = await api.get('/api/admin/ai-usage/audit-log', { params });
    return data;
  },
};
