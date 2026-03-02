import { api } from './client';

export interface GradePredictionResponse {
  id: number;
  student_id: number;
  course_id: number | null;
  course_name: string | null;
  predicted_grade: number;
  confidence: number;
  trend: 'improving' | 'stable' | 'declining';
  factors: string[];
  prediction_date: string;
  created_at: string;
}

export interface GradePredictionListResponse {
  predictions: GradePredictionResponse[];
  overall_gpa_prediction: number | null;
  strongest_course: string | null;
  at_risk_course: string | null;
}

/** Generate (or refresh) predictions for all enrolled courses */
export async function generatePredictions(): Promise<GradePredictionListResponse> {
  const res = await api.post<GradePredictionListResponse>('/api/grade-prediction/generate');
  return res.data;
}

/** Generate (or refresh) prediction for a single course */
export async function generateCoursePrediction(
  courseId: number
): Promise<GradePredictionResponse> {
  const res = await api.post<GradePredictionResponse>(
    `/api/grade-prediction/generate/${courseId}`
  );
  return res.data;
}

/** Fetch latest cached predictions for all courses */
export async function getPredictions(): Promise<GradePredictionListResponse> {
  const res = await api.get<GradePredictionListResponse>('/api/grade-prediction/');
  return res.data;
}

/** Fetch latest cached prediction for a specific course */
export async function getCoursePrediction(
  courseId: number
): Promise<GradePredictionResponse> {
  const res = await api.get<GradePredictionResponse>(`/api/grade-prediction/${courseId}`);
  return res.data;
}

/** Parent: fetch grade predictions for a linked child */
export async function getChildPredictions(
  studentUserId: number
): Promise<GradePredictionListResponse> {
  const res = await api.get<GradePredictionListResponse>(
    `/api/grade-prediction/student/${studentUserId}`
  );
  return res.data;
}
