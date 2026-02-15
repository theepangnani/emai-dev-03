import { api } from './client';

// Parent Types (ported from web frontend/src/api/parent.ts)
export interface ChildHighlight {
  student_id: number;
  user_id: number;
  full_name: string;
  grade_level: number | null;
  overdue_count: number;
  due_today_count: number;
  upcoming_count: number;
  completed_today_count: number;
  courses: Array<{
    id: number;
    name: string;
    description: string | null;
    subject: string | null;
    google_classroom_id: string | null;
    teacher_id: number | null;
    created_at: string;
    teacher_name: string | null;
    teacher_email: string | null;
  }>;
  overdue_items: Array<{
    title: string;
    type: string;
    course_name: string;
    due_date: string;
  }>;
  due_today_items: Array<{
    title: string;
    type: string;
    course_name: string;
    due_date: string;
  }>;
}

export interface ParentDashboardData {
  children: ChildSummary[];
  google_connected: boolean;
  unread_messages: number;
  total_overdue: number;
  total_due_today: number;
  total_tasks: number;
  child_highlights: ChildHighlight[];
  all_assignments: Array<{
    id: number;
    title: string;
    description: string | null;
    course_id: number;
    google_classroom_id: string | null;
    due_date: string | null;
    max_points: number | null;
    created_at: string;
  }>;
  all_tasks: Array<Record<string, unknown>>;
}

export interface ChildSummary {
  student_id: number;
  user_id: number;
  full_name: string;
  email: string | null;
  grade_level: number | null;
  school_name: string | null;
  date_of_birth: string | null;
  phone: string | null;
  address: string | null;
  city: string | null;
  province: string | null;
  postal_code: string | null;
  notes: string | null;
  relationship_type: string | null;
  invite_link: string | null;
  course_count: number;
  active_task_count: number;
}

export interface ChildOverview {
  student_id: number;
  user_id: number;
  full_name: string;
  grade_level: number | null;
  google_connected: boolean;
  courses: Array<{
    id: number;
    name: string;
    description: string | null;
    subject: string | null;
    google_classroom_id: string | null;
    teacher_id: number | null;
    created_at: string;
    teacher_name: string | null;
    teacher_email: string | null;
  }>;
  assignments: Array<{
    id: number;
    title: string;
    description: string | null;
    course_id: number;
    google_classroom_id: string | null;
    due_date: string | null;
    max_points: number | null;
    created_at: string;
  }>;
  study_guides_count: number;
}

// Parent API — mobile uses read-only subset
export const parentApi = {
  getDashboard: async () => {
    const response = await api.get('/api/parent/dashboard');
    return response.data as ParentDashboardData;
  },

  getChildren: async () => {
    const response = await api.get('/api/parent/children');
    return response.data as ChildSummary[];
  },

  getChildOverview: async (studentId: number) => {
    const response = await api.get(
      `/api/parent/children/${studentId}/overview`
    );
    return response.data as ChildOverview;
  },
};
