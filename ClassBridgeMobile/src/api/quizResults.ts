import { api } from './client';

export interface QuizResultSummary {
  id: number;
  study_guide_id: number;
  quiz_title: string | null;
  score: number;
  total_questions: number;
  percentage: number;
  attempt_number: number;
  completed_at: string;
}

export interface QuizHistoryStats {
  total_attempts: number;
  unique_quizzes: number;
  average_score: number;
  best_score: number;
  recent_trend: 'improving' | 'declining' | 'stable';
}

export const quizResultsApi = {
  list: async (params?: { student_user_id?: number; limit?: number }) => {
    const response = await api.get('/api/quiz-results/', { params });
    return response.data as QuizResultSummary[];
  },

  stats: async (params?: { student_user_id?: number }) => {
    const response = await api.get('/api/quiz-results/stats', { params });
    return response.data as QuizHistoryStats;
  },
};
