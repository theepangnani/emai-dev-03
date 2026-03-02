/**
 * Typed API client for the Learning Journal feature.
 */
import apiClient from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type JournalMood =
  | 'excited'
  | 'confident'
  | 'curious'
  | 'confused'
  | 'frustrated'
  | 'bored';

export interface JournalEntry {
  id: number;
  student_id: number;
  course_id: number | null;
  title: string | null;
  content: string;
  mood: JournalMood | null;
  tags: string[] | null;
  ai_prompt_used: string | null;
  is_teacher_visible: boolean;
  word_count: number;
  created_at: string;
  updated_at: string | null;
}

export interface JournalEntryCreate {
  title?: string;
  content: string;
  mood?: JournalMood;
  tags?: string[];
  course_id?: number;
  ai_prompt_used?: string;
  is_teacher_visible?: boolean;
}

export interface JournalEntryUpdate {
  title?: string;
  content?: string;
  mood?: JournalMood;
  tags?: string[];
  course_id?: number;
  is_teacher_visible?: boolean;
}

export interface JournalListResponse {
  entries: JournalEntry[];
  total: number;
  page: number;
  limit: number;
}

export interface JournalStats {
  total_entries: number;
  avg_words: number;
  mood_distribution: Record<JournalMood, number>;
  streak_days: number;
  entries_this_week: number;
}

export interface ReflectionPrompt {
  id: number | null;
  prompt_text: string;
  category: string;
  is_ai_generated: boolean;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export const learningJournalApi = {
  /** Create a new journal entry. */
  createEntry: (data: JournalEntryCreate): Promise<JournalEntry> =>
    apiClient.post('/api/journal/entries', data).then((r) => r.data),

  /** List own entries (paginated, optional course filter). */
  listEntries: (params?: {
    course_id?: number;
    page?: number;
    limit?: number;
  }): Promise<JournalListResponse> =>
    apiClient.get('/api/journal/entries', { params }).then((r) => r.data),

  /** Get a single entry by ID. */
  getEntry: (id: number): Promise<JournalEntry> =>
    apiClient.get(`/api/journal/entries/${id}`).then((r) => r.data),

  /** Update an existing entry. */
  updateEntry: (id: number, data: JournalEntryUpdate): Promise<JournalEntry> =>
    apiClient.patch(`/api/journal/entries/${id}`, data).then((r) => r.data),

  /** Delete an entry. */
  deleteEntry: (id: number): Promise<void> =>
    apiClient.delete(`/api/journal/entries/${id}`).then(() => undefined),

  /** Fetch aggregated stats for the current student. */
  getStats: (): Promise<JournalStats> =>
    apiClient.get('/api/journal/stats').then((r) => r.data),

  /** Get a reflection prompt (AI or random). */
  getPrompt: (options?: { ai?: boolean; category?: string }): Promise<ReflectionPrompt> =>
    apiClient.get('/api/journal/prompt', { params: options }).then((r) => r.data),

  /** List all seed prompts. */
  listPrompts: (): Promise<ReflectionPrompt[]> =>
    apiClient.get('/api/journal/prompts').then((r) => r.data),

  /** Teacher: get teacher-visible entries for a course. */
  getTeacherVisibleEntries: (courseId: number): Promise<JournalEntry[]> =>
    apiClient.get(`/api/journal/teacher/${courseId}`).then((r) => r.data),
};

// Mood metadata for display
export const MOOD_META: Record<JournalMood, { emoji: string; label: string; color: string }> = {
  excited:    { emoji: '🤩', label: 'Excited',    color: '#f59e0b' },
  confident:  { emoji: '😎', label: 'Confident',  color: '#10b981' },
  curious:    { emoji: '🤔', label: 'Curious',    color: '#6366f1' },
  confused:   { emoji: '😕', label: 'Confused',   color: '#f97316' },
  frustrated: { emoji: '😤', label: 'Frustrated', color: '#ef4444' },
  bored:      { emoji: '😴', label: 'Bored',      color: '#6b7280' },
};
