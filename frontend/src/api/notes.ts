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

export interface ChildNoteResponse {
  id: number;
  user_id: number;
  course_content_id: number;
  content: string;
  plain_text: string;
  has_images: boolean;
  child_name: string;
  student_id: number;
  created_at: string;
  updated_at: string | null;
}

export interface NoteUpsert {
  course_content_id: number;
  content: string;
  plain_text: string;
  has_images?: boolean;
}

export const notesApi = {
  /** List current user's notes, optionally by course_content_id */
  list: async (courseContentId?: number) => {
    const params = courseContentId ? { course_content_id: courseContentId } : {};
    const { data } = await api.get<NoteResponse[]>('/api/notes/', { params });
    return data;
  },

  /** Get a single note by ID */
  get: async (noteId: number) => {
    const { data } = await api.get<NoteResponse>(`/api/notes/${noteId}`);
    return data;
  },

  /** Create or update (upsert) a note */
  upsert: async (body: NoteUpsert) => {
    const { data } = await api.put<NoteResponse>('/api/notes/', body);
    return data;
  },

  /** Delete a note */
  delete: async (noteId: number) => {
    await api.delete(`/api/notes/${noteId}`);
  },

  /** Get a child's notes (parent-only, read-only) */
  getChildNotes: async (studentId: number, courseContentId?: number) => {
    const params = courseContentId ? { course_content_id: courseContentId } : {};
    const { data } = await api.get<ChildNoteResponse[]>(
      `/api/notes/children/${studentId}`,
      { params },
    );
    return data;
  },
};
