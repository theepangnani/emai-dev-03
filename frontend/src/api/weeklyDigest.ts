import { api } from './client';

export interface DigestChildTask {
  completed: number;
  total: number;
}

export interface DigestChildAssignment {
  submitted: number;
  due: number;
}

export interface DigestQuizScore {
  quiz_count: number;
  average_percentage: number | null;
}

export interface DigestOverdueItem {
  id: number;
  title: string;
  due_date: string | null;
  item_type: string;
}

export interface ChildDigest {
  student_id: number;
  full_name: string;
  grade_level: number | null;
  tasks: DigestChildTask;
  assignments: DigestChildAssignment;
  study_guides_created: number;
  quiz_scores: DigestQuizScore;
  overdue_items: DigestOverdueItem[];
  highlight: string;
}

export interface WeeklyDigestResponse {
  week_start: string;
  week_end: string;
  greeting: string;
  children: ChildDigest[];
  overall_summary: string;
}

export interface WeeklyDigestSendResponse {
  success: boolean;
  message: string;
}

export const weeklyDigestApi = {
  preview: async () => {
    const response = await api.get('/api/digest/weekly/preview');
    return response.data as WeeklyDigestResponse;
  },
  send: async () => {
    const response = await api.post('/api/digest/weekly/send');
    return response.data as WeeklyDigestSendResponse;
  },
};
