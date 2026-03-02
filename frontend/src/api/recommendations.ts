/**
 * AI Course Recommendations and University Pathway Alignment API client (#503, #506).
 */
import { api } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type GoalPathway = 'university' | 'college' | 'workplace' | 'undecided';
export type RecommendationPriority = 'high' | 'medium' | 'low';

export interface GenerateRecommendationsRequest {
  plan_id: number;
  student_id?: number;
  goal: GoalPathway;
  interests: string[];
  target_programs?: string[];
}

export interface RecommendationItem {
  course_code: string;
  course_name: string;
  grade_level: number;
  reason: string;
  priority: RecommendationPriority;
}

export interface RecommendationsResponse {
  id: number;
  plan_id: number;
  student_id: number;
  goal: GoalPathway;
  recommendations: RecommendationItem[];
  overall_advice: string | null;
  generated_at: string;
  cached: boolean;
}

export interface PathwayProgramResult {
  name: string;
  universities: string[];
  required_courses: string[];
  covered: string[];
  missing: string[];
  recommended_courses: string[];
  recommended_covered: string[];
  readiness_pct: number;
  min_average: number | null;
  notes: string;
}

export interface UniversityPathwaysResponse {
  plan_id: number;
  programs: PathwayProgramResult[];
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export const recommendationsApi = {
  /**
   * Generate AI course recommendations for a student's academic plan.
   * Results are cached on the server for 1 hour per plan.
   */
  generateCourseRecommendations: async (
    body: GenerateRecommendationsRequest,
  ): Promise<RecommendationsResponse> => {
    const res = await api.post('/api/recommendations/courses', body);
    return res.data;
  },

  /**
   * Retrieve the most recent AI recommendations for a plan (if < 1 hour old).
   */
  getLatestRecommendations: async (planId: number): Promise<RecommendationsResponse> => {
    const res = await api.get(`/api/recommendations/courses/${planId}`);
    return res.data;
  },

  /**
   * Map a plan's courses against Ontario university program admission requirements.
   * Optionally filter by program names (comma-separated).
   */
  getUniversityPathways: async (
    planId: number,
    programs?: string[],
  ): Promise<UniversityPathwaysResponse> => {
    const params: Record<string, string | number> = { plan_id: planId };
    if (programs && programs.length > 0) {
      params.programs = programs.join(',');
    }
    const res = await api.get('/api/recommendations/university-pathways', { params });
    return res.data;
  },
};

// ---------------------------------------------------------------------------
// Static program names (mirrors UNIVERSITY_PROGRAMS keys from backend)
// ---------------------------------------------------------------------------
export const ONTARIO_PROGRAMS = [
  'Computer Science',
  'Engineering',
  'Medicine / Pre-Med',
  'Business',
  'Arts & Humanities',
  'Nursing',
  'Education',
  'Law (Undergraduate)',
  'Architecture',
  'Kinesiology',
  'Mathematics & Statistics',
  'Environmental Science',
] as const;

export type OntarioProgram = (typeof ONTARIO_PROGRAMS)[number];
