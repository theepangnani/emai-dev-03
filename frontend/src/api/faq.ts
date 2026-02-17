import { api } from './client';

// ── Types ────────────────────────────────────────────────────────

export interface FAQQuestionItem {
  id: number;
  title: string;
  description: string | null;
  category: string;
  status: string;
  error_code: string | null;
  created_by_user_id: number;
  is_pinned: boolean;
  view_count: number;
  creator_name: string;
  answer_count: number;
  approved_answer_count: number;
  created_at: string;
  updated_at: string | null;
  archived_at: string | null;
}

export interface FAQAnswerItem {
  id: number;
  question_id: number;
  content: string;
  created_by_user_id: number;
  status: string;
  reviewed_by_user_id: number | null;
  reviewed_at: string | null;
  is_official: boolean;
  creator_name: string;
  reviewer_name: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface FAQQuestionDetail extends FAQQuestionItem {
  answers: FAQAnswerItem[];
}

// ── API ──────────────────────────────────────────────────────────

export const faqApi = {
  // Public
  listQuestions: async (params?: {
    category?: string;
    status?: string;
    search?: string;
    pinned_only?: boolean;
    skip?: number;
    limit?: number;
  }) => {
    const resp = await api.get<FAQQuestionItem[]>('/api/faq/questions', { params });
    return resp.data;
  },

  getQuestion: async (id: number) => {
    const resp = await api.get<FAQQuestionDetail>(`/api/faq/questions/${id}`);
    return resp.data;
  },

  createQuestion: async (data: { title: string; description?: string; category?: string }) => {
    const resp = await api.post<FAQQuestionItem>('/api/faq/questions', data);
    return resp.data;
  },

  updateQuestion: async (id: number, data: { title?: string; description?: string; category?: string; status?: string }) => {
    const resp = await api.patch<FAQQuestionItem>(`/api/faq/questions/${id}`, data);
    return resp.data;
  },

  deleteQuestion: async (id: number) => {
    await api.delete(`/api/faq/questions/${id}`);
  },

  submitAnswer: async (questionId: number, data: { content: string }) => {
    const resp = await api.post<FAQAnswerItem>(`/api/faq/questions/${questionId}/answers`, data);
    return resp.data;
  },

  updateAnswer: async (answerId: number, data: { content: string }) => {
    const resp = await api.patch<FAQAnswerItem>(`/api/faq/answers/${answerId}`, data);
    return resp.data;
  },

  getByErrorCode: async (code: string) => {
    const resp = await api.get<{ id: number; title: string; url: string }>(`/api/faq/by-error-code/${code}`);
    return resp.data;
  },

  // Admin
  listPendingAnswers: async (params?: { skip?: number; limit?: number }) => {
    const resp = await api.get<FAQAnswerItem[]>('/api/faq/admin/pending', { params });
    return resp.data;
  },

  approveAnswer: async (answerId: number) => {
    const resp = await api.patch<FAQAnswerItem>(`/api/faq/admin/answers/${answerId}/approve`);
    return resp.data;
  },

  rejectAnswer: async (answerId: number) => {
    const resp = await api.patch<FAQAnswerItem>(`/api/faq/admin/answers/${answerId}/reject`);
    return resp.data;
  },

  markOfficial: async (answerId: number) => {
    const resp = await api.patch<FAQAnswerItem>(`/api/faq/admin/answers/${answerId}/mark-official`);
    return resp.data;
  },

  pinQuestion: async (questionId: number, is_pinned: boolean) => {
    const resp = await api.patch<FAQQuestionItem>(`/api/faq/admin/questions/${questionId}/pin`, { is_pinned });
    return resp.data;
  },

  deleteAnswer: async (answerId: number) => {
    await api.delete(`/api/faq/admin/answers/${answerId}`);
  },

  createOfficialQuestion: async (data: {
    title: string;
    description?: string;
    category?: string;
    answer_content: string;
    is_official?: boolean;
  }) => {
    const resp = await api.post<FAQQuestionDetail>('/api/faq/admin/questions', data);
    return resp.data;
  },
};
