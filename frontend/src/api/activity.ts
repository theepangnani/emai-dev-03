import { api } from './client';

export interface ActivityItem {
  activity_type: 'course_created' | 'task_created' | 'material_uploaded' | 'task_completed' | 'message_received' | 'notification_received' | 'study_guide_generated';
  title: string;
  description: string;
  resource_type: string;
  resource_id: number;
  student_id: number | null;
  student_name: string | null;
  created_at: string;
  icon_type: string;
}

export interface TimelineEntry {
  type: 'upload' | 'study_guide' | 'quiz' | 'badge' | 'level_up';
  title: string;
  course: string | null;
  date: string;
  xp: number | null;
  score: number | null;
  badge_id: string | null;
}

export interface TimelineResponse {
  items: TimelineEntry[];
  total: number;
}

export const activityApi = {
  getRecent: async (studentId?: number, limit = 10): Promise<ActivityItem[]> => {
    const params: Record<string, string | number> = { limit };
    if (studentId) params.student_id = studentId;
    const { data } = await api.get('/api/activity/recent', { params });
    return data;
  },

  getTimeline: async (params: {
    days?: number;
    type?: string;
    course_id?: number;
    limit?: number;
    offset?: number;
  } = {}): Promise<TimelineResponse> => {
    const { data } = await api.get('/api/activity/timeline', { params });
    return data;
  },
};
