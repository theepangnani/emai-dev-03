import { api } from './client';

export interface CourseItem {
  id: number;
  name: string;
  description: string | null;
  subject: string | null;
  google_classroom_id: string | null;
  teacher_id: number | null;
  created_at: string;
  teacher_name: string | null;
  teacher_email: string | null;
}

export const coursesApi = {
  list: async () => {
    const response = await api.get('/api/courses/');
    return response.data as CourseItem[];
  },
};
