/**
 * Mock Exam API client — AI-generated teacher exams (#667).
 */
import { api } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface QuestionItem {
  question: string;
  options: string[]; // exactly 4
  correct_index?: number; // hidden for students until completed
  explanation?: string;
}

export interface MockExam {
  id: number;
  teacher_user_id: number;
  course_id: number;
  course_name: string | null;
  title: string;
  description: string | null;
  questions: QuestionItem[];
  num_questions: number;
  time_limit_minutes: number;
  total_marks: number;
  is_published: boolean;
  created_at: string | null;
  assignment_count: number;
  completed_count: number;
}

export interface MockExamAssignment {
  id: number;
  exam_id: number;
  exam_title: string | null;
  course_id: number | null;
  course_name: string | null;
  time_limit_minutes: number | null;
  total_marks: number | null;
  num_questions: number;
  questions: QuestionItem[];
  student_id: number;
  student_name: string | null;
  assigned_at: string | null;
  due_date: string | null;
  started_at: string | null;
  completed_at: string | null;
  answers: number[] | null;
  score: number | null;
  time_taken_seconds: number | null;
  status: 'assigned' | 'in_progress' | 'completed';
}

export interface GenerateExamRequest {
  course_id: number;
  topic: string;
  num_questions: number;
  difficulty: 'easy' | 'medium' | 'hard';
  time_limit_minutes: number;
}

export interface GenerateExamResponse {
  course_id: number;
  course_name: string;
  topic: string;
  difficulty: string;
  time_limit_minutes: number;
  suggested_title: string;
  questions: QuestionItem[];
  num_questions: number;
  total_marks: number;
}

export interface SaveExamRequest {
  course_id: number;
  title: string;
  description?: string;
  questions: QuestionItem[];
  time_limit_minutes: number;
  total_marks?: number;
}

export interface AssignExamRequest {
  student_ids: number[] | 'all';
  due_date?: string | null;
}

export interface AssignExamResponse {
  exam_id: number;
  assigned_count: number;
  skipped_count: number;
  assignment_ids: number[];
}

export interface SubmitAnswersRequest {
  answers: number[];
  time_taken_seconds: number;
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export const mockExamsApi = {
  /**
   * Generate exam questions via AI (preview only, not saved).
   */
  generate: async (body: GenerateExamRequest): Promise<GenerateExamResponse> => {
    const res = await api.post('/api/mock-exams/generate', body);
    return res.data;
  },

  /**
   * Save a generated exam.
   */
  save: async (body: SaveExamRequest): Promise<MockExam> => {
    const res = await api.post('/api/mock-exams/', body);
    return res.data;
  },

  /**
   * Assign an exam to students.
   */
  assign: async (examId: number, body: AssignExamRequest): Promise<AssignExamResponse> => {
    const res = await api.post(`/api/mock-exams/${examId}/assign`, body);
    return res.data;
  },

  /**
   * List exams (teachers see theirs; students see assigned).
   */
  list: async (courseId?: number): Promise<MockExam[] | MockExamAssignment[]> => {
    const params: Record<string, string | number> = {};
    if (courseId !== undefined) params.course_id = courseId;
    const res = await api.get('/api/mock-exams/', { params });
    return res.data;
  },

  /**
   * Get a specific assignment by assignment ID (used by ExamPage).
   */
  getAssignment: async (assignmentId: number): Promise<MockExamAssignment> => {
    const res = await api.get(`/api/mock-exams/assignments/${assignmentId}`);
    return res.data;
  },

  /**
   * Submit answers for an assignment.
   */
  submit: async (assignmentId: number, body: SubmitAnswersRequest): Promise<MockExamAssignment> => {
    const res = await api.patch(`/api/mock-exams/assignments/${assignmentId}/submit`, body);
    return res.data;
  },

  /**
   * Delete an exam (teacher only).
   */
  deleteExam: async (examId: number): Promise<void> => {
    await api.delete(`/api/mock-exams/${examId}`);
  },
};
