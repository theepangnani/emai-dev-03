import { api } from './client';

export interface StudyActivityResponse {
  study_streak_days: number;
  last_study_date: string | null; // ISO date string YYYY-MM-DD
  longest_streak: number;
  streak_updated: boolean;
}

export interface StudentProfile {
  id: number;
  user_id: number;
  grade_level: number | null;
  school_name: string | null;
  study_streak_days: number;
  last_study_date: string | null;
  longest_streak: number;
}

export const studentApi = {
  /** Record study activity for today. Idempotent — safe to call multiple times per day. */
  recordStudyActivity: async (): Promise<StudyActivityResponse> => {
    const response = await api.post('/api/students/study-activity');
    return response.data as StudyActivityResponse;
  },

  /** Get current streak data without updating it. */
  getStreak: async (): Promise<StudyActivityResponse> => {
    const response = await api.get('/api/students/streak');
    return response.data as StudyActivityResponse;
  },

  /** Get the logged-in student's own profile (includes numeric student id). */
  getMyProfile: async (): Promise<StudentProfile> => {
    const response = await api.get('/api/students/me');
    return response.data as StudentProfile;
  },
};
