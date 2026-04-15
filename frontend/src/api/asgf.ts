import { api } from './client';

export interface IntentClassifyResponse {
  subject: string;
  grade_level: string;
  topic: string;
  confidence: number;
  bloom_tier: string;
}

export const asgfApi = {
  classifyIntent: async (question: string): Promise<IntentClassifyResponse> => {
    const response = await api.post<IntentClassifyResponse>('/api/asgf/classify-intent', { question });
    return response.data;
  },
};
