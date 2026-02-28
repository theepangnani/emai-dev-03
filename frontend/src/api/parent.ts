import { api } from './client';

// Parent Types
export interface ChildHighlight {
  student_id: number;
  user_id: number;
  full_name: string;
  grade_level: number | null;
  overdue_count: number;
  due_today_count: number;
  upcoming_count: number;
  completed_today_count: number;
  courses: Array<{ id: number; name: string; description: string | null; subject: string | null; google_classroom_id: string | null; classroom_type?: string | null; teacher_id: number | null; created_at: string; teacher_name: string | null; teacher_email: string | null }>;
  overdue_items: Array<{ title: string; type: string; course_name: string; due_date: string }>;
  due_today_items: Array<{ title: string; type: string; course_name: string; due_date: string }>;
}

export interface ParentDashboardData {
  children: ChildSummary[];
  google_connected: boolean;
  unread_messages: number;
  total_overdue: number;
  total_due_today: number;
  total_tasks: number;
  child_highlights: ChildHighlight[];
  all_assignments: Array<{ id: number; title: string; description: string | null; course_id: number; google_classroom_id: string | null; due_date: string | null; max_points: number | null; created_at: string }>;
  all_tasks: Array<Record<string, any>>;
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
  invite_status: 'active' | 'pending' | 'email_unverified' | null;
  invite_id: number | null;
}

export interface ChildOverview {
  student_id: number;
  user_id: number;
  full_name: string;
  grade_level: number | null;
  google_connected: boolean;
  courses: Array<{ id: number; name: string; description: string | null; subject: string | null; google_classroom_id: string | null; classroom_type?: string | null; teacher_id: number | null; created_at: string; teacher_name: string | null; teacher_email: string | null }>;
  assignments: Array<{ id: number; title: string; description: string | null; course_id: number; google_classroom_id: string | null; due_date: string | null; max_points: number | null; created_at: string }>;
  study_guides_count: number;
}

export interface DiscoveredChild {
  user_id: number;
  email: string;
  full_name: string;
  google_courses: string[];
  already_linked: boolean;
}

export interface DiscoverChildrenResponse {
  discovered: DiscoveredChild[];
  google_connected: boolean;
  courses_searched: number;
}

export interface LinkedTeacher {
  id: number;
  student_id: number;
  teacher_user_id: number | null;
  teacher_name: string | null;
  teacher_email: string | null;
  added_by_user_id: number;
  created_at: string | null;
}

// Parent API
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
    const response = await api.get(`/api/parent/children/${studentId}/overview`);
    return response.data as ChildOverview;
  },

  linkChild: async (studentEmail: string, relationshipType: string = 'guardian', fullName?: string) => {
    const response = await api.post('/api/parent/children/link', {
      student_email: studentEmail,
      relationship_type: relationshipType,
      ...(fullName ? { full_name: fullName } : {}),
    });
    return response.data as ChildSummary;
  },

  discoverViaGoogle: async () => {
    const response = await api.post('/api/parent/children/discover-google');
    return response.data as DiscoverChildrenResponse;
  },

  linkChildrenBulk: async (userIds: number[], relationshipType: string = 'guardian') => {
    const response = await api.post('/api/parent/children/link-bulk', {
      user_ids: userIds,
      relationship_type: relationshipType,
    });
    return response.data as ChildSummary[];
  },

  syncChildCourses: async (studentId: number) => {
    const response = await api.post(`/api/parent/children/${studentId}/sync-courses`);
    return response.data as { message: string; courses: Array<{ id: number; name: string; google_id: string }> };
  },

  createChild: async (fullName: string, relationshipType: string = 'guardian', email?: string) => {
    const response = await api.post('/api/parent/children/create', {
      full_name: fullName,
      relationship_type: relationshipType,
      ...(email ? { email } : {}),
    });
    return response.data as ChildSummary;
  },

  updateChild: async (studentId: number, data: { full_name?: string; email?: string; grade_level?: number; school_name?: string; date_of_birth?: string; phone?: string; address?: string; city?: string; province?: string; postal_code?: string; notes?: string }) => {
    const response = await api.patch(`/api/parent/children/${studentId}`, data);
    return response.data as ChildSummary;
  },

  assignCoursesToChild: async (studentId: number, courseIds: number[]) => {
    const response = await api.post(`/api/parent/children/${studentId}/courses`, {
      course_ids: courseIds,
    });
    return response.data as { message: string; assigned: Array<{ course_id: number; course_name: string }> };
  },

  unassignCourseFromChild: async (studentId: number, courseId: number) => {
    const response = await api.delete(`/api/parent/children/${studentId}/courses/${courseId}`);
    return response.data;
  },

  linkTeacher: async (studentId: number, teacherEmail: string, teacherName?: string) => {
    const response = await api.post(`/api/parent/children/${studentId}/teachers`, {
      teacher_email: teacherEmail,
      ...(teacherName ? { teacher_name: teacherName } : {}),
    });
    return response.data as LinkedTeacher;
  },

  getLinkedTeachers: async (studentId: number) => {
    const response = await api.get(`/api/parent/children/${studentId}/teachers`);
    return response.data as LinkedTeacher[];
  },

  unlinkTeacher: async (studentId: number, linkId: number) => {
    const response = await api.delete(`/api/parent/children/${studentId}/teachers/${linkId}`);
    return response.data;
  },

  resetChildPassword: async (studentId: number, newPassword?: string) => {
    const response = await api.post(`/api/parent/children/${studentId}/reset-password`, {
      ...(newPassword ? { new_password: newPassword } : {}),
    });
    return response.data as { message: string };
  },

  requestCompletion: async (studentId: number, taskId: number, message?: string) => {
    const response = await api.post(`/api/parent/children/${studentId}/request-completion`, {
      task_id: taskId,
      ...(message ? { message } : {}),
    });
    return response.data as { message: string };
  },
};
