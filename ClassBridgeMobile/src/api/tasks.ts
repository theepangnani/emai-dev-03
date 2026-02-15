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

// Tasks API — mobile supports list + toggle completion
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

  toggleComplete: async (taskId: number, isCompleted: boolean) => {
    const response = await api.patch(`/api/tasks/${taskId}`, {
      is_completed: isCompleted,
    });
    return response.data as TaskItem;
  },
};
