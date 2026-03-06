import { api } from './client';

export interface NoteItem {
  id: number;
  user_id: number;
  course_content_id: number;
  content: string | null;
  plain_text: string | null;
  has_images: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface NoteCreateTaskData {
  title: string;
  due_date?: string;
  priority?: string;
  linked?: boolean;
}

export const notesApi = {
  getByContent: async (courseContentId: number) => {
    const response = await api.get(`/api/notes/by-content/${courseContentId}`);
    return response.data as NoteItem;
  },

  upsert: async (courseContentId: number, data: { content: string | null; has_images?: boolean }) => {
    const response = await api.put(`/api/notes/by-content/${courseContentId}`, data);
    return response.data as NoteItem;
  },

  delete: async (courseContentId: number) => {
    await api.delete(`/api/notes/by-content/${courseContentId}`);
  },

  list: async () => {
    const response = await api.get('/api/notes/');
    return response.data as NoteItem[];
  },

  createTask: async (noteId: number, data: NoteCreateTaskData) => {
    const response = await api.post(`/api/notes/${noteId}/create-task`, data);
    return response.data;
  },
};
