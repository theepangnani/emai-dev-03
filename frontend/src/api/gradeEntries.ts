import { api } from './client';

// --- Types ---

export interface AssignmentColumn {
  id: number;
  title: string;
  due_date: string | null;
}

export interface GradeCell {
  id: number;
  grade: number | null;
  max_grade: number;
  letter_grade: string | null;
  feedback: string | null;
  is_published: boolean;
  term: string | null;
}

export interface StudentRow {
  student_id: number;
  student_name: string;
  /** Key is assignment id (string) or "term:Fall 2025" */
  grades: Record<string, GradeCell | null>;
}

export interface CourseGradeMatrix {
  course_id: number;
  course_name: string;
  assignments: AssignmentColumn[];
  students: StudentRow[];
}

export interface BulkEntryItem {
  student_id: number;
  course_id: number;
  assignment_id?: number | null;
  term?: string | null;
  grade?: number | null;
  max_grade?: number;
  feedback?: string | null;
  is_published?: boolean;
}

export interface BulkUpsertResponse {
  updated: number;
  created: number;
  entries: Array<{
    id: number;
    student_id: number;
    course_id: number;
    assignment_id: number | null;
    term: string | null;
    grade: number | null;
    max_grade: number;
    letter_grade: string | null;
    feedback: string | null;
    is_published: boolean;
  }>;
}

export interface TeacherGradeEntry {
  id: number;
  assignment_id: number | null;
  assignment_title: string | null;
  term: string | null;
  grade: number | null;
  max_grade: number;
  letter_grade: string | null;
  feedback: string | null;
  is_published: boolean;
}

export interface TeacherGradeCourse {
  course_id: number;
  course_name: string;
  grades: TeacherGradeEntry[];
}

export interface StudentGradesResponse {
  student_id: number;
  student_name: string;
  courses: TeacherGradeCourse[];
}

export interface PublishResponse {
  published: number;
  notifications_sent: number;
  message: string;
}

// --- API ---

export const gradeEntriesApi = {
  /**
   * Teacher: get the student×assignment grade matrix for a course.
   */
  getCourseMatrix: async (courseId: number): Promise<CourseGradeMatrix> => {
    const resp = await api.get(`/api/grade-entries/course/${courseId}`);
    return resp.data as CourseGradeMatrix;
  },

  /**
   * Teacher: atomically upsert a batch of grade entries.
   */
  bulkUpsert: async (entries: BulkEntryItem[]): Promise<BulkUpsertResponse> => {
    const resp = await api.put('/api/grade-entries/bulk', { entries });
    return resp.data as BulkUpsertResponse;
  },

  /**
   * Student / parent: get published teacher-entered grades for a student.
   */
  getStudentGrades: async (studentId: number): Promise<StudentGradesResponse> => {
    const resp = await api.get(`/api/grade-entries/student/${studentId}`);
    return resp.data as StudentGradesResponse;
  },

  /**
   * Teacher: publish all draft grades for a course + send student notifications.
   */
  publishCourseGrades: async (courseId: number): Promise<PublishResponse> => {
    const resp = await api.post(`/api/grade-entries/publish/${courseId}`);
    return resp.data as PublishResponse;
  },
};
