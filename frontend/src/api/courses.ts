import { api } from './client';

// Course Content Types
export interface CourseContentItem {
  id: number;
  course_id: number;
  course_name: string | null;
  title: string;
  description: string | null;
  text_content: string | null;
  content_type: string;
  reference_url: string | null;
  google_classroom_url: string | null;
  created_by_user_id: number | null;
  google_classroom_material_id: string | null;
  created_at: string;
  updated_at: string | null;
  archived_at: string | null;
  last_viewed_at: string | null;
}

export interface CourseContentUpdateResponse extends CourseContentItem {
  archived_guides_count: number;
}

// Assignment Types
export interface AssignmentItem {
  id: number;
  title: string;
  description: string | null;
  course_id: number;
  course_name: string | null;
  google_classroom_id: string | null;
  due_date: string | null;
  max_points: number | null;
  created_at: string;
}

// Courses API
export const coursesApi = {
  list: async () => {
    const response = await api.get('/api/courses/');
    return response.data;
  },

  get: async (id: number) => {
    const response = await api.get(`/api/courses/${id}`);
    return response.data;
  },

  teachingList: async () => {
    const response = await api.get('/api/courses/teaching');
    return response.data;
  },

  create: async (data: { name: string; description?: string; subject?: string; teacher_email?: string }) => {
    const response = await api.post('/api/courses/', data);
    return response.data;
  },

  update: async (id: number, data: { name?: string; description?: string; subject?: string; teacher_email?: string }) => {
    const response = await api.patch(`/api/courses/${id}`, data);
    return response.data;
  },

  createdByMe: async () => {
    const response = await api.get('/api/courses/created/me');
    return response.data;
  },

  getDefault: async () => {
    const response = await api.get('/api/courses/default');
    return response.data;
  },

  listStudents: async (courseId: number) => {
    const response = await api.get(`/api/courses/${courseId}/students`);
    return response.data as Array<{ student_id: number; user_id: number; full_name: string; email: string; grade_level: number | null }>;
  },

  addStudent: async (courseId: number, email: string) => {
    const response = await api.post(`/api/courses/${courseId}/students`, { email });
    return response.data;
  },

  removeStudent: async (courseId: number, studentId: number) => {
    const response = await api.delete(`/api/courses/${courseId}/students/${studentId}`);
    return response.data;
  },

  announce: async (courseId: number, subject: string, body: string) => {
    const response = await api.post(`/api/courses/${courseId}/announce`, { subject, body });
    return response.data as { recipient_count: number; email_count: number; course_name: string };
  },

  enrolledByMe: async () => {
    const response = await api.get('/api/courses/enrolled/me');
    return response.data;
  },

  enroll: async (courseId: number) => {
    const response = await api.post(`/api/courses/${courseId}/enroll`);
    return response.data;
  },

  unenroll: async (courseId: number) => {
    const response = await api.delete(`/api/courses/${courseId}/enroll`);
    return response.data;
  },
};

// Course Content API
export const courseContentsApi = {
  list: async (courseId: number, contentType?: string) => {
    const params: Record<string, any> = { course_id: courseId };
    if (contentType) params.content_type = contentType;
    const response = await api.get('/api/course-contents/', { params });
    return response.data as CourseContentItem[];
  },

  listAll: async (params?: { student_user_id?: number; content_type?: string; include_archived?: boolean }) => {
    const response = await api.get('/api/course-contents/', { params: params || {} });
    return response.data as CourseContentItem[];
  },

  get: async (id: number) => {
    const response = await api.get(`/api/course-contents/${id}`);
    return response.data as CourseContentItem;
  },

  create: async (data: {
    course_id: number;
    title: string;
    description?: string;
    text_content?: string;
    content_type?: string;
    reference_url?: string;
    google_classroom_url?: string;
  }) => {
    const response = await api.post('/api/course-contents/', data);
    return response.data as CourseContentItem;
  },

  update: async (id: number, data: {
    title?: string;
    description?: string;
    text_content?: string;
    content_type?: string;
    reference_url?: string;
    google_classroom_url?: string;
  }) => {
    const response = await api.patch(`/api/course-contents/${id}`, data);
    return response.data as CourseContentUpdateResponse;
  },

  delete: async (id: number) => {
    await api.delete(`/api/course-contents/${id}`);
  },

  restore: async (id: number) => {
    const response = await api.patch(`/api/course-contents/${id}/restore`);
    return response.data as CourseContentItem;
  },

  permanentDelete: async (id: number) => {
    await api.delete(`/api/course-contents/${id}/permanent`);
  },
};

// Assignments API
export const assignmentsApi = {
  list: async (courseId?: number): Promise<AssignmentItem[]> => {
    const params = courseId ? { course_id: courseId } : {};
    const response = await api.get('/api/assignments/', { params });
    return response.data;
  },

  get: async (id: number): Promise<AssignmentItem> => {
    const response = await api.get(`/api/assignments/${id}`);
    return response.data;
  },

  create: async (data: { course_id: number; title: string; description?: string; due_date?: string; max_points?: number }): Promise<AssignmentItem> => {
    const response = await api.post('/api/assignments/', data);
    return response.data;
  },

  update: async (id: number, data: { title?: string; description?: string; due_date?: string | null; max_points?: number | null }): Promise<AssignmentItem> => {
    const response = await api.put(`/api/assignments/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/assignments/${id}`);
  },
};
