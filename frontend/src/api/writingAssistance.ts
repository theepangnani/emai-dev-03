/**
 * Writing Assistance API client.
 *
 * All endpoints require an authenticated user.
 */
import { api } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type WritingFeedbackType =
  | 'grammar'
  | 'clarity'
  | 'structure'
  | 'argumentation'
  | 'vocabulary'
  | 'overall';

export type FeedbackSeverity = 'info' | 'warning' | 'error';

export type AssignmentType = 'essay' | 'report' | 'letter' | 'lab';

export interface WritingFeedbackItem {
  type: WritingFeedbackType;
  message: string;
  suggestion: string;
  severity: FeedbackSeverity;
}

export interface WritingAnalysisRequest {
  title: string;
  text: string;
  course_id?: number | null;
  assignment_type?: AssignmentType;
}

export interface WritingAnalysisResponse {
  session_id: number;
  overall_score: number;
  feedback: WritingFeedbackItem[];
  improved_text: string;
  suggestions_count: number;
  word_count: number;
}

export interface WritingImproveRequest {
  session_id: number;
  instruction: string;
}

export interface WritingImproveResponse {
  improved_text: string;
  instruction: string;
}

export interface WritingSessionSummary {
  id: number;
  title: string;
  assignment_type: string;
  overall_score: number | null;
  word_count: number;
  suggestions_count: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface WritingSessionDetail {
  id: number;
  title: string;
  assignment_type: string;
  original_text: string;
  improved_text: string | null;
  feedback: WritingFeedbackItem[] | null;
  overall_score: number | null;
  word_count: number;
  course_id: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface WritingTemplate {
  id: number;
  name: string;
  description: string;
  template_type: string;
  structure_outline: string;
  is_active: boolean;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/** Analyze a piece of writing and receive scored feedback + improved version. */
export async function analyzeWriting(
  request: WritingAnalysisRequest,
): Promise<WritingAnalysisResponse> {
  const { data } = await api.post<WritingAnalysisResponse>('/api/writing/analyze', request);
  return data;
}

/** Apply a specific improvement instruction to a previous writing session. */
export async function improveWriting(
  request: WritingImproveRequest,
): Promise<WritingImproveResponse> {
  const { data } = await api.post<WritingImproveResponse>('/api/writing/improve', request);
  return data;
}

/** List all writing sessions for the current user (summary only). */
export async function getSessions(): Promise<WritingSessionSummary[]> {
  const { data } = await api.get<WritingSessionSummary[]>('/api/writing/sessions');
  return data;
}

/** Get the full writing session including text and feedback. */
export async function getSession(sessionId: number): Promise<WritingSessionDetail> {
  const { data } = await api.get<WritingSessionDetail>(`/api/writing/sessions/${sessionId}`);
  return data;
}

/** List all active writing templates. */
export async function getTemplates(): Promise<WritingTemplate[]> {
  const { data } = await api.get<WritingTemplate[]>('/api/writing/templates');
  return data;
}
