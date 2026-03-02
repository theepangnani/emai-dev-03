import { api } from './client';

// ─── Interfaces ──────────────────────────────────────────────────────────────

export interface OntarioBoard {
  id: number;
  name: string;
  short_name: string;
  region: string;
}

export type CoursePathway = 'U' | 'C' | 'M' | 'E' | 'O';

export interface CourseCatalogItem {
  id: number;
  course_code: string;
  course_name: string;
  grade_level: 9 | 10 | 11 | 12;
  subject_area: string;
  pathway: CoursePathway;
  credits: number;
  prerequisites: string[]; // list of course codes
  description?: string;
  board_id: number;
}

export interface PlanCourse {
  id: number;
  course_code: string;
  course_name: string;
  grade_level: 9 | 10 | 11 | 12;
  semester: 1 | 2;
  credits: number;
  pathway: CoursePathway;
  subject_area: string;
  prerequisites: string[];
  has_prerequisite_warning?: boolean;
}

export interface AcademicPlan {
  id: number;
  student_id: number;
  student_name?: string;
  plan_name: string;
  board_id: number;
  board_name?: string;
  created_at: string;
  updated_at: string;
  courses: PlanCourse[];
  total_credits: number;
}

export interface ValidationIssue {
  course_code: string;
  issue_type: 'missing_prerequisite' | 'credit_shortfall' | 'compulsory_missing' | 'overloaded_semester';
  message: string;
  severity: 'error' | 'warning';
}

export interface OssdRequirement {
  name: string;
  required_credits: number;
  earned_credits: number;
  fulfilled: boolean;
}

export interface ValidationResult {
  is_valid: boolean;
  total_credits: number;
  credits_needed: number;
  issues: ValidationIssue[];
  ossd_requirements: OssdRequirement[];
  compulsory_fulfilled: boolean;
}

// ─── API Client ───────────────────────────────────────────────────────────────

export const academicPlanApi = {
  /** List all Ontario school boards */
  getBoards: async (): Promise<OntarioBoard[]> => {
    const res = await api.get<OntarioBoard[]>('/api/ontario/boards');
    return res.data;
  },

  /** Browse course catalog for a board, with optional filters */
  getCourses: async (
    boardId: number,
    params?: {
      grade?: 9 | 10 | 11 | 12;
      subject?: string;
      search?: string;
    },
  ): Promise<CourseCatalogItem[]> => {
    const res = await api.get<CourseCatalogItem[]>(
      `/api/ontario/boards/${boardId}/courses`,
      { params },
    );
    return res.data;
  },

  /** Create a new academic plan */
  createPlan: async (data: {
    plan_name: string;
    board_id: number;
    student_id?: number;
  }): Promise<AcademicPlan> => {
    const res = await api.post<AcademicPlan>('/api/academic-plans/', data);
    return res.data;
  },

  /** List all academic plans (for current user / linked students) */
  getPlans: async (): Promise<AcademicPlan[]> => {
    const res = await api.get<AcademicPlan[]>('/api/academic-plans/');
    return res.data;
  },

  /** Get a single academic plan with all courses */
  getPlan: async (id: number): Promise<AcademicPlan> => {
    const res = await api.get<AcademicPlan>(`/api/academic-plans/${id}`);
    return res.data;
  },

  /** Add a course to a plan */
  addCourse: async (
    planId: number,
    data: {
      course_code: string;
      grade_level: 9 | 10 | 11 | 12;
      semester: 1 | 2;
    },
  ): Promise<PlanCourse> => {
    const res = await api.post<PlanCourse>(
      `/api/academic-plans/${planId}/courses`,
      data,
    );
    return res.data;
  },

  /** Remove a course from a plan */
  removeCourse: async (planId: number, planCourseId: number): Promise<void> => {
    await api.delete(`/api/academic-plans/${planId}/courses/${planCourseId}`);
  },

  /** Validate a plan against OSSD rules and prerequisites */
  validatePlan: async (id: number): Promise<ValidationResult> => {
    const res = await api.get<ValidationResult>(
      `/api/academic-plans/${id}/validate`,
    );
    return res.data;
  },
};
