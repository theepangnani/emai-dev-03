import { api } from './client';

// ─── Types ────────────────────────────────────────────────────────────────────

export type LearningStyle = 'visual' | 'auditory' | 'reading' | 'kinesthetic';
export type MasteryLevel = 'beginner' | 'developing' | 'proficient' | 'advanced';
export type Difficulty = 'easy' | 'medium' | 'hard';
export type Trend = 'improving' | 'stable' | 'declining';

export interface PersonalizationProfile {
  id: number;
  student_id: number;
  learning_style: LearningStyle | null;
  learning_style_confidence: number;   // 0-1
  preferred_difficulty: string;        // "easy" | "medium" | "hard" | "adaptive"
  study_session_length: number;        // minutes
  preferred_study_time: string;        // "morning" | "afternoon" | "evening"
  strong_subjects: string[];
  weak_subjects: string[];
  last_analyzed_at: string | null;
  ai_analysis_count: number;
  recommendations_generated_at: string | null;
}

export interface PersonalizationProfileUpdate {
  learning_style?: LearningStyle;
  preferred_difficulty?: string;
  study_session_length?: number;
  preferred_study_time?: string;
}

export interface SubjectMastery {
  id: number;
  student_id: number;
  subject_code: string;
  subject_name: string;
  mastery_score: number;    // 0-100
  mastery_level: MasteryLevel;
  quiz_score_avg: number;
  quiz_attempts: number;
  grade_avg: number;
  last_quiz_date: string | null;
  trend: Trend;
  recommended_next_topics: string[];
}

export interface AdaptiveDifficultyInfo {
  student_id: number;
  subject_code: string;
  content_type: string;
  current_difficulty: Difficulty;
  recommended_difficulty: Difficulty;
  consecutive_correct: number;
  consecutive_incorrect: number;
  total_attempts: number;
}

export interface StudyRecommendations {
  weak_areas: string[];
  recommended_topics: string[];
  study_schedule: Record<string, string>;
  preferred_format: 'flashcards' | 'study_guides' | 'quizzes';
  difficulty_adjustment: 'increase' | 'maintain' | 'decrease';
  summary?: string;
  generated_at?: string | null;
}

export interface AnalyzeResponse {
  profile: PersonalizationProfile;
  recommendations: StudyRecommendations;
}

// ─── API client ───────────────────────────────────────────────────────────────

export const personalizationApi = {
  /**
   * Get the current student's personalization profile.
   * Creates a blank profile if none exists yet.
   */
  getProfile: async (): Promise<PersonalizationProfile> => {
    const res = await api.get<PersonalizationProfile>('/api/personalization/profile');
    return res.data;
  },

  /**
   * Update editable preferences (learning style, session length, etc.).
   */
  updateProfile: async (data: PersonalizationProfileUpdate): Promise<PersonalizationProfile> => {
    const res = await api.put<PersonalizationProfile>('/api/personalization/profile', data);
    return res.data;
  },

  /**
   * Get all subject mastery scores.
   * Automatically recomputes if data is older than 24 hours.
   */
  getMastery: async (): Promise<SubjectMastery[]> => {
    const res = await api.get<SubjectMastery[]>('/api/personalization/mastery');
    return res.data;
  },

  /**
   * Force recompute mastery scores from latest data.
   */
  refreshMastery: async (): Promise<SubjectMastery[]> => {
    const res = await api.post<SubjectMastery[]>('/api/personalization/mastery/refresh');
    return res.data;
  },

  /**
   * Get mastery data for a single subject.
   */
  getSubjectMastery: async (subjectCode: string): Promise<SubjectMastery> => {
    const res = await api.get<SubjectMastery>(`/api/personalization/mastery/${encodeURIComponent(subjectCode)}`);
    return res.data;
  },

  /**
   * Get recommended difficulty for a student/subject/content_type combo.
   */
  getDifficulty: async (subjectCode: string, contentType: string): Promise<AdaptiveDifficultyInfo> => {
    const res = await api.get<AdaptiveDifficultyInfo>(
      `/api/personalization/difficulty/${encodeURIComponent(subjectCode)}/${contentType}`
    );
    return res.data;
  },

  /**
   * Report an attempt result to update adaptive difficulty.
   */
  reportAttempt: async (
    subjectCode: string,
    contentType: string,
    passed: boolean
  ): Promise<AdaptiveDifficultyInfo> => {
    const res = await api.post<AdaptiveDifficultyInfo>(
      `/api/personalization/difficulty/${encodeURIComponent(subjectCode)}/${contentType}/feedback`,
      { passed }
    );
    return res.data;
  },

  /**
   * Run AI learning-style detection and generate personalised study recommendations.
   * Stores results on the profile and returns both.
   */
  analyze: async (): Promise<AnalyzeResponse> => {
    const res = await api.post<AnalyzeResponse>('/api/personalization/analyze');
    return res.data;
  },

  /**
   * Get the latest cached AI recommendations without triggering reanalysis.
   */
  getRecommendations: async (): Promise<StudyRecommendations> => {
    const res = await api.get<StudyRecommendations>('/api/personalization/recommendations');
    return res.data;
  },

  // ── Parent / Admin views ────────────────────────────────────────────────

  /**
   * Parent/Admin: view a child's subject mastery scores.
   */
  getChildMastery: async (studentId: number): Promise<SubjectMastery[]> => {
    const res = await api.get<SubjectMastery[]>(`/api/personalization/children/${studentId}/mastery`);
    return res.data;
  },

  /**
   * Parent/Admin: view a child's personalization profile.
   */
  getChildProfile: async (studentId: number): Promise<PersonalizationProfile> => {
    const res = await api.get<PersonalizationProfile>(`/api/personalization/children/${studentId}/profile`);
    return res.data;
  },
};
