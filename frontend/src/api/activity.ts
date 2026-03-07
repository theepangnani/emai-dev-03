import { api } from './client';

export interface ActivityItem {
  activity_type: 'course_created' | 'task_created' | 'material_uploaded' | 'task_completed' | 'message_received' | 'notification_received';
  title: string;
  description: string;
  resource_type: string;
  resource_id: number;
  student_id: number | null;
  student_name: string | null;
  created_at: string;
  icon_type: string;
}

export const activityApi = {
  getRecent: async (studentId?: number, limit = 10): Promise<ActivityItem[]> => {
    const params: Record<string, any> = { limit };
    if (studentId) params.student_id = studentId;
    const { data } = await api.get('/api/activity/recent', { params });
    return data;
  },
};
