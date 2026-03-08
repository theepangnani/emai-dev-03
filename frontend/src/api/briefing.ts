import { api } from './client';

export interface BriefingTask {
  id: number;
  title: string;
  due_date: string | null;
  priority: string;
  course_name: string | null;
  is_overdue: boolean;
}

export interface BriefingAssignment {
  id: number;
  title: string;
  due_date: string | null;
  course_name: string;
  max_points: number | null;
  status: string;
  is_late: boolean;
}

export interface BriefingChildSection {
  student_id: number;
  full_name: string;
  grade_level: number | null;
  overdue_tasks: BriefingTask[];
  due_today_tasks: BriefingTask[];
  upcoming_assignments: BriefingAssignment[];
  recent_study_count: number;
  needs_attention: boolean;
}

export interface DailyBriefingResponse {
  date: string;
  greeting: string;
  children: BriefingChildSection[];
  total_overdue: number;
  total_due_today: number;
  total_upcoming: number;
  attention_needed: boolean;
}

export const briefingApi = {
  getDaily: async () => {
    const response = await api.get('/api/briefing/daily');
    return response.data as DailyBriefingResponse;
  },
};
