import { api } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SubjectArea = 'math' | 'science' | 'english' | 'history' | 'french' | 'geography' | 'other';
export type HelpMode = 'hint' | 'explain' | 'solve' | 'check';

export interface HomeworkHelpRequest {
  subject: SubjectArea;
  question: string;
  mode: HelpMode;
  context?: string;
  course_id?: number;
}

export interface HomeworkHelpResponse {
  session_id: number;
  subject: SubjectArea;
  mode: HelpMode;
  question: string;
  response: string;
  steps?: string[];
  hints?: string[];
}

export interface FollowUpRequest {
  session_id: number;
  follow_up: string;
}

export interface FollowUpResponse {
  session_id: number;
  response: string;
  follow_up_count: number;
}

export interface HomeworkSessionSummary {
  id: number;
  subject: SubjectArea;
  mode: HelpMode;
  question: string;
  response: string;
  follow_up_count: number;
  created_at: string;
  is_saved: boolean;
}

export interface SaveSolutionRequest {
  title: string;
  tags?: string[];
}

export interface SavedSolutionOut {
  id: number;
  session_id: number;
  title: string;
  tags?: string[];
  subject: SubjectArea;
  mode: HelpMode;
  question: string;
  response: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export const homeworkHelpApi = {
  /** Request AI homework help. */
  getHelp: async (body: HomeworkHelpRequest): Promise<HomeworkHelpResponse> => {
    const { data } = await api.post<HomeworkHelpResponse>('/api/homework/help', body);
    return data;
  },

  /** Ask a follow-up question on an existing session. */
  followUp: async (body: FollowUpRequest): Promise<FollowUpResponse> => {
    const { data } = await api.post<FollowUpResponse>('/api/homework/follow-up', body);
    return data;
  },

  /** Fetch the student's recent homework sessions. */
  getSessions: async (subject?: SubjectArea): Promise<HomeworkSessionSummary[]> => {
    const params = subject ? { subject } : undefined;
    const { data } = await api.get<HomeworkSessionSummary[]>('/api/homework/sessions', { params });
    return data;
  },

  /** Save a session as a named solution. */
  saveSolution: async (sessionId: number, body: SaveSolutionRequest): Promise<SavedSolutionOut> => {
    const { data } = await api.post<SavedSolutionOut>(`/api/homework/sessions/${sessionId}/save`, body);
    return data;
  },

  /** Get all saved solutions. */
  getSavedSolutions: async (): Promise<SavedSolutionOut[]> => {
    const { data } = await api.get<SavedSolutionOut[]>('/api/homework/saved');
    return data;
  },

  /** Delete a saved solution. */
  deleteSavedSolution: async (savedId: number): Promise<void> => {
    await api.delete(`/api/homework/saved/${savedId}`);
  },
};
