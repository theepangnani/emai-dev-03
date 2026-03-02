import { api } from './client';

export interface QuizAssignmentCreate {
  student_id: number;
  study_guide_id: number;
  difficulty: 'easy' | 'medium' | 'hard';
  due_date?: string | null;   // ISO date string YYYY-MM-DD
  note?: string | null;
}

export interface QuizAssignmentResponse {
  id: number;
  parent_user_id: number;
  student_id: number;
  study_guide_id: number;
  difficulty: 'easy' | 'medium' | 'hard';
  due_date: string | null;
  assigned_at: string;
  completed_at: string | null;
  score: number | null;
  attempt_count: number;
  status: 'assigned' | 'in_progress' | 'completed';
  note: string | null;
  // Joined fields
  study_guide_title: string | null;
  course_name: string | null;
  student_name: string | null;
}

export interface QuizAssignmentListParams {
  status?: 'assigned' | 'in_progress' | 'completed';
  student_id?: number;
}

export const quizAssignmentsApi = {
  /** Parent assigns a quiz to their child. */
  assign(data: QuizAssignmentCreate): Promise<QuizAssignmentResponse> {
    return api.post<QuizAssignmentResponse>('/api/quiz-assignments/', data).then(r => r.data);
  },

  /** List assignments — role-scoped (parent sees own, student sees assigned). */
  list(params?: QuizAssignmentListParams): Promise<QuizAssignmentResponse[]> {
    return api
      .get<QuizAssignmentResponse[]>('/api/quiz-assignments/', { params })
      .then(r => r.data);
  },

  /** Student marks a quiz assignment complete with a score (0-100). */
  complete(id: number, score: number): Promise<QuizAssignmentResponse> {
    return api
      .patch<QuizAssignmentResponse>(`/api/quiz-assignments/${id}/complete`, { score })
      .then(r => r.data);
  },

  /** Parent cancels a quiz assignment (only if not yet completed). */
  cancel(id: number): Promise<void> {
    return api.delete(`/api/quiz-assignments/${id}`).then(() => undefined);
  },
};
