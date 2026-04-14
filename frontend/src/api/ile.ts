/**
 * Interactive Learning Engine (Flash Tutor) API client — CB-ILE-001
 */
import { api } from './client';

// --- Types ---

export interface ILEQuestionOption {
  A: string;
  B: string;
  C: string;
  D: string;
}

export interface ILEQuestion {
  index: number;
  question: string;
  options: ILEQuestionOption | null;
  format: string;
  difficulty: string;
  blooms_tier: string;
}

export interface ILECurrentQuestion {
  session_id: number;
  question: ILEQuestion;
  question_index: number;
  total_questions: number;
  mode: string;
  attempt_number: number;
  disabled_options: string[];
  streak_count: number;
}

export interface ILESession {
  id: number;
  student_id: number;
  parent_id: number | null;
  mode: string;
  subject: string;
  topic: string;
  grade_level: number | null;
  question_count: number;
  difficulty: string;
  blooms_tier: string;
  timer_enabled: boolean;
  timer_seconds: number | null;
  is_private_practice: boolean;
  status: string;
  current_question_index: number;
  score: number | null;
  total_correct: number | null;
  xp_awarded: number | null;
  started_at: string;
  completed_at: string | null;
  expires_at: string | null;
  course_id: number | null;
  course_content_id: number | null;
}

export interface ILESessionSummary {
  id: number;
  mode: string;
  subject: string;
  topic: string;
  status: string;
  score: number | null;
  question_count: number;
  total_correct: number | null;
  xp_awarded: number | null;
  started_at: string;
  completed_at: string | null;
}

export interface ILEAnswerFeedback {
  is_correct: boolean;
  attempt_number: number;
  xp_earned: number;
  hint: string | null;
  parent_hint_note: string | null;
  explanation: string | null;
  correct_answer: string | null;
  question_complete: boolean;
  session_complete: boolean;
  streak_count: number;
  streak_broken: boolean;
}

export interface ILEQuestionResult {
  index: number;
  question: string;
  correct_answer: string;
  student_answer: string | null;
  is_correct: boolean;
  attempts: number;
  xp_earned: number;
  difficulty: string;
  format: string;
}

export interface ILEAreaToRevisit {
  index: number;
  question: string;
  correct_answer: string;
  student_answer: string | null;
  attempts: number;
}

export interface ILESessionResults {
  session_id: number;
  mode: string;
  subject: string;
  topic: string;
  score: number;
  total_questions: number;
  percentage: number;
  total_xp: number;
  questions: ILEQuestionResult[];
  streak_at_end: number;
  time_taken_seconds: number | null;
  weak_areas: string[];
  suggested_next_topic: string | null;
  areas_to_revisit: ILEAreaToRevisit[];
  aha_detected: boolean;
}

export interface ILETopic {
  subject: string;
  topic: string;
  course_id: number | null;
  course_name: string | null;
  mastery_pct: number | null;
  is_weak_area: boolean;
  next_review_at: string | null;
}

export interface ILEMasteryEntry {
  subject: string;
  topic: string;
  total_sessions: number;
  avg_attempts: number;
  is_weak_area: boolean;
  current_difficulty: string;
  last_score_pct: number | null;
  next_review_at: string | null;
  glow_intensity: number;
}

export interface ILEMasteryMap {
  student_id: number;
  entries: ILEMasteryEntry[];
  total_topics: number;
  mastered_topics: number;
  weak_topics: number;
}

export interface ILECareerConnect {
  career: string;
  connection: string;
}

export interface ILESessionCreate {
  mode: 'learning' | 'testing' | 'parent_teaching';
  subject: string;
  topic: string;
  grade_level?: number;
  question_count?: number;
  difficulty?: 'easy' | 'medium' | 'challenging';
  blooms_tier?: 'recall' | 'understand' | 'apply';
  timer_enabled?: boolean;
  timer_seconds?: number;
  is_private_practice?: boolean;
  course_id?: number;
  course_content_id?: number;
  child_student_id?: number;
}

// --- API ---

export const ileApi = {
  // Sessions
  createSession: (data: ILESessionCreate) =>
    api.post<ILESession>('/api/ile/sessions', data).then(r => r.data),

  createSessionFromStudyGuide: (params: {
    study_guide_id?: number;
    course_content_id?: number;
    mode?: string;
    question_count?: number;
    difficulty?: string;
  }) =>
    api.post<ILESession>('/api/ile/sessions/from-study-guide', null, { params }).then(r => r.data),

  getActiveSession: () =>
    api.get<ILESession | null>('/api/ile/sessions/active').then(r => r.data),

  getSession: (id: number) =>
    api.get<ILESession>(`/api/ile/sessions/${id}`).then(r => r.data),

  getSessionHistory: (limit = 20) =>
    api.get<ILESessionSummary[]>('/api/ile/sessions', { params: { limit } }).then(r => r.data),

  // Questions
  getCurrentQuestion: (sessionId: number) =>
    api.get<ILECurrentQuestion>(`/api/ile/sessions/${sessionId}/question`).then(r => r.data),

  submitAnswer: (sessionId: number, answer: string, timeTakenMs?: number, parentHintNote?: string) =>
    api.post<ILEAnswerFeedback>(`/api/ile/sessions/${sessionId}/answer`, {
      answer,
      time_taken_ms: timeTakenMs,
      parent_hint_note: parentHintNote || undefined,
    }).then(r => r.data),

  addParentHint: (sessionId: number, hintNote: string) =>
    api.post<{ question_index: number; parent_hint_note: string }>(`/api/ile/sessions/${sessionId}/parent-hint`, {
      hint_note: hintNote,
    }).then(r => r.data),

  // Session lifecycle
  completeSession: (sessionId: number) =>
    api.post<ILESessionResults>(`/api/ile/sessions/${sessionId}/complete`).then(r => r.data),

  abandonSession: (sessionId: number) =>
    api.post(`/api/ile/sessions/${sessionId}/abandon`).then(r => r.data),

  getSessionResults: (sessionId: number) =>
    api.get<ILESessionResults>(`/api/ile/sessions/${sessionId}/results`).then(r => r.data),

  // Topics
  getTopics: () =>
    api.get<{ topics: ILETopic[] }>('/api/ile/topics').then(r => r.data.topics),

  // Mastery
  getMasteryMap: () =>
    api.get<ILEMasteryMap>('/api/ile/mastery').then(r => r.data),

  getSurpriseMe: () =>
    api.get<{ topic: ILETopic; reason: string }>('/api/ile/topics/surprise-me').then(r => r.data),

  // Career Connect
  getCareerConnect: (sessionId: number) =>
    api.get<ILECareerConnect>(`/api/ile/sessions/${sessionId}/career-connect`).then(r => r.data),
};
