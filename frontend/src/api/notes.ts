import { api } from './client';

export interface NoteResponse {
  id: number;
  user_id: number;
  course_content_id: number;
  content: string | null;
  plain_text: string | null;
  has_images: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface NoteListItem {
  id: number;
  user_id: number;
  course_content_id: number;
  has_images: boolean;
  plain_text_preview: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface NoteUpsert {
  content: string | null;
  plain_text: string | null;
}

export const notesApi = {
  get: async (courseContentId: number): Promise<NoteResponse> => {
    const response = await api.get(`/api/notes/content/${courseContentId}`);
    return response.data;
  },

  upsert: async (courseContentId: number, data: NoteUpsert): Promise<NoteResponse> => {
    const response = await api.put(`/api/notes/content/${courseContentId}`, data);
    return response.data;
  },

  delete: async (courseContentId: number): Promise<void> => {
    await api.delete(`/api/notes/content/${courseContentId}`);
  },

  listMine: async (): Promise<NoteListItem[]> => {
    const response = await api.get('/api/notes/mine');
    return response.data;
  },

  listChildren: async (courseContentId: number): Promise<NoteListItem[]> => {
    const response = await api.get(`/api/notes/content/${courseContentId}/children`);
    return response.data;
  },
};
