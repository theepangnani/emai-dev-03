import { api } from './client';

export interface AIUsageResponse {
  count: number;
  limit: number;
  remaining: number;
  at_limit: boolean;
  warning_threshold: number;
  period: string;
  reset_date: string;
}

export interface AIUsageRequestData {
  requested_amount: number;
  reason?: string;
}

export interface AIUsageRequestResponse {
  id: number;
  status: string;
  message: string;
}

export const aiUsageApi = {
  getUsage: async () => {
    const response = await api.get<AIUsageResponse>('/api/ai-usage');
    return response.data;
  },

  requestMore: async (data: AIUsageRequestData) => {
    const response = await api.post<AIUsageRequestResponse>('/api/ai-usage/request', data);
    return response.data;
  },
};
