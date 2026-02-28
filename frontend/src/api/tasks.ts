import { api } from './client';

// Task Types
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
  course_name: string | null;
  course_content_title: string | null;
  study_guide_title: string | null;
  study_guide_type: string | null;
  last_reminder_sent_at: string | null;
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
