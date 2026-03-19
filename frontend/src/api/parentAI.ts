import { api, AI_TIMEOUT } from './client';

export interface WeakSpot {
  topic: string;
  severity: 'high' | 'medium' | 'low';
  detail: string;
  quiz_score_summary: string | null;
  suggested_action: string;
}

export interface WeakSpotsResponse {
  student_name: string;
  course_name: string | null;
  weak_spots: WeakSpot[];
  summary: string;
  total_quizzes_analyzed: number;
  total_assignments_analyzed: number;
}

export interface ReadinessItem {
  label: string;
  status: 'done' | 'partial' | 'missing';
  detail: string | null;
}

export interface ReadinessCheckResponse {
  student_name: string;
  assignment_title: string;
  course_name: string;
  readiness_score: number;
  summary: string;
  items: ReadinessItem[];
}

export interface PracticeProblem {
  number: number;
  question: string;
  hint: string | null;
}

export interface PracticeProblemsResponse {
  student_name: string;
  course_name: string;
  topic: string;
  problems: PracticeProblem[];
  instructions: string;
}

export const parentAIApi = {
  getWeakSpots: (studentId: number, courseId?: number) =>
    api.post<WeakSpotsResponse>('/api/parent-ai/weak-spots', {
      student_id: studentId,
      course_id: courseId ?? null,
    }, AI_TIMEOUT),

  checkReadiness: (studentId: number, assignmentId: number) =>
    api.post<ReadinessCheckResponse>('/api/parent-ai/readiness-check', {
      student_id: studentId,
      assignment_id: assignmentId,
    }, AI_TIMEOUT),

  generatePracticeProblems: (studentId: number, courseId: number, topic: string) =>
    api.post<PracticeProblemsResponse>('/api/parent-ai/practice-problems', {
      student_id: studentId,
      course_id: courseId,
      topic,
    }, AI_TIMEOUT),
};
