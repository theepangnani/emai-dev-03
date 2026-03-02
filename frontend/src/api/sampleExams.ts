/**
 * Sample Exam API client — teacher-uploaded exam files with AI assessment (#577).
 */
import { api } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CurriculumCoverage {
  breadth: 'poor' | 'fair' | 'good' | 'excellent';
  depth: 'poor' | 'fair' | 'good' | 'excellent';
  gaps: string[];
  overlap: string[];
}

export interface DifficultyDistribution {
  easy: number;
  medium: number;
  hard: number;
}

export interface DifficultyAnalysis {
  distribution: DifficultyDistribution;
  appropriate_for_level: boolean;
  suggestions: string[];
}

export interface ImprovementSuggestion {
  question_number: number;
  issue: string;
  suggestion: string;
}

export interface QuestionQuality {
  total_questions: number;
  clear_questions: number;
  ambiguous_questions: number[];
  improvement_suggestions: ImprovementSuggestion[];
}

export interface ExamAssessment {
  overall_score: number;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  curriculum_coverage: CurriculumCoverage;
  difficulty_analysis: DifficultyAnalysis;
  question_quality: QuestionQuality;
  recommendations: string[];
}

export interface SampleExam {
  id: number;
  created_by_user_id: number;
  course_id: number | null;
  course_name: string | null;
  title: string;
  description: string | null;
  file_name: string | null;
  original_content: string | null;
  exam_type: 'sample' | 'practice' | 'past';
  difficulty_level: string | null;
  is_public: boolean;
  assessment: ExamAssessment | null;
  assessment_generated_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface SampleExamListResponse {
  total: number;
  items: SampleExam[];
  offset: number;
  limit: number;
}

export interface PracticeMode {
  exam_id: number;
  title: string;
  questions: string[];
  question_count: number;
}

export interface UploadExamParams {
  file: File;
  title: string;
  description?: string;
  course_id?: number | null;
  exam_type?: 'sample' | 'practice' | 'past';
  assess_on_upload?: boolean;
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export const sampleExamsApi = {
  /**
   * Upload an exam file and trigger AI assessment.
   */
  async upload(params: UploadExamParams): Promise<SampleExam> {
    const form = new FormData();
    form.append('file', params.file);
    form.append('title', params.title);
    if (params.description) form.append('description', params.description);
    if (params.course_id != null) form.append('course_id', String(params.course_id));
    form.append('exam_type', params.exam_type ?? 'sample');
    form.append('assess_on_upload', String(params.assess_on_upload ?? true));

    const res = await api.post('/api/sample-exams/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  /**
   * List sample exams visible to the current user.
   */
  async list(params?: {
    course_id?: number;
    exam_type?: string;
    is_public?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<SampleExamListResponse> {
    const res = await api.get('/api/sample-exams/', { params });
    return res.data;
  },

  /**
   * Get a single exam with full assessment details.
   */
  async get(id: number): Promise<SampleExam> {
    const res = await api.get(`/api/sample-exams/${id}`);
    return res.data;
  },

  /**
   * Delete an exam (creator or admin only).
   */
  async delete(id: number): Promise<void> {
    await api.delete(`/api/sample-exams/${id}`);
  },

  /**
   * Re-run AI assessment on an existing exam.
   */
  async reassess(id: number): Promise<SampleExam> {
    const res = await api.post(`/api/sample-exams/${id}/assess`);
    return res.data;
  },

  /**
   * Get questions extracted from the exam for practice mode.
   */
  async getPractice(id: number): Promise<PracticeMode> {
    const res = await api.get(`/api/sample-exams/${id}/practice`);
    return res.data;
  },

  /**
   * Toggle is_public for a sample exam.
   */
  async togglePublish(id: number): Promise<{ id: number; is_public: boolean }> {
    const res = await api.patch(`/api/sample-exams/${id}/publish`);
    return res.data;
  },
};
