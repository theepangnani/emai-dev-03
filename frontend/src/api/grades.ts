import { api } from './client';

// --- Types ---

export interface CourseGradeInfo {
  course_id: number;
  course_name: string;
  assignment_count: number;
  graded_count: number;
  average_grade: number;
  letter_grade: string;
  color: 'green' | 'yellow' | 'red';
}

export interface ChildGradeSummary {
  student_id: number;
  student_name: string;
  overall_average: number;
  letter_grade: string;
  color: 'green' | 'yellow' | 'red';
  courses: CourseGradeInfo[];
}

export interface GradeSummaryResponse {
  children: ChildGradeSummary[];
}

export interface CourseAssignmentGrade {
  grade_record_id: number;
  assignment_id: number | null;
  assignment_title: string;
  grade: number;
  max_grade: number;
  percentage: number;
  letter_grade: string;
  color: 'green' | 'yellow' | 'red';
  due_date: string | null;
  status: string;
  student_id: number;
  recorded_at: string | null;
}

export interface CourseGradesResponse {
  course_id: number;
  course_name: string;
  average_grade: number;
  letter_grade: string;
  color: 'green' | 'yellow' | 'red';
  total_graded: number;
  assignments: CourseAssignmentGrade[];
}

export interface GradeSyncResponse {
  synced: number;
  errors: number;
  message: string;
}

// --- API ---

export const gradesApi = {
  summary: async (studentId?: number) => {
    const params: Record<string, unknown> = {};
    if (studentId) params.student_id = studentId;
    const resp = await api.get('/api/grades/summary', { params });
    return resp.data as GradeSummaryResponse;
  },

  byCourse: async (courseId: number, studentId?: number) => {
    const params: Record<string, unknown> = {};
    if (studentId) params.student_id = studentId;
    const resp = await api.get(`/api/grades/course/${courseId}`, { params });
    return resp.data as CourseGradesResponse;
  },

  syncGrades: async (courseId: number) => {
    const resp = await api.post(`/api/google/sync-grades/${courseId}`);
    return resp.data as GradeSyncResponse;
  },
};
