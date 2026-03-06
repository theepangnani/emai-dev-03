import { api } from './client';

export interface NoteResponse {
  id: number;
  user_id: number;
  course_content_id: number;
  content: string;
  plain_text: string;
  has_images: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface NoteListItem {
  id: number;
  course_content_id: number;
  plain_text: string;
  has_images: boolean;
  updated_at: string | null;
  created_at: string;
}

export interface NoteUpsert {
  content: string;
  plain_text: string;
  has_images: boolean;
}

export const notesApi = {
  list: async (courseContentId?: number) => {
    const params = courseContentId ? { course_content_id: courseContentId } : {};
    const response = await api.get('/api/notes/', { params });
    return response.data as NoteListItem[];
  },

  getByContent: async (courseContentId: number) => {
    const response = await api.get(`/api/notes/by-content/${courseContentId}`);
    return response.data as NoteResponse | null;
  },

  upsert: async (courseContentId: number, data: NoteUpsert) => {
    const response = await api.put(`/api/notes/by-content/${courseContentId}`, data);
    return response.data as NoteResponse;
  },

  delete: async (courseContentId: number) => {
    await api.delete(`/api/notes/by-content/${courseContentId}`);
  },
};
