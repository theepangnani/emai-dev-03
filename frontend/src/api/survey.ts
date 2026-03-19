import { api } from './client';

export interface SurveyQuestion {
  key: string;
  text: string;
  type: 'single_select' | 'multi_select' | 'likert' | 'likert_matrix' | 'free_text';
  required: boolean;
  options?: string[];
  sub_items?: string[];
  allow_other?: boolean;
  likert_min_label?: string;
  likert_max_label?: string;
}

export interface SurveyAnswerPayload {
  question_key: string;
  question_type: string;
  answer_value: string | string[] | number | Record<string, number>;
}

export interface SurveySubmission {
  role: string;
  session_id: string;
  answers: SurveyAnswerPayload[];
}

export const surveyApi = {
  getQuestions: (role: string) =>
    api.get<SurveyQuestion[]>(`/api/survey/questions/${role}`).then(r => r.data),

  submit: (data: SurveySubmission) =>
    api.post('/api/survey', data).then(r => r.data),
};
