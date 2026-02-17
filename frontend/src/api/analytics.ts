import { api } from './client';

export interface GradeItem {
  student_assignment_id: number;
  assignment_id: number | null;
  assignment_title: string | null;
  course_id: number;
  course_name: string;
  grade: number;
  max_points: number;
  percentage: number;
  status: string;
  source: string;
  submitted_at: string | null;
  due_date: string | null;
}

export interface CourseAverage {
  course_id: number;
  course_name: string;
  average_percentage: number;
  graded_count: number;
  total_count: number;
  completion_rate: number;
}

export interface GradeSummary {
  overall_average: number;
  total_graded: number;
  total_assignments: number;
  completion_rate: number;
  course_averages: CourseAverage[];
  trend: string;
}

export interface TrendPoint {
  date: string;
  percentage: number;
  assignment_title: string;
  course_name: string;
}

export interface TrendResponse {
  points: TrendPoint[];
  trend: string;
}

export interface AIInsight {
  insight: string;
  generated_at: string;
}

export interface WeeklyReport {
  id: number;
  student_id: number;
  report_type: string;
  period_start: string;
  period_end: string;
  data: Record<string, unknown>;
  generated_at: string;
}

export interface SyncResult {
  synced: number;
  errors: number;
  message: string;
}

export const analyticsApi = {
  getSummary: async (studentId: number) => {
    const resp = await api.get('/api/analytics/summary', { params: { student_id: studentId } });
    return resp.data as GradeSummary;
  },

  getTrends: async (studentId: number, courseId?: number, days?: number) => {
    const params: Record<string, unknown> = { student_id: studentId };
    if (courseId) params.course_id = courseId;
    if (days) params.days = days;
    const resp = await api.get('/api/analytics/trends', { params });
    return resp.data as TrendResponse;
  },

  getGrades: async (studentId: number, courseId?: number, limit?: number, offset?: number) => {
    const params: Record<string, unknown> = { student_id: studentId };
    if (courseId) params.course_id = courseId;
    if (limit) params.limit = limit;
    if (offset) params.offset = offset;
    const resp = await api.get('/api/analytics/grades', { params });
    return resp.data as { grades: GradeItem[]; total: number };
  },

  getAIInsight: async (studentId: number, focusArea?: string) => {
    const resp = await api.post('/api/analytics/ai-insights', {
      student_id: studentId,
      focus_area: focusArea ?? null,
    });
    return resp.data as AIInsight;
  },

  getWeeklyReport: async (studentId: number) => {
    const resp = await api.get('/api/analytics/reports/weekly', { params: { student_id: studentId } });
    return resp.data as WeeklyReport;
  },

  syncGrades: async (studentId: number) => {
    const resp = await api.post('/api/analytics/sync-grades', null, { params: { student_id: studentId } });
    return resp.data as SyncResult;
  },
};
