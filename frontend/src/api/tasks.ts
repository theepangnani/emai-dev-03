import { api } from './client';

// Task Types

// CB-TASKSYNC-001 (#3920) — source attribution surfaced from backend so the
// frontend can render auto-created badges and retire string-level dedup.
export type TaskSource =
  | 'assignment'
  | 'email_digest'
  | 'study_guide'
  | 'manual';

export type TaskSourceStatus =
  | 'active'
  | 'tentative'
  | 'source_deleted'
  | 'source_submitted'
  | 'upgraded';

export interface TaskItem {
  id: number;
  created_by_user_id: number;
  assigned_to_user_id: number | null;
  title: string;
  description: string | null;
  due_date: string | null;
  is_completed: boolean;
  completed_at: string | null;
  archived_at: string | null;
  priority: string | null;
  category: string | null;
  creator_name: string;
  assignee_name: string | null;
  course_id: number | null;
  course_content_id: number | null;
  study_guide_id: number | null;
  note_id: number | null;
  course_name: string | null;
  course_content_title: string | null;
  study_guide_title: string | null;
  study_guide_type: string | null;
  last_reminder_sent_at: string | null;
  // CB-TASKSYNC-001 (#3920) — source-attribution fields; all optional so
  // manual/legacy Tasks serialize with null. `source_ref` is surfaced to let
  // the calendar retire string-level dedup in favour of an FK-style check.
  // `source` accepts arbitrary strings too so a new backend value doesn't
  // force a frontend release — TaskSourceBadge renders a neutral fallback.
  source?: TaskSource | (string & {}) | null;
  source_ref?: string | null;
  source_confidence?: number | null;
  source_status?: TaskSourceStatus | null;
  source_created_at?: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface AssignableUser {
  user_id: number;
  name: string;
  role: string;
}

// Tasks API
export const tasksApi = {
  get: async (taskId: number) => {
    const response = await api.get(`/api/tasks/${taskId}`);
    return response.data as TaskItem;
  },

  list: async (params?: { assigned_to_user_id?: number; is_completed?: boolean; priority?: string; include_archived?: boolean; course_id?: number; study_guide_id?: number }) => {
    const response = await api.get('/api/tasks/', { params });
    return response.data as TaskItem[];
  },

  create: async (data: { title: string; description?: string; due_date?: string; assigned_to_user_id?: number; priority?: string; category?: string; course_id?: number; course_content_id?: number; study_guide_id?: number }) => {
    const response = await api.post('/api/tasks/', data);
    return response.data as TaskItem;
  },

  update: async (taskId: number, data: { title?: string; description?: string; due_date?: string; assigned_to_user_id?: number; is_completed?: boolean; priority?: string; category?: string; course_id?: number; course_content_id?: number; study_guide_id?: number }) => {
    const response = await api.patch(`/api/tasks/${taskId}`, data);
    return response.data as TaskItem;
  },

  delete: async (taskId: number) => {
    await api.delete(`/api/tasks/${taskId}`);
  },

  restore: async (taskId: number) => {
    const response = await api.patch(`/api/tasks/${taskId}/restore`);
    return response.data as TaskItem;
  },

  permanentDelete: async (taskId: number) => {
    await api.delete(`/api/tasks/${taskId}/permanent`);
  },

  getAssignableUsers: async () => {
    const response = await api.get('/api/tasks/assignable-users');
    return response.data as AssignableUser[];
  },

  remind: async (taskId: number) => {
    const response = await api.post(`/api/tasks/${taskId}/remind`);
    return response.data as { success: boolean; reminded_at: string; assignee_name: string };
  },
};

// ICS Import Types
export interface ICSEventPreview {
  index: number;
  summary: string;
  dtstart: string;
  dtend: string | null;
  description: string | null;
  location: string | null;
}

export interface ICSParseResponse {
  events: ICSEventPreview[];
  total: number;
}

export interface ICSImportResponse {
  created_count: number;
  skipped_count: number;
  errors: string[];
}

// ICS Import API
export const icsImportApi = {
  parse: async (file: File): Promise<ICSParseResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/import/ics/parse', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  import: async (file: File, selectedIndices?: number[]): Promise<ICSImportResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const params: Record<string, string> = {};
    if (selectedIndices && selectedIndices.length > 0) {
      params.selected_indices = selectedIndices.join(',');
    }
    const response = await api.post('/api/import/ics', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params,
    });
    return response.data;
  },
};
