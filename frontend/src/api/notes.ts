import { api } from './client';

export interface NoteItem {
  id: number;
  user_id: number;
  title: string | null;
  content: string;
  color: string;
  is_pinned: boolean;
  course_id: number | null;
  study_guide_id: number | null;
  task_id: number | null;
  course_name: string | null;
  study_guide_title: string | null;
  task_title: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface NoteCreate {
  title?: string;
  content: string;
  color?: string;
  is_pinned?: boolean;
  course_id?: number | null;
  study_guide_id?: number | null;
  task_id?: number | null;
}

export interface NoteUpdate {
  title?: string | null;
  content?: string;
  color?: string;
  is_pinned?: boolean;
  course_id?: number | null;
  study_guide_id?: number | null;
  task_id?: number | null;
  is_archived?: boolean;
}

export const notesApi = {
  list: async (params?: { course_id?: number; search?: string; pinned?: boolean }) => {
    const response = await api.get('/api/notes/', { params });
    return response.data as NoteItem[];
  },

  create: async (data: NoteCreate) => {
    const response = await api.post('/api/notes/', data);
    return response.data as NoteItem;
  },

  update: async (noteId: number, data: NoteUpdate) => {
    const response = await api.patch(`/api/notes/${noteId}`, data);
    return response.data as NoteItem;
  },

  delete: async (noteId: number) => {
    await api.delete(`/api/notes/${noteId}`);
  },
};
