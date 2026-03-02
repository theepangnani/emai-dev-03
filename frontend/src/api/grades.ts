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

// --- Google Classroom live grade types (#838) ---

/** A single graded submission fetched live from Google Classroom. */
export interface ClassroomGradeItem {
  course_id: number | null;
  course_name: string;
  assignment_title: string;
  assignment_id: number | null;
  grade: number;
  max_grade: number;
  percentage: number;
  graded_at: string | null;
}

export interface ClassroomGradesResponse {
  grades: ClassroomGradeItem[];
  cached: boolean;
}

export interface ClassroomCourseGradesResponse {
  grades: ClassroomGradeItem[];
  course_id: number;
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

  /**
   * Fetch live graded submissions from Google Classroom for the current student.
   * Parents: pass childId (user_id of child) to get grades for a linked child.
   * Returns [] if Google is not connected or the API call fails.
   */
  getGrades: async (childId?: number): Promise<ClassroomGradeItem[]> => {
    const params: Record<string, unknown> = {};
    if (childId !== undefined) params.child_id = childId;
    const resp = await api.get('/api/google/classroom/grades', { params });
    return (resp.data as ClassroomGradesResponse).grades ?? [];
  },

  /**
   * Fetch live graded submissions from Google Classroom for a specific course.
   */
  getCourseGrades: async (courseId: number, childId?: number): Promise<ClassroomGradeItem[]> => {
    const params: Record<string, unknown> = {};
    if (childId !== undefined) params.child_id = childId;
    const resp = await api.get(`/api/google/classroom/grades/course/${courseId}`, { params });
    return (resp.data as ClassroomCourseGradesResponse).grades ?? [];
  },
};
