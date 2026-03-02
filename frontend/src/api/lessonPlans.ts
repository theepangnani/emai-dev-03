/**
 * Lesson Plans API client — TeachAssist integration.
 *
 * All endpoints require TEACHER or ADMIN role.
 */
import { api } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type LessonPlanType = 'long_range' | 'unit' | 'daily';

export interface ThreePartLesson {
  minds_on?: string | null;
  action?: string | null;
  consolidation?: string | null;
}

export interface DifferentiationPlan {
  enrichment?: string | null;
  support?: string | null;
  ell?: string | null;
}

export interface LessonPlanItem {
  id: number;
  teacher_id: number;
  course_id: number | null;
  plan_type: LessonPlanType;
  title: string;
  strand: string | null;
  unit_number: number | null;
  grade_level: string | null;
  subject_code: string | null;
  big_ideas: string[];
  curriculum_expectations: string[];
  overall_expectations: string[];
  specific_expectations: string[];
  learning_goals: string[];
  success_criteria: string[];
  three_part_lesson: ThreePartLesson | null;
  assessment_for_learning: string | null;
  assessment_of_learning: string | null;
  differentiation: DifferentiationPlan | null;
  materials_resources: string[];
  cross_curricular: string[];
  duration_minutes: number | null;
  start_date: string | null;  // ISO date string
  end_date: string | null;    // ISO date string
  is_template: boolean;
  imported_from: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface LessonPlanCreate {
  plan_type: LessonPlanType;
  title: string;
  course_id?: number | null;
  strand?: string;
  unit_number?: number;
  grade_level?: string;
  subject_code?: string;
  big_ideas?: string[];
  curriculum_expectations?: string[];
  overall_expectations?: string[];
  specific_expectations?: string[];
  learning_goals?: string[];
  success_criteria?: string[];
  three_part_lesson?: ThreePartLesson | null;
  assessment_for_learning?: string;
  assessment_of_learning?: string;
  differentiation?: DifferentiationPlan | null;
  materials_resources?: string[];
  cross_curricular?: string[];
  duration_minutes?: number;
  start_date?: string;
  end_date?: string;
  is_template?: boolean;
}

export type LessonPlanUpdate = Partial<LessonPlanCreate>;

export interface LessonPlanListParams {
  plan_type?: LessonPlanType;
  course_id?: number;
  grade_level?: string;
}

export interface ImportResult {
  imported: number;
  plans: LessonPlanItem[];
}

// ---------------------------------------------------------------------------
// API client
// ---------------------------------------------------------------------------

export const lessonPlanApi = {
  /** List the current teacher's lesson plans, with optional filters. */
  list: async (params?: LessonPlanListParams): Promise<LessonPlanItem[]> => {
    const response = await api.get('/api/lesson-plans/', { params });
    return response.data as LessonPlanItem[];
  },

  /** Get a single lesson plan by ID. */
  get: async (id: number): Promise<LessonPlanItem> => {
    const response = await api.get(`/api/lesson-plans/${id}`);
    return response.data as LessonPlanItem;
  },

  /** Create a new lesson plan. */
  create: async (data: LessonPlanCreate): Promise<LessonPlanItem> => {
    const response = await api.post('/api/lesson-plans/', data);
    return response.data as LessonPlanItem;
  },

  /** Update a lesson plan (partial update supported). */
  update: async (id: number, data: LessonPlanUpdate): Promise<LessonPlanItem> => {
    const response = await api.put(`/api/lesson-plans/${id}`, data);
    return response.data as LessonPlanItem;
  },

  /** Delete a lesson plan permanently. */
  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/lesson-plans/${id}`);
  },

  /** Duplicate a lesson plan. */
  duplicate: async (id: number): Promise<LessonPlanItem> => {
    const response = await api.post(`/api/lesson-plans/${id}/duplicate`);
    return response.data as LessonPlanItem;
  },

  /** List all public/shared templates. */
  templates: async (): Promise<LessonPlanItem[]> => {
    const response = await api.get('/api/lesson-plans/templates');
    return response.data as LessonPlanItem[];
  },

  /** Import lesson plans from a TeachAssist XML or CSV file. */
  import: async (file: File): Promise<ImportResult> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/lesson-plans/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data as ImportResult;
  },

  /** AI-generate learning goals, success criteria, and 3-part lesson for a plan. */
  aiGenerate: async (id: number): Promise<LessonPlanItem> => {
    const response = await api.post(`/api/lesson-plans/${id}/ai-generate`);
    return response.data as LessonPlanItem;
  },
};
