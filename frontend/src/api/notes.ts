import { api } from './client';

export interface NoteItem {
  id: number;
  user_id: number;
  course_content_id: number;
  content: string | null;
  plain_text: string | null;
  has_images: boolean;
  highlights_json: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface NoteHighlight {
  text: string;
  start: number;
  end: number;
}

export interface NoteVersionItem {
  id: number;
  note_id: number;
  version_number: number;
  created_at: string;
  created_by_user_id: number | null;
  preview: string;
}

export interface NoteVersionFull {
  id: number;
  note_id: number;
  content: string;
  version_number: number;
  created_at: string;
  created_by_user_id: number | null;
}

export interface NoteCreateTaskData {
  title: string;
  due_date?: string;
  priority?: string;
  linked?: boolean;
}

export const notesApi = {
  getByContent: async (courseContentId: number) => {
    // List to find the note, then fetch full content via single-note endpoint
    const listResp = await api.get('/api/notes/', { params: { course_content_id: courseContentId } });
    const notes = listResp.data as NoteItem[];
    if (notes.length === 0) throw { response: { status: 404 } };
    const fullResp = await api.get(`/api/notes/${notes[0].id}`);
    return fullResp.data as NoteItem;
  },

  upsert: async (courseContentId: number, data: { content: string | null; has_images?: boolean; highlights_json?: string }) => {
    const payload: Record<string, unknown> = {
      course_content_id: courseContentId,
      content: data.content || '',
    };
    if (data.highlights_json !== undefined) {
      payload.highlights_json = data.highlights_json;
    }
    const response = await api.put('/api/notes/', payload);
    return response.data as NoteItem;
  },

  delete: async (noteId: number) => {
    await api.delete(`/api/notes/${noteId}`);
  },

  list: async (courseContentId?: number) => {
    const params = courseContentId ? { course_content_id: courseContentId } : {};
    const response = await api.get('/api/notes/', { params });
    return response.data as NoteItem[];
  },

  getChildNotes: async (studentUserId: number, courseContentId: number) => {
    const response = await api.get(`/api/notes/children/${studentUserId}`, {
      params: { course_content_id: courseContentId },
    });
    const notes = response.data as NoteItem[];
    if (notes.length === 0) return null;
    const fullResp = await api.get(`/api/notes/${notes[0].id}`);
    return fullResp.data as NoteItem;
  },

  listVersions: async (noteId: number) => {
    const response = await api.get(`/api/notes/${noteId}/versions`);
    return response.data as NoteVersionItem[];
  },

  getVersion: async (noteId: number, versionId: number) => {
    const response = await api.get(`/api/notes/${noteId}/versions/${versionId}`);
    return response.data as NoteVersionFull;
  },

  restoreVersion: async (noteId: number, versionId: number) => {
    const response = await api.post(`/api/notes/${noteId}/restore/${versionId}`);
    return response.data as NoteItem;
  },

  uploadImage: async (file: File): Promise<{ id: number; image_url: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/notes/images', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  createTask: async (noteId: number, courseContentId: number, data: NoteCreateTaskData) => {
    const response = await api.post('/api/tasks/', {
      title: data.title,
      due_date: data.due_date,
      priority: data.priority,
      course_content_id: data.linked ? courseContentId : undefined,
      note_id: data.linked ? noteId : undefined,
    });
    return response.data;
  },
};
