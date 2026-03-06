import { api } from './client';

export interface NoteItem {
  id: number;
  user_id: number;
  course_content_id: number;
  content: string;
  plain_text: string;
  has_images: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface ChildNoteItem extends NoteItem {
  read_only: boolean;
  student_name: string;
}

export const notesApi = {
  /** List current user's notes, optionally filtered by course_content_id. */
  list: async (params?: { course_content_id?: number }) => {
    const response = await api.get('/api/notes/', { params });
    return response.data as NoteItem[];
  },

  /** Get the current user's note for a specific course content item. */
  get: async (courseContentId: number) => {
    const response = await api.get(`/api/notes/${courseContentId}`);
    return response.data as NoteItem;
  },

  /** Create or update a note for a course content item. */
  upsert: async (courseContentId: number, content: string) => {
    const response = await api.put(`/api/notes/${courseContentId}`, { content });
    return response.data as NoteItem;
  },

  /** Delete a note for a course content item. */
  delete: async (courseContentId: number) => {
    await api.delete(`/api/notes/${courseContentId}`);
  },

  /** Get a child's notes (parent read-only). */
  getChildNotes: async (studentId: number, courseContentId?: number) => {
    const params: Record<string, number> = {};
    if (courseContentId !== undefined) params.course_content_id = courseContentId;
    const response = await api.get(`/api/notes/children/${studentId}`, { params });
    return response.data as ChildNoteItem[];
  },
};
