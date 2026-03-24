import { api, AI_TIMEOUT } from './client';

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
  source_files_count: number;
  category: string | null;
  display_order: number;
  parent_content_id: number | null;
  is_master: boolean;
  material_group_id: number | null;
  created_at: string;
  updated_at: string | null;
  archived_at: string | null;
  last_viewed_at: string | null;
  document_type: string | null;
  study_goal: string | null;
  study_goal_text: string | null;
}

export interface SourceFileItem {
  id: number;
  course_content_id: number;
  filename: string;
  file_type: string | null;
  file_size: number | null;
  created_at: string;
}

export interface CourseContentUpdateResponse extends CourseContentItem {
  archived_guides_count: number;
}

export interface LinkedMaterialItem {
  id: number;
  title: string;
  is_master: boolean;
  content_type: string;
  has_file: boolean;
  original_filename: string | null;
  created_at: string;
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

  browse: async (params: { search?: string; subject?: string; teacher_name?: string } = {}) => {
    const response = await api.get('/api/courses/browse', { params });
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

  create: async (data: {
    name: string;
    description?: string;
    subject?: string;
    teacher_email?: string;
    teacher_id?: number;
    student_ids?: number[];
    new_teacher_name?: string;
    new_teacher_email?: string;
    require_approval?: boolean;
  }) => {
    const response = await api.post('/api/courses/', data);
    return response.data;
  },

  searchTeachers: async (q: string) => {
    const response = await api.get('/api/courses/teachers/search', { params: { q } });
    return response.data as Array<{ id: number; name: string; email: string | null; is_shadow: boolean }>;
  },

  searchStudents: async (q: string) => {
    const response = await api.get('/api/courses/students/search', { params: { q } });
    return response.data as Array<{ id: number; user_id: number; name: string; email: string }>;
  },

  update: async (id: number, data: { name?: string; description?: string; subject?: string; teacher_email?: string; teacher_id?: number | null; require_approval?: boolean }) => {
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

  getDefault: async (studentUserId?: number) => {
    const params = studentUserId ? { student_user_id: studentUserId } : {};
    const response = await api.get('/api/courses/default', { params });
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

  enrollmentStatus: async (courseId: number) => {
    const response = await api.get(`/api/courses/${courseId}/enrollment-status`);
    return response.data as { status: string; request_id?: number };
  },

  enrollmentStatusBatch: async (courseIds: number[]) => {
    const { data } = await api.post('/api/courses/enrollment-status/batch', { course_ids: courseIds });
    return data as Record<string, { status: string; request_id?: number }>;
  },

  listEnrollmentRequests: async (courseId: number, status?: string) => {
    const params = status ? { status } : {};
    const response = await api.get(`/api/courses/${courseId}/enrollment-requests`, { params });
    return response.data as Array<{
      id: number;
      course_id: number;
      student_id: number;
      requested_by_user_id: number | null;
      status: string;
      student_name: string | null;
      student_email: string | null;
      created_at: string;
      resolved_at: string | null;
      resolved_by_user_id: number | null;
    }>;
  },

  resolveEnrollmentRequest: async (courseId: number, requestId: number, status: 'approved' | 'rejected') => {
    const response = await api.patch(`/api/courses/${courseId}/enrollment-requests/${requestId}`, { status });
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
      ...AI_TIMEOUT,
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
    category?: string | null;
    display_order?: number;
  }) => {
    const response = await api.patch(`/api/course-contents/${id}`, data);
    return response.data as CourseContentUpdateResponse;
  },

  replaceFile: async (id: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.put(`/api/course-contents/${id}/replace-file`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      ...AI_TIMEOUT,
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

  getLinkedMaterials: async (contentId: number) => {
    const response = await api.get(`/api/course-contents/${contentId}/linked-materials`);
    return response.data as LinkedMaterialItem[];
  },

  permanentDelete: async (id: number) => {
    await api.delete(`/api/course-contents/${id}/permanent`);
  },

  getLinkedCourseIds: async () => {
    const response = await api.get('/api/course-contents/linked-course-ids');
    return response.data as LinkedCourseIdsResponse;
  },

  listSourceFiles: async (contentId: number): Promise<SourceFileItem[]> => {
    const response = await api.get(`/api/course-contents/${contentId}/source-files`);
    return response.data;
  },

  downloadSourceFile: async (contentId: number, fileId: number, filename?: string) => {
    const response = await api.get(`/api/course-contents/${contentId}/source-files/${fileId}/download`, {
      responseType: 'blob',
    });
    const contentDisposition = response.headers['content-disposition'];
    let resolvedFilename = filename || `file-${fileId}`;
    if (contentDisposition) {
      const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;\n]+)/i);
      const stdMatch = contentDisposition.match(/filename="?([^";\n]+)"?/);
      if (utf8Match) resolvedFilename = decodeURIComponent(utf8Match[1]);
      else if (stdMatch) resolvedFilename = stdMatch[1];
    }
    const url = URL.createObjectURL(response.data);
    const a = document.createElement('a');
    a.href = url;
    a.download = resolvedFilename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },

  /** Fetch a source file as a blob URL (authenticated). Used for inline image/PDF preview. */
  getSourceFileBlobUrl: async (contentId: number, fileId: number, expectedType?: string): Promise<string> => {
    const response = await api.get(`/api/course-contents/${contentId}/source-files/${fileId}/download`, {
      responseType: 'blob',
    });
    let blob = response.data;
    // If the blob type is generic but we know the expected type, re-create with correct type
    if (expectedType && (!blob.type || blob.type === 'application/octet-stream')) {
      blob = new Blob([blob], { type: expectedType });
    }
    return URL.createObjectURL(blob);
  },

  uploadMultiFiles: async (files: File[], courseId: number, title?: string, contentType?: string, aiTool?: string, aiCustomPrompt?: string) => {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }
    formData.append('course_id', String(courseId));
    if (title) formData.append('title', title);
    if (contentType) formData.append('content_type', contentType);
    if (aiTool && aiTool !== 'none') formData.append('ai_tool', aiTool);
    if (aiCustomPrompt) formData.append('ai_custom_prompt', aiCustomPrompt);
    const response = await api.post('/api/course-contents/upload-multi', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      ...AI_TIMEOUT,
    });
    return response.data as CourseContentItem;
  },

  addFilesToMaterial: async (contentId: number, files: File[]): Promise<CourseContentItem> => {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }
    const response = await api.post(`/api/course-contents/${contentId}/add-files`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      ...AI_TIMEOUT,
    });
    return response.data as CourseContentItem;
  },

  reorderSubMaterials: async (contentId: number, subIds: number[]): Promise<{ updated: number }> => {
    const response = await api.put(`/api/course-contents/${contentId}/reorder-subs`, { sub_ids: subIds });
    return response.data;
  },

  bulkCategorize: async (contentIds: number[], category: string) => {
    const response = await api.post('/api/course-contents/bulk-categorize', {
      content_ids: contentIds,
      category,
    });
    return response.data as { updated: number; category: string };
  },

  bulkArchive: async (contentIds: number[]) => {
    const response = await api.post('/api/course-contents/bulk-archive', {
      content_ids: contentIds,
    });
    return response.data as { archived: number };
  },

  deleteSubMaterial: async (masterId: number, subId: number): Promise<void> => {
    await api.delete(`/api/course-contents/${masterId}/sub-materials/${subId}`);
  },

  listCategories: async () => {
    const response = await api.get('/api/course-contents/categories');
    return response.data as string[];
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
      ...AI_TIMEOUT,
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
