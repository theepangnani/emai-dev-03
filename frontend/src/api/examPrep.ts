import { api } from './client';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface WeakArea {
  topic: string;
  confidence_pct: number;  // 0-100
  source: 'quiz' | 'test' | 'teacher_grade' | string;
}

export interface StudyDay {
  day: string;   // "Day 1", "Day 2", ...
  tasks: string[];
}

export interface PrepResource {
  type: 'review' | 'practice' | 'memorize' | string;
  title: string;
  study_guide_id?: number;
}

export interface ExamPrepPlan {
  id: number;
  student_id: number;
  course_id: number | null;
  course_name: string | null;
  exam_date: string | null;      // ISO date string
  title: string;
  weak_areas: WeakArea[] | null;
  study_schedule: StudyDay[] | null;
  recommended_resources: PrepResource[] | null;
  ai_advice: string | null;
  status: 'active' | 'completed' | 'archived';
  generated_at: string;          // ISO datetime string
}

export interface GeneratePlanRequest {
  title: string;
  student_id?: number;   // required for parent role
  course_id?: number;
  exam_date?: string;    // ISO date string "YYYY-MM-DD"
}

// ─── API Client ───────────────────────────────────────────────────────────────

export const examPrepApi = {
  /**
   * Generate a new AI exam prep plan.
   * Analyzes quiz history, report cards, and grade entries.
   */
  generate: async (data: GeneratePlanRequest): Promise<ExamPrepPlan> => {
    const res = await api.post<ExamPrepPlan>('/api/exam-prep/generate', data);
    return res.data;
  },

  /**
   * List all active exam prep plans for the current user's students.
   */
  list: async (): Promise<ExamPrepPlan[]> => {
    const res = await api.get<ExamPrepPlan[]>('/api/exam-prep/');
    return res.data;
  },

  /**
   * Get full details of a specific exam prep plan.
   */
  get: async (id: number): Promise<ExamPrepPlan> => {
    const res = await api.get<ExamPrepPlan>(`/api/exam-prep/${id}`);
    return res.data;
  },

  /**
   * Archive (soft-delete) an exam prep plan.
   */
  archive: async (id: number): Promise<void> => {
    await api.delete(`/api/exam-prep/${id}`);
  },
};
