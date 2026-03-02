import { api } from './client';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface SubjectAnalysis {
  trend: 'improving' | 'declining' | 'stable' | string;
  avg_score: number;
  note: string;
}

export interface AIInsight {
  id: number;
  student_id: number;
  insight_type: 'weekly' | 'monthly' | 'on_demand' | string;
  summary: string;
  strengths: string[] | null;
  concerns: string[] | null;
  recommendations: string[] | null;
  subject_analysis: Record<string, SubjectAnalysis> | null;
  learning_style_note: string | null;
  parent_actions: string[] | null;
  generated_at: string;    // ISO datetime string
  period_start: string | null;
  period_end: string | null;
  exists?: boolean;         // only in /latest response
}

export interface AIInsightLatestResponse extends AIInsight {
  exists: true;
}

export interface AIInsightNotFound {
  exists: false;
}

export type LatestInsightResponse = AIInsightLatestResponse | AIInsightNotFound;

export interface GenerateInsightRequest {
  student_id: number;
  insight_type?: 'weekly' | 'monthly' | 'on_demand';
}

// ─── API Client ───────────────────────────────────────────────────────────────

export const aiInsightsApi = {
  /**
   * Generate a new AI insight for a student.
   * Aggregates quiz history, grades, report cards, assignments, and study streak.
   */
  generate: async (data: GenerateInsightRequest): Promise<AIInsight> => {
    const res = await api.post<AIInsight>('/api/ai-insights/generate', data);
    return res.data;
  },

  /**
   * List all insights accessible to the current user.
   */
  list: async (): Promise<AIInsight[]> => {
    const res = await api.get<AIInsight[]>('/api/ai-insights/');
    return res.data;
  },

  /**
   * Get a specific insight by ID.
   */
  get: async (id: number): Promise<AIInsight> => {
    const res = await api.get<AIInsight>(`/api/ai-insights/${id}`);
    return res.data;
  },

  /**
   * Delete an insight.
   */
  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/ai-insights/${id}`);
  },

  /**
   * Get the latest insight for a student.
   * Returns { exists: false } if no insight has been generated yet.
   */
  getLatest: async (studentId: number): Promise<LatestInsightResponse> => {
    const res = await api.get<LatestInsightResponse>(`/api/ai-insights/student/${studentId}/latest`);
    return res.data;
  },
};
