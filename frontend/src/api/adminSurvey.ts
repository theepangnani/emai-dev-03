import { api } from './client';

export interface SurveyStats {
  total_responses: number;
  by_role: Record<string, number>;
  completion_rate: number;
}

export interface SurveyQuestionAnalytics {
  question_key: string;
  question_text: string;
  question_type: string;
  total_answers: number;
  distribution: Record<string, number> | null;
  average: number | null;
  sub_item_averages: Record<string, number> | null;
  free_text_responses: string[] | null;
}

export interface DailySubmission {
  date: string;
  count: number;
}

export interface SurveyAnalytics {
  stats: SurveyStats;
  questions: SurveyQuestionAnalytics[];
  daily_submissions: DailySubmission[];
}

export interface SurveyResponseItem {
  id: number;
  session_id: string;
  role: string;
  completed: boolean;
  created_at: string;
  completed_at: string | null;
}

export interface SurveyAnswerItem {
  id: number;
  question_key: string;
  question_type: string;
  answer_value: any;
  created_at: string;
}

export interface SurveyResponseDetail extends SurveyResponseItem {
  answers: SurveyAnswerItem[];
}

export interface SurveyResponseList {
  items: SurveyResponseItem[];
  total: number;
}

export const adminSurveyApi = {
  analytics: (params: { role?: string; date_from?: string; date_to?: string }) =>
    api.get<SurveyAnalytics>('/api/admin/survey/analytics', { params }).then(r => r.data),

  responses: (params: { role?: string; date_from?: string; date_to?: string; skip?: number; limit?: number }) =>
    api.get<SurveyResponseList>('/api/admin/survey/responses', { params }).then(r => r.data),

  responseDetail: (id: number) =>
    api.get<SurveyResponseDetail>(`/api/admin/survey/responses/${id}`).then(r => r.data),

  exportCsv: (params: { role?: string; date_from?: string; date_to?: string }) =>
    api.get('/api/admin/survey/export/csv', { params, responseType: 'blob' }).then(r => {
      const url = window.URL.createObjectURL(new Blob([r.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `survey-export-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }),
};
