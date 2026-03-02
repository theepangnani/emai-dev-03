import { api } from './client';

// --- Types ---
export interface ParsedCourse {
  name: string;
  teacher_name: string | null;
  section: string | null;
}

export interface ParsedAssignment {
  title: string;
  description: string | null;
  due_date: string | null;
  max_points: number | null;
  course_name: string | null;
  status: string | null;
  _is_duplicate?: boolean;
}

export interface ParsedMaterial {
  title: string;
  description: string | null;
  type: string | null;
  url: string | null;
  _is_duplicate?: boolean;
}

export interface ParsedAnnouncement {
  title: string | null;
  body: string;
  date: string | null;
  author: string | null;
}

export interface ParsedGrade {
  assignment_title: string;
  score: number | null;
  max_score: number | null;
  course_name: string | null;
}

export interface ParsedImportData {
  courses: ParsedCourse[];
  assignments: ParsedAssignment[];
  materials: ParsedMaterial[];
  announcements: ParsedAnnouncement[];
  grades: ParsedGrade[];
}

export interface ImportSession {
  id: number;
  user_id: number;
  student_id: number | null;
  source_type: string;
  status: string;
  parsed_data: ParsedImportData | null;
  reviewed_data: ParsedImportData | null;
  courses_created: number;
  assignments_created: number;
  materials_created: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ImportSessionListItem {
  id: number;
  source_type: string;
  status: string;
  courses_created: number;
  assignments_created: number;
  materials_created: number;
  created_at: string;
  completed_at: string | null;
}

export interface ImportCommitResult {
  session_id: number;
  status: string;
  courses_created: number;
  assignments_created: number;
  materials_created: number;
}

export interface ImportCreateResult {
  session_id: number;
  status: string;
  message: string;
}

// --- API Functions ---
export const classroomImportApi = {
  // Copy-paste import
  importCopyPaste: async (data: { text: string; source_hint?: string; student_id?: number }): Promise<ImportCreateResult> => {
    const response = await api.post('/api/import/copypaste', data);
    return response.data as ImportCreateResult;
  },

  // Screenshot import
  importScreenshot: async (files: File[], studentId?: number, sourceHint?: string): Promise<ImportCreateResult> => {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    if (studentId) formData.append('student_id', String(studentId));
    if (sourceHint) formData.append('source_hint', sourceHint);
    const response = await api.post('/api/import/screenshot', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data as ImportCreateResult;
  },

  // ICS import
  importICS: async (file: File, studentId?: number): Promise<ImportCreateResult> => {
    const formData = new FormData();
    formData.append('file', file);
    if (studentId) formData.append('student_id', String(studentId));
    const response = await api.post('/api/import/ics', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data as ImportCreateResult;
  },

  // CSV import
  importCSV: async (file: File, templateType: string, studentId?: number): Promise<ImportCreateResult> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('template_type', templateType);
    if (studentId) formData.append('student_id', String(studentId));
    const response = await api.post('/api/import/csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data as ImportCreateResult;
  },

  // Download CSV template
  downloadCSVTemplate: async (type: 'assignments' | 'materials' | 'grades'): Promise<void> => {
    const response = await api.get('/api/import/templates/csv', {
      params: { type },
      responseType: 'blob',
    });
    const contentDisposition = response.headers['content-disposition'];
    let filename = `${type}-template.csv`;
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

  // Session management
  listSessions: async (): Promise<ImportSessionListItem[]> => {
    const response = await api.get('/api/import/sessions');
    return response.data as ImportSessionListItem[];
  },

  getSession: async (id: number): Promise<ImportSession> => {
    const response = await api.get(`/api/import/sessions/${id}`);
    return response.data as ImportSession;
  },

  updateSession: async (id: number, reviewedData: ParsedImportData): Promise<ImportSession> => {
    const response = await api.patch(`/api/import/sessions/${id}`, { reviewed_data: reviewedData });
    return response.data as ImportSession;
  },

  commitSession: async (id: number): Promise<ImportCommitResult> => {
    const response = await api.post(`/api/import/sessions/${id}/commit`);
    return response.data as ImportCommitResult;
  },

  deleteSession: async (id: number): Promise<void> => {
    await api.delete(`/api/import/sessions/${id}`);
  },
};
