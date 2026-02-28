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
  has_file: boolean;
  original_filename: string | null;
  file_size: number | null;
  mime_type: string | null;
  created_at: string;
  updated_at: string | null;
  archived_at: string | null;
  last_viewed_at: string | null;
}

export interface CourseContentUpdateResponse extends CourseContentItem {
  archived_guides_count: number;
}

export interface LinkedCourseChild {
  student_id: number;
  user_id: number;
  full_name: string;
}

export interface LinkedCourseIdsResponse {
  linked_course_ids: number[];
  course_student_map: Record<number, number[]>;
  children: LinkedCourseChild[];
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

// Teacher Course Management type (#947)
export interface TeacherCourseManagement {
  id: number;
  name: string;
  description: string | null;
  subject: string | null;
  google_classroom_id: string | null;
  classroom_type: string | null;
  teacher_id: number | null;
  teacher_name: string | null;
  created_by_user_id: number | null;
  is_private: boolean;
  is_default: boolean;
  student_count: number;
  assignment_count: number;
  material_count: number;
  last_activity: string | null;
  source: 'google' | 'manual' | 'admin';
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

  teachingManagement: async (): Promise<TeacherCourseManagement[]> => {
    const response = await api.get('/api/courses/teaching/management');
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

  delete: async (id: number) => {
    const response = await api.delete(`/api/courses/${id}`);
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
    ai_tool?: string;
    ai_custom_prompt?: string;
  }) => {
    const response = await api.post('/api/course-contents/', data);
    return response.data as CourseContentItem;
  },

  uploadFile: async (file: File, courseId: number, title?: string, contentType?: string, aiTool?: string, aiCustomPrompt?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('course_id', String(courseId));
    if (title) formData.append('title', title);
    if (contentType) formData.append('content_type', contentType);
    if (aiTool && aiTool !== 'none') formData.append('ai_tool', aiTool);
    if (aiCustomPrompt) formData.append('ai_custom_prompt', aiCustomPrompt);
    const response = await api.post('/api/course-contents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data as CourseContentItem;
  },

  update: async (id: number, data: {
    title?: string;
    description?: string;
    text_content?: string;
    content_type?: string;
    reference_url?: string;
    google_classroom_url?: string;
    course_id?: number;
  }) => {
    const response = await api.patch(`/api/course-contents/${id}`, data);
    return response.data as CourseContentUpdateResponse;
  },

  replaceFile: async (id: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.put(`/api/course-contents/${id}/replace-file`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
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

  getLinkedCourseIds: async () => {
    const response = await api.get('/api/course-contents/linked-course-ids');
    return response.data as LinkedCourseIdsResponse;
  },

  download: async (id: number, originalFilename?: string) => {
    const response = await api.get(`/api/course-contents/${id}/download`, {
      responseType: 'blob',
    });
    const contentDisposition = response.headers['content-disposition'];
    let filename = originalFilename || `document-${id}`;
    if (contentDisposition) {
      // Try filename*=UTF-8'' first (RFC 5987), then standard filename=
      const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;\n]+)/i);
      const stdMatch = contentDisposition.match(/filename="?([^";\n]+)"?/);
      if (utf8Match) filename = decodeURIComponent(utf8Match[1]);
      else if (stdMatch) filename = stdMatch[1];
    }
    const url = URL.createObjectURL(response.data);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
};

// Submission Types (#839)
export interface SubmissionResponse {
  id: number;
  student_id: number;
  assignment_id: number;
  status: string;
  submitted_at: string | null;
  grade: number | null;
  submission_file_name: string | null;
  submission_notes: string | null;
  is_late: boolean;
  assignment_title: string | null;
  course_name: string | null;
  student_name: string | null;
  has_file: boolean;
}

export interface SubmissionListItem {
  student_id: number;
  student_name: string;
  status: string;
  submitted_at: string | null;
  is_late: boolean;
  grade: number | null;
  has_file: boolean;
}

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

  // Submission endpoints (#839)
  submit: async (assignmentId: number, formData: FormData): Promise<SubmissionResponse> => {
    const response = await api.post(`/api/assignments/${assignmentId}/submit`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  getSubmission: async (assignmentId: number): Promise<SubmissionResponse> => {
    const response = await api.get(`/api/assignments/${assignmentId}/submission`);
    return response.data;
  },

  listSubmissions: async (assignmentId: number): Promise<SubmissionListItem[]> => {
    const response = await api.get(`/api/assignments/${assignmentId}/submissions`);
    return response.data;
  },

  downloadSubmission: async (assignmentId: number, studentId?: number) => {
    const params = studentId ? { student_id: studentId } : {};
    const response = await api.get(`/api/assignments/${assignmentId}/submission/download`, {
      responseType: 'blob',
      params,
    });
    const contentDisposition = response.headers['content-disposition'];
    let filename = `submission-${assignmentId}`;
    if (contentDisposition) {
      const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;\n]+)/i);
      const stdMatch = contentDisposition.match(/filename="?([^";\n]+)"?/);
      if (utf8Match) filename = decodeURIComponent(utf8Match[1]);
      else if (stdMatch) filename = stdMatch[1];
    }
    const url = URL.createObjectURL(response.data);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
};
