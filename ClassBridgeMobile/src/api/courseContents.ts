import { api } from './client';

export interface CourseContentItem {
  id: number;
  course_id: number | null;
  course_name: string | null;
  title: string;
  description: string | null;
  content_type: string;
  has_file: boolean;
  original_filename: string | null;
  created_at: string;
  archived_at: string | null;
}

export const courseContentsApi = {
  list: async (params?: { student_user_id?: number }) => {
    const response = await api.get('/api/course-contents/', { params });
    return response.data as CourseContentItem[];
  },
};
