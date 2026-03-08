import { api } from './client';

export interface ReadinessQuestion {
  id: number;
  type: 'multiple_choice' | 'short_answer' | 'application';
  question: string;
  options?: string[];
}

export interface ReadinessCheckResponse {
  id: number;
  student_id: number;
  course_id: number;
  topic: string | null;
  questions: ReadinessQuestion[];
  created_at: string;
}

export interface TopicBreakdown {
  topic: string;
  score: number;
  status: 'strong' | 'developing' | 'needs_work';
  feedback: string;
}

export interface ReadinessReport {
  id: number;
  student_id: number;
  student_name: string;
  course_name: string;
  topic: string | null;
  overall_score: number;
  summary: string;
  topic_breakdown: TopicBreakdown[];
  suggestions: string[];
  questions: ReadinessQuestion[];
  answers: { question_id: number; answer: string }[] | null;
  created_at: string;
  completed_at: string | null;
}

export interface ReadinessListItem {
  id: number;
  student_name: string;
  course_name: string;
  topic: string | null;
  overall_score: number | null;
  status: 'pending' | 'completed';
  created_at: string;
}

export const readinessApi = {
  create: (data: { student_id: number; course_id: number; topic?: string }) =>
    api.post<ReadinessCheckResponse>('/api/readiness-check', data).then(r => r.data),

  submit: (id: number, answers: { question_id: number; answer: string }[]) =>
    api.post<{ message: string; id: number; overall_score: number }>(
      `/api/readiness-check/${id}/submit`, { answers }
    ).then(r => r.data),

  getReport: (id: number) =>
    api.get<ReadinessReport>(`/api/readiness-check/${id}/report`).then(r => r.data),

  list: () =>
    api.get<ReadinessListItem[]>('/api/readiness-check').then(r => r.data),
};
