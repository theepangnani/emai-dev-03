import { api } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TutorMatchBreakdown {
  subject_match: number;
  subject_match_max: number;
  grade_match: number;
  grade_match_max: number;
  rating_score: number;
  rating_score_max: number;
  style_match: number;
  style_match_max: number;
  price_score: number;
  price_score_max: number;
}

export interface MatchedTutorInfo {
  id: number;
  tutor_name: string | null;
  headline: string;
  bio: string;
  subjects: string[];
  grade_levels: string[];
  hourly_rate_cad: number;
  avg_rating: number | null;
  review_count: number;
  is_verified: boolean;
  is_accepting_students: boolean;
  available_days: string[];
  available_hours_start: string | null;
  available_hours_end: string | null;
  online_only: boolean;
  location_city: string | null;
  years_experience: number | null;
}

export interface TutorMatch {
  tutor_id: number;
  tutor: MatchedTutorInfo;
  score: number;
  breakdown: TutorMatchBreakdown;
  covered_weak_subjects: string[];
  total_weak_subjects: number;
  explanation: string;
  has_ai_explanation: boolean;
  // Only present in compatibility endpoint
  student_learning_style?: string | null;
  student_grade?: number | null;
}

export interface RecommendationsResponse {
  student_id: number;
  total_matches: number;
  matches: TutorMatch[];
}

export interface ChildRecommendationsResponse extends RecommendationsResponse {
  student_name: string | null;
}

export interface TutorMatchPreference {
  max_hourly_rate_cad: number | null;
  preferred_subjects: string[];
  preferred_grade_levels: string[];
  preferred_availability: string[];
  min_rating: number;
  prefer_verified_only: boolean;
}

export interface TutorMatchPreferenceUpdate {
  max_hourly_rate_cad?: number | null;
  preferred_subjects?: string[];
  preferred_grade_levels?: string[];
  preferred_availability?: string[];
  min_rating?: number;
  prefer_verified_only?: boolean;
}

// ---------------------------------------------------------------------------
// API client
// ---------------------------------------------------------------------------

export const tutorMatchingApi = {
  /** Get top AI-matched tutors for the current student. */
  getRecommendations(params?: { limit?: number; include_ai?: boolean }): Promise<RecommendationsResponse> {
    const query = new URLSearchParams();
    if (params?.limit !== undefined) query.set('limit', String(params.limit));
    if (params?.include_ai !== undefined) query.set('include_ai', String(params.include_ai));
    const qs = query.toString();
    return api
      .get<RecommendationsResponse>(`/api/tutor-matching/recommendations${qs ? `?${qs}` : ''}`)
      .then((r) => r.data);
  },

  /** Score a specific tutor against the current student. */
  scoreTutor(tutorId: number, includeAi = false): Promise<TutorMatch> {
    return api
      .post<TutorMatch>(
        `/api/tutor-matching/score/${tutorId}${includeAi ? '?include_ai=true' : ''}`,
      )
      .then((r) => r.data);
  },

  /** Save the current user's matching preferences. */
  updatePreferences(prefs: TutorMatchPreferenceUpdate): Promise<{ message: string; preferences: TutorMatchPreference }> {
    return api
      .post<{ message: string; preferences: TutorMatchPreference }>('/api/tutor-matching/preferences', prefs)
      .then((r) => r.data);
  },

  /** Get the current user's saved matching preferences. */
  getPreferences(): Promise<TutorMatchPreference> {
    return api.get<TutorMatchPreference>('/api/tutor-matching/preferences').then((r) => r.data);
  },

  /** Get full compatibility analysis between current student and a specific tutor. */
  getCompatibility(tutorId: number): Promise<TutorMatch> {
    return api
      .get<TutorMatch>(`/api/tutor-matching/compatibility/${tutorId}`)
      .then((r) => r.data);
  },

  /** Get AI-matched tutors for a specific child (parent endpoint). */
  getChildRecommendations(
    studentId: number,
    params?: { limit?: number; include_ai?: boolean },
  ): Promise<ChildRecommendationsResponse> {
    const query = new URLSearchParams();
    if (params?.limit !== undefined) query.set('limit', String(params.limit));
    if (params?.include_ai !== undefined) query.set('include_ai', String(params.include_ai));
    const qs = query.toString();
    return api
      .get<ChildRecommendationsResponse>(
        `/api/tutor-matching/children/${studentId}/recommendations${qs ? `?${qs}` : ''}`,
      )
      .then((r) => r.data);
  },
};
