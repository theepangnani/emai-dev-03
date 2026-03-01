import { api } from './client';

export interface DocumentItem {
  id: number;
  title: string;
  /** "document" | "study_guide" | "quiz" | "flashcards" */
  type: string;
  course_id: number;
  course_name: string;
  created_at: string;
  has_study_guide: boolean;
  has_quiz: boolean;
  has_flashcards: boolean;
  /** Present for parents only */
  child_name: string | null;
}

export interface DocumentsResponse {
  items: DocumentItem[];
  total: number;
}

export interface DocumentsParams {
  course_id?: number;
  type?: string;
  search?: string;
  child_id?: number;
  limit?: number;
  offset?: number;
}

export const documentsApi = {
  list: async (params?: DocumentsParams): Promise<DocumentsResponse> => {
    const response = await api.get('/api/documents/', { params });
    return response.data as DocumentsResponse;
  },
};
