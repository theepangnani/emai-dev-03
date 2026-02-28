import { api } from './client';

// Task Types (ported from web frontend/src/api/tasks.ts)
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
  created_at: string;
  updated_at: string | null;
}

export interface AssignableUser {
  user_id: number;
  name: string;
  role: string;
}

export interface CreateTaskData {
  title: string;
  description?: string;
  due_date?: string;
  assigned_to_user_id?: number;
  priority?: string;
}

// Tasks API
export const tasksApi = {
  list: async (params?: {
    assigned_to_user_id?: number;
    is_completed?: boolean;
    priority?: string;
    course_id?: number;
  }) => {
    const response = await api.get('/api/tasks/', { params });
    return response.data as TaskItem[];
  },

  create: async (data: CreateTaskData) => {
    const response = await api.post('/api/tasks/', data);
    return response.data as TaskItem;
  },

  update: async (
    taskId: number,
    data: {
      title?: string;
      description?: string;
      due_date?: string;
      is_completed?: boolean;
      priority?: string;
      assigned_to_user_id?: number;
    }
  ) => {
    const response = await api.patch(`/api/tasks/${taskId}`, data);
    return response.data as TaskItem;
  },

  toggleComplete: async (taskId: number, isCompleted: boolean) => {
    const response = await api.patch(`/api/tasks/${taskId}`, {
      is_completed: isCompleted,
    });
    return response.data as TaskItem;
  },

  getAssignableUsers: async () => {
    const response = await api.get('/api/tasks/assignable-users');
    return response.data as AssignableUser[];
  },
};
