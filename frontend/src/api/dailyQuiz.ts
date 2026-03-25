import { api, AI_TIMEOUT } from './client';

export interface DailyQuizQuestion {
  question: string;
  options: { A: string; B: string; C: string; D: string };
  correct_answer: string;
  explanation: string;
}

export interface DailyQuizResponse {
  id: number;
  user_id: number;
  quiz_date: string;
  questions: DailyQuizQuestion[];
  total_questions: number;
  score: number | null;
  percentage: number | null;
  completed_at: string | null;
}

export interface DailyQuizSubmitResponse {
  score: number;
  total_questions: number;
  percentage: number;
  xp_awarded: number | null;
}

export const dailyQuizApi = {
  getQuiz: async () => {
    const response = await api.get('/api/quiz-of-the-day/', AI_TIMEOUT);
    return response.data as DailyQuizResponse;
  },

  submit: async (answers: Record<number, string>) => {
    const response = await api.post('/api/quiz-of-the-day/submit', { answers });
    return response.data as DailyQuizSubmitResponse;
  },
};
