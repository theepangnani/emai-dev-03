import { api } from './client';

export interface NoteUpsert {
  course_content_id: number;
  content: string;
  plain_text: string;
  has_images: boolean;
}

export interface NoteResponse {
  id: number;
  user_id: number;
  course_content_id: number;
  content: string;
  plain_text: string;
  has_images: boolean;
  created_at: string;
  updated_at: string | null;
  course_content_title: string | null;
}

export interface NoteSummary {
  id: number;
  course_content_id: number;
  has_images: boolean;
  plain_text_preview: string;
  updated_at: string | null;
  course_content_title: string | null;
}

export const notesApi = {
  list: async (courseContentId?: number): Promise<NoteSummary[]> => {
    const params: Record<string, string> = {};
    if (courseContentId !== undefined) params.course_content_id = String(courseContentId);
    const { data } = await api.get('/api/notes/', { params });
    return data;
  },

  get: async (noteId: number): Promise<NoteResponse> => {
    const { data } = await api.get(`/api/notes/${noteId}`);
    return data;
  },

  upsert: async (note: NoteUpsert): Promise<NoteResponse> => {
    const { data } = await api.put('/api/notes/', note);
    return data;
  },

  delete: async (noteId: number): Promise<void> => {
    await api.delete(`/api/notes/${noteId}`);
  },

  listChildren: async (studentId: number, courseContentId?: number): Promise<NoteSummary[]> => {
    const params: Record<string, string> = {};
    if (courseContentId !== undefined) params.course_content_id = String(courseContentId);
    const { data } = await api.get(`/api/notes/children/${studentId}`, { params });
    return data;
  },
};
