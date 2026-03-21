import { api } from './client';

export interface SubjectSummary {
  name: string;
  guides: number;
  quizzes: number;
}

export interface LevelReached {
  level: number;
  title: string;
}

export interface BadgeEarned {
  name: string;
  date: string;
}

export interface ReportCardData {
  student_name: string;
  term: string;
  subjects_studied: SubjectSummary[];
  total_uploads: number;
  total_guides: number;
  total_quizzes: number;
  total_xp: number;
  level_reached: LevelReached;
  badges_earned: BadgeEarned[];
  longest_streak: number;
  most_reviewed_topics: string[];
  study_sessions: number;
  total_study_minutes: number;
}

export const reportCardApi = {
  get: async (term?: string) => {
    const params = term ? `?term=${encodeURIComponent(term)}` : '';
    const response = await api.get<ReportCardData>(`/api/report-card${params}`);
    return response.data;
  },

  getForChild: async (studentId: number, term?: string) => {
    const params = term ? `?term=${encodeURIComponent(term)}` : '';
    const response = await api.get<ReportCardData>(`/api/report-card/children/${studentId}${params}`);
    return response.data;
  },
};
