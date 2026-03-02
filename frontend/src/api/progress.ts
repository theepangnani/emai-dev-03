import { api } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StudyStreak {
  current: number;
  longest: number;
  last_study_date: string | null;
}

export interface QuizGuideStats {
  guide_title: string;
  avg_score: number;
  attempts: number;
}

export interface QuizPerformance {
  total_attempts: number;
  average_score: number;
  by_guide: QuizGuideStats[];
}

export interface TeacherGradeCourse {
  course_name: string;
  average: number;
  letter: string;
  entries: number;
}

export interface TeacherGrades {
  overall_average: number;
  by_course: TeacherGradeCourse[];
}

export interface ReportCardTerm {
  term: string;
  average: number;
}

export interface ReportCards {
  latest_average: number | null;
  by_term: ReportCardTerm[];
}

export interface AssignmentStats {
  total: number;
  submitted: number;
  submission_rate_pct: number;
}

export interface StudentProgress {
  student_id: number;
  student_name: string;
  study_streak: StudyStreak;
  quiz_performance: QuizPerformance;
  teacher_grades: TeacherGrades;
  report_cards: ReportCards;
  assignments: AssignmentStats;
  ai_insights: string | null;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const progressApi = {
  /**
   * Fetch the consolidated progress snapshot for a student.
   * @param studentId  The student's DB id.
   * @param refreshAi  When true, bypass the 24 h AI cache and generate fresh insights.
   */
  getStudentProgress: async (studentId: number, refreshAi = false): Promise<StudentProgress> => {
    const resp = await api.get(`/api/students/${studentId}/progress`, {
      params: refreshAi ? { refresh_ai: true } : undefined,
    });
    return resp.data as StudentProgress;
  },

  /**
   * Fetch via the parent-scoped alias (same data, parent RBAC gate).
   */
  getChildProgress: async (studentId: number, refreshAi = false): Promise<StudentProgress> => {
    const resp = await api.get(`/api/parent/children/${studentId}/progress`, {
      params: refreshAi ? { refresh_ai: true } : undefined,
    });
    return resp.data as StudentProgress;
  },
};
