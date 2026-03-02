import { api } from './client';

// ─── Types ────────────────────────────────────────────────────────────────────

export type SessionType = 'work' | 'short_break' | 'long_break';

export interface StudySessionResponse {
  id: number;
  user_id: number;
  session_type: SessionType;
  started_at: string;
  ended_at: string | null;
  duration_minutes: number | null;
  course_id: number | null;
  completed: boolean;
  created_at: string;
}

export interface StudyStreakResponse {
  id: number;
  user_id: number;
  current_streak: number;
  longest_streak: number;
  last_session_date: string | null;
  total_sessions: number;
  total_focus_minutes: number;
}

export interface DayStats {
  date: string;   // ISO date YYYY-MM-DD
  minutes: number;
}

export interface StudyStatsResponse {
  today_minutes: number;
  week_minutes: number;
  total_sessions: number;
  current_streak: number;
  longest_streak: number;
  sessions_by_day: DayStats[];
}

// ─── API calls ────────────────────────────────────────────────────────────────

export const studyTimerApi = {
  /** Start a new Pomodoro session. */
  startSession: async (
    sessionType: SessionType,
    courseId?: number,
  ): Promise<StudySessionResponse> => {
    const res = await api.post<StudySessionResponse>('/api/study-timer/sessions/start', {
      session_type: sessionType,
      course_id: courseId ?? null,
    });
    return res.data;
  },

  /** End a running session and get the updated record. */
  endSession: async (sessionId: number): Promise<StudySessionResponse> => {
    const res = await api.post<StudySessionResponse>(
      `/api/study-timer/sessions/${sessionId}/end`,
    );
    return res.data;
  },

  /** List the 30 most recent sessions. */
  getSessions: async (): Promise<StudySessionResponse[]> => {
    const res = await api.get<StudySessionResponse[]>('/api/study-timer/sessions');
    return res.data;
  },

  /** Get the current streak for the authenticated user. */
  getStreak: async (): Promise<StudyStreakResponse> => {
    const res = await api.get<StudyStreakResponse>('/api/study-timer/streak');
    return res.data;
  },

  /** Get aggregated study stats for the authenticated user. */
  getStats: async (): Promise<StudyStatsResponse> => {
    const res = await api.get<StudyStatsResponse>('/api/study-timer/stats');
    return res.data;
  },

  /** Parent: get a linked child's study stats by user ID. */
  getChildStats: async (studentUserId: number): Promise<StudyStatsResponse> => {
    const res = await api.get<StudyStatsResponse>(
      `/api/study-timer/stats/${studentUserId}`,
    );
    return res.data;
  },
};
