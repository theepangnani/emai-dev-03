import { api, AI_TIMEOUT } from './client';

// === Types ===

export interface SchoolReportCard {
  id: number;
  student_id: number;
  original_filename: string;
  term: string | null;
  grade_level: string | null;
  school_name: string | null;
  report_date: string | null;
  school_year: string | null;
  has_text_content: boolean;
  has_analysis: boolean;
  created_at: string;
}

export interface UploadResponse {
  uploaded: SchoolReportCard[];
  failed: string[];
  total_uploaded: number;
}

export interface GradeAnalysisItem {
  subject: string;
  grade: string | null;
  median: string | null;
  level: number | null;
  teacher_comment: string | null;
  feedback: string;
}

export interface LearningSkillRating {
  skill: string;
  rating: string; // E, G, S, N
}

export interface LearningSkillsSummary {
  ratings: LearningSkillRating[];
  summary: string;
}

export interface ImprovementArea {
  area: string;
  detail: string;
  priority: string; // high, medium, low
}

export interface ParentTip {
  tip: string;
  related_subject: string | null;
}

export interface FullAnalysis {
  id: number;
  report_card_id: number;
  analysis_type: string;
  teacher_feedback_summary: string;
  grade_analysis: GradeAnalysisItem[];
  learning_skills: LearningSkillsSummary;
  improvement_areas: ImprovementArea[];
  parent_tips: ParentTip[];
  overall_summary: string;
  created_at: string;
}

export interface GradeTrend {
  subject: string;
  trajectory: string; // improving, declining, stable
  data: string;
  note: string;
}

export interface CareerSuggestion {
  career: string;
  reasoning: string;
  related_subjects: string[];
  next_steps: string;
}

export interface CareerPathAnalysis {
  id: number;
  student_id: number;
  strengths: string[];
  grade_trends: GradeTrend[];
  career_suggestions: CareerSuggestion[];
  overall_assessment: string;
  report_cards_analyzed: number;
  created_at: string;
}

// === API Functions ===

export const schoolReportCardsApi = {
  upload: (formData: FormData) =>
    api.post<UploadResponse>('/api/school-report-cards/upload', formData, {
      ...AI_TIMEOUT,
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  list: (studentId: number) =>
    api.get<SchoolReportCard[]>(`/api/school-report-cards/${studentId}`),

  getAnalysis: (reportCardId: number) =>
    api.get<FullAnalysis | null>(`/api/school-report-cards/${reportCardId}/analysis`),

  analyze: (reportCardId: number) =>
    api.post<FullAnalysis>(`/api/school-report-cards/${reportCardId}/analyze`, {}, AI_TIMEOUT),

  careerPath: (studentId: number) =>
    api.post<CareerPathAnalysis>(`/api/school-report-cards/${studentId}/career-path`, {}, AI_TIMEOUT),

  delete: (reportCardId: number) =>
    api.delete(`/api/school-report-cards/${reportCardId}`),
};
