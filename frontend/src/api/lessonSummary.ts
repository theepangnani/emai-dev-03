/**
 * Lesson Summary API client.
 *
 * Endpoints for AI-powered class notes summarization.
 * All endpoints require an authenticated student or admin user.
 */
import { api } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type InputType = 'text' | 'transcript' | 'audio_transcript' | 'uploaded_notes';

export interface KeyConcept {
  concept: string;
  definition: string;
}

export interface ImportantDate {
  date: string;
  event: string;
}

export interface LessonSummaryRequest {
  title: string;
  raw_input: string;
  input_type?: InputType;
  course_id?: number | null;
}

export interface LessonSummaryUpdateRequest {
  title?: string;
  raw_input?: string;
}

export interface LessonSummaryListItem {
  id: number;
  title: string;
  course_id: number | null;
  course_name: string | null;
  input_type: InputType;
  word_count: number;
  created_at: string;
  updated_at: string | null;
}

export interface LessonSummaryResponse {
  id: number;
  student_id: number;
  course_id: number | null;
  course_name: string | null;
  title: string;
  input_type: InputType;
  raw_input: string;
  summary: string | null;
  key_concepts: KeyConcept[] | null;
  important_dates: ImportantDate[] | null;
  study_questions: string[] | null;
  action_items: string[] | null;
  word_count: number;
  created_at: string;
  updated_at: string | null;
}

export interface FlashcardsFromSummaryResponse {
  study_guide_id: number;
  title: string;
  card_count: number;
  message: string;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/** Generate an AI summary from raw class notes or a transcript. */
export async function generateSummary(
  request: LessonSummaryRequest,
): Promise<LessonSummaryResponse> {
  const { data } = await api.post<LessonSummaryResponse>(
    '/api/lesson-summary/generate',
    request,
  );
  return data;
}

/** List all lesson summaries for the current student, most recent first. */
export async function listSummaries(courseId?: number): Promise<LessonSummaryListItem[]> {
  const params: Record<string, unknown> = {};
  if (courseId !== undefined) params.course_id = courseId;
  const { data } = await api.get<LessonSummaryListItem[]>('/api/lesson-summary/', { params });
  return data;
}

/** Get the full detail of a single lesson summary. */
export async function getSummary(summaryId: number): Promise<LessonSummaryResponse> {
  const { data } = await api.get<LessonSummaryResponse>(`/api/lesson-summary/${summaryId}`);
  return data;
}

/** Update the title or raw_input of an existing lesson summary. */
export async function updateSummary(
  summaryId: number,
  updates: LessonSummaryUpdateRequest,
): Promise<LessonSummaryResponse> {
  const { data } = await api.patch<LessonSummaryResponse>(
    `/api/lesson-summary/${summaryId}`,
    updates,
  );
  return data;
}

/** Delete a lesson summary. */
export async function deleteSummary(summaryId: number): Promise<void> {
  await api.delete(`/api/lesson-summary/${summaryId}`);
}

/** Convert key concepts of a lesson summary into a flashcard study guide. */
export async function convertToFlashcards(
  summaryId: number,
): Promise<FlashcardsFromSummaryResponse> {
  const { data } = await api.post<FlashcardsFromSummaryResponse>(
    `/api/lesson-summary/${summaryId}/to-flashcards`,
  );
  return data;
}
