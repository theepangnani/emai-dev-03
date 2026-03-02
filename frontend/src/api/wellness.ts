import { api } from './client';

// -------------------------------------------------------------------------
// Enums (mirror Python enums)
// -------------------------------------------------------------------------

export type MoodLevel = 'great' | 'good' | 'okay' | 'struggling' | 'overwhelmed';
export type EnergyLevel = 'high' | 'medium' | 'low';

// -------------------------------------------------------------------------
// Request / response types
// -------------------------------------------------------------------------

export interface WellnessCheckInCreate {
  mood: MoodLevel;
  energy: EnergyLevel;
  stress_level: number; // 1-5
  sleep_hours?: number | null;
  notes?: string | null;
  is_private?: boolean;
}

export interface WellnessCheckInResponse {
  id: number;
  student_id: number;
  mood: MoodLevel;
  energy: EnergyLevel;
  stress_level: number;
  sleep_hours: number | null;
  notes: string | null;
  is_private: boolean;
  check_in_date: string; // ISO date "YYYY-MM-DD"
  created_at: string;
  updated_at: string | null;
}

export interface DayTrendPoint {
  date: string; // "YYYY-MM-DD"
  mood: MoodLevel | null;
  energy: EnergyLevel | null;
  stress_level: number | null;
  sleep_hours: number | null;
  has_entry: boolean;
}

export interface WellnessTrendResponse {
  days: DayTrendPoint[];
  avg_stress: number | null;
  avg_sleep: number | null;
  dominant_mood: MoodLevel | null;
  dominant_energy: EnergyLevel | null;
  streak_days: number;
}

export interface WellnessSummary {
  student_id: number;
  week_avg_stress: number | null;
  week_avg_sleep: number | null;
  dominant_mood: MoodLevel | null;
  dominant_energy: EnergyLevel | null;
  alert_active: boolean;
  total_check_ins_this_week: number;
  streak_days: number;
}

// -------------------------------------------------------------------------
// API calls
// -------------------------------------------------------------------------

export const wellnessApi = {
  /** Create or update today's wellness check-in (student only). */
  submitCheckIn(data: WellnessCheckInCreate): Promise<WellnessCheckInResponse> {
    return api.post<WellnessCheckInResponse>('/api/wellness/check-in', data).then(r => r.data);
  },

  /** Get today's check-in for the authenticated student, or null. */
  getToday(): Promise<WellnessCheckInResponse | null> {
    return api.get<WellnessCheckInResponse | null>('/api/wellness/today').then(r => r.data);
  },

  /** Get trend for the authenticated student. */
  getTrend(days: number = 7): Promise<WellnessTrendResponse> {
    return api.get<WellnessTrendResponse>('/api/wellness/trend', { params: { days } }).then(r => r.data);
  },

  /** Get non-private summary for a student (teacher/admin/parent). */
  getStudentSummary(studentId: number): Promise<WellnessSummary> {
    return api
      .get<WellnessSummary>(`/api/wellness/student/${studentId}/summary`)
      .then(r => r.data);
  },

  /** Get non-private trend for a child (parent only). */
  getChildTrend(studentId: number, days: number = 7): Promise<WellnessTrendResponse> {
    return api
      .get<WellnessTrendResponse>(`/api/wellness/student/${studentId}/trend`, { params: { days } })
      .then(r => r.data);
  },
};
